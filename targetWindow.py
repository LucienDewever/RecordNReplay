import ctypes
import time
import win32con
import win32gui
import win32api
import win32process


def list_windows():
    windows = []

    def _enum_handler(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title.strip():
            return
        # Skip windows with no actual size (tool windows, hidden helpers, etc.)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if right - left <= 0 or bottom - top <= 0:
            return
        windows.append((hwnd, title))

    win32gui.EnumWindows(_enum_handler, None)
    return windows


def pick_window():
    windows = list_windows()
    if not windows:
        print("No windows found.")
        return None

    print("\nSelect a target window:")
    for i, (hwnd, title) in enumerate(windows):
        print(f"  [{i}] {title}")

    while True:
        choice = input("Enter number (or blank to cancel): ").strip()
        if choice == "":
            return None
        if choice.isdigit() and 0 <= int(choice) < len(windows):
            return windows[int(choice)][0]
        print("Invalid selection, try again.")


def activate_window(hwnd, restore_if_minimized=True, settle_delay=0.05):
    if not win32gui.IsWindow(hwnd):
        raise ValueError(f"Invalid window handle: {hwnd}")

    if restore_if_minimized and win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    fg_hwnd = win32gui.GetForegroundWindow()
    target_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
    current_thread_id = win32api.GetCurrentThreadId()
    fg_thread_id = None
    if fg_hwnd:
        fg_thread_id, _ = win32process.GetWindowThreadProcessId(fg_hwnd)

    attached_self = False
    attached_fg = False
    try:
        if target_thread_id != current_thread_id:
            attached_self = ctypes.windll.user32.AttachThreadInput(
                current_thread_id, target_thread_id, True
            )
        if fg_thread_id and fg_thread_id != target_thread_id:
            attached_fg = ctypes.windll.user32.AttachThreadInput(
                fg_thread_id, target_thread_id, True
            )

        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
    finally:
        if attached_self:
            ctypes.windll.user32.AttachThreadInput(
                current_thread_id, target_thread_id, False
            )
        if attached_fg:
            ctypes.windll.user32.AttachThreadInput(
                fg_thread_id, target_thread_id, False
            )

    # Give the OS a moment to actually complete the switch before you
    # start sending input; skipping this causes flaky first keystrokes.
    time.sleep(settle_delay)

    return win32gui.GetForegroundWindow() == hwnd


def window_bounds(hwnd):
    """Return (left, top, right, bottom) screen coordinates of the window."""
    return win32gui.GetWindowRect(hwnd)


 
def engage_cursor_capture(hwnd, settle_delay=0.1):
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    cx = (left + right) // 2
    cy = (top + bottom) // 2
    screen_x, screen_y = win32gui.ClientToScreen(hwnd, (cx, cy))
 
    ctypes.windll.user32.SetCursorPos(screen_x, screen_y)
    time.sleep(0.02)
 
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.02)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
 
    time.sleep(settle_delay)

if __name__ == "__main__":
    hwnd = pick_window()
    if hwnd:
        title = win32gui.GetWindowText(hwnd)
        print(f"\nActivating: {title}")
        ok = activate_window(hwnd)
        print("Success." if ok else "Failed to bring window to foreground.")