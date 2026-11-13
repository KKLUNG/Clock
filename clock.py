"""下班倒數計時時鐘：無邊框、置頂、可拖曳的桌面小工具。"""

import colorsys
import ctypes
import math
import sys
import time
import tkinter as tk
from collections import namedtuple
from datetime import datetime, timedelta

from appconfig import at_today, load_config, save_position
from bubble import SpeechBubble, round_rect_points
from fireworks import launch_fireworks
from monitors import is_on_screen
from quotes import QuotePicker, load_quotes, period_by_time, period_of, record_play
from settings import SettingsWindow

# 以下尺寸是 100% 縮放時的像素，實際會依螢幕 DPI 放大
WIDTH, HEIGHT, RADIUS = 280, 130, 16
KEY = "#010203"  # 透明色，用來挖出圓角
WHITE = "#ffffff"
PALETTES = {
    "morning": ("#3a7bd5", "#00d2ff"),
    "afternoon": ("#f7971e", "#ffd200"),
    "lasthour": ("#ff0080", "#7928ca"),
    "weekend": ("#11998e", "#38ef7d"),
}
GLOW_COLORS = ("#ffffff", "#ff66c4")
UI_FONT = "Microsoft JhengHei UI"
DIGIT_FONT = "Consolas"
POP_MAX, POP_MIN = 52, 36  # 最後 10 秒數字放大縮回的字級
ANIM_MS = 40
RAINBOW_SECONDS = 60
FIREWORKS_GRACE = timedelta(seconds=60)
FIRST_QUOTE_DELAY = 5  # 秒

State = namedtuple("State", "mode remaining progress lunch_text palette")


def fmt(delta):
    total = int(delta.total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_state(now, config):
    if now.weekday() >= 5:
        return State("weekend", None, 0.0, "", "weekend")
    end = at_today(now, config["end_time"])
    if now >= end:
        return State("off", None, 1.0, "", "off")
    start = at_today(now, config["start_time"])
    remaining = end - now
    total = (end - start).total_seconds()
    progress = min(max((now - start).total_seconds() / total, 0.0), 1.0) if total > 0 else 0.0

    lunch_start = at_today(now, config["lunch_start"])
    lunch_end = at_today(now, config["lunch_end"])
    if now < lunch_start:
        lunch_text = f"午休倒數 {fmt(lunch_start - now)}"
    elif now < lunch_end:
        lunch_text = "午休中"
    else:
        lunch_text = ""

    if remaining <= timedelta(hours=1):
        palette = "lasthour"
    elif now < lunch_end:
        palette = "morning"
    else:
        palette = "afternoon"
    mode = "final10" if remaining <= timedelta(seconds=10) else "working"
    return State(mode, remaining, progress, lunch_text, palette)


def demo_offset(config):
    """讓虛擬時間落在最近一個平日的下班前 15 秒。"""
    real = datetime.now().replace(microsecond=0)
    day = real
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return at_today(day, config["end_time"]) - timedelta(seconds=15) - real


def hex_to_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def mix(c1, c2, t):
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return rgb_to_hex(x + (y - x) * t for x, y in zip(a, b))


def shade(color, factor):
    return rgb_to_hex(v * factor for v in hex_to_rgb(color))


class ClockApp:
    def __init__(self, demo=False):
        self.config = load_config()
        self.demo = demo
        self.offset = demo_offset(self.config) if demo else timedelta(0)

        self.root = tk.Tk()
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.w, self.h = self.px(WIDTH), self.px(HEIGHT)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", KEY)
        self.root.configure(bg=KEY)
        self.canvas = tk.Canvas(self.root, width=self.w, height=self.h, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.build_items()

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="來一句", command=self.quote_now)
        self.menu.add_command(label="放煙火", command=lambda: launch_fireworks(self.root))
        self.menu.add_command(label="設定…", command=self.open_settings)
        self.menu.add_command(label="重設位置", command=self.reset_position)
        self.menu.add_separator()
        self.menu.add_command(label="結束", command=self.root.destroy)

        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<Button-3>", self.show_menu)

        self.state = None
        self.palette = None
        self.big_font = None
        self.shown_seconds = None
        self.pop_start = 0.0
        self.rainbow_until = 0.0
        self.animating = False

        self.picker = QuotePicker(load_quotes())
        self.bubble = None
        self.settings = None
        self.last_period = None
        self.next_quote_at = time.monotonic() + FIRST_QUOTE_DELAY

        self.tick()
        self.place_window()

    def px(self, value):
        return round(value * self.scale)

    def now(self):
        return datetime.now().replace(microsecond=0) + self.offset

    # ---- 畫面元件 ----

    def build_items(self):
        c, w, h, r = self.canvas, self.w, self.h, self.px(RADIUS)
        # 每個像素欄一條垂直線組成漸層，依圓角半徑算出上下內縮量
        self.columns = []
        for x in range(w):
            cx = x + 0.5
            d = max(r - cx, cx - (w - r), 0)
            inset = r - math.sqrt(max(r * r - d * d, 0)) if d else 0
            self.columns.append(c.create_line(x, inset, x, h - inset + 1))

        b = self.px(2)
        self.glow = c.create_polygon(round_rect_points(b, b, w - b, h - b, r), smooth=True,
                                     fill="", outline="", width=self.px(3), state="hidden")

        pad, bar_y = self.px(16), self.px(90)
        self.track = c.create_line(pad, bar_y, w - self.px(64), bar_y, width=self.px(8), capstyle=tk.ROUND)
        self.bar = c.create_line(pad, bar_y, pad, bar_y, width=self.px(8), capstyle=tk.ROUND, fill=WHITE)

        self.title = self.text_pair(pad, self.px(14), "nw", (UI_FONT, 10))
        self.tag = self.text_pair(w - pad, self.px(14), "ne", (UI_FONT, 10, "bold"))
        self.big = self.text_pair(w // 2, self.px(54), "center", (DIGIT_FONT, 30, "bold"), self.px(2))
        self.percent = self.text_pair(w - pad, bar_y, "e", (DIGIT_FONT, 10, "bold"))
        self.lunch = self.text_pair(pad, self.px(112), "w", (UI_FONT, 10))

    def text_pair(self, x, y, anchor, font, shadow=None):
        """白字加一層往右下偏移的陰影，回傳 (陰影, 文字)。"""
        d = shadow if shadow is not None else self.px(1)
        back = self.canvas.create_text(x + d, y + d, anchor=anchor, font=font)
        front = self.canvas.create_text(x, y, anchor=anchor, font=font, fill=WHITE)
        return back, front

    def set_text(self, pair, text):
        for item in pair:
            self.canvas.itemconfigure(item, text=text)

    def set_font(self, pair, font):
        for item in pair:
            self.canvas.itemconfigure(item, font=font)

    def move_text(self, pair, x, y):
        back, front = pair
        dx, dy = (a - b for a, b in zip(self.canvas.coords(back), self.canvas.coords(front)))
        self.canvas.coords(front, x, y)
        self.canvas.coords(back, x + dx, y + dy)

    def set_shadow_color(self, color):
        for pair in (self.title, self.tag, self.big, self.percent, self.lunch):
            self.canvas.itemconfigure(pair[0], fill=color)

    def paint_palette(self, name):
        if name == "off":
            self.paint_rainbow(0.0)
            self.canvas.itemconfigure(self.track, fill="#333355")
            self.set_shadow_color("#333355")
            return
        c1, c2 = PALETTES[name]
        last = max(len(self.columns) - 1, 1)
        for i, item in enumerate(self.columns):
            self.canvas.itemconfigure(item, fill=mix(c1, c2, i / last))
        mid = mix(c1, c2, 0.5)
        self.canvas.itemconfigure(self.track, fill=shade(mid, 0.6))
        self.set_shadow_color(shade(mid, 0.45))

    def paint_rainbow(self, offset):
        for i, item in enumerate(self.columns):
            hue = (i / len(self.columns) * 0.8 + offset) % 1
            self.canvas.itemconfigure(item, fill=rgb_to_hex(v * 255 for v in colorsys.hsv_to_rgb(hue, 0.65, 1.0)))

    def set_big_font(self, font):
        if font != self.big_font:
            self.big_font = font
            self.set_font(self.big, font)

    # ---- 每秒更新 ----

    def tick(self):
        now = self.now()
        state = get_state(now, self.config)
        if self.state and self.state.mode in ("working", "final10") and state.mode == "off":
            # 睡眠醒來時已經超過下班時間太久就不放
            if self.config["fireworks"] and now - at_today(now, self.config["end_time"]) <= FIREWORKS_GRACE:
                launch_fireworks(self.root)
        self.state = state
        self.render(state)
        self.ensure_animation()
        self.update_quotes(now)
        # 對齊到下一個整秒，避免累積誤差跳秒
        delay = 1000 - datetime.now().microsecond // 1000
        self.root.after(delay, self.tick)

    def render(self, state):
        if state.palette != self.palette:
            self.palette = state.palette
            self.paint_palette(state.palette)
            if state.palette == "off":
                self.rainbow_until = time.monotonic() + RAINBOW_SECONDS
        if state.palette != "lasthour":
            self.canvas.itemconfigure(self.glow, state="hidden")

        if state.mode in ("weekend", "off"):
            for pair in (self.title, self.tag, self.percent, self.lunch):
                self.set_text(pair, "")
            for item in (self.track, self.bar):
                self.canvas.itemconfigure(item, state="hidden")
            self.set_text(self.big, "今天放假" if state.mode == "weekend" else "下班囉！")
            self.set_big_font((UI_FONT, 24, "bold"))
            self.move_text(self.big, self.w // 2, self.h // 2)
            return

        final10 = state.mode == "final10"
        self.set_text(self.title, "" if final10 else "下班倒數")
        self.set_text(self.tag, "快下班了！" if state.palette == "lasthour" and not final10 else "")
        self.set_text(self.lunch, state.lunch_text)
        self.set_text(self.percent, f"{int(state.progress * 100)}%")
        self.canvas.itemconfigure(self.track, state="normal")
        x1, y, x2, _ = self.canvas.coords(self.track)
        self.canvas.coords(self.bar, x1, y, x1 + (x2 - x1) * state.progress, y)
        self.canvas.itemconfigure(self.bar, state="normal" if state.progress > 0 else "hidden")
        self.move_text(self.big, self.w // 2, self.px(54))

        if final10:
            seconds = int(state.remaining.total_seconds())
            if seconds != self.shown_seconds:
                self.shown_seconds = seconds
                self.pop_start = time.monotonic()
                self.set_big_font((DIGIT_FONT, POP_MAX, "bold"))
            self.set_text(self.big, str(seconds))
        else:
            self.shown_seconds = None
            self.set_text(self.big, fmt(state.remaining))
            self.set_big_font((DIGIT_FONT, 30, "bold"))

    # ---- 動畫：只在最後一小時、最後 10 秒、剛下班時執行 ----

    def needs_animation(self):
        if self.state.palette == "lasthour":
            return True
        return self.state.mode == "off" and time.monotonic() < self.rainbow_until

    def ensure_animation(self):
        if not self.animating and self.needs_animation():
            self.animating = True
            self.animate()

    def animate(self):
        if not self.needs_animation():
            self.animating = False
            return
        t = time.monotonic()
        state = self.state
        if state.palette == "lasthour":
            pulse = (math.sin(t * 2 * math.pi / 1.6) + 1) / 2
            self.canvas.itemconfigure(self.glow, state="normal", outline=mix(*GLOW_COLORS, pulse))
        if state.mode == "final10":
            k = min((t - self.pop_start) / 0.35, 1.0)
            ease = 1 - (1 - k) ** 3
            self.set_big_font((DIGIT_FONT, round(POP_MAX - (POP_MAX - POP_MIN) * ease), "bold"))
        if state.mode == "off":
            self.paint_rainbow(t * 0.25 % 1)
        self.root.after(ANIM_MS, self.animate)

    # ---- 心情小語 ----

    def update_quotes(self, now):
        period = period_of(now, self.config)
        changed = period != self.last_period and self.last_period is not None
        self.last_period = period
        if not self.config["show_quotes"] or period is None:
            return
        if changed or time.monotonic() >= self.next_quote_at:
            self.show_quote(period)

    def quote_now(self):
        # 手動「來一句」不受週末、下班或開關限制
        self.show_quote(period_by_time(self.now(), self.config))

    def show_quote(self, period):
        self.next_quote_at = time.monotonic() + self.config["quote_interval"] * 60
        quote = self.picker.pick(period)
        if not quote:
            return
        if not self.demo:
            record_play(period, quote)
        self.close_bubble()
        accent = PALETTES.get(self.palette, PALETTES["lasthour"])[0]
        self.bubble = SpeechBubble(self.root, quote, self.window_rect(), accent, self.scale)

    def close_bubble(self):
        if self.bubble:
            self.bubble.close()
            self.bubble = None

    def window_rect(self):
        return self.root.winfo_x(), self.root.winfo_y(), self.w, self.h

    # ---- 設定畫面 ----

    def open_settings(self):
        if self.settings and self.settings.alive:
            self.settings.lift()
        else:
            self.settings = SettingsWindow(self.root, self.apply_settings)

    def apply_settings(self):
        self.config = load_config()
        self.picker.set_quotes(load_quotes())
        self.next_quote_at = time.monotonic() + self.config["quote_interval"] * 60

    # ---- 視窗位置與選單 ----

    def place_window(self):
        x, y = self.config.get("x"), self.config.get("y")
        # 記住的位置不在任何螢幕上（例如拔掉外接螢幕）時，回到主螢幕右上角
        valid = isinstance(x, int) and isinstance(y, int) and is_on_screen(x + self.w // 2, y + self.h // 2)
        if not valid:
            x = self.root.winfo_screenwidth() - self.w - self.px(24)
            y = self.px(24)
        self.root.geometry(f"+{x}+{y}")

    def start_drag(self, event):
        self.drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def on_drag(self, event):
        dx, dy = self.drag_offset
        x, y = event.x_root - dx, event.y_root - dy
        self.root.geometry(f"+{x}+{y}")
        if self.bubble:
            self.bubble.follow((x, y, self.w, self.h))

    def end_drag(self, event):
        if not self.demo:
            save_position(self.root.winfo_x(), self.root.winfo_y())

    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def reset_position(self):
        self.config["x"] = self.config["y"] = None
        self.place_window()
        if not self.demo:
            save_position(None, None)

    def run(self):
        self.root.mainloop()


def main():
    # --demo：虛擬時間設在下班前 15 秒，預覽最後倒數和煙火，不影響正在執行的時鐘
    demo = "--demo" in sys.argv[1:]
    if not demo:
        # 避免開機啟動 + 手動開啟時出現兩個時鐘
        ctypes.windll.kernel32.CreateMutexW(None, False, "OffWorkClockSingleInstance")
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            sys.exit(0)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 高 DPI 螢幕不模糊
    except (AttributeError, OSError):
        pass
    ClockApp(demo).run()


if __name__ == "__main__":
    main()
