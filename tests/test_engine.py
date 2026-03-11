"""
Test Engine Module - Core testing functionality

This module provides the core engine for running tests and validating
software functionality.
"""

import unittest
import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime


class TestResult:
    """Represents the result of a test execution."""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = False
        self.failed = False
        self.skipped = False
        self.error_message: Optional[str] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.duration: float = 0.0
    
    def mark_passed(self):
        """Mark test as passed."""
        self.passed = True
        self.failed = False
        self.skipped = False
    
    def mark_failed(self, error_message: str):
        """Mark test as failed with error message."""
        self.passed = False
        self.failed = True
        self.error_message = error_message
    
    def mark_skipped(self, reason: str = ""):
        """Mark test as skipped."""
        self.passed = False
        self.failed = False
        self.skipped = True
        self.error_message = reason
    
    def set_timing(self, start: datetime, end: datetime):
        """Set timing information for the test."""
        self.start_time = start
        self.end_time = end
        self.duration = (end - start).total_seconds()


class TestEngine:
    """
    Core test engine for executing and managing test suites.
    
    Provides functionality for:
    - Discovering tests
    - Executing tests with proper setup/teardown
    - Collecting and reporting results
    - Handling test fixtures and dependencies
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the test engine.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.test_results: List[TestResult] = []
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        self._discovered_tests: List[str] = []
    
    def discover_tests(self, test_path: str) -> List[str]:
        """
        Discover available tests in the given path.
        
        Args:
            test_path: Path to search for tests
            
        Returns:
            List of discovered test names
        """
        self._discovered_tests = []
        
        # Recursively find test files
        if os.path.isfile(test_path):
            if test_path.endswith('_test.py') or test_path.endswith('.py'):
                self._discovered_tests.append(test_path)
        elif os.path.isdir(test_path):
            for root, dirs, files in os.walk(test_path):
                for file in files:
                    if file.startswith('test_') and file.endswith('.py'):
                        full_path = os.path.join(root, file)
                        self._discovered_tests.append(full_path)
        
        return self._discovered_tests
    
    def run_test(self, test_name: str, test_func: callable) -> TestResult:
        """
        Run a single test function.
        
        Args:
            test_name: Name of the test
            test_func: The test function to execute
            
        Returns:
            TestResult object containing test execution details
        """
        result = TestResult(test_name)
        start_time = datetime.now()
        
        try:
            # Execute the test function
            test_func()
            result.mark_passed()
        except unittest.SkipTest as e:
            result.mark_skipped(str(e))
        except AssertionError as e:
            result.mark_failed(str(e))
        except Exception as e:
            result.mark_failed(f"Unexpected error: {type(e).__name__}: {str(e)}")
        
        end_time = datetime.now()
        result.set_timing(start_time, end_time)
        
        return result
    
    def run_suite(self, test_functions: List[tuple]) -> List[TestResult]:
        """
        Run a suite of tests.
        
        Args:
            test_functions: List of (test_name, test_func) tuples
            
        Returns:
            List of TestResult objects
        """
        self.test_results = []
        
        for test_name, test_func in test_functions:
            result = self.run_test(test_name, test_func)
            self.test_results.append(result)
            
            # Update counters
            self.total_tests += 1
            if result.passed:
                self.passed_tests += 1
            elif result.failed:
                self.failed_tests += 1
            elif result.skipped:
                self.skipped_tests += 1
        
        return self.test_results
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of test execution results.
        
        Returns:
            Dictionary containing summary statistics
        """
        return {
            'total': self.total_tests,
            'passed': self.passed_tests,
            'failed': self.failed_tests,
            'skipped': self.skipped_tests,
            'success_rate': (self.passed_tests / self.total_tests * 100) 
                           if self.total_tests > 0 else 0,
            'results': self.test_results
        }
    
    def generate_report(self, output_format: str = 'text') -> str:
        """
        Generate a test report in the specified format.
        
        Args:
            output_format: Format for the report ('text', 'json', 'html')
            
        Returns:
            Formatted report string
        """
        summary = self.get_summary()
        
        if output_format == 'json':
            import json
            return json.dumps(summary, indent=2, default=str)
        
        elif output_format == 'html':
            return self._generate_html_report(summary)
        
        else:
            return self._generate_text_report(summary)
    
    def _generate_text_report(self, summary: Dict[str, Any]) -> str:
        """Generate a plain text report."""
        lines = [
            "=" * 60,
            "TEST EXECUTION REPORT",
            "=" * 60,
            f"Total Tests:  {summary['total']}",
            f"Passed:       {summary['passed']}",
            f"Failed:       {summary['failed']}",
            f"Skipped:      {summary['skipped']}",
            f"Success Rate: {summary['success_rate']:.2f}%",
            "-" * 60,
            "DETAILED RESULTS:",
            "-" * 60
        ]
        
        for result in summary['results']:
            status = "✓ PASS" if result.passed else ("✗ FAIL" if result.failed else "⊘ SKIP")
            lines.append(f"{status} - {result.test_name} ({result.duration:.3f}s)")
            if result.error_message:
                lines.append(f"  → {result.error_message}")
        
        return "\n".join(lines)
    
    def _generate_html_report(self, summary: Dict[str, Any]) -> str:
        """Generate an HTML report."""
        html = [
            "<html><head><title>Test Report</title></head><body>",
            "<h1>Test Execution Report</h1>",
            f"<p>Total: {summary['total']} | ",
            f"Passed: <span style='color:green'>{summary['passed']}</span> | ",
            f"Failed: <span style='color:red'>{summary['failed']}</span> | ",
            f"Skipped: {summary['skipped']}</p>",
            "<table border='1'>",
            "<tr><th>Test</th><th>Status</th><th>Duration</th><th>Message</th></tr>"
        ]
        
        for result in summary['results']:
            status = "PASS" if result.passed else ("FAIL" if result.failed else "SKIP")
            color = "green" if result.passed else ("red" if result.failed else "orange")
            html.append(
                f"<tr><td>{result.test_name}</td>"
                f"<td style='color:{color}'>{status}</td>"
                f"<td>{result.duration:.3f}s</td>"
                f"<td>{result.error_message or ''}</td></tr>"
            )
        
        html.extend(["</table></body></html>"])
        return "\n".join(html)


class TestRunner:
    """
    High-level test runner that orchestrates test discovery and execution.
    """
    
    def __init__(self, engine: TestEngine):
        self.engine = engine
    
    def run_from_path(self, path: str) -> Dict[str, Any]:
        """
        Discover and run all tests in the given path.
        
        Args:
            path: Path to test files
            
        Returns:
            Summary dictionary of test results
        """
        # Discover tests
        discovered = self.engine.discover_tests(path)
        
        # Import and collect test functions
        test_functions = []
        for test_file in discovered:
            try:
                module_name = os.path.basename(test_file)[:-3]
                # Add to path for import
                sys.path.insert(0, os.path.dirname(test_file))
                module = __import__(module_name)
                
                # Find test functions
                for attr_name in dir(module):
                    if attr_name.startswith('test_'):
                        attr = getattr(module, attr_name)
                        if callable(attr):
                            test_functions.append((attr_name, attr))
            except Exception as e:
                print(f"Warning: Could not load {test_file}: {e}")
        
        # Run tests
        self.engine.run_suite(test_functions)
        
        return self.engine.get_summary()


# Example usage and basic tests
if __name__ == '__main__':
    # Create engine and run a simple test
    engine = TestEngine()
    
    def sample_test():
        """Sample test function for demonstration."""
        assert 1 + 1 == 2, "Basic math should work"
    
    def failing_test():
        """Sample failing test."""
        assert 1 == 2, "This should fail"
    
    results = engine.run_suite([
        ('sample_test', sample_test),
        ('failing_test', failing_test)
    ])
    
    print(engine.generate_report('text'))
