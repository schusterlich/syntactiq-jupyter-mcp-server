FROM jupyter/minimal-notebook:python-3.10

# Switch to root to install curl for healthchecks, then switch back to the notebook user
USER root
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
USER ${NB_UID}

# Install Python dependencies according to the official jupyter-mcp-server documentation
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "jupyterlab==4.4.1" \
    "jupyter-collaboration==4.0.2" \
    "ipykernel" && \
    pip uninstall -y pycrdt datalayer_pycrdt && \
    pip install "datalayer_pycrdt==0.12.17" 