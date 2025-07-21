import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { IDocumentManager } from '@jupyterlab/docmanager';
import { INotebookTracker } from '@jupyterlab/notebook';
import { ICommandPalette } from '@jupyterlab/apputils';
import { URLExt } from '@jupyterlab/coreutils';
import { ServerConnection } from '@jupyterlab/services';
import { NotebookPanel } from '@jupyterlab/notebook';
import { Cell, CodeCell, MarkdownCell } from '@jupyterlab/cells';
import { IOutput } from '@jupyterlab/nbformat';

/**
 * A utility function to wait for a condition to be true, with a timeout.
 * @param predicate - A function that returns true when the condition is met.
 * @param options - Options for timeout and interval.
 * @returns A promise that resolves to true if the condition is met, false otherwise.
 */
async function waitFor(
  predicate: () => boolean,
  options: { timeout?: number; interval?: number } = {}
): Promise<boolean> {
  const { timeout = 3000, interval = 100 } = options; // Default timeout of 3 seconds
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    if (predicate()) {
      return true;
    }
    await new Promise(resolve => setTimeout(resolve, interval));
  }
  return false; // Timed out
}

/**
 * A utility to find the first element in an INotebookTracker that satisfies a condition.
 * @param tracker - The INotebookTracker to search.
 * @param predicate - The function to test each panel.
 * @returns The first panel that satisfies the condition, or null.
 */
function findInTracker(tracker: INotebookTracker, predicate: (panel: NotebookPanel) => boolean): NotebookPanel | null {
    let foundPanel: NotebookPanel | null = null;
    tracker.forEach(panel => {
        if (foundPanel) return; // Already found, short-circuit
        if (predicate(panel)) {
            foundPanel = panel;
        }
    });
    return foundPanel;
}

/**
 * Initialization data for the hotreload_extension extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: 'hotreload_extension:plugin',
  description: 'A JupyterLab extension for programmatic notebook control.',
  autoStart: true,
  requires: [INotebookTracker, ICommandPalette, IDocumentManager],
  activate: (
    app: JupyterFrontEnd,
    tracker: INotebookTracker,
    palette: ICommandPalette,
    docManager: IDocumentManager
  ) => {
    console.log('JupyterLab extension hotreload_extension is activated!');

    const command = 'notebook:revert-from-disk';
    app.commands.addCommand(command, {
      label: 'Hot Reload',
      execute: () => {
        const panel = tracker.currentWidget;
        if (panel) {
          panel.context.revert();
        }
      }
    });

    palette.addItem({ command, category: 'Notebook Operations' });

    // Connect to the WebSocket server
    setupWebSocket(app, tracker, docManager);
  }
};

/**
 * Processes cell outputs to make them more LLM-friendly by truncating image data.
 */
function processCellOutputsForLLM(outputs: IOutput[]): IOutput[] {
  if (!outputs || outputs.length === 0) {
    return [];
  }
  return outputs.map(output => {
    const newOutput = JSON.parse(JSON.stringify(output)); // Deep copy
    if (newOutput.output_type === 'display_data' || newOutput.output_type === 'execute_result') {
      if (newOutput.data) {
        for (const mimeType in newOutput.data) {
          if (mimeType.startsWith('image/')) {
            const original_data = newOutput.data[mimeType];
            let original_size_bytes = 0;
            if (typeof original_data === 'string'){
                original_size_bytes = new TextEncoder().encode(original_data).length;
            }
            // Replace the actual image data with a placeholder
            newOutput.data[mimeType] = `<image_data_truncated: ${mimeType}, original_size=${original_size_bytes} bytes>`;
          }
        }
      }
    }
    return newOutput;
  });
}

/**
 * Set up WebSocket connection to listen for commands.
 */
function setupWebSocket(
  app: JupyterFrontEnd,
  tracker: INotebookTracker,
  docManager: IDocumentManager
): void {
  try {
    const settings = ServerConnection.makeSettings();
    const baseUrl = settings.baseUrl;
    const wsProtocol = baseUrl.startsWith('https') ? 'wss' : 'ws';
    const wsUrl = URLExt.join(baseUrl, 'api/hotreload/ws').replace(/^https?/, wsProtocol);

    console.log(`Connecting to WebSocket at: ${wsUrl}`);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connection established');
        // Send an initial heartbeat immediately to signal presence
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: 'frontend-heartbeat' }));
        }
    };

    ws.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('WebSocket message received:', data);

        if (data.action === 'open-notebook' && data.path) {
          try {
            const widget = await docManager.open(data.path);
            
            // Wait for the notebook panel to be tracked, ensuring it's fully active.
            const panelReady = await waitFor(() => {
                return !!widget && tracker.has(widget);
            }, { timeout: 10000 }); // 10-second timeout for opening

            if (panelReady) {
                ws.send(JSON.stringify({ action: 'notebook-opened', path: data.path, success: true }));
            } else {
                ws.send(JSON.stringify({ action: 'notebook-opened', path: data.path, success: false, error: 'Timeout: Notebook panel did not become active in the tracker.' }));
            }
          } catch (error) {
            const errorMsg = error instanceof Error ? error.message : String(error);
            ws.send(JSON.stringify({ action: 'notebook-opened', path: data.path, success: false, error: `Failed to open document: ${errorMsg}` }));
          }
          return;
        }

        const panels: NotebookPanel[] = [];
        tracker.forEach(p => panels.push(p));
        const panel = panels.find(p => p.context.path === data.path || p.context.path.endsWith(data.path));

        if (!panel) {
          const replyAction = data.action ? `${data.action.replace(/-cell/g, '')}-failed` : 'action-failed';
          ws.send(JSON.stringify({ action: replyAction, path: data.path, success: false, error: 'Target notebook is not open or not found.' }));
          return;
        }

        if (data.action === 'save') {
            await panel.context.save();
            if (data.waitForSave) ws.send(JSON.stringify({ action: 'saved', path: data.path, success: true }));
        } else if (data.action === 'get-cells') {
            if (!panel.model) {
                ws.send(JSON.stringify({ action: 'cells-data', path: data.path, success: false, error: 'Notebook model not found' }));
                return;
            }
            const cellsData = panel.content.widgets.map((cell: Cell) => {
              const cellModel = cell.model;
              const cellData: any = {
                cell_id: cellModel.id,
                cell_type: cellModel.type,
                content: cellModel.sharedModel.getSource()
              };
              if (cellModel.type === 'code') {
                const outputsModel = (cellModel as any).outputs;
                if (outputsModel) {
                  const rawOutputs = outputsModel.toJSON() as IOutput[];
                  cellData.outputs = processCellOutputsForLLM(rawOutputs);
                  cellData.execution_count = (cellModel as any).executionCount;
                }
              }
              return cellData;
            });
            ws.send(JSON.stringify({ action: 'cells-data', path: data.path, cells: cellsData }));
        } else if (data.action === 'insert-cell') {
            if (!panel.model) {
                 ws.send(JSON.stringify({ action: 'cell-inserted', path: data.path, success: false, error: 'Notebook model not found' }));
              return;
            }
            const notebookModel = panel.model;
            let position = notebookModel.cells.length; // Default to end
            
            notebookModel.sharedModel.insertCell(position, {
              cell_type: data.cell_type === 'markdown' ? 'markdown' : 'code',
              source: data.content || ''
            });

            // Wait for the cell widget to be created before we proceed.
            const widgetReady = await waitFor(() => {
                // Check if a cell at the target position with the right content exists
                if (notebookModel.cells.length > position) {
                    const cellModel = notebookModel.cells.get(position);
                    return cellModel && cellModel.sharedModel.getSource() === data.content;
                }
                return false;
            }, { timeout: 5000 });

            if (!widgetReady) {
                ws.send(JSON.stringify({ action: 'cell-inserted', path: data.path, success: false, error: 'Failed to verify cell widget creation on the frontend.' }));
                return;
            }

            // Now that the cell is confirmed to exist, save the notebook to get a permanent ID.
            await panel.context.save();
            
            const insertedCellModel = notebookModel.cells.get(position);
            const newCellId = insertedCellModel.id;

            ws.send(JSON.stringify({ action: 'cell-inserted', path: data.path, success: true, cell_id: newCellId, position }));

        } else if (data.action === 'execute-cell') {
            const notebook = panel.content;
            const sessionContext = panel.sessionContext;
            ws.send(JSON.stringify({ action: 'cell-execution-acknowledged', path: data.path, cell_id: data.cell_id }));
            
            let cellWidget: Cell | undefined;
            const widgetExists = await waitFor(() => {
                cellWidget = notebook.widgets.find(w => w.model.id === data.cell_id);
                return !!cellWidget;
            }, { timeout: 300000 }); // Increased timeout to 5 min

            if (!widgetExists || !cellWidget) {
                ws.send(JSON.stringify({ action: 'cell-executed', path: data.path, cell_id: data.cell_id, status: 'error', error_type: 'ExecutionError', error_message: `Cell widget with ID ${data.cell_id} not found` }));
                return;
            }

            if (cellWidget instanceof MarkdownCell) {
                cellWidget.rendered = true;
                ws.send(JSON.stringify({ action: 'cell-executed', path: data.path, cell_id: data.cell_id, status: 'success', outputs: [] }));
            } else if (cellWidget instanceof CodeCell) {
                const kernelReady = await waitFor(() => !!sessionContext.session?.kernel, { timeout: 10000 });
                if (!kernelReady || !sessionContext.session?.kernel) {
                    ws.send(JSON.stringify({ action: 'cell-executed', path: data.path, cell_id: data.cell_id, status: 'error', error_type: 'ExecutionError', error_message: 'Kernel not available (timed out)' }));
                    return;
                }

                // Use JupyterLab's proper cell execution method instead of raw kernel execution
                try {
                    // Execute the cell using JupyterLab's built-in execution method
                    // This properly ties the execution to the cell model
                    const executed = await CodeCell.execute(cellWidget, sessionContext);
                    
                    if (executed) {
                        // Read the results from the cell model after execution
                        const finalOutputs = cellWidget.model.outputs.toJSON() as IOutput[];
                        const executionCount = cellWidget.model.executionCount;
                        
                        ws.send(JSON.stringify({ 
                            action: 'cell-executed', 
                            path: data.path, 
                            cell_id: data.cell_id, 
                            status: 'success', 
                            outputs: processCellOutputsForLLM(finalOutputs), 
                            execution_count: executionCount
                        }));
                    } else {
                        ws.send(JSON.stringify({ 
                            action: 'cell-executed', 
                            path: data.path, 
                            cell_id: data.cell_id, 
                            status: 'error', 
                            error_type: 'ExecutionError', 
                            error_message: 'Cell execution failed'
                        }));
                    }
                } catch (error) {
                    const errorMsg = error instanceof Error ? error.message : String(error);
                    ws.send(JSON.stringify({ 
                        action: 'cell-executed', 
                        path: data.path, 
                        cell_id: data.cell_id, 
                        status: 'error', 
                        error_type: 'ExecutionError', 
                        error_message: `Cell execution error: ${errorMsg}`
                    }));
                }
            }
        } else if (data.action === 'replace-cell' && data.path && data.cell_id) {
          console.log(`Replace cell request received for cell ${data.cell_id} in ${data.path}`);
          
          // Find the target notebook panel
          const targetPanel = findInTracker(tracker, panel => {
            return panel.context.path === data.path || panel.context.path.endsWith(data.path);
          });

          if (!targetPanel) {
            ws.send(JSON.stringify({
              action: 'cell-replaced',
              path: data.path,
              cell_id: data.cell_id,
              success: false,
              error: 'Notebook not found or not open'
            }));
            return;
          }

          console.log(`Found notebook for cell replacement: ${targetPanel.context.path}`);

          // Get notebook model
          const notebook = targetPanel.content;
          const notebookModel = notebook.model;
          if (!notebookModel) {
            console.error('Notebook model is null, cannot replace cell.');
            ws.send(JSON.stringify({
              action: 'cell-replaced',
              path: data.path,
              cell_id: data.cell_id,
              success: false,
              error: 'Notebook model is null'
            }));
            return;
          }

          // Find the cell with the given ID
          let cellIndex = -1;
          for (let i = 0; i < notebook.widgets.length; i++) {
            if (notebook.widgets[i].model.id === data.cell_id) {
              cellIndex = i;
              break;
            }
          }

          if (cellIndex >= 0) {
            const cellWidget = notebook.widgets[cellIndex];
            cellWidget.model.sharedModel.setSource(data.content || '');

            // Wait for the change to be reflected in the model
            const replaced = await waitFor(() => {
                return cellWidget.model.sharedModel.getSource() === (data.content || '');
            });

            if (replaced) {
                ws.send(JSON.stringify({
                  action: 'cell-replaced',
                  path: data.path,
                  cell_id: data.cell_id,
                  success: true
                }));
            } else {
                ws.send(JSON.stringify({
                  action: 'cell-replaced',
                  path: data.path,
                  cell_id: data.cell_id,
                  success: false,
                  error: 'Failed to verify cell content replacement.'
                }));
            }
          } else {
            console.error(`Cell with ID ${data.cell_id} not found`);
            ws.send(JSON.stringify({
              action: 'cell-replaced',
              path: data.path,
              cell_id: data.cell_id,
              success: false,
              error: `Cell with ID ${data.cell_id} not found`
            }));
          }
        } else if (data.action === 'delete-cell' && data.path && data.cell_id) {
          console.log(`Delete cell request received for cell ${data.cell_id} in ${data.path}`);
          
          // Find the target notebook panel
          const targetPanel = findInTracker(tracker, panel => {
            return panel.context.path === data.path || panel.context.path.endsWith(data.path);
          });

          if (!targetPanel) {
            ws.send(JSON.stringify({
              action: 'cell-deleted',
              path: data.path,
              cell_id: data.cell_id,
              success: false,
              error: 'Notebook not found or not open'
            }));
            return;
          }

          console.log(`Found notebook for cell deletion: ${targetPanel.context.path}`);

          // Get notebook model
          const notebook = targetPanel.content;
          const notebookModel = notebook.model;
          if (!notebookModel) {
            console.error('Notebook model is null, cannot delete cell.');
            ws.send(JSON.stringify({
              action: 'cell-deleted',
              path: data.path,
              cell_id: data.cell_id,
              success: false,
              error: 'Notebook model is null'
            }));
            return;
          }

          // Find the cell with the given ID
          let cellIndex = -1;
          for (let i = 0; i < notebook.widgets.length; i++) {
            if (notebook.widgets[i].model.id === data.cell_id) {
              cellIndex = i;
              break;
            }
          }

          if (cellIndex >= 0) {
            notebookModel.sharedModel.deleteCell(cellIndex);

            // Wait for the model to update and confirm deletion
            const deleted = await waitFor(() => {
                for (let i = 0; i < notebookModel.cells.length; i++) {
                    if (notebookModel.cells.get(i).id === data.cell_id) {
                        return false; // Still exists
                    }
                }
                return true; // No longer found
            });

            if (deleted) {
                ws.send(JSON.stringify({
                  action: 'cell-deleted',
                  path: data.path,
                  cell_id: data.cell_id,
                  success: true,
                  index: cellIndex
                }));
            } else {
                ws.send(JSON.stringify({
                  action: 'cell-deleted',
                  path: data.path,
                  cell_id: data.cell_id,
                  success: false,
                  error: 'Failed to verify cell deletion from model.'
                }));
            }
          } else {
            console.error(`Cell with ID ${data.cell_id} not found`);
            ws.send(JSON.stringify({
              action: 'cell-deleted',
              path: data.path,
              cell_id: data.cell_id,
              success: false,
              error: `Cell with ID ${data.cell_id} not found`
            }));
          }
        } else if (data.action === 'close-notebook-tab' && data.path) {
            console.log(`Close notebook tab request received for: ${data.path}`);
            const panelToClose = findInTracker(tracker, p => p.context.path === data.path || p.context.path.endsWith(data.path));

            if (panelToClose) {
                // Save before closing to avoid the dialog
                await panelToClose.context.save();
                console.log(`Notebook ${panelToClose.context.path} saved before closing.`);

                await panelToClose.close();
                console.log(`Notebook tab ${panelToClose.context.path} has been closed.`);
                
                ws.send(JSON.stringify({ action: 'notebook-tab-closed', path: data.path, success: true, message: 'Notebook tab saved and closed successfully.' }));
            } else {
                ws.send(JSON.stringify({ action: 'notebook-tab-closed', path: data.path, success: false, error: 'Notebook tab not found or not open.' }));
            }
        } else if ((data.action === 'reload' && data.path) || (data.path && !data.action)) {
          console.log('Processing as reload action');
          handleReloadAction(data.path, tracker);
        }
      } catch (error) {
        console.error('Error processing WebSocket message:', error);
      }
    };

    ws.onerror = (error: Event) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = (event: CloseEvent) => {
      console.log(`WebSocket closed with code ${event.code}`);
      // Attempt to reconnect after a delay
      setTimeout(() => setupWebSocket(app, tracker, docManager), 3000);
    };

    // Send a heartbeat every 30 seconds to signal frontend presence
    const heartbeatInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: 'frontend-heartbeat' }));
        }
    }, 10000);

    // Clean up the interval on close
    ws.addEventListener('close', () => {
        clearInterval(heartbeatInterval);
    });

  } catch (error) {
    console.error('Error setting up WebSocket:', error);
  }
}

/**
 * Reload notebook content from disk but preserve execution state
 */
async function smartReloadNotebook(panel: NotebookPanel): Promise<void> {
  const notebook = panel.content;
  const context = panel.context;

  // Save scroll position
  const scrollTop = notebook.node.scrollTop;

  // Store current active cell index
  const activeCellIndex = notebook.activeCellIndex;

  // Save execution state of each cell
  const cellStates = notebook.widgets.map(cell => {
    // Only code cells have execution count and outputs
    if (cell.model.type === 'code') {
      const codeCell = cell as CodeCell;
      const outputs: IOutput[] = [];

      // Get outputs if available
      if (codeCell.model.outputs) {
        // Use toJSON to get all outputs as an array
        outputs.push(...(codeCell.model.outputs.toJSON() as IOutput[]));
      }

      return {
        executionCount: codeCell.model.executionCount,
        outputs,
        isCodeCell: true
      };
    }

    return {
      executionCount: null,
      outputs: [],
      isCodeCell: false
    };
  });

  console.log(`Preserving state for ${cellStates.length} cells`);

  try {
    // Fetch the latest content from disk
    await context.revert();

    // Update each cell to restore outputs
    const updatedCells = notebook.widgets;
    console.log(`Restoring state for ${Math.min(cellStates.length, updatedCells.length)} cells`);

    updatedCells.forEach((cell, i) => {
      if (i < cellStates.length && cellStates[i].isCodeCell && cell.model.type === 'code') {
        const savedState = cellStates[i];
        const codeCell = cell as CodeCell;

        // Restore execution count if present
        if (savedState.executionCount !== null && savedState.executionCount !== undefined) {
          codeCell.model.executionCount = savedState.executionCount;
        }

        // Restore outputs if present and cell has outputs model
        if (savedState.outputs.length > 0 && codeCell.model.outputs) {
          codeCell.model.outputs.clear();
          savedState.outputs.forEach(output => {
            codeCell.model.outputs.add(output);
          });
        }

        // Mark the cell as executed if it had outputs
        if (savedState.executionCount !== null && savedState.outputs.length > 0) {
          codeCell.addClass('jp-mod-executed');
        }
      }
    });

    // Restore notebook scroll position
    notebook.node.scrollTop = scrollTop;

    // Restore active cell
    if (activeCellIndex >= 0 && activeCellIndex < notebook.widgets.length) {
      notebook.activeCellIndex = activeCellIndex;
    }

    console.log('Notebook hot-reloaded with preserved execution state');
  } catch (error) {
    console.error('Error during smart reload:', error);
    // Fallback to regular revert
    await context.revert();
  }
}

// Add a separate function to handle reload actions
function handleReloadAction(path: string, tracker: INotebookTracker): void {
  const panel = findInTracker(tracker, p => p.context.path.endsWith(path.split('/').pop()!));
  if (panel) {
      console.log(`Reloading notebook: ${panel.context.path}`);
      smartReloadNotebook(panel);
  }
}

export default plugin;
