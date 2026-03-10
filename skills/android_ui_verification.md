---
name: android_ui_verification
version: 1.0.0
description: Automated end-to-end UI testing and verification on an Android Emulator
  using ADB.
metadata:
  category: design
  source: 'antigravity-awesome-skills (MIT) — source: community'
  triggers:
  - autonomous debugging of layout issues or interaction bugs
eval_cases:
- id: android_ui_verification-approach
  prompt: How should I approach android_ui_verification for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on android_ui_verification
  tags:
  - android_ui_verification
- id: android_ui_verification-best-practices
  prompt: What are the key best practices and pitfalls for android_ui_verification?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for android_ui_verification
  tags:
  - android_ui_verification
  - best-practices
- id: android_ui_verification-antipatterns
  prompt: What are the most common mistakes to avoid with android_ui_verification?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - android_ui_verification
  - antipatterns
---
# android_ui_verification

# Android UI Verification Skill

This skill provides a systematic approach to testing React Native applications on an Android emulator using ADB commands. It allows for autonomous interaction, state verification, and visual regression checking.

## When to Use
- Verifying UI changes in React Native or Native Android apps.
- Autonomous debugging of layout issues or interaction bugs.
- Ensuring feature functionality when manual testing is too slow.
- Capturing automated screenshots for PR documentation.

## 🛠 Prerequisites
- Android Emulator running.
- `adb` installed and in PATH.
- Application in debug mode for logcat access.

## 🚀 Workflow

### 1. Device Calibration
Before interacting, always verify the screen resolution to ensure tap coordinates are accurate.
```bash
adb shell wm size
```
*Note: Layouts are often scaled. Use the physical size returned as the base for coordinate calculations.*

### 2. UI Inspection (State Discovery)
Use the `uiautomator` dump to find the exact bounds of UI elements (buttons, inputs).
```bash
adb shell uiautomator dump /sdcard/view.xml && adb pull /sdcard/view.xml ./artifacts/view.xml
```
Search the `view.xml` for `text`, `content-desc`, or `resource-id`. The `bounds` attribute `[x1,y1][x2,y2]` defines the clickable area.

### 3. Interaction Commands
- **Tap**: `adb shell input tap <x> <y>` (Use the center of the element bounds).
- **Swipe**: `adb shell input swipe <x1> <y1> <x2> <y2> <duration_ms>` (Used for scrolling).
- **Text Input**: `adb shell input text "<message>"` (Note: Limited support for special characters).
- **Key Events**: `adb shell input keyevent <code_id>` (e.g., 66 for Enter).

### 4. Verification & Reporting
#### Visual Verification
Capture a screenshot after interaction to confirm UI changes.
```bash
adb shell screencap -p /sdcard/screen.png && adb pull /sdcard/screen.png ./artifacts/test_result.png
```

#### Analytical Verification
Monitor the JS console logs in real-time to detect errors or log successes.
```bash
adb logcat -d | grep "ReactNativeJS" | tail -n 20
```

#### Cleanup
Always store generated files in the `artifacts/` folder to satisfy project organization rules.

## 💡 Best Practices
- **Wait for Animations**: Always add a short sleep (e.g., 1-2s) between interaction and verification.
- **Center Taps**: Calculate the arithmetic mean of `[x1,y1][x2,y2]` for the most reliable tap target.
- **Log Markers**: Use distinct log messages in the code (e.g., `✅ Action Successful`) to make `grep` verification easy.
- **Fail Fast**: If a `uiautomator dump` fails or doesn't find the expected text, stop and troubleshoot rather than blind-tapping.
