"""Windows helpers for tools/make_howto.py: find windows, simulate the mouse and the keyboard (real pixels)."""
import ctypes, time
from ctypes import wintypes

u = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # real pixels: 1920x1080 on the primary screen, whatever the scaling
except Exception:
    u.SetProcessDPIAware()

KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x2, 0x4
VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "enter": 0x0D, "esc": 0x1B, "tab": 0x09}


def windows(match=None):
    """[(hwnd, title, class, (l, t, r, b))] of visible windows; `match(title, cls)` filters."""
    out = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(h, _):
        if u.IsWindowVisible(h):
            t, c = ctypes.create_unicode_buffer(300), ctypes.create_unicode_buffer(100)
            u.GetWindowTextW(h, t, 300)
            u.GetClassNameW(h, c, 100)
            r = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            if match is None or match(t.value, c.value):
                out.append((h, t.value, c.value, (r.left, r.top, r.right, r.bottom)))
        return True

    u.EnumWindows(each, 0)
    return out


def find(title_part=None, cls=None, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        w = windows(lambda t, c: (title_part is None or title_part in t) and (cls is None or c == cls))
        w = [x for x in w if (x[3][2] - x[3][0]) > 20]
        if w:
            return w[0]
        time.sleep(0.3)
    return None


def move(x, y, steps=18, dur=0.5):
    p = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(p))
    for i in range(1, steps + 1):   # a visible, smooth move
        u.SetCursorPos(int(p.x + (x - p.x) * i / steps), int(p.y + (y - p.y) * i / steps))
        time.sleep(dur / steps)


def click(x, y):
    move(x, y)
    time.sleep(0.15)
    u.mouse_event(0x2, 0, 0, 0, 0)
    time.sleep(0.06)
    u.mouse_event(0x4, 0, 0, 0, 0)


def combo(*keys):
    codes = [VK.get(k) or ord(k.upper()) for k in keys]
    for c in codes:
        u.keybd_event(c, 0, 0, 0)
        time.sleep(0.03)
    time.sleep(0.08)
    for c in reversed(codes):
        u.keybd_event(c, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.03)


class KI(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class INP(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KI), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def type_text(text, delay=0.06):
    for ch in text:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            i = INP(type=1)
            i.ki = KI(0, ord(ch), flags, 0, 0)
            u.SendInput(1, ctypes.byref(i), ctypes.sizeof(INP))
        time.sleep(delay)


SHELL_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW", "NotifyIconOverflowWindow",
                 "TopLevelWindowForOverflowXamlIsland", "XamlExplorerHostIslandWindow", "Windows.UI.Core.CoreWindow",
                 "HevantiMiniButton", "HevantiMiniToast"}


def foreign(allowed=("הבנתי", "פתרון משוואה", "YouTube", "about:blank", "127.0.0.1"), area=(0, 0, 1920, 1080)):
    """Titles of other windows that touch the recorded screen. It only looks: no window of the student is ever moved or minimized."""
    hit = []
    for h, t, c, (l, tp, r, b) in windows():
        if c in SHELL_CLASSES or not t.strip() or u.IsIconic(h):
            continue
        if r - l < 160 or b - tp < 100 or r <= area[0] or l >= area[2] or b <= area[1] or tp >= area[3]:
            continue
        if any(a in t for a in allowed):
            continue
        hit.append(t)
    return hit
