# Copyright (c) 2023-2024 Datalayer, Inc.
#
# BSD 3-Clause License

import re
from typing import Any, Union


def _is_base64_image_data(text: str) -> bool:
    """
    Detect if text contains base64 image data that should be suppressed.
    
    Args:
        text: The text to check
        
    Returns:
        bool: True if this appears to be base64 image data
    """
    # Check for JSON with image data first (regardless of length)
    json_image_indicators = [
        '"image/png":"',  # PNG in JSON
        '"image/jpeg":"',
        '"image/svg+xml":"',
        'data:image/',  # Data URL format
    ]
    if any(indicator in text for indicator in json_image_indicators):
        return True
    
    # Check for raw base64 image data (requires longer length)
    if len(text) > 1000:  # Base64 images are typically quite long
        if any(indicator in text for indicator in [
            'iVBORw0KGgo',  # Raw PNG signature
            '/9j/',  # JPEG signature
        ]):
            return True
        
        # Check if it's mostly base64 characters (rough heuristic)
        base64_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
        if len(text) > 5000:  # Only check very long strings
            sample = text[:1000] + text[-1000:]  # Sample from beginning and end
            non_base64_chars = sum(1 for c in sample if c not in base64_chars and c not in ' \n\t')
            if non_base64_chars < len(sample) * 0.1:  # Less than 10% non-base64 chars
                return True
    
    return False


def extract_image_info(output: Union[dict, Any]) -> dict:
    """
    Extract structured image information from Jupyter cell output.
    
    Args:
        output: Jupyter cell output (dict, CRDT object, or other format)
        
    Returns:
        dict: Structured image information or None
    """
    # Handle different output formats
    output_dict = None
    
    # Try to convert to dict if it's a CRDT object
    if hasattr(output, 'to_py'):
        try:
            output_dict = output.to_py()
        except:
            pass
    elif hasattr(output, '__dict__'):
        try:
            output_dict = output.__dict__
        except:
            pass
    elif isinstance(output, dict):
        output_dict = output
    else:
        # Try to parse as JSON string if it looks like one
        if isinstance(output, str) and output.strip().startswith('{'):
            try:
                import json
                output_dict = json.loads(output)
            except:
                pass
    
    if not isinstance(output_dict, dict):
        return None
    
    # Look for image data in various locations
    data_sources = [
        output_dict.get("data", {}),  # Standard Jupyter format
        output_dict,  # Sometimes images are at top level
        output_dict.get("metadata", {}).get("data", {}),  # Alternative format
    ]
    
    for data in data_sources:
        if not isinstance(data, dict):
            continue
            
        for mime_type in ["image/png", "image/jpeg", "image/svg+xml", "image/gif"]:
            if mime_type in data:
                image_data = data[mime_type]
                
                # Handle various image data formats
                if hasattr(image_data, 'source'):
                    image_data = str(image_data.source)
                elif hasattr(image_data, 'to_py'):
                    image_data = image_data.to_py()
                elif isinstance(image_data, list):
                    image_data = ''.join(str(item) for item in image_data)
                else:
                    image_data = str(image_data)
                
                if image_data and len(image_data) > 50:  # Must be substantial data
                    return {
                        "type": "image",
                        "mime_type": mime_type,
                        "size_bytes": len(image_data),
                        "base64_data": image_data,  # Full base64 data for platform processing
                        "description": f"Generated {mime_type.split('/')[-1].upper()} image"
                    }
    
    return None


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
        output_str = str(output)
        # Check if this is base64 image data and suppress it
        if _is_base64_image_data(output_str):
            return "[📊 Image Data Detected - Use JupyterLab to view the image]"
        return strip_ansi_codes(output_str)
    
    output_type = output.get("output_type")
    
    if output_type == "stream":
        text = output.get("text", "")
        if isinstance(text, list):
            text = ''.join(text)
        elif hasattr(text, 'source'):
            text = str(text.source)
        text_str = str(text)
        # Check if this is base64 image data and suppress it
        if _is_base64_image_data(text_str):
            return "[📊 Image Data in Stream - Use JupyterLab to view the image]"
        return strip_ansi_codes(text_str)
    
    elif output_type in ["display_data", "execute_result"]:
        data = output.get("data", {})
        
        # Check for images first and handle them specially
        if "image/png" in data:
            return "[📊 PNG Image Generated - Use JupyterLab to view the chart]"
        elif "image/jpeg" in data:
            return "[📊 JPEG Image Generated - Use JupyterLab to view the image]"
        elif "image/svg+xml" in data:
            return "[📊 SVG Image Generated - Use JupyterLab to view the vector graphic]"
        elif "text/html" in data:
            return "[📄 HTML Output - Use JupyterLab to view interactive content]"
        elif "text/plain" in data:
            plain_text = data["text/plain"]
            if hasattr(plain_text, 'source'):
                plain_text = str(plain_text.source)
            plain_text_str = str(plain_text)
            # Check if this is base64 image data and suppress it
            if _is_base64_image_data(plain_text_str):
                return "[📊 Image Data in Text Output - Use JupyterLab to view the image]"
            return strip_ansi_codes(plain_text_str)
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


def safe_extract_outputs_with_images(outputs: Any, full_output: bool = False) -> dict:
    """
    Extract outputs with separate text and image arrays for structured processing.
    
    Args:
        outputs: Cell outputs (could be CRDT YArray or traditional list)
        full_output: If True, return full outputs without truncation
        
    Returns:
        dict: {
            "text_outputs": list[str],  # Clean text outputs (images suppressed)
            "images": list[dict]        # Structured image data with base64
        }
    """
    if not outputs:
        return {"text_outputs": [], "images": []}
    
    text_outputs = []
    images = []
    
    # Handle CRDT YArray
    if hasattr(outputs, '__iter__') and not isinstance(outputs, (str, dict)):
        try:
            for output in outputs:
                # Extract image info first
                image_info = extract_image_info(output)
                if image_info:
                    images.append(image_info)
                
                # Always get text representation (will be clean due to image suppression)
                extracted = extract_output(output)
                if extracted:
                    truncated = truncate_output(extracted, full_output)
                    text_outputs.append(truncated)
        except Exception as e:
            text_outputs.append(f"[Error extracting output: {str(e)}]")
    else:
        # Handle single output or traditional list
        image_info = extract_image_info(outputs)
        if image_info:
            images.append(image_info)
            
        extracted = extract_output(outputs)
        if extracted:
            truncated = truncate_output(extracted, full_output)
            text_outputs.append(truncated)
    
    return {
        "text_outputs": text_outputs,
        "images": images
    }