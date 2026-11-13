"""多螢幕：查詢螢幕範圍。座標都是實體像素，和 Tk 視窗座標一致。"""

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32")  # 獨立的實例，設定 argtypes 不影響其他模組
MONITOR_DEFAULTTONULL = 0
MONITOR_DEFAULTTONEAREST = 2


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


MonitorEnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                     ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.c_void_p, MonitorEnumProc, wintypes.LPARAM]


def rect_tuple(r):
    return r.left, r.top, r.right, r.bottom


def work_area_at(x, y):
    """(x, y) 所在螢幕的工作區（扣掉工作列），回傳 (left, top, right, bottom)；不在任何螢幕上就用最近的螢幕。"""
    info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    user32.GetMonitorInfoW(user32.MonitorFromPoint(wintypes.POINT(x, y), MONITOR_DEFAULTTONEAREST), ctypes.byref(info))
    return rect_tuple(info.rcWork)


def is_on_screen(x, y):
    return bool(user32.MonitorFromPoint(wintypes.POINT(x, y), MONITOR_DEFAULTTONULL))


def all_monitors():
    """每個螢幕的完整範圍 (left, top, right, bottom)。"""
    rects = []

    def callback(hmon, hdc, rect, lparam):
        rects.append(rect_tuple(rect.contents))
        return True

    user32.EnumDisplayMonitors(None, None, MonitorEnumProc(callback), 0)
    return rects
