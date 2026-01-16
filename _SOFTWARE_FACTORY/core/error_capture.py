#!/usr/bin/env python3
"""
Error Capture System - Feedback Loop to TDD Backlog
====================================================
Based on MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

Captures errors from:
1. Build/compilation (cargo, tsc, swift, kotlin, gradle)
2. E2E Playwright journeys (console.error, gRPC errors)
3. Mobile tests (iOS Simulator logs, Android Logcat)

Feeds errors back to Wiggum TDD backlog as new tasks.

Usage:
    from core.error_capture import ErrorCapture, ErrorType

    capture = ErrorCapture(project)
    errors = capture.parse_build_output(output)
    tasks = capture.errors_to_tasks(errors)
"""

import re
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


class ErrorType(str, Enum):
    """Types of errors that can be captured"""
    # Build errors
    RUST_COMPILE = "rust_compile"
    TYPESCRIPT_COMPILE = "typescript_compile"
    SWIFT_COMPILE = "swift_compile"
    KOTLIN_COMPILE = "kotlin_compile"
    PYTHON_SYNTAX = "python_syntax"

    # Runtime errors
    GRPC_ERROR = "grpc_error"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"

    # Test errors
    E2E_ASSERTION = "e2e_assertion"
    E2E_TIMEOUT = "e2e_timeout"
    E2E_SELECTOR = "e2e_selector"
    UNIT_TEST_FAIL = "unit_test_fail"

    # Mobile specific
    IOS_CRASH = "ios_crash"
    IOS_CONSTRAINT = "ios_constraint"
    ANDROID_CRASH = "android_crash"
    ANDROID_ANR = "android_anr"

    # Console errors
    CONSOLE_ERROR = "console_error"
    CONSOLE_WARN = "console_warn"
    UNHANDLED_REJECTION = "unhandled_rejection"


class ErrorSeverity(str, Enum):
    """Severity levels for prioritization"""
    CRITICAL = "critical"  # Crashes, security, data loss
    HIGH = "high"          # Blocking functionality
    MEDIUM = "medium"      # Degraded functionality
    LOW = "low"            # Warnings, minor issues


@dataclass
class CapturedError:
    """A captured error with context"""
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    column: Optional[int] = None
    code: Optional[str] = None  # Error code (E0001, TS2304, etc.)
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    source: str = ""  # Where the error came from (build, e2e, mobile)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def id(self) -> str:
        """Generate unique ID for deduplication"""
        unique_str = f"{self.error_type}:{self.file_path}:{self.line_number}:{self.message[:100]}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "error_type": self.error_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "column": self.column,
            "code": self.code,
            "stack_trace": self.stack_trace,
            "context": self.context,
            "source": self.source,
            "timestamp": self.timestamp,
        }


# ============================================================================
# ERROR PATTERNS
# ============================================================================

# Rust compiler errors
RUST_ERROR_PATTERNS = [
    # error[E0382]: borrow of moved value: `x`
    (r'error\[(?P<code>E\d+)\]: (?P<message>.+)\n\s*--> (?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+)',
     ErrorType.RUST_COMPILE, ErrorSeverity.HIGH),
    # warning: unused variable: `x`
    (r'warning: (?P<message>.+)\n\s*--> (?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+)',
     ErrorType.RUST_COMPILE, ErrorSeverity.LOW),
    # panicked at 'message', src/main.rs:10:5
    (r"panicked at '(?P<message>[^']+)', (?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+)",
     ErrorType.RUST_COMPILE, ErrorSeverity.CRITICAL),
]

# TypeScript compiler errors
TYPESCRIPT_ERROR_PATTERNS = [
    # src/index.ts(10,5): error TS2304: Cannot find name 'foo'.
    (r'(?P<file>[^(\s]+)\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>TS\d+): (?P<message>.+)',
     ErrorType.TYPESCRIPT_COMPILE, ErrorSeverity.HIGH),
    # src/index.ts:10:5 - error TS2304: Cannot find name 'foo'.
    (r'(?P<file>[^:\s]+):(?P<line>\d+):(?P<col>\d+) - error (?P<code>TS\d+): (?P<message>.+)',
     ErrorType.TYPESCRIPT_COMPILE, ErrorSeverity.HIGH),
]

# Swift compiler errors
SWIFT_ERROR_PATTERNS = [
    # /path/to/file.swift:10:5: error: cannot find 'foo' in scope
    (r'(?P<file>[^:\s]+\.swift):(?P<line>\d+):(?P<col>\d+): error: (?P<message>.+)',
     ErrorType.SWIFT_COMPILE, ErrorSeverity.HIGH),
    # /path/to/file.swift:10:5: warning: ...
    (r'(?P<file>[^:\s]+\.swift):(?P<line>\d+):(?P<col>\d+): warning: (?P<message>.+)',
     ErrorType.SWIFT_COMPILE, ErrorSeverity.LOW),
]

# Kotlin/Gradle errors
KOTLIN_ERROR_PATTERNS = [
    # e: file:///path/to/file.kt:10:5 Unresolved reference: foo
    (r'e: (?:file://)?(?P<file>[^:\s]+\.kt):(?P<line>\d+):(?P<col>\d+) (?P<message>.+)',
     ErrorType.KOTLIN_COMPILE, ErrorSeverity.HIGH),
    # w: file:///path/to/file.kt:10:5 ...
    (r'w: (?:file://)?(?P<file>[^:\s]+\.kt):(?P<line>\d+):(?P<col>\d+) (?P<message>.+)',
     ErrorType.KOTLIN_COMPILE, ErrorSeverity.LOW),
]

# Python errors
PYTHON_ERROR_PATTERNS = [
    # File "/path/to/file.py", line 10, in <module>
    (r'File "(?P<file>[^"]+)", line (?P<line>\d+).*\n.*\n(?P<message>\w+Error: .+)',
     ErrorType.PYTHON_SYNTAX, ErrorSeverity.HIGH),
    # SyntaxError: invalid syntax
    (r'(?P<file>[^:\s]+\.py):(?P<line>\d+):(?P<col>\d+): (?P<code>\w+): (?P<message>.+)',
     ErrorType.PYTHON_SYNTAX, ErrorSeverity.HIGH),
]

# gRPC errors
GRPC_ERROR_PATTERNS = [
    # gRPC Error (INVALID_ARGUMENT): message
    (r'gRPC Error \((?P<code>[A-Z_]+)\): (?P<message>.+)',
     ErrorType.GRPC_ERROR, ErrorSeverity.HIGH),
    # grpc-status: 3, grpc-message: message
    (r'grpc-status:\s*(?P<code>\d+).*grpc-message:\s*(?P<message>.+)',
     ErrorType.GRPC_ERROR, ErrorSeverity.HIGH),
    # Failed to fetch modules via gRPC
    (r'Failed to (?P<message>fetch .+ via gRPC.*)',
     ErrorType.GRPC_ERROR, ErrorSeverity.MEDIUM),
]

# Playwright E2E errors
PLAYWRIGHT_ERROR_PATTERNS = [
    # Error: expect(locator).toBeVisible()
    (r'Error: expect\((?P<context>locator|page)\)\.(?P<message>to\w+)\(\)',
     ErrorType.E2E_ASSERTION, ErrorSeverity.HIGH),
    # Timeout 30000ms exceeded
    (r'Timeout (?P<message>\d+ms exceeded.+)',
     ErrorType.E2E_TIMEOUT, ErrorSeverity.HIGH),
    # locator.click: Target closed
    (r'locator\.(?P<message>\w+: Target closed)',
     ErrorType.E2E_SELECTOR, ErrorSeverity.HIGH),
    # waiting for locator('[data-testid="..."]')
    (r"waiting for (?P<message>locator\(['\"][^'\"]+['\"]\).*)",
     ErrorType.E2E_SELECTOR, ErrorSeverity.MEDIUM),
]

# iOS specific errors
IOS_ERROR_PATTERNS = [
    # *** Terminating app due to uncaught exception
    (r'\*\*\* Terminating app due to uncaught exception.*(?P<message>.+)',
     ErrorType.IOS_CRASH, ErrorSeverity.CRITICAL),
    # Unable to simultaneously satisfy constraints
    (r'Unable to simultaneously satisfy constraints.*(?P<message>.+)',
     ErrorType.IOS_CONSTRAINT, ErrorSeverity.MEDIUM),
    # Fatal error: ...
    (r'Fatal error: (?P<message>.+)',
     ErrorType.IOS_CRASH, ErrorSeverity.CRITICAL),
]

# Android specific errors
ANDROID_ERROR_PATTERNS = [
    # FATAL EXCEPTION: main
    (r'FATAL EXCEPTION: (?P<context>\w+)\s*(?P<message>.+)',
     ErrorType.ANDROID_CRASH, ErrorSeverity.CRITICAL),
    # ANR in com.example.app
    (r'ANR in (?P<message>[\w.]+)',
     ErrorType.ANDROID_ANR, ErrorSeverity.CRITICAL),
    # java.lang.NullPointerException
    (r'(?P<code>java\.lang\.\w+Exception): (?P<message>.+)',
     ErrorType.ANDROID_CRASH, ErrorSeverity.HIGH),
]

# Console errors (browser)
CONSOLE_ERROR_PATTERNS = [
    # [error] message or console.error: message
    (r'(?:console\.error|ERROR|\[error\]):\s*(?P<message>.+)',
     ErrorType.CONSOLE_ERROR, ErrorSeverity.MEDIUM),
    # Unhandled Promise Rejection
    (r'Unhandled (?:Promise )?Rejection.*(?P<message>.+)',
     ErrorType.UNHANDLED_REJECTION, ErrorSeverity.HIGH),
    # [warn] or console.warn
    (r'(?:console\.warn|WARN|\[warn\]):\s*(?P<message>.+)',
     ErrorType.CONSOLE_WARN, ErrorSeverity.LOW),
]


# ============================================================================
# ERROR CAPTURE CLASS
# ============================================================================

class ErrorCapture:
    """
    Captures and parses errors from various sources.

    Supports:
    - Build output (cargo, tsc, swiftc, gradle)
    - E2E test output (Playwright, Detox)
    - Mobile logs (iOS Simulator, Android Logcat)
    - Console logs
    """

    def __init__(self, project_config: Any = None):
        self.project = project_config
        self.errors: List[CapturedError] = []
        self._seen_ids: set = set()

    def parse_output(self, output: str, source: str = "unknown") -> List[CapturedError]:
        """
        Parse any output for errors.

        Args:
            output: Raw output text
            source: Source identifier (build, e2e, mobile, etc.)

        Returns:
            List of captured errors
        """
        errors = []

        # Try all pattern groups
        pattern_groups = [
            (RUST_ERROR_PATTERNS, "rust"),
            (TYPESCRIPT_ERROR_PATTERNS, "typescript"),
            (SWIFT_ERROR_PATTERNS, "swift"),
            (KOTLIN_ERROR_PATTERNS, "kotlin"),
            (PYTHON_ERROR_PATTERNS, "python"),
            (GRPC_ERROR_PATTERNS, "grpc"),
            (PLAYWRIGHT_ERROR_PATTERNS, "playwright"),
            (IOS_ERROR_PATTERNS, "ios"),
            (ANDROID_ERROR_PATTERNS, "android"),
            (CONSOLE_ERROR_PATTERNS, "console"),
        ]

        for patterns, pattern_source in pattern_groups:
            for pattern, error_type, severity in patterns:
                for match in re.finditer(pattern, output, re.MULTILINE | re.IGNORECASE):
                    groups = match.groupdict()

                    error = CapturedError(
                        error_type=error_type,
                        severity=severity,
                        message=groups.get("message", match.group(0))[:500],
                        file_path=groups.get("file"),
                        line_number=int(groups["line"]) if groups.get("line") else None,
                        column=int(groups["col"]) if groups.get("col") else None,
                        code=groups.get("code"),
                        context={"pattern_source": pattern_source},
                        source=source,
                    )

                    # Deduplicate
                    if error.id not in self._seen_ids:
                        self._seen_ids.add(error.id)
                        errors.append(error)

        self.errors.extend(errors)
        return errors

    def parse_build_output(self, output: str, domain: str = "unknown") -> List[CapturedError]:
        """Parse build/compilation output"""
        return self.parse_output(output, source=f"build:{domain}")

    def parse_e2e_output(self, output: str, test_name: str = "") -> List[CapturedError]:
        """Parse E2E test output (Playwright, Detox)"""
        return self.parse_output(output, source=f"e2e:{test_name}")

    def parse_mobile_logs(self, logs: str, platform: str = "ios") -> List[CapturedError]:
        """Parse mobile device/simulator logs"""
        return self.parse_output(logs, source=f"mobile:{platform}")

    async def capture_ios_simulator_logs(
        self,
        bundle_id: str,
        duration_seconds: int = 10
    ) -> List[CapturedError]:
        """
        Capture iOS Simulator console logs for an app.

        Uses `xcrun simctl` to stream logs from the booted simulator.

        Args:
            bundle_id: App bundle ID (e.g., com.example.app)
            duration_seconds: How long to capture logs

        Returns:
            List of captured errors
        """
        import asyncio

        try:
            # Stream logs from booted simulator
            proc = await asyncio.create_subprocess_shell(
                f'xcrun simctl spawn booted log stream --predicate \'subsystem == "{bundle_id}"\' --level=error',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Collect output for specified duration
            await asyncio.sleep(duration_seconds)
            proc.terminate()

            stdout, stderr = await proc.communicate()
            logs = stdout.decode() + "\n" + stderr.decode()

            return self.parse_mobile_logs(logs, platform="ios")

        except Exception as e:
            print(f"[ErrorCapture] Failed to capture iOS logs: {e}")
            return []

    async def capture_android_logcat(
        self,
        package_name: str,
        duration_seconds: int = 10,
        device_id: str = None
    ) -> List[CapturedError]:
        """
        Capture Android Logcat errors for an app.

        Args:
            package_name: App package name (e.g., com.example.app)
            duration_seconds: How long to capture logs
            device_id: Optional specific device ID

        Returns:
            List of captured errors
        """
        import asyncio

        try:
            device_flag = f"-s {device_id}" if device_id else ""
            # Filter by package and error level
            cmd = f'adb {device_flag} logcat -v time --pid=$(adb shell pidof {package_name}) *:E'

            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Collect output for specified duration
            await asyncio.sleep(duration_seconds)
            proc.terminate()

            stdout, stderr = await proc.communicate()
            logs = stdout.decode() + "\n" + stderr.decode()

            return self.parse_mobile_logs(logs, platform="android")

        except Exception as e:
            print(f"[ErrorCapture] Failed to capture Android logs: {e}")
            return []

    def parse_detox_output(self, output: str, test_name: str = "") -> List[CapturedError]:
        """
        Parse Detox (React Native E2E) test output.

        Detox outputs include:
        - Jest test failures
        - Element not found errors
        - Timeout errors
        - Native crash logs
        """
        errors = []

        # Detox specific patterns
        detox_patterns = [
            # Element not found
            (r'Element not found.*identifier: [\'"](?P<message>[^\'"]+)[\'"]',
             ErrorType.E2E_SELECTOR, ErrorSeverity.HIGH),
            # Timeout
            (r'Test exceeded timeout of (?P<message>\d+ms)',
             ErrorType.E2E_TIMEOUT, ErrorSeverity.HIGH),
            # Assertion
            (r'Error: (?P<message>expect\(.+\)\.to\w+)',
             ErrorType.E2E_ASSERTION, ErrorSeverity.HIGH),
            # Native crash
            (r'Application.*crashed.*(?P<message>.+)',
             ErrorType.IOS_CRASH, ErrorSeverity.CRITICAL),
        ]

        for pattern, error_type, severity in detox_patterns:
            for match in re.finditer(pattern, output, re.MULTILINE | re.IGNORECASE):
                groups = match.groupdict()
                error = CapturedError(
                    error_type=error_type,
                    severity=severity,
                    message=groups.get("message", match.group(0))[:500],
                    context={"test_name": test_name, "framework": "detox"},
                    source=f"detox:{test_name}",
                )
                if error.id not in self._seen_ids:
                    self._seen_ids.add(error.id)
                    errors.append(error)

        # Also parse standard patterns
        errors.extend(self.parse_output(output, source=f"detox:{test_name}"))

        self.errors.extend(errors)
        return errors

    def parse_xcuitest_output(self, output: str, test_name: str = "") -> List[CapturedError]:
        """
        Parse XCUITest (iOS native E2E) test output.

        XCUITest outputs include:
        - Test failures with assertion info
        - Element query failures
        - App crashes
        """
        errors = []

        xcuitest_patterns = [
            # Test failed assertion
            (r'XCTAssert\w+ failed.*(?P<message>.+)',
             ErrorType.E2E_ASSERTION, ErrorSeverity.HIGH),
            # Element not found
            (r'No matches found for.*(?P<message>\w+\[[^\]]+\])',
             ErrorType.E2E_SELECTOR, ErrorSeverity.HIGH),
            # Timeout waiting for element
            (r'Timed out waiting for (?P<message>.+)',
             ErrorType.E2E_TIMEOUT, ErrorSeverity.HIGH),
            # Test failure
            (r't = \s*[\d.]+s\s*(?P<file>[^:]+):(?P<line>\d+): error: (?P<message>.+)',
             ErrorType.E2E_ASSERTION, ErrorSeverity.HIGH),
        ]

        for pattern, error_type, severity in xcuitest_patterns:
            for match in re.finditer(pattern, output, re.MULTILINE | re.IGNORECASE):
                groups = match.groupdict()
                error = CapturedError(
                    error_type=error_type,
                    severity=severity,
                    message=groups.get("message", match.group(0))[:500],
                    file_path=groups.get("file"),
                    line_number=int(groups["line"]) if groups.get("line") else None,
                    context={"test_name": test_name, "framework": "xcuitest"},
                    source=f"xcuitest:{test_name}",
                )
                if error.id not in self._seen_ids:
                    self._seen_ids.add(error.id)
                    errors.append(error)

        # Also parse standard patterns
        errors.extend(self.parse_output(output, source=f"xcuitest:{test_name}"))

        self.errors.extend(errors)
        return errors

    def parse_espresso_output(self, output: str, test_name: str = "") -> List[CapturedError]:
        """
        Parse Espresso (Android native E2E) test output.

        Espresso outputs include:
        - NoMatchingViewException
        - PerformException
        - Test assertion failures
        """
        errors = []

        espresso_patterns = [
            # No matching view
            (r'NoMatchingViewException.*(?P<message>View Matcher: .+)',
             ErrorType.E2E_SELECTOR, ErrorSeverity.HIGH),
            # Perform exception
            (r'PerformException.*(?P<message>.+)',
             ErrorType.E2E_ASSERTION, ErrorSeverity.HIGH),
            # Assertion failure
            (r'java\.lang\.AssertionError: (?P<message>.+)',
             ErrorType.E2E_ASSERTION, ErrorSeverity.HIGH),
            # Test failure with location
            (r'at (?P<file>[^(]+)\((?P<class>[^:]+):(?P<line>\d+)\)',
             ErrorType.E2E_ASSERTION, ErrorSeverity.HIGH),
        ]

        for pattern, error_type, severity in espresso_patterns:
            for match in re.finditer(pattern, output, re.MULTILINE | re.IGNORECASE):
                groups = match.groupdict()
                error = CapturedError(
                    error_type=error_type,
                    severity=severity,
                    message=groups.get("message", match.group(0))[:500],
                    file_path=groups.get("file") or groups.get("class"),
                    line_number=int(groups["line"]) if groups.get("line") else None,
                    context={"test_name": test_name, "framework": "espresso"},
                    source=f"espresso:{test_name}",
                )
                if error.id not in self._seen_ids:
                    self._seen_ids.add(error.id)
                    errors.append(error)

        # Also parse standard patterns
        errors.extend(self.parse_output(output, source=f"espresso:{test_name}"))

        self.errors.extend(errors)
        return errors

    def parse_playwright_json_report(self, report_path: Path) -> List[CapturedError]:
        """
        Parse Playwright JSON report for detailed error extraction.

        The JSON report contains structured data about:
        - Failed tests
        - Error messages
        - Stack traces
        - Attachments (screenshots, traces)
        """
        errors = []

        if not report_path.exists():
            return errors

        try:
            report = json.loads(report_path.read_text())

            for suite in report.get("suites", []):
                for spec in suite.get("specs", []):
                    for test in spec.get("tests", []):
                        for result in test.get("results", []):
                            if result.get("status") == "failed":
                                error_msg = ""
                                stack_trace = ""

                                # Extract error from attachments
                                for attachment in result.get("attachments", []):
                                    if attachment.get("name") == "error":
                                        error_msg = attachment.get("body", "")

                                # Or from error object
                                error_obj = result.get("error", {})
                                if error_obj:
                                    error_msg = error_obj.get("message", error_msg)
                                    stack_trace = error_obj.get("stack", "")

                                if error_msg:
                                    # Determine error type from message
                                    error_type = ErrorType.E2E_ASSERTION
                                    if "timeout" in error_msg.lower():
                                        error_type = ErrorType.E2E_TIMEOUT
                                    elif "locator" in error_msg.lower():
                                        error_type = ErrorType.E2E_SELECTOR
                                    elif "grpc" in error_msg.lower():
                                        error_type = ErrorType.GRPC_ERROR

                                    error = CapturedError(
                                        error_type=error_type,
                                        severity=ErrorSeverity.HIGH,
                                        message=error_msg[:500],
                                        file_path=spec.get("file"),
                                        line_number=spec.get("line"),
                                        stack_trace=stack_trace[:2000] if stack_trace else None,
                                        context={
                                            "test_title": test.get("title"),
                                            "suite": suite.get("title"),
                                            "duration": result.get("duration"),
                                            "retry": result.get("retry", 0),
                                        },
                                        source="playwright:json_report",
                                    )

                                    if error.id not in self._seen_ids:
                                        self._seen_ids.add(error.id)
                                        errors.append(error)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"[ErrorCapture] Failed to parse Playwright report: {e}")

        self.errors.extend(errors)
        return errors

    def errors_to_tasks(self, errors: List[CapturedError] = None) -> List[Dict[str, Any]]:
        """
        Convert captured errors to TDD task format.

        Returns list of task dicts ready for TaskStore.create_task()
        """
        if errors is None:
            errors = self.errors

        tasks = []

        for error in errors:
            # Determine domain from error type
            domain = self._error_type_to_domain(error.error_type)

            # Determine task type
            task_type = "fix"
            if error.severity == ErrorSeverity.CRITICAL:
                task_type = "hotfix"
            elif error.error_type in [ErrorType.E2E_ASSERTION, ErrorType.E2E_TIMEOUT]:
                task_type = "fix_e2e"

            # Build task description
            description = self._build_task_description(error)

            # WSJF scoring based on severity
            wsjf_score = {
                ErrorSeverity.CRITICAL: 10.0,
                ErrorSeverity.HIGH: 7.0,
                ErrorSeverity.MEDIUM: 4.0,
                ErrorSeverity.LOW: 2.0,
            }.get(error.severity, 5.0)

            task = {
                "type": task_type,
                "domain": domain,
                "description": description,
                "files": [error.file_path] if error.file_path else [],
                "severity": error.severity.value,
                "wsjf_score": wsjf_score,
                "context": {
                    "error_id": error.id,
                    "error_type": error.error_type.value,
                    "error_code": error.code,
                    "line_number": error.line_number,
                    "column": error.column,
                    "stack_trace": error.stack_trace,
                    "source": error.source,
                    "original_message": error.message,
                    "captured_at": error.timestamp,
                },
                "acceptance_criteria": [
                    f"Error '{error.code or error.error_type.value}' is resolved",
                    "Build/test passes without this error",
                    "No regression introduced",
                ],
            }

            tasks.append(task)

        return tasks

    def _error_type_to_domain(self, error_type: ErrorType) -> str:
        """Map error type to project domain"""
        mapping = {
            ErrorType.RUST_COMPILE: "rust",
            ErrorType.TYPESCRIPT_COMPILE: "typescript",
            ErrorType.SWIFT_COMPILE: "swift",
            ErrorType.KOTLIN_COMPILE: "kotlin",
            ErrorType.PYTHON_SYNTAX: "python",
            ErrorType.GRPC_ERROR: "backend",
            ErrorType.API_ERROR: "backend",
            ErrorType.E2E_ASSERTION: "e2e",
            ErrorType.E2E_TIMEOUT: "e2e",
            ErrorType.E2E_SELECTOR: "e2e",
            ErrorType.IOS_CRASH: "ios",
            ErrorType.IOS_CONSTRAINT: "ios",
            ErrorType.ANDROID_CRASH: "android",
            ErrorType.ANDROID_ANR: "android",
            ErrorType.CONSOLE_ERROR: "frontend",
            ErrorType.UNHANDLED_REJECTION: "frontend",
        }
        return mapping.get(error_type, "unknown")

    def _build_task_description(self, error: CapturedError) -> str:
        """Build human-readable task description"""
        parts = []

        # Error type prefix
        type_labels = {
            ErrorType.RUST_COMPILE: "Fix Rust compilation error",
            ErrorType.TYPESCRIPT_COMPILE: "Fix TypeScript compilation error",
            ErrorType.SWIFT_COMPILE: "Fix Swift compilation error",
            ErrorType.KOTLIN_COMPILE: "Fix Kotlin compilation error",
            ErrorType.PYTHON_SYNTAX: "Fix Python syntax error",
            ErrorType.GRPC_ERROR: "Fix gRPC error",
            ErrorType.E2E_ASSERTION: "Fix E2E test assertion failure",
            ErrorType.E2E_TIMEOUT: "Fix E2E test timeout",
            ErrorType.E2E_SELECTOR: "Fix E2E selector issue",
            ErrorType.IOS_CRASH: "Fix iOS crash",
            ErrorType.ANDROID_CRASH: "Fix Android crash",
            ErrorType.CONSOLE_ERROR: "Fix console error",
        }

        parts.append(type_labels.get(error.error_type, f"Fix {error.error_type.value}"))

        # Add error code if present
        if error.code:
            parts.append(f"[{error.code}]")

        # Add file location if present
        if error.file_path:
            location = error.file_path
            if error.line_number:
                location += f":{error.line_number}"
            parts.append(f"in {location}")

        # Add message summary (first line, truncated)
        msg_summary = error.message.split('\n')[0][:100]
        parts.append(f"- {msg_summary}")

        return " ".join(parts)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of captured errors"""
        by_type = {}
        by_severity = {}
        by_source = {}

        for error in self.errors:
            by_type[error.error_type.value] = by_type.get(error.error_type.value, 0) + 1
            by_severity[error.severity.value] = by_severity.get(error.severity.value, 0) + 1
            by_source[error.source] = by_source.get(error.source, 0) + 1

        return {
            "total": len(self.errors),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_source": by_source,
            "critical_count": by_severity.get("critical", 0),
            "high_count": by_severity.get("high", 0),
        }

    def clear(self):
        """Clear captured errors"""
        self.errors = []
        self._seen_ids = set()


# ============================================================================
# PLAYWRIGHT CONSOLE CAPTURE (for E2E tests)
# ============================================================================

def generate_playwright_console_capture_fixture() -> str:
    """
    Generate TypeScript fixture code for Playwright to capture console errors.

    This can be written to tests/fixtures/console-capture.ts
    """
    return '''
import { test as base, expect } from '@playwright/test';

export interface ConsoleCapture {
  errors: string[];
  warnings: string[];
  grpcErrors: string[];
  networkErrors: string[];
}

/**
 * Extended test fixture that captures all console output and fails on errors.
 *
 * Usage:
 *   import { test, expect } from './fixtures/console-capture';
 *
 *   test('my test', async ({ page, consoleCapture }) => {
 *     await page.goto('/');
 *     // Test will fail if any gRPC errors or console.error
 *   });
 */
export const test = base.extend<{ consoleCapture: ConsoleCapture }>({
  consoleCapture: async ({ page }, use) => {
    const capture: ConsoleCapture = {
      errors: [],
      warnings: [],
      grpcErrors: [],
      networkErrors: [],
    };

    // Capture console messages
    page.on('console', (msg) => {
      const text = msg.text();

      if (msg.type() === 'error') {
        capture.errors.push(text);

        // Detect gRPC errors
        if (text.includes('gRPC') ||
            text.includes('INVALID_ARGUMENT') ||
            text.includes('UNAVAILABLE') ||
            text.includes('UNAUTHENTICATED') ||
            text.includes('PERMISSION_DENIED')) {
          capture.grpcErrors.push(text);
        }
      } else if (msg.type() === 'warning') {
        capture.warnings.push(text);

        // Also check warnings for gRPC issues
        if (text.includes('gRPC') || text.includes('Failed to fetch')) {
          capture.grpcErrors.push(text);
        }
      }
    });

    // Capture page errors (uncaught exceptions)
    page.on('pageerror', (error) => {
      capture.errors.push(`PageError: ${error.message}`);
    });

    // Capture failed network requests
    page.on('requestfailed', (request) => {
      capture.networkErrors.push(`${request.method()} ${request.url()}: ${request.failure()?.errorText}`);
    });

    // Capture response errors
    page.on('response', (response) => {
      // Check for gRPC errors in headers
      const grpcStatus = response.headers()['grpc-status'];
      if (grpcStatus && grpcStatus !== '0') {
        const grpcMessage = response.headers()['grpc-message'] || 'Unknown';
        capture.grpcErrors.push(
          `gRPC ${grpcStatus}: ${decodeURIComponent(grpcMessage)} (${response.url()})`
        );
      }

      // Check for HTTP errors
      if (response.status() >= 400) {
        capture.networkErrors.push(
          `HTTP ${response.status()}: ${response.url()}`
        );
      }
    });

    await use(capture);

    // After test: fail if critical errors detected
    if (capture.grpcErrors.length > 0) {
      throw new Error(
        `gRPC errors detected during test:\\n${capture.grpcErrors.join('\\n')}`
      );
    }

    // Optionally fail on console.error (configurable)
    const failOnConsoleError = process.env.FAIL_ON_CONSOLE_ERROR === 'true';
    if (failOnConsoleError && capture.errors.length > 0) {
      throw new Error(
        `Console errors detected during test:\\n${capture.errors.join('\\n')}`
      );
    }
  },
});

export { expect };

/**
 * Helper to assert no gRPC errors occurred
 */
export function assertNoGrpcErrors(capture: ConsoleCapture) {
  if (capture.grpcErrors.length > 0) {
    throw new Error(
      `Expected no gRPC errors but found ${capture.grpcErrors.length}:\\n` +
      capture.grpcErrors.join('\\n')
    );
  }
}

/**
 * Helper to assert backend is healthy
 */
export async function assertBackendHealthy(capture: ConsoleCapture) {
  // Wait a bit for async errors to appear
  await new Promise(r => setTimeout(r, 100));
  assertNoGrpcErrors(capture);
}
'''


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Error Capture System")
    parser.add_argument("--test", action="store_true", help="Run test")
    parser.add_argument("--parse", type=str, help="Parse file for errors")
    parser.add_argument("--generate-fixture", action="store_true", help="Generate Playwright fixture")

    args = parser.parse_args()

    if args.generate_fixture:
        print(generate_playwright_console_capture_fixture())

    elif args.test:
        # Test with sample outputs
        capture = ErrorCapture()

        # Test Rust error
        rust_output = """
error[E0382]: borrow of moved value: `x`
 --> src/main.rs:10:5
  |
9 |     let y = x;
  |             - value moved here
10|     println!("{}", x);
  |                    ^ value borrowed here after move
"""
        errors = capture.parse_build_output(rust_output, "rust")
        print(f"Rust errors: {len(errors)}")
        for e in errors:
            print(f"  - {e.error_type.value}: {e.message[:50]}")

        # Test gRPC error
        grpc_output = """
[TenantStore] Failed to fetch modules via gRPC: Error: gRPC Error (INVALID_ARGUMENT): Invalid tenant_id: invalid length: expected length 32 for simple format, found 0
"""
        errors = capture.parse_e2e_output(grpc_output, "tenant-test")
        print(f"\ngRPC errors: {len(errors)}")
        for e in errors:
            print(f"  - {e.error_type.value}: {e.message[:50]}")

        # Test TypeScript error
        ts_output = """
src/components/App.tsx(15,10): error TS2304: Cannot find name 'useState'.
src/components/App.tsx(20,5): error TS2339: Property 'foo' does not exist on type 'Props'.
"""
        errors = capture.parse_build_output(ts_output, "typescript")
        print(f"\nTypeScript errors: {len(errors)}")
        for e in errors:
            print(f"  - {e.error_type.value}: {e.message[:50]}")

        # Convert to tasks
        tasks = capture.errors_to_tasks()
        print(f"\nGenerated {len(tasks)} tasks:")
        for t in tasks:
            print(f"  - [{t['domain']}] {t['description'][:60]}...")

        # Summary
        print(f"\nSummary: {json.dumps(capture.get_summary(), indent=2)}")

    elif args.parse:
        path = Path(args.parse)
        if path.exists():
            capture = ErrorCapture()
            content = path.read_text()
            errors = capture.parse_output(content, source=path.name)

            print(f"Found {len(errors)} errors in {path.name}:")
            for e in errors:
                print(f"\n[{e.severity.value.upper()}] {e.error_type.value}")
                print(f"  Message: {e.message[:100]}")
                if e.file_path:
                    print(f"  File: {e.file_path}:{e.line_number or '?'}")
                if e.code:
                    print(f"  Code: {e.code}")
