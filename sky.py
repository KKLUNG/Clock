"""天空模式的裝飾：太陽依工作進度沿著弧線移動，加班和下班後換成彎月和星星。"""

import math

# palette: (半徑, 顏色, 有沒有光芒)，半徑是 100% 縮放時的像素
SUN_STYLES = {
    "morning": (9, "#ffcf5c", False),     # 剛升起的小太陽
    "noon": (13, "#fff4b8", True),        # 中午大太陽
    "afternoon": (11, "#ff6a3d", False),  # 夕陽
    "lasthour": (11, "#ff4e3a", False),
    "weekend": (13, "#fff4b8", True),
}
MOON_COLOR = "#f6f1d5"
STAR_COLOR = "#fffbe6"
# (x 比例, y 比例)：避開左上的標題、右上的「快下班了！」和中間的數字
STARS = ((0.36, 0.04), (0.47, 0.16), (0.57, 0.03), (0.67, 0.14), (0.05, 0.50), (0.95, 0.46))
RAY_COUNT = 8
OFF_MOON_T = 0.8  # 下班後月亮固定在右上方


class SkyDecor:
    def __init__(self, canvas, px, width, pad):
        self.canvas, self.px, self.width = canvas, px, width
        self.left, self.right = pad + px(10), width - pad - px(10)
        self.horizon, self.top = px(96), px(24)
        c = canvas
        self.stars = [c.create_oval(0, 0, 0, 0, fill=STAR_COLOR, outline="") for _ in STARS]
        self.rays = [c.create_line(0, 0, 0, 0, width=max(px(2), 1), capstyle="round") for _ in range(RAY_COUNT)]
        self.sun = c.create_oval(0, 0, 0, 0, outline="")
        self.moon = c.create_oval(0, 0, 0, 0, fill=MOON_COLOR, outline="")
        self.moon_shadow = c.create_oval(0, 0, 0, 0, outline="")
        self.items = (*self.stars, *self.rays, self.sun, self.moon, self.moon_shadow)
        self.hide()

    def hide(self):
        for item in self.items:
            self.canvas.itemconfigure(item, state="hidden")

    def arc_point(self, t):
        t = min(max(t, 0.0), 1.0)
        x = self.left + (self.right - self.left) * t
        y = self.horizon - math.sin(math.pi * t) * (self.horizon - self.top)
        return x, y

    def circle(self, item, x, y, r):
        self.canvas.coords(item, x - r, y - r, x + r, y + r)
        self.canvas.itemconfigure(item, state="normal")

    def update(self, palette, t, color_at):
        """palette 決定畫太陽還是月亮，t 是在弧線上的位置 (0~1)，color_at(x) 回傳該位置的背景色。"""
        self.hide()
        if palette == "overtime":
            self.show_moon(t, color_at)
        elif palette == "off":
            self.show_moon(OFF_MOON_T, color_at)
        elif palette in SUN_STYLES:
            self.show_sun(palette, 0.5 if palette == "weekend" else t)

    def show_sun(self, palette, t):
        radius, color, has_rays = SUN_STYLES[palette]
        r = self.px(radius)
        x, y = self.arc_point(t)
        self.circle(self.sun, x, y, r)
        self.canvas.itemconfigure(self.sun, fill=color)
        if has_rays:
            inner, outer = r + self.px(3), r + self.px(8)
            for i, ray in enumerate(self.rays):
                a = 2 * math.pi * i / RAY_COUNT
                self.canvas.coords(ray, x + math.cos(a) * inner, y + math.sin(a) * inner,
                                   x + math.cos(a) * outer, y + math.sin(a) * outer)
                self.canvas.itemconfigure(ray, fill=color, state="normal")

    def show_moon(self, t, color_at):
        r = self.px(10)
        x, y = self.arc_point(t)
        self.circle(self.moon, x, y, r)
        # 疊一個背景色的圓、往右上錯開，剩下的就是彎月
        sx, sy = x + r * 0.45, y - r * 0.25
        self.circle(self.moon_shadow, sx, sy, r * 0.85)
        self.canvas.itemconfigure(self.moon_shadow, fill=color_at(sx))
        star_r = max(self.px(1.5), 1)
        for star, (fx, fy) in zip(self.stars, STARS):
            sx, sy = self.width * fx, self.px(6) + fy * (self.horizon - self.px(6))
            if abs(sx - x) > r * 2 or abs(sy - y) > r * 2:  # 別跟月亮重疊
                self.circle(star, sx, sy, star_r)
