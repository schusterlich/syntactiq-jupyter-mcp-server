#!/usr/bin/env python3
"""
Unit Test Suite for Error/Warning Detection Functions

Tests all the new error and warning detection functionality added to utils.py
including edge cases, regex patterns, and integration with different output formats.
"""

import unittest
import sys
from typing import Dict, Any, List, Optional

# Import the functions we want to test
from jupyter_mcp_server.utils import (
    detect_error_in_output,
    detect_warning_in_output,
    extract_error_and_warning_info,
    safe_extract_outputs_with_images,
    ERROR_PATTERNS,
    WARNING_PATTERNS
)


class TestErrorDetection(unittest.TestCase):
    """Test error detection functionality"""
    
    def test_syntax_error_detection(self):
        """Test detection of syntax errors"""
        test_cases = [
            "SyntaxError: unterminated string literal (detected at line 1)",
            "  File \"<stdin>\", line 1\n    print('test\nSyntaxError: unterminated string literal",
            "SyntaxError: invalid syntax",
            "SyntaxError: unexpected EOF while parsing"
        ]
        
        for case in test_cases:
            with self.subTest(case=case):
                result = detect_error_in_output(case)
                self.assertIsNotNone(result, f"Should detect syntax error in: {case}")
                self.assertEqual(result["type"], "syntax_error")
                self.assertIn("SyntaxError", result["message"])
    
    def test_runtime_error_detection(self):
        """Test detection of runtime errors"""
        test_cases = [
            ("ZeroDivisionError: division by zero", "zero_division_error"),
            ("NameError: name 'undefined_var' is not defined", "name_error"),
            ("TypeError: unsupported operand type(s)", "type_error"),
            ("ValueError: invalid literal for int()", "value_error"),
            ("KeyError: 'missing_key'", "key_error"),
            ("IndexError: list index out of range", "index_error"),
            ("AttributeError: 'NoneType' object has no attribute", "attribute_error"),
            ("FileNotFoundError: No such file or directory", "file_not_found_error"),
            ("ImportError: No module named", "import_error"),
            ("ModuleNotFoundError: No module named 'missing_module'", "module_not_found_error")
        ]
        
        for error_text, expected_type in test_cases:
            with self.subTest(error_text=error_text):
                result = detect_error_in_output(error_text)
                self.assertIsNotNone(result, f"Should detect error in: {error_text}")
                self.assertEqual(result["type"], expected_type)
                self.assertIn(error_text.split(":")[0], result["message"])
    
    def test_traceback_error_detection(self):
        """Test detection of errors in full tracebacks"""
        traceback_text = """
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ZeroDivisionError: division by zero
        """
        
        result = detect_error_in_output(traceback_text)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "zero_division_error")
        self.assertIn("ZeroDivisionError", result["message"])
    
    def test_no_error_detection(self):
        """Test that normal output doesn't trigger error detection"""
        normal_outputs = [
            "Hello, World!",
            "Result: 42",
            "Processing complete",
            "Error: This is just a string mentioning error",
            "The function returned an error code",
            ""
        ]
        
        for output in normal_outputs:
            with self.subTest(output=output):
                result = detect_error_in_output(output)
                self.assertIsNone(result, f"Should not detect error in normal output: {output}")
    
    def test_edge_cases(self):
        """Test edge cases for error detection"""
        edge_cases = [
            None,
            "",
            "   ",
            123,  # Non-string input
            [],   # Non-string input
            {}    # Non-string input
        ]
        
        for case in edge_cases:
            with self.subTest(case=case):
                result = detect_error_in_output(case)
                self.assertIsNone(result, f"Should handle edge case gracefully: {case}")


class TestWarningDetection(unittest.TestCase):
    """Test warning detection functionality"""
    
    def test_user_warning_detection(self):
        """Test detection of user warnings"""
        test_cases = [
            "UserWarning: This is a test warning",
            "/tmp/ipykernel_42/123.py:1: UserWarning: Test warning message",
            "UserWarning: Deprecation notice"
        ]
        
        for case in test_cases:
            with self.subTest(case=case):
                result = detect_warning_in_output(case)
                self.assertIsNotNone(result, f"Should detect warning in: {case}")
                self.assertEqual(result["type"], "user_warning")
                self.assertIn("UserWarning", result["message"])
    
    def test_deprecation_warning_detection(self):
        """Test detection of deprecation warnings"""
        test_cases = [
            "DeprecationWarning: This feature is deprecated",
            "/path/file.py:10: DeprecationWarning: Use new_function instead"
        ]
        
        for case in test_cases:
            with self.subTest(case=case):
                result = detect_warning_in_output(case)
                self.assertIsNotNone(result, f"Should detect warning in: {case}")
                self.assertEqual(result["type"], "deprecation_warning")
                self.assertIn("DeprecationWarning", result["message"])
    
    def test_various_warning_types(self):
        """Test detection of various warning types"""
        warning_cases = [
            ("FutureWarning: This will change", "future_warning"),
            ("RuntimeWarning: Runtime issue detected", "runtime_warning"),
            ("SyntaxWarning: Invalid syntax detected", "syntax_warning"),
            ("DeprecationWarning: This is deprecated", "deprecation_warning")
        ]
        
        for warning_text, expected_type in warning_cases:
            with self.subTest(warning_text=warning_text):
                result = detect_warning_in_output(warning_text)
                self.assertIsNotNone(result, f"Should detect warning: {warning_text}")
                self.assertEqual(result["type"], expected_type)
                self.assertIn(warning_text.split(":")[0], result["message"])
    
    def test_no_warning_detection(self):
        """Test that normal output doesn't trigger warning detection"""
        normal_outputs = [
            "Hello, World!",
            "The system issued a warning",
            "Processing complete",
            ""
        ]
        
        for output in normal_outputs:
            with self.subTest(output=output):
                result = detect_warning_in_output(output)
                self.assertIsNone(result, f"Should not detect warning in normal output: {output}")


class TestExtractErrorWarningInfo(unittest.TestCase):
    """Test the main extraction function"""
    
    def test_extract_error_from_single_output(self):
        """Test extracting error from a single output"""
        error_output = "ZeroDivisionError: division by zero"
        
        result = extract_error_and_warning_info([error_output])
        
        self.assertIsNotNone(result["error"])
        self.assertIsNone(result["warning"])
        self.assertEqual(result["error"]["type"], "zero_division_error")
    
    def test_extract_warning_from_single_output(self):
        """Test extracting warning from a single output"""
        warning_output = "UserWarning: This is a test warning"
        
        result = extract_error_and_warning_info([warning_output])
        
        self.assertIsNone(result["error"])
        self.assertIsNotNone(result["warning"])
        self.assertEqual(result["warning"]["type"], "user_warning")
    
    def test_extract_both_error_and_warning(self):
        """Test extracting both error and warning from multiple outputs"""
        outputs = [
            "UserWarning: This is a warning",
            "Some normal output",
            "ValueError: This is an error"
        ]
        
        result = extract_error_and_warning_info(outputs)
        
        self.assertIsNotNone(result["error"])
        self.assertIsNotNone(result["warning"])
        self.assertEqual(result["error"]["type"], "value_error")
        self.assertEqual(result["warning"]["type"], "user_warning")
    
    def test_extract_from_empty_outputs(self):
        """Test extraction from empty outputs"""
        result = extract_error_and_warning_info([])
        
        self.assertIsNone(result["error"])
        self.assertIsNone(result["warning"])
    
    def test_extract_from_none_outputs(self):
        """Test extraction from None outputs"""
        result = extract_error_and_warning_info(None)
        
        self.assertIsNone(result["error"])
        self.assertIsNone(result["warning"])


class TestSafeExtractOutputsWithImages(unittest.TestCase):
    """Test the enhanced safe_extract_outputs_with_images function"""
    
    def test_extract_with_error(self):
        """Test that error information is included when present"""
        # Mock output that would contain an error
        mock_output = {
            "output_type": "stream",
            "text": "ZeroDivisionError: division by zero"
        }
        
        result = safe_extract_outputs_with_images([mock_output])
        
        self.assertIn("text_outputs", result)
        self.assertIn("images", result)
        self.assertIn("error", result)
        self.assertNotIn("warning", result)
        
        self.assertEqual(result["error"]["type"], "zero_division_error")
    
    def test_extract_with_warning(self):
        """Test that warning information is included when present"""
        # Mock output that would contain a warning
        mock_output = {
            "output_type": "stream", 
            "text": "UserWarning: This is a test warning"
        }
        
        result = safe_extract_outputs_with_images([mock_output])
        
        self.assertIn("text_outputs", result)
        self.assertIn("images", result)
        self.assertIn("warning", result)
        self.assertNotIn("error", result)
        
        self.assertEqual(result["warning"]["type"], "user_warning")
    
    def test_extract_normal_output(self):
        """Test that normal output doesn't include error/warning fields"""
        # Mock normal output
        mock_output = {
            "output_type": "stream",
            "text": "Hello, World!"
        }
        
        result = safe_extract_outputs_with_images([mock_output])
        
        self.assertIn("text_outputs", result)
        self.assertIn("images", result)
        self.assertNotIn("error", result)
        self.assertNotIn("warning", result)
    
    def test_extract_empty_outputs(self):
        """Test extraction from empty outputs"""
        result = safe_extract_outputs_with_images([])
        
        expected_keys = {"text_outputs", "images"}
        self.assertEqual(set(result.keys()), expected_keys)
        self.assertEqual(result["text_outputs"], [])
        self.assertEqual(result["images"], [])


class TestRegexPatterns(unittest.TestCase):
    """Test the robustness of regex patterns"""
    
    def test_error_patterns_coverage(self):
        """Test that all error patterns are reasonable"""
        # Test some common error formats
        test_errors = {
            "SyntaxError: invalid syntax": "syntax_error",
            "NameError: name 'x' is not defined": "name_error",
            "TypeError: 'int' object is not callable": "type_error",
            "ValueError: invalid literal": "value_error",
            "KeyError: 'missing'": "key_error",
            "IndexError: list index out of range": "index_error"
        }
        
        for error_text, expected_type in test_errors.items():
            result = detect_error_in_output(error_text)
            self.assertIsNotNone(result, f"Should detect {expected_type} in: {error_text}")
            self.assertEqual(result["type"], expected_type)
    
    def test_warning_patterns_coverage(self):
        """Test that all warning patterns are reasonable"""
        test_warnings = {
            "UserWarning: test message": "user_warning",
            "DeprecationWarning: deprecated": "deprecation_warning",
            "FutureWarning: future change": "future_warning",
            "RuntimeWarning: runtime issue": "runtime_warning"
        }
        
        for warning_text, expected_type in test_warnings.items():
            result = detect_warning_in_output(warning_text)
            self.assertIsNotNone(result, f"Should detect {expected_type} in: {warning_text}")
            self.assertEqual(result["type"], expected_type)
    
    def test_false_positive_prevention(self):
        """Test that patterns don't create false positives"""
        false_positive_texts = [
            "This string contains the word TypeError but isn't an error",
            "Error: This is just a message with Error at the start",
            "The function returned error code 404",
            "I'm warning you about something"
        ]
        
        for text in false_positive_texts:
            error_result = detect_error_in_output(text)
            warning_result = detect_warning_in_output(text)
            
            self.assertIsNone(error_result, f"Should not detect error in: {text}")
            self.assertIsNone(warning_result, f"Should not detect warning in: {text}")


if __name__ == "__main__":
    # Run all tests
    print("🧪 Running Unit Tests for Error/Warning Detection")
    print("=" * 60)
    
    # Create test suite
    test_loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestErrorDetection,
        TestWarningDetection, 
        TestExtractErrorWarningInfo,
        TestSafeExtractOutputsWithImages,
        TestRegexPatterns
    ]
    
    for test_class in test_classes:
        tests = test_loader.loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"📊 Test Summary:")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    
    if result.failures:
        print(f"\n❌ Failures:")
        for test, failure in result.failures:
            print(f"   • {test}: {failure}")
    
    if result.errors:
        print(f"\n🚨 Errors:")
        for test, error in result.errors:
            print(f"   • {test}: {error}")
    
    if result.wasSuccessful():
        print(f"\n🎉 All tests passed! Error/warning detection is working correctly.")
    else:
        print(f"\n⚠️  Some tests failed. Please review and fix issues.")
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1) 