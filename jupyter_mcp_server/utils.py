# Copyright (c) 2023-2024 Datalayer, Inc.
#
# BSD 3-Clause License

import re
from typing import Any, Union


def extract_output(output: Union[dict, Any]) -> str:
    """
    Extracts readable output from a Jupyter cell output dictionary.
    Handles both traditional and CRDT-based Jupyter formats.

    Args:
        output: The output from a Jupyter cell (dict or CRDT object).

    Returns:
        str: A string representation of the output.
    """
    # Handle pycrdt._text.Text objects
    if hasattr(output, 'source'):
        return str(output.source)
    
    # Handle CRDT YText objects
    if hasattr(output, '__str__') and 'Text' in str(type(output)):
        text_content = str(output)
        return strip_ansi_codes(text_content)
    
    # Handle lists (common in error tracebacks)
    if isinstance(output, list):
        return '\n'.join(extract_output(item) for item in output)
    
    # Handle traditional dictionary format
    if not isinstance(output, dict):
        return strip_ansi_codes(str(output))
    
    output_type = output.get("output_type")
    
    if output_type == "stream":
        text = output.get("text", "")
        if isinstance(text, list):
            text = ''.join(text)
        elif hasattr(text, 'source'):
            text = str(text.source)
        return strip_ansi_codes(str(text))
    
    elif output_type in ["display_data", "execute_result"]:
        data = output.get("data", {})
        if "text/plain" in data:
            plain_text = data["text/plain"]
            if hasattr(plain_text, 'source'):
                plain_text = str(plain_text.source)
            return strip_ansi_codes(str(plain_text))
        elif "text/html" in data:
            return "[HTML Output]"
        elif "image/png" in data:
            return "[Image Output (PNG)]"
        else:
            return f"[{output_type} Data: keys={list(data.keys())}]"
    
    elif output_type == "error":
        traceback = output.get("traceback", [])
        if isinstance(traceback, list):
            clean_traceback = []
            for line in traceback:
                if hasattr(line, 'source'):
                    line = str(line.source)
                clean_traceback.append(strip_ansi_codes(str(line)))
            return '\n'.join(clean_traceback)
        else:
            if hasattr(traceback, 'source'):
                traceback = str(traceback.source)
            return strip_ansi_codes(str(traceback))
    
    else:
        return f"[Unknown output type: {output_type}]"


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', text)


def truncate_output(output: str, full_output: bool = False) -> str:
    """
    Truncate output to be mindful of LLM context windows.
    
    Args:
        output: The output string to potentially truncate
        full_output: If True, return full output without truncation
        
    Returns:
        str: Original or truncated output with clear indication if shortened
    """
    # Hard limit: ~10k LLM tokens = ~40k characters (protects against massive outputs like full databases)
    MAX_CHARS = 40000
    DEFAULT_CHARS = 1000
    
    limit = MAX_CHARS if full_output else DEFAULT_CHARS
    
    if len(output) <= limit:
        return output
    
    # Truncate and add transparent indicator
    truncated = output[:limit].rstrip()
    remaining_chars = len(output) - len(truncated)
    
    if full_output:
        return f"{truncated}\n\n... [Output truncated at 40k chars (safety limit) - {remaining_chars} more characters]"
    else:
        return f"{truncated}\n\n... [Output truncated - {remaining_chars} more characters. Use 'full_output=True' to see complete output, but only if you need to]"


def safe_extract_outputs(outputs: Any, full_output: bool = False) -> list[str]:
    """
    Safely extract all outputs from a cell, handling CRDT structures.
    
    Args:
        outputs: Cell outputs (could be CRDT YArray or traditional list)
        full_output: If True, return full outputs without truncation
        
    Returns:
        list[str]: List of string representations of outputs (potentially truncated)
    """
    if not outputs:
        return []
    
    result = []
    
    # Handle CRDT YArray
    if hasattr(outputs, '__iter__') and not isinstance(outputs, (str, dict)):
        try:
            for output in outputs:
                extracted = extract_output(output)
                if extracted:
                    truncated = truncate_output(extracted, full_output)
                    result.append(truncated)
        except Exception as e:
            result.append(f"[Error extracting output: {str(e)}]")
    else:
        # Handle single output or traditional list
        extracted = extract_output(outputs)
        if extracted:
            truncated = truncate_output(extracted, full_output)
            result.append(truncated)
    
    return result