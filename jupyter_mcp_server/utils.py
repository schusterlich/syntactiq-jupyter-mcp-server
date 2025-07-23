# Copyright (c) 2023-2024 Datalayer, Inc.
#
# BSD 3-Clause License

import re
from typing import Any, Union, Optional, Dict, List


# Error and Warning Detection Constants
ERROR_PATTERNS = {
    'syntax_error': r'\bSyntaxError\s*:\s*(.+)',
    'name_error': r'\bNameError\s*:\s*(.+)', 
    'type_error': r'\bTypeError\s*:\s*(.+)',
    'value_error': r'\bValueError\s*:\s*(.+)',
    'attribute_error': r'\bAttributeError\s*:\s*(.+)',
    'key_error': r'\bKeyError\s*:\s*(.+)',
    'index_error': r'\bIndexError\s*:\s*(.+)',
    'zero_division_error': r'\bZeroDivisionError\s*:\s*(.+)',
    'file_not_found_error': r'\bFileNotFoundError\s*:\s*(.+)',
    'permission_error': r'\bPermissionError\s*:\s*(.+)',
    'import_error': r'\bImportError\s*:\s*(.+)',
    'module_not_found_error': r'\bModuleNotFoundError\s*:\s*(.+)',
    'runtime_error': r'\bRuntimeError\s*:\s*(.+)',
    'assertion_error': r'\bAssertionError\s*:\s*(.+)',
    'connection_error': r'\bConnectionError\s*:\s*(.+)',
    'timeout_error': r'\bTimeoutError\s*:\s*(.+)',
    'memory_error': r'\bMemoryError\s*:\s*(.+)',
    'keyboard_interrupt': r'\bKeyboardInterrupt\s*:\s*(.+)',
    'indentation_error': r'\bIndentationError\s*:\s*(.+)',
    'tab_error': r'\bTabError\s*:\s*(.+)',
    'unicode_error': r'\bUnicodeError\s*:\s*(.+)',
    'overflow_error': r'\bOverflowError\s*:\s*(.+)',
    'recursion_error': r'\bRecursionLimitExceeded\s*:\s*(.+)',
}

WARNING_PATTERNS = {
    # Order matters - more specific patterns first
    'deprecation_warning': r'\bDeprecationWarning\s*:\s*(.+)',
    'future_warning': r'\bFutureWarning\s*:\s*(.+)',
    'pending_deprecation_warning': r'\bPendingDeprecationWarning\s*:\s*(.+)',
    'runtime_warning': r'\bRuntimeWarning\s*:\s*(.+)',
    'syntax_warning': r'\bSyntaxWarning\s*:\s*(.+)',
    'import_warning': r'\bImportWarning\s*:\s*(.+)',
    'unicode_warning': r'\bUnicodeWarning\s*:\s*(.+)',
    'bytes_warning': r'\bBytesWarning\s*:\s*(.+)',
    'resource_warning': r'\bResourceWarning\s*:\s*(.+)',
    'user_warning': r'\bUserWarning\s*:\s*(.+)',
    # Generic warning pattern last - should be more specific
    'category_warning': r'(?:^|\s|/)([A-Z]\w*Warning)\s*:\s*(.+)',
}


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


def classify_execution_output(outputs: Any) -> Dict[str, Any]:
    """
    Classify execution outputs to detect errors, warnings, and their types.
    
    Args:
        outputs: Cell outputs (could be CRDT YArray or traditional list)
        
    Returns:
        dict: {
            "has_error": bool,
            "has_warning": bool,
            "error": Optional[Dict],  # {"type": str, "message": str, "severity": str}
            "warning": Optional[Dict],  # {"type": str, "message": str, "severity": str}
            "execution_status": str  # "success", "error", "warning"
        }
    """
    result = {
        "has_error": False,
        "has_warning": False,
        "error": None,
        "warning": None,
        "execution_status": "success"
    }
    
    if not outputs:
        return result
    
    # Collect all text outputs for analysis
    all_output_text = []
    
    # Handle CRDT YArray or traditional list
    if hasattr(outputs, '__iter__') and not isinstance(outputs, (str, dict)):
        try:
            for output in outputs:
                text = extract_output(output)
                if text:
                    all_output_text.append(text)
        except Exception:
            pass
    else:
        text = extract_output(outputs)
        if text:
            all_output_text.append(text)
    
    # Analyze each output for errors and warnings
    for output_text in all_output_text:
        error_info = _detect_error(output_text)
        if error_info:
            result["has_error"] = True
            result["error"] = error_info
            result["execution_status"] = "error"
            break  # First error wins
        
        warning_info = _detect_warning(output_text)
        if warning_info and not result["has_warning"]:
            result["has_warning"] = True
            result["warning"] = warning_info
            if result["execution_status"] == "success":
                result["execution_status"] = "warning"
    
    return result


def _detect_error(text: str) -> Optional[Dict[str, str]]:
    """
    Detect if text contains error information and classify it.
    
    Args:
        text: Output text to analyze
        
    Returns:
        Optional[Dict]: Error info if detected, None otherwise
    """
    if not text or not isinstance(text, str):
        return None
    
    text_lower = text.lower()
    
    # Common error patterns with classification
    error_patterns = [
        # Syntax Errors
        (r'syntaxerror[:\s]', "syntax_error", "SyntaxError"),
        (r'indentationerror[:\s]', "syntax_error", "IndentationError"),
        (r'tabserror[:\s]', "syntax_error", "TabsError"),
        
        # Runtime Errors
        (r'zerodivisionerror[:\s]', "runtime_error", "ZeroDivisionError"),
        (r'valueerror[:\s]', "runtime_error", "ValueError"),
        (r'typeerror[:\s]', "runtime_error", "TypeError"),
        (r'nameerror[:\s]', "runtime_error", "NameError"),
        (r'attributeerror[:\s]', "runtime_error", "AttributeError"),
        (r'keyerror[:\s]', "runtime_error", "KeyError"),
        (r'indexerror[:\s]', "runtime_error", "IndexError"),
        (r'filenotfounderror[:\s]', "runtime_error", "FileNotFoundError"),
        (r'importerror[:\s]', "runtime_error", "ImportError"),
        (r'modulenotfounderror[:\s]', "runtime_error", "ModuleNotFoundError"),
        
        # General error patterns
        (r'traceback \(most recent call last\)', "runtime_error", "Exception"),
        (r'error[:\s].*occurred', "runtime_error", "Error"),
        (r'exception[:\s]', "runtime_error", "Exception"),
        (r'failed[:\s]', "runtime_error", "Failure"),
    ]
    
    for pattern, error_type, error_class in error_patterns:
        if re.search(pattern, text_lower):
            # Extract a clean error message
            message = _extract_error_message(text, error_class)
            return {
                "type": error_type,
                "message": message,
                "severity": "error",
                "error_class": error_class
            }
    
    return None


def _detect_warning(text: str) -> Optional[Dict[str, str]]:
    """
    Detect if text contains warning information and classify it.
    
    Args:
        text: Output text to analyze
        
    Returns:
        Optional[Dict]: Warning info if detected, None otherwise
    """
    if not text or not isinstance(text, str):
        return None
    
    text_lower = text.lower()
    
    # Common warning patterns
    warning_patterns = [
        (r'userwarning[:\s]', "user_warning", "UserWarning"),
        (r'deprecationwarning[:\s]', "deprecation_warning", "DeprecationWarning"),
        (r'futurewarning[:\s]', "future_warning", "FutureWarning"),
        (r'runtimewarning[:\s]', "runtime_warning", "RuntimeWarning"),
        (r'warning[:\s]', "general_warning", "Warning"),
        (r'caution[:\s]', "general_warning", "Caution"),
        (r'note[:\s]', "info_warning", "Note"),
    ]
    
    for pattern, warning_type, warning_class in warning_patterns:
        if re.search(pattern, text_lower):
            message = _extract_warning_message(text, warning_class)
            return {
                "type": warning_type,
                "message": message,
                "severity": "warning",
                "warning_class": warning_class
            }
    
    return None


def _extract_error_message(text: str, error_class: str) -> str:
    """
    Extract a clean, concise error message from error output.
    
    Args:
        text: Full error output text
        error_class: The detected error class
        
    Returns:
        str: Clean error message
    """
    lines = text.strip().split('\n')
    
    # Look for the actual error message (usually the last line)
    for line in reversed(lines):
        line = line.strip()
        if error_class.lower() in line.lower() and ':' in line:
            # Extract message after the colon
            parts = line.split(':', 1)
            if len(parts) > 1:
                return parts[1].strip()
    
    # Fallback: return first non-empty line or truncated version
    for line in lines:
        line = line.strip()
        if line and not line.startswith('-'):
            return line[:100] + "..." if len(line) > 100 else line
    
    return f"{error_class} occurred"


def _extract_warning_message(text: str, warning_class: str) -> str:
    """
    Extract a clean, concise warning message from warning output.
    
    Args:
        text: Full warning output text
        warning_class: The detected warning class
        
    Returns:
        str: Clean warning message
    """
    lines = text.strip().split('\n')
    
    # Look for the warning message
    for line in lines:
        line = line.strip()
        if warning_class.lower() in line.lower() and ':' in line:
            parts = line.split(':', 1)
            if len(parts) > 1:
                return parts[1].strip()
    
    # Fallback: return first meaningful line
    for line in lines:
        line = line.strip()
        if line and not line.startswith('/') and len(line) > 10:
            return line[:150] + "..." if len(line) > 150 else line
    
    return f"{warning_class} occurred"


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


def safe_extract_outputs_with_enhanced_structure(outputs: Any, full_output: bool = False) -> dict:
    """
    Extract outputs with enhanced structure including error/warning detection.
    
    Args:
        outputs: Cell outputs (could be CRDT YArray or traditional list)
        full_output: If True, return full outputs without truncation
        
    Returns:
        dict: {
            "text_outputs": list[str],     # Clean text outputs (images suppressed)
            "images": list[dict],          # Structured image data with base64
            "execution_status": str,       # "success", "error", "warning" 
            "error": Optional[dict],       # Error details if detected
            "warning": Optional[dict]      # Warning details if detected
        }
    """
    if not outputs:
        return {
            "text_outputs": [],
            "images": [],
            "execution_status": "success",
            "error": None,
            "warning": None
        }
    
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
    
    # Classify execution status and detect errors/warnings
    classification = classify_execution_output(outputs)
    
    result = {
        "text_outputs": text_outputs,
        "images": images,
        "execution_status": classification["execution_status"]
    }
    
    # Only include error/warning fields if they exist (conditional approach)
    if classification["error"]:
        result["error"] = classification["error"]
    
    if classification["warning"]:
        result["warning"] = classification["warning"]
    
    return result


def safe_extract_outputs_with_images(outputs: Any, full_output: bool = False) -> dict:
    """
    Extract outputs with separate text and image arrays for structured processing.
    Now includes error and warning detection.
    
    Args:
        outputs: Cell outputs (could be CRDT YArray or traditional list)
        full_output: If True, return full outputs without truncation
        
    Returns:
        dict: {
            "text_outputs": list[str],  # Clean text outputs (images suppressed)
            "images": list[dict],       # Structured image data with base64
            "error": dict or None,      # Error info if detected
            "warning": dict or None     # Warning info if detected
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
    
    # Extract error and warning information
    error_warning_info = extract_error_and_warning_info(outputs)
    
    result = {
        "text_outputs": text_outputs,
        "images": images
    }
    
    # Only include error field if there's an error
    if error_warning_info["error"]:
        result["error"] = error_warning_info["error"]
    
    # Only include warning field if there's a warning  
    if error_warning_info["warning"]:
        result["warning"] = error_warning_info["warning"]
    
    return result


def detect_error_in_output(output_text: str) -> Optional[Dict[str, str]]:
    """
    Detect Python errors in Jupyter output text and return structured error data.
    
    Args:
        output_text: The output text from a Jupyter cell
        
    Returns:
        Dict with error info if found, None otherwise:
        {
            "type": "syntax_error",
            "message": "SyntaxError: unterminated string literal"
        }
    """
    if not output_text or not isinstance(output_text, str):
        return None
    
    # Check for error patterns
    for error_type, pattern in ERROR_PATTERNS.items():
        match = re.search(pattern, output_text, re.IGNORECASE | re.MULTILINE)
        if match:
            # Extract the error message, clean it up
            error_message = match.group(0).strip()
            # Remove extra whitespace and normalize
            error_message = ' '.join(error_message.split())
            
            return {
                "type": error_type,
                "message": error_message
            }
    
    return None


def detect_warning_in_output(output_text: str) -> Optional[Dict[str, str]]:
    """
    Detect Python warnings in Jupyter output text and return structured warning data.
    
    Args:
        output_text: The output text from a Jupyter cell
        
    Returns:
        Dict with warning info if found, None otherwise:
        {
            "type": "user_warning", 
            "message": "UserWarning: This is a test warning"
        }
    """
    if not output_text or not isinstance(output_text, str):
        return None
    
    # Check for warning patterns
    for warning_type, pattern in WARNING_PATTERNS.items():
        match = re.search(pattern, output_text, re.IGNORECASE | re.MULTILINE)
        if match:
            # Extract the warning message, clean it up
            warning_message = match.group(0).strip()
            # Remove extra whitespace and normalize
            warning_message = ' '.join(warning_message.split())
            
            return {
                "type": warning_type,
                "message": warning_message
            }
    
    return None


def extract_error_and_warning_info(outputs: Any) -> Dict[str, Optional[Dict[str, str]]]:
    """
    Extract both error and warning information from Jupyter cell outputs.
    
    Args:
        outputs: Cell outputs (could be CRDT YArray or traditional list)
        
    Returns:
        Dict with error and warning info:
        {
            "error": {"type": "...", "message": "...", "severity": "error"} or None,
            "warning": {"type": "...", "message": "...", "severity": "warning"} or None
        }
    """
    if not outputs:
        return {"error": None, "warning": None}
    
    # Collect all output text for analysis
    all_output_text = []
    
    # Handle CRDT YArray
    if hasattr(outputs, '__iter__') and not isinstance(outputs, (str, dict)):
        try:
            for output in outputs:
                extracted = extract_output(output)
                if extracted:
                    all_output_text.append(extracted)
        except Exception:
            pass
    else:
        # Handle single output or traditional list
        extracted = extract_output(outputs)
        if extracted:
            all_output_text.append(extracted)
    
    # Combine all output text
    combined_text = '\n'.join(all_output_text)
    
    # Detect error and warning
    error_info = detect_error_in_output(combined_text)
    warning_info = detect_warning_in_output(combined_text)
    
    return {
        "error": error_info,
        "warning": warning_info
    }