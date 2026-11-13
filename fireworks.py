"""下班煙火：全螢幕透明、滑鼠可穿透的煙火動畫。"""

import ctypes
import math
import random
import time
import tkinter as tk

from monitors import all_monitors

KEY = "#000001"  # 透明色，畫面上這個顏色的地方會被挖空
FRAME_MS = 33
MAX_SPARKS = 600
COLORS = [(255, 64, 129), (255, 215, 0), (0, 229, 255), (118, 255, 3), (213, 0, 249), (255, 145, 0)]
TRAIL_COLOR = (255, 220, 160)

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def make_click_through(win):
    # 在 Tk 原本的視窗樣式上加旗標，讓滑鼠點擊穿透到下面的視窗
    win.update_idletasks()
    user32 = ctypes.windll.user32
    hwnd = user32.GetParent(win.winfo_id())
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    flags = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | flags)


class Fireworks:
    def __init__(self, root, duration):
        # 一個透明視窗蓋住所有螢幕，canvas 座標 = 螢幕座標 - 左上角原點
        self.monitors = all_monitors() or [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]
        self.ox = min(m[0] for m in self.monitors)
        self.oy = min(m[1] for m in self.monitors)
        width = max(m[2] for m in self.monitors) - self.ox
        height = max(m[3] for m in self.monitors) - self.oy
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", KEY)
        self.win.geometry(f"{width}x{height}+{self.ox}+{self.oy}")
        self.canvas = tk.Canvas(self.win, width=width, height=height, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        make_click_through(self.win)
        root.lift()  # 時鐘維持在煙火上面

        self.unit = root.winfo_screenheight() / 1080  # 速度與大小依主螢幕高度縮放
        self.gravity = 0.22 * self.unit
        self.max_sparks = MAX_SPARKS * len(self.monitors)
        self.rockets = []
        self.sparks = []
        start = time.monotonic()
        self.launch_until = start + duration - 2
        self.stop_at = start + duration + 2
        self.next_launch = start
        self.step()

    def place(self, item, x, y, r):
        self.canvas.coords(item, x - r, y - r, x + r, y + r)

    def add_spark(self, x, y, vx, vy, color, life, size):
        if len(self.sparks) >= self.max_sparks:
            return
        item = self.canvas.create_oval(0, 0, 0, 0, fill=rgb_to_hex(color), outline="")
        self.sparks.append({"id": item, "x": x, "y": y, "vx": vx, "vy": vy, "color": color,
                            "life": life, "max_life": life, "size": size})

    def launch(self):
        # 隨機挑一個螢幕，從那個螢幕的底部發射
        left, top, right, bottom = random.choice(self.monitors)
        rise = random.uniform(0.45, 0.8) * (bottom - top)
        color = random.choice(COLORS)
        self.rockets.append({
            "id": self.canvas.create_oval(0, 0, 0, 0, fill=rgb_to_hex(color), outline=""),
            "x": random.uniform(left + 0.1 * (right - left), right - 0.1 * (right - left)) - self.ox,
            "y": bottom - self.oy,
            "vx": random.uniform(-1, 1) * self.unit,
            "vy": -math.sqrt(2 * self.gravity * rise),
            "color": color,
        })

    def explode(self, rocket):
        n = random.randint(60, 80)
        base = random.uniform(5, 8) * self.unit
        for i in range(n):
            angle = 2 * math.pi * i / n + random.uniform(-0.05, 0.05)
            speed = base * random.uniform(0.3, 1.0)  # 速度有快有慢，爆開後是實心的球而不是一圈細環
            color = (255, 255, 255) if random.random() < 0.15 else rocket["color"]
            self.add_spark(rocket["x"], rocket["y"], math.cos(angle) * speed, math.sin(angle) * speed,
                           color, random.randint(40, 60), 4.5 * self.unit)

    def update_rockets(self):
        flying = []
        for rocket in self.rockets:
            rocket["x"] += rocket["vx"]
            rocket["y"] += rocket["vy"]
            rocket["vy"] += self.gravity
            self.place(rocket["id"], rocket["x"], rocket["y"], 3 * self.unit)
            self.add_spark(rocket["x"], rocket["y"], 0, 0, TRAIL_COLOR, 12, 2 * self.unit)
            if rocket["vy"] >= 0:  # 升到最高點就爆開
                self.canvas.delete(rocket["id"])
                self.explode(rocket)
            else:
                flying.append(rocket)
        self.rockets = flying

    def update_sparks(self):
        alive = []
        for spark in self.sparks:
            spark["life"] -= 1
            if spark["life"] <= 0:
                self.canvas.delete(spark["id"])
                continue
            spark["vx"] *= 0.97
            spark["vy"] = spark["vy"] * 0.97 + self.gravity * 0.35
            spark["x"] += spark["vx"]
            spark["y"] += spark["vy"]
            # 越接近消失越小、越暗，但不暗到接近黑色，免得在淺色背景上變成髒點
            f = spark["life"] / spark["max_life"]
            self.place(spark["id"], spark["x"], spark["y"], spark["size"] * (0.3 + 0.7 * f))
            self.canvas.itemconfigure(spark["id"], fill=rgb_to_hex(c * (0.5 + 0.5 * f) for c in spark["color"]))
            alive.append(spark)
        self.sparks = alive

    def step(self):
        now = time.monotonic()
        if now < self.launch_until and now >= self.next_launch:
            self.launch()
            self.next_launch = now + random.uniform(0.3, 0.5) / len(self.monitors)  # 螢幕越多發射越密
        self.update_rockets()
        self.update_sparks()
        finished = now >= self.launch_until and not self.rockets and not self.sparks
        if finished or now >= self.stop_at:
            self.win.destroy()
            return
        self.win.after(FRAME_MS, self.step)


def launch_fireworks(root, duration=8):
    """前 duration-2 秒持續發射，火花消失後自動關閉，最多 duration+2 秒。"""
    return Fireworks(root, duration)
