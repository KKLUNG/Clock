"""心情小語的對話泡泡：出現在時鐘上方（空間不夠就改到下方），停留一段時間後淡出。"""

import tkinter as tk

from monitors import work_area_at

KEY = "#010203"  # 透明色，用來挖出圓角
BG = "#ffffff"
FG = "#2b2b3a"
UI_FONT = "Microsoft JhengHei UI"
# 以下尺寸是 100% 縮放時的像素
WIDTH, PAD, RADIUS, TAIL, GAP = 260, 12, 12, 10, 4
SHOW_MS = 15000
FADE_STEPS, FADE_MS = 10, 40


def round_rect_points(x1, y1, x2, y2, r):
    """搭配 create_polygon(smooth=True) 畫出圓角矩形。"""
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


class SpeechBubble:
    def __init__(self, root, text, clock_rect, accent, scale):
        self.scale = scale
        self.alive = True
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", KEY)
        self.win.configure(bg=KEY)
        self.canvas = tk.Canvas(self.win, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda e: self.close())

        w, pad, r, tail, line = self.px(WIDTH), self.px(PAD), self.px(RADIUS), self.px(TAIL), self.px(2)
        text_item = self.canvas.create_text(0, 0, text=text, anchor="nw", width=w - 2 * pad,
                                            font=(UI_FONT, 11), fill=FG)
        x1, y1, x2, y2 = self.canvas.bbox(text_item)
        body_h = (y2 - y1) + 2 * pad
        self.w, self.h = w, body_h + tail

        cx, cy, cw, ch = clock_rect
        top = work_area_at(cx + cw // 2, cy + ch // 2)[1]
        self.above = cy - self.h - self.px(GAP) >= top
        x, y = self.position(clock_rect)
        tx = min(max(cx + cw // 2 - x, r + tail), w - r - tail)  # 尾巴盡量指向時鐘中央

        body_top = 0 if self.above else tail
        body_bottom = body_top + body_h
        self.canvas.create_polygon(round_rect_points(line, body_top + line, w - line, body_bottom - line, r),
                                   smooth=True, fill=BG, outline=accent, width=line)
        # 尾巴：先用白色三角形蓋掉那一段外框，再補上兩條斜邊
        if self.above:
            base, tip, inner = body_bottom - line, self.h - 1, body_bottom - 2 * line
        else:
            base, tip, inner = body_top + line, 1, body_top + 2 * line
        self.canvas.create_polygon(tx - tail, inner, tx + tail, inner, tx, tip, fill=BG, outline="")
        self.canvas.create_line(tx - tail, base, tx, tip, tx + tail, base, fill=accent, width=line)
        self.canvas.coords(text_item, pad, body_top + pad)
        self.canvas.tag_raise(text_item)

        self.canvas.configure(width=w, height=self.h)
        self.win.geometry(f"{w}x{self.h}+{x}+{y}")
        self.win.after(SHOW_MS, self.fade)

    def px(self, value):
        return round(value * self.scale)

    def position(self, clock_rect):
        # 以時鐘所在的螢幕為範圍，雙螢幕時泡泡才會跟著時鐘過去
        cx, cy, cw, ch = clock_rect
        left, _, right, _ = work_area_at(cx + cw // 2, cy + ch // 2)
        x = min(max(cx + (cw - self.w) // 2, left), right - self.w)
        y = cy - self.h - self.px(GAP) if self.above else cy + ch + self.px(GAP)
        return x, y

    def follow(self, clock_rect):
        """拖曳時鐘時一起移動，維持原本在上方或下方。"""
        if self.alive:
            x, y = self.position(clock_rect)
            self.win.geometry(f"+{x}+{y}")

    def fade(self, step=0):
        if not self.alive:
            return
        if step >= FADE_STEPS:
            self.close()
            return
        self.win.attributes("-alpha", 1 - step / FADE_STEPS)
        self.win.after(FADE_MS, self.fade, step + 1)

    def close(self):
        if self.alive:
            self.alive = False
            self.win.destroy()
