"""下班倒數計時時鐘：無邊框、置頂、可拖曳的桌面小工具。"""

import colorsys
import ctypes
import math
import sys
import time
import tkinter as tk
from collections import namedtuple
from datetime import datetime, timedelta

from appconfig import (ZOOM_MAX, ZOOM_MIN, at_today, effective_end, load_config, overtime_active, save_config,
                       save_position)
from fireworks import launch_fireworks
from monitors import is_on_screen
from quotes import QuotePicker, load_quotes, period_by_time, period_of, record_play
from settings import SettingsWindow
from sky import SkyDecor
from themes import THEMES

# 以下尺寸是 100% 縮放時的像素，實際會依螢幕 DPI 放大
WIDTH, HEIGHT, RADIUS = 280, 130, 16
MARQUEE_HEIGHT = 28  # 跑馬燈那一行的高度
KEY = "#010203"  # 透明色，用來挖出圓角
WHITE = "#ffffff"
RAINBOW_DARK = "#333355"  # 彩虹背景上的陰影和進度條軌道色
UI_FONT = "Microsoft JhengHei UI"
DIGIT_FONT = "Consolas"
POP_MAX, POP_MIN = 52, 36  # 最後 10 秒數字放大縮回的字級
ANIM_MS = 40
RAINBOW_SECONDS = 60
FIREWORKS_GRACE = timedelta(seconds=60)
MARQUEE_MS = 33  # 跑馬燈每一幀往左移 1px（依 DPI 放大），約每秒 30px
ZOOM_PRESETS = (("小（80%）", 0.8), ("標準（100%）", 1.0), ("大（125%）", 1.25), ("特大（150%）", 1.5))
ZOOM_STEP = 0.1

State = namedtuple("State", "mode remaining progress lunch_text palette closing title")


def fmt(delta):
    total = int(delta.total_seconds())
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_state(now, config):
    if now.weekday() >= 5:
        return State("weekend", None, 0.0, "", "weekend", False, "")
    end = at_today(now, config["end_time"])
    final_end = effective_end(now, config)  # 有加班就是加班結束時間
    if now >= final_end:
        return State("off", None, 1.0, "", "off", False, "")

    overtime = now >= end
    if overtime:
        start, target, title = end, final_end, "加班倒數"
    else:
        start, target, title = at_today(now, config["start_time"]), end, "下班倒數"
    remaining = target - now
    total = (target - start).total_seconds()
    progress = min(max((now - start).total_seconds() / total, 0.0), 1.0) if total > 0 else 0.0

    lunch_start = at_today(now, config["lunch_start"])
    lunch_end = at_today(now, config["lunch_end"])
    if overtime:
        lunch_text = ""
    elif now < lunch_start:
        lunch_text = f"午休倒數 {fmt(lunch_start - now)}"
    elif now < lunch_end:
        lunch_text = "午休中"
    else:
        lunch_text = ""

    # 「快下班」看的是今天真正下班的時間：有加班時，原本下班前的最後一小時不算
    closing = final_end - now <= timedelta(hours=1)
    if overtime:
        palette = "overtime"
    elif closing:
        palette = "lasthour"
    elif now < lunch_start:
        palette = "morning"
    elif now < lunch_end:
        palette = "noon"
    else:
        palette = "afternoon"
    if final_end - now <= timedelta(seconds=10):
        mode = "final10"
    else:
        mode = "overtime" if overtime else "working"
    return State(mode, remaining, progress, lunch_text, palette, closing, title)


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


def round_rect_points(x1, y1, x2, y2, r):
    """搭配 create_polygon(smooth=True) 畫出圓角矩形。"""
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


class ClockApp:
    def __init__(self, demo=False):
        self.config = load_config()
        self.demo = demo
        self.offset = demo_offset(self.config) if demo else timedelta(0)

        self.root = tk.Tk()
        self.theme = THEMES[self.config["theme"]]
        self.dpi_scale = self.root.winfo_fpixels("1i") / 96
        self.zoom = self.config["zoom"]
        self.compute_sizes()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", KEY)
        self.root.configure(bg=KEY)
        self.canvas = tk.Canvas(self.root, width=self.w, height=self.h, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.build_items()

        self.zoom_var = tk.DoubleVar(value=self.zoom)
        size_menu = tk.Menu(self.root, tearoff=0)
        for label, zoom in ZOOM_PRESETS:
            size_menu.add_radiobutton(label=label, value=zoom, variable=self.zoom_var,
                                      command=lambda z=zoom: self.set_zoom(z))
        size_menu.add_separator()
        size_menu.add_command(label="按住 Ctrl 滾動滑鼠滾輪可以微調", state="disabled")

        self.theme_var = tk.StringVar(value=self.config["theme"])
        theme_menu = tk.Menu(self.root, tearoff=0)
        for key, theme in THEMES.items():
            theme_menu.add_radiobutton(label=theme["name"], value=key, variable=self.theme_var,
                                       command=lambda k=key: self.set_theme(k))

        self.overtime_var = tk.BooleanVar()
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="下一句", command=self.next_quote)
        self.menu.add_command(label="放煙火", command=lambda: launch_fireworks(self.root))
        self.menu.add_checkbutton(label="今天加班", variable=self.overtime_var, command=self.toggle_overtime)
        self.menu.add_cascade(label="變色模式", menu=theme_menu)
        self.menu.add_cascade(label="大小", menu=size_menu)
        self.menu.add_command(label="設定…", command=self.open_settings)
        self.menu.add_command(label="重設位置", command=self.reset_position)
        self.menu.add_separator()
        self.menu.add_command(label="結束", command=self.root.destroy)
        self.bind_events(self.canvas)

        self.state = None
        self.palette = None
        self.big_font = None
        self.shown_seconds = None
        self.pop_start = 0.0
        self.rainbow_until = 0.0
        self.animating = False

        self.picker = QuotePicker(load_quotes())
        self.settings = None
        self.last_period = None
        self.marquee_visible = False
        self.marquee_running = False
        self.marquee_x = 0
        self.marquee_width = 0
        self.quote_started = 0.0
        self.force_next = False

        self.tick()
        self.place_window()

    def px(self, value):
        return round(value * self.scale)

    def fs(self, size):
        """字級（點）只需乘上縮放比例，DPI 的部分 Tk 會自己處理。"""
        return round(size * self.zoom)

    def compute_sizes(self):
        self.scale = self.dpi_scale * self.zoom
        self.w, self.h = self.px(WIDTH), self.px(HEIGHT)
        self.base_h, self.full_h = self.h, self.px(HEIGHT + MARQUEE_HEIGHT)
        self.pad = self.px(16)

    def bind_events(self, widget):
        widget.bind("<ButtonPress-1>", self.start_drag)
        widget.bind("<B1-Motion>", self.on_drag)
        widget.bind("<ButtonRelease-1>", self.end_drag)
        widget.bind("<Button-3>", self.show_menu)
        widget.bind("<Control-MouseWheel>", self.on_zoom_wheel)

    def now(self):
        return datetime.now().replace(microsecond=0) + self.offset

    # ---- 畫面元件 ----

    def build_items(self):
        c, w, r = self.canvas, self.w, self.px(RADIUS)
        pad, bar_y = self.pad, self.px(90)
        # 每個像素欄一條垂直線組成漸層，依圓角半徑算出上下內縮量
        self.columns = []
        self.insets = []
        for x in range(w):
            cx = x + 0.5
            d = max(r - cx, cx - (w - r), 0)
            self.insets.append(r - math.sqrt(max(r * r - d * d, 0)) if d else 0)
            self.columns.append(c.create_line(x, 0, x, 0))

        # 跑馬燈放在獨立的小畫布，背景是一張接續外框漸層的圖：捲動時只需重畫文字和這張圖，
        # 不用重畫上百條漸層線，超出左右的文字也會被小畫布自然裁掉
        self.mq_w, self.mq_h = w - 2 * pad, self.px(MARQUEE_HEIGHT - 6)
        self.mq = tk.Canvas(c, width=self.mq_w, height=self.mq_h, highlightthickness=0, bd=0)
        self.mq_image = tk.PhotoImage(width=self.mq_w, height=self.mq_h)
        self.mq.create_image(0, 0, image=self.mq_image, anchor="nw")
        self.marquee_y = self.mq_h // 2
        self.marquee = self.text_pair(self.mq_w, self.marquee_y, "w", (UI_FONT, self.fs(10)), canvas=self.mq)
        self.bind_events(self.mq)
        self.mq_window = c.create_window(pad, self.base_h, window=self.mq, anchor="nw", state="hidden")
        self.separator = c.create_line(pad, self.base_h - self.px(4), w - pad, self.base_h - self.px(4),
                                       state="hidden")

        self.glow = c.create_polygon(0, 0, 0, 0, smooth=True, fill="", outline="", width=self.px(3), state="hidden")
        self.layout(self.h)
        self.column_colors = None
        self.sky = SkyDecor(c, self.px, w, pad)  # 畫在漸層之上、文字和進度條之下

        self.track = c.create_line(pad, bar_y, w - self.px(64), bar_y, width=self.px(8), capstyle=tk.ROUND)
        self.bar = c.create_line(pad, bar_y, pad, bar_y, width=self.px(8), capstyle=tk.ROUND, fill=WHITE)

        self.title = self.text_pair(pad, self.px(14), "nw", (UI_FONT, self.fs(10)))
        self.tag = self.text_pair(w - pad, self.px(14), "ne", (UI_FONT, self.fs(10), "bold"))
        self.big = self.text_pair(w // 2, self.px(54), "center", (DIGIT_FONT, self.fs(30), "bold"), self.px(2))
        self.percent = self.text_pair(w - pad, bar_y, "e", (DIGIT_FONT, self.fs(10), "bold"))
        self.lunch = self.text_pair(pad, self.px(112), "w", (UI_FONT, self.fs(10)))

    def layout(self, h):
        """改變時鐘高度：重新計算漸層欄和發光外框的座標。"""
        self.h = h
        self.canvas.configure(height=h)
        for x, (item, inset) in enumerate(zip(self.columns, self.insets)):
            self.canvas.coords(item, x, inset, x, h - inset + 1)
        b = self.px(2)
        self.canvas.coords(self.glow, *round_rect_points(b, b, self.w - b, h - b, self.px(RADIUS)))

    def text_pair(self, x, y, anchor, font, shadow=None, canvas=None):
        """白字加一層往右下偏移的陰影，回傳 (陰影, 文字)。"""
        canvas = canvas or self.canvas
        d = shadow if shadow is not None else self.px(1)
        back = canvas.create_text(x + d, y + d, anchor=anchor, font=font)
        front = canvas.create_text(x, y, anchor=anchor, font=font, fill=WHITE)
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

    def set_text_colors(self, fg, shadow):
        for back, front in (self.title, self.tag, self.big, self.percent, self.lunch):
            self.canvas.itemconfigure(back, fill=shadow)
            self.canvas.itemconfigure(front, fill=fg)
        self.mq.itemconfigure(self.marquee[0], fill=shadow)
        self.mq.itemconfigure(self.marquee[1], fill=fg)

    def set_track_color(self, color):
        for item in (self.track, self.separator):
            self.canvas.itemconfigure(item, fill=color)

    def paint_palette(self, name):
        theme = self.theme
        self.canvas.itemconfigure(self.bar, fill=theme["bar"])
        colors_pair = theme["palettes"][name]
        if colors_pair == "rainbow":
            self.column_colors = None
            self.paint_rainbow(0.0)
            self.set_track_color(RAINBOW_DARK)
            self.set_text_colors(theme["fg"], RAINBOW_DARK)
            return
        c1, c2 = colors_pair
        last = max(len(self.columns) - 1, 1)
        colors = [mix(c1, c2, i / last) for i in range(len(self.columns))]
        self.column_colors = colors  # 天空模式畫彎月時要用到背景色
        for item, color in zip(self.columns, colors):
            self.canvas.itemconfigure(item, fill=color)
        # 跑馬燈背景圖：取同一段漸層，接起來看不出接縫
        row = "{" + " ".join(colors[self.pad:self.pad + self.mq_w]) + "}"
        self.mq_image.put(" ".join([row] * self.mq_h))
        mid = mix(c1, c2, 0.5)
        if theme["shadow"] == "light":  # 淺色底：深色字配淺色陰影
            self.set_track_color(shade(mid, 0.85))
            self.set_text_colors(theme["fg"], mix(mid, WHITE, 0.6))
        else:
            self.set_track_color(shade(mid, 0.6))
            self.set_text_colors(theme["fg"], shade(mid, 0.45))

    def color_at(self, x):
        if not self.column_colors:
            return RAINBOW_DARK
        return self.column_colors[min(max(int(x), 0), len(self.column_colors) - 1)]

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
        self.refresh()
        # 對齊到下一個整秒，避免累積誤差跳秒
        delay = 1000 - datetime.now().microsecond // 1000
        self.root.after(delay, self.tick)

    def refresh(self):
        now = self.now()
        state = get_state(now, self.config)
        if self.state and self.state.mode in ("working", "overtime", "final10") and state.mode == "off":
            # 睡眠醒來時已經超過下班時間太久就不放
            if self.config["fireworks"] and now - effective_end(now, self.config) <= FIREWORKS_GRACE:
                launch_fireworks(self.root)
        self.state = state
        self.update_quotes(now)  # 先決定跑馬燈要不要顯示，時鐘高度才會正確
        self.render(state)
        self.ensure_animation()

    def render(self, state):
        if state.palette != self.palette:
            self.palette = state.palette
            self.paint_palette(state.palette)
            if state.palette == "off":
                self.rainbow_until = time.monotonic() + RAINBOW_SECONDS
        if not state.closing:
            # 霓虹模式的外框一直亮著，其他模式只有快下班時才發光（由 animate 負責閃爍）
            border = self.theme["border"]
            self.canvas.itemconfigure(self.glow, state="normal" if border else "hidden", outline=border or "")
        if self.theme["sky"]:
            t = 0.5 if state.mode == "weekend" else state.progress
            self.sky.update(state.palette, t, self.color_at)

        if state.mode in ("weekend", "off"):
            for pair in (self.title, self.tag, self.percent, self.lunch):
                self.set_text(pair, "")
            for item in (self.track, self.bar):
                self.canvas.itemconfigure(item, state="hidden")
            self.set_text(self.big, "今天放假" if state.mode == "weekend" else "下班囉！")
            self.set_big_font((UI_FONT, self.fs(24), "bold"))
            self.move_text(self.big, self.w // 2, self.h // 2)
            return

        final10 = state.mode == "final10"
        self.set_text(self.title, "" if final10 else state.title)
        self.set_text(self.tag, "快下班了！" if state.closing and not final10 else "")
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
                self.set_big_font((DIGIT_FONT, self.fs(POP_MAX), "bold"))
            self.set_text(self.big, str(seconds))
        else:
            self.shown_seconds = None
            self.set_text(self.big, fmt(state.remaining))
            self.set_big_font((DIGIT_FONT, self.fs(30), "bold"))

    # ---- 動畫：只在最後一小時、最後 10 秒、剛下班時執行 ----

    def needs_animation(self):
        if self.state.closing:
            return True
        rainbow = self.theme["palettes"]["off"] == "rainbow"
        return rainbow and self.state.mode == "off" and time.monotonic() < self.rainbow_until

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
        if state.closing:
            pulse = (math.sin(t * 2 * math.pi / 1.6) + 1) / 2
            self.canvas.itemconfigure(self.glow, state="normal", outline=mix(*self.theme["glow"], pulse))
        if state.mode == "final10":
            k = min((t - self.pop_start) / 0.35, 1.0)
            ease = 1 - (1 - k) ** 3
            self.set_big_font((DIGIT_FONT, self.fs(POP_MAX - (POP_MAX - POP_MIN) * ease), "bold"))
        if state.mode == "off" and self.column_colors is None:
            self.paint_rainbow(t * 0.25 % 1)
        self.root.after(ANIM_MS, self.animate)

    # ---- 心情小語 ----

    def update_quotes(self, now):
        period = period_of(now, self.config)
        if period and self.last_period and period != self.last_period:
            self.force_next = True  # 進入或結束午休：這一圈跑完就換成新時段的小語
        self.last_period = period
        self.set_marquee_visible(self.config["show_quotes"] and period is not None)

    def set_marquee_visible(self, visible):
        if visible == self.marquee_visible:
            return
        self.marquee_visible = visible
        self.layout(self.full_h if visible else self.base_h)
        for item in (self.mq_window, self.separator):
            self.canvas.itemconfigure(item, state="normal" if visible else "hidden")
        if visible:
            self.next_quote()
            if not self.marquee_running:
                self.marquee_running = True
                self.scroll()

    def next_quote(self):
        """換下一句，從右邊重新捲進來。"""
        if not self.marquee_visible:
            return
        period = self.last_period or period_by_time(self.now(), self.config)
        quote = self.picker.pick(period) or ""
        if quote and not self.demo:
            record_play(period, quote)
        self.set_marquee_text(quote)
        self.quote_started = time.monotonic()
        self.force_next = False

    def set_marquee_text(self, quote):
        for item in self.marquee:
            self.mq.itemconfigure(item, text=quote)
        x1, _, x2, _ = self.mq.bbox(self.marquee[1])
        self.marquee_width = x2 - x1
        self.restart_marquee()

    def restart_marquee(self):
        """把文字放回小畫布右邊外側，重新捲進來。"""
        self.marquee_x = self.mq_w
        back, front = self.marquee
        d = self.px(1)
        self.mq.coords(front, self.marquee_x, self.marquee_y)
        self.mq.coords(back, self.marquee_x + d, self.marquee_y + d)

    def scroll(self):
        if not self.marquee_visible:
            self.marquee_running = False
            return
        step = max(self.px(1), 1)
        self.marquee_x -= step
        for item in self.marquee:
            self.mq.move(item, -step, 0)
        if self.marquee_x + self.marquee_width < 0:
            # 整句捲出左邊，這一圈跑完：時間到了才換下一句，否則同一句再跑一圈
            if self.force_next or time.monotonic() - self.quote_started >= self.config["quote_seconds"]:
                self.next_quote()
            else:
                self.restart_marquee()
        self.root.after(MARQUEE_MS, self.scroll)

    # ---- 縮放 ----

    def on_zoom_wheel(self, event):
        self.set_zoom(self.zoom + (ZOOM_STEP if event.delta > 0 else -ZOOM_STEP))

    def set_zoom(self, zoom):
        zoom = round(min(max(zoom, ZOOM_MIN), ZOOM_MAX), 2)
        self.zoom_var.set(zoom)
        if zoom == self.zoom:
            return
        self.zoom = zoom
        quote = self.mq.itemcget(self.marquee[1], "text")
        # 所有尺寸和字級都跟著縮放比例變，直接整個畫面重建
        self.mq.destroy()
        self.canvas.delete("all")
        self.compute_sizes()
        self.canvas.configure(width=self.w)
        self.build_items()
        self.palette = self.big_font = self.shown_seconds = None
        if self.marquee_visible:
            self.layout(self.full_h)
            for item in (self.mq_window, self.separator):
                self.canvas.itemconfigure(item, state="normal")
            self.set_marquee_text(quote)  # 同一句從頭再跑，不算新的一次播放
        self.render(self.state)
        if not self.demo:
            save_config({"zoom": zoom})

    # ---- 設定畫面 ----

    def open_settings(self):
        if self.settings and self.settings.alive:
            self.settings.lift()
        else:
            self.settings = SettingsWindow(self.root, self.apply_settings)

    def apply_settings(self):
        self.config = load_config()
        self.picker.set_quotes(load_quotes())
        self.apply_theme()
        self.next_quote()  # 小語可能改過，馬上換一句

    # ---- 變色模式與加班 ----

    def apply_theme(self):
        self.theme = THEMES[self.config["theme"]]
        self.theme_var.set(self.config["theme"])
        self.palette = None  # 強制重新上色
        self.sky.hide()
        self.refresh()

    def set_theme(self, key):
        self.config["theme"] = key
        if not self.demo:
            save_config({"theme": key})
        self.apply_theme()

    def toggle_overtime(self):
        # 只記今天的日期，隔天自動失效
        value = self.now().date().isoformat() if self.overtime_var.get() else None
        self.config["overtime_date"] = value
        if not self.demo:
            save_config({"overtime_date": value})
        self.refresh()

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

    def end_drag(self, event):
        if not self.demo:
            save_position(self.root.winfo_x(), self.root.winfo_y())

    def show_menu(self, event):
        # 跑馬燈沒顯示時（週末、下班後、關掉小語），「下一句」沒有作用
        self.menu.entryconfigure(0, state="normal" if self.marquee_visible else "disabled")
        now = self.now()
        self.overtime_var.set(overtime_active(now, self.config))
        self.menu.entryconfigure(2, label=f"今天加班（到 {self.config['overtime_end']}）",
                                 state="normal" if now.weekday() < 5 else "disabled")
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
