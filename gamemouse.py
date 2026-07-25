import ctypes
import ctypes.wintypes as wintypes
import threading

user32 = ctypes.windll.user32

# --- Raw Input constants ---
RIDEV_INPUTSINK = 0x00000100
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
WM_INPUT = 0x00FF
WM_DESTROY = 0x0002

HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_GENERIC_MOUSE = 0x02


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("usButtonFlags", wintypes.USHORT),
        ("usButtonData", wintypes.USHORT),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG),
    ]


class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("mouse", RAWMOUSE),
    ]


WNDPROCTYPE = ctypes.WINFUNCTYPE(
    ctypes.c_long, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM
)


class RawMouseRecorder:

    # Runs a hidden message-only window in the background, registers it for mouse input,
    # and reports relative motion deltas as they arrive.


    def __init__(self, on_delta):
        self.on_delta = on_delta
        self._thread = None
        self._hwnd = None
        self._running = False
        self._wndproc_ref = WNDPROCTYPE(self._wndproc)  # keep alive

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_DESTROY, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)

    # --- internals ---

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            self._handle_raw_input(lparam)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _handle_raw_input(self, lparam):
        size = wintypes.UINT(0)
        user32.GetRawInputData(
            lparam, RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER)
        )
        if size.value == 0:
            return

        buf = ctypes.create_string_buffer(size.value)
        got = user32.GetRawInputData(
            lparam, RID_INPUT, buf, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER)
        )
        if got != size.value:
            return

        raw = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents
        if raw.header.dwType == RIM_TYPEMOUSE:
            dx, dy = raw.mouse.lLastX, raw.mouse.lLastY
            if dx != 0 or dy != 0:
                self.on_delta(dx, dy)

    def _run(self):
        WNDCLASS = wintypes.WNDCLASS if hasattr(wintypes, "WNDCLASS") else None
        import win32gui  # pywin32, reuse its helpers for class registration

        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wndproc_ref
        wc.lpszClassName = "RawMouseRecorderWindow"
        wc.hInstance = win32gui.GetModuleHandle(None)
        class_atom = win32gui.RegisterClass(wc)

        self._hwnd = win32gui.CreateWindow(
            class_atom, "RawMouseRecorder", 0, 0, 0, 0, 0, 0, 0,
            wc.hInstance, None,
        )

        rid = RAWINPUTDEVICE(
            usUsagePage=HID_USAGE_PAGE_GENERIC,
            usUsage=HID_USAGE_GENERIC_MOUSE,
            dwFlags=RIDEV_INPUTSINK,
            hwndTarget=self._hwnd,
        )
        if not user32.RegisterRawInputDevices(
            ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)
        ):
            raise ctypes.WinError()

        # Standard Win32 message pump for this thread's window.
        msg = wintypes.MSG()
        while self._running:
            bRet = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if bRet == 0 or bRet == -1:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == "__main__":
    import time

    def _print_delta(dx, dy):
        print(f"dx={dx:+5d}  dy={dy:+5d}")

    rec = RawMouseRecorder(on_delta=_print_delta)
    rec.start()
    print("Move the mouse. Recording raw deltas for 5 seconds...")
    time.sleep(5)
    rec.stop()