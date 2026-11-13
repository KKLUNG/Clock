"""設定檔讀寫：config.json 等資料檔都放在程式旁邊。"""

import json
import sys
from datetime import date
from pathlib import Path

from themes import THEMES

# 打包成 exe 後 __file__ 會指向暫存資料夾，改以 exe 所在位置為準
APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CONFIG_PATH = APP_DIR / "config.json"
DEFAULTS = {"start_time": "09:00", "end_time": "18:00", "lunch_start": "12:00", "lunch_end": "13:00",
            "overtime_end": "20:00", "overtime_date": None, "theme": "colorful",
            "fireworks": True, "show_quotes": True, "quote_seconds": 30, "zoom": 1.0, "x": None, "y": None}
TIME_KEYS = ("start_time", "end_time", "lunch_start", "lunch_end")
QUOTE_SECONDS = (10, 30, 60, 120)
ZOOM_MIN, ZOOM_MAX = 0.6, 2.0


def parse_hhmm(text):
    h, m = map(int, text.split(":"))
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(text)
    return h, m


def at_today(now, hhmm):
    h, m = parse_hhmm(hhmm)
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


def overtime_active(now, config):
    """只有勾選的日期是今天、而且是平日才算加班，隔天自動失效。"""
    return now.weekday() < 5 and config["overtime_date"] == now.date().isoformat()


def effective_end(now, config):
    """今天真正下班的時間：有加班就是加班結束時間。"""
    end = at_today(now, config["end_time"])
    if overtime_active(now, config):
        return max(end, at_today(now, config["overtime_end"]))
    return end


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path, data):
    """寫入失敗（例如沒有寫入權限）時回傳 False，不讓程式崩潰。"""
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def load_config():
    config = dict(DEFAULTS)
    data = read_json(CONFIG_PATH, {})
    if isinstance(data, dict):
        config.update(data)
    # 格式錯誤時退回預設值，不讓程式崩潰
    for key in (*TIME_KEYS, "overtime_end"):
        try:
            parse_hhmm(str(config[key]))
        except (ValueError, AttributeError):
            config[key] = DEFAULTS[key]
    try:
        date.fromisoformat(config["overtime_date"])
    except (TypeError, ValueError):
        config["overtime_date"] = None
    if config["theme"] not in THEMES:
        config["theme"] = DEFAULTS["theme"]
    for key in ("fireworks", "show_quotes"):
        if not isinstance(config[key], bool):
            config[key] = DEFAULTS[key]
    if not isinstance(config["quote_seconds"], int) or config["quote_seconds"] < 1:
        config["quote_seconds"] = DEFAULTS["quote_seconds"]
    zoom = config["zoom"]
    valid_zoom = isinstance(zoom, (int, float)) and not isinstance(zoom, bool) and ZOOM_MIN <= zoom <= ZOOM_MAX
    config["zoom"] = float(zoom) if valid_zoom else DEFAULTS["zoom"]
    config.pop("quote_interval", None)  # 舊版泡泡用的「每幾分鐘」，已改成 quote_seconds
    return config


def save_config(updates):
    # 重新讀檔再寫回，只改動指定的欄位
    config = load_config()
    config.update(updates)
    return write_json(CONFIG_PATH, config)


def save_position(x, y):
    save_config({"x": x, "y": y})
