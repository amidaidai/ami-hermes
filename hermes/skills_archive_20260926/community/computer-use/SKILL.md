---
name: computer-use
category: community
description: Drive desktop in background without stealing focus.
---

# Computer Use — Drive Desktop in Background

Control the desktop environment programmatically without stealing focus from the user. Useful for automated testing, demonstrations, and background tasks.

## When to use

- You need to automate mouse/keyboard actions without interrupting the user
- You're running automated tests that interact with GUI applications
- You want to take screenshots or record screen content in the background
- You need to simulate user input for demos or testing

## Requirements

- Python with `pyautogui`, `pynput`, or similar
- On Windows: consider `pywin32` for window management
- On macOS: `osascript` for AppleScript control
- On Linux: `xdotool`, `wmctrl`, `Xlib`

## Approach

### Headless / Background Automation

Where possible, use application APIs instead of GUI automation:

```python
# Instead of clicking a button, use the API
# Instead of typing into a field, write the file directly
# Instead of reading the screen, query the database
```

### Focus-Safe Automation (Windows)

```python
import win32gui
import win32con
import time

def run_in_background(window_title, action_func):
    """Run an action on a window without stealing focus."""
    # Find the window
    hwnd = win32gui.FindWindow(None, window_title)
    if not hwnd:
        print(f"Window '{window_title}' not found")
        return
    
    # Save current foreground window
    current = win32gui.GetForegroundWindow()
    
    # Send messages directly (no focus switch)
    action_func(hwnd)
    
    # Restore focus
    win32gui.SetForegroundWindow(current)

def send_keys_no_focus(hwnd, text):
    """Send keystrokes to a window without activating it."""
    for char in text:
        win32gui.PostMessage(hwnd, win32con.WM_CHAR, ord(char), 0)
        time.sleep(0.01)
```

### Focus-Safe Automation (macOS)

```bash
# Use AppleScript without activating the app
osascript -e '
tell application "System Events"
    tell process "Safari"
        set frontmost to false
        keystroke "hello"
    end tell
end tell'
```

### Focus-Safe Automation (Linux)

```bash
# Use xdotool with --window parameter (doesn't steal focus)
xdotool type --window $(xdotool search --name "Terminal") "command"
xdotool key --window $(xdotool search --name "Terminal") Return
```

### Screenshots Without Focus

```python
import pyautogui

# Take screenshot — does not affect window focus
screenshot = pyautogui.screenshot()
screenshot.save("desktop.png")
```

## Best Practices

1. **Always prefer API automation over GUI automation** — faster, more reliable, focus-safe
2. **Save and restore focus** — before any action, record the active window; restore it after
3. **Add delays** — background input can be lost if the target application is busy
4. **Test with focus** first, then remove the focus-stealing requirement
5. **Use virtual displays** for truly headless automation (Xvfb on Linux, headless mode on macOS)

## Pitfalls

- Windows `PostMessage` may not work with all applications (some require `SendMessage`)
- Background keystrokes can be intercepted by security software
- Some applications require focus to process input correctly
- Screenshots capture what's visible — overlapping windows will occlude the target
- macOS security permissions (Accessibility) must be granted for any input automation

## Verification

Run a test that types text into a notepad/textedit window in the background, then verify the text appears without the window ever coming to the foreground.
