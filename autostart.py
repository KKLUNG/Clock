"""開機自動執行：寫入目前使用者的 Run 登錄機碼，不需要系統管理員權限。"""

import os
import sys
import winreg
from pathlib import Path

from appconfig import APP_DIR

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "OffWorkClock"
# 舊版 install_startup.ps1 建立的捷徑
LEGACY_SHORTCUT = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup\OffWorkClock.lnk"


def command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{APP_DIR / "clock.py"}"'


def is_enabled():
    if LEGACY_SHORTCUT.exists():
        return True
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
        return True
    except OSError:
        return False


def set_enabled(enabled):
    """失敗時丟出 OSError，由呼叫端提示使用者。"""
    LEGACY_SHORTCUT.unlink(missing_ok=True)  # 統一改用登錄機碼，避免重複啟動
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
