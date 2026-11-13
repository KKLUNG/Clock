"""設定畫面：上下班時間、心情小語、播放統計，讓使用者不必手動修改 JSON。"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

import autostart
from appconfig import QUOTE_SECONDS, TIME_KEYS, load_config, save_config
from default_quotes import DEFAULT_QUOTES
from fireworks import launch_fireworks
from monitors import work_area_at
from quotes import PERIOD_NAMES, PERIODS, clear_stats, load_quotes, load_stats, save_quotes

UI_FONT = "Microsoft JhengHei UI"
TITLE = "下班倒數 設定"
TIME_LABELS = {"start_time": "上班時間", "end_time": "下班時間", "lunch_start": "午休開始", "lunch_end": "午休結束"}
STATS_COLUMNS = (("period", "時段", 60, "center"), ("quote", "小語", 380, "w"), ("count", "次數", 60, "center"))


class SettingsWindow:
    def __init__(self, root, on_saved):
        self.root = root
        self.on_saved = on_saved
        self.config = load_config()
        self.quotes = load_quotes()
        self.quotes_changed = False
        self.sort_column, self.sort_reverse = "count", True
        self.scale = root.winfo_fpixels("1i") / 96

        self.win = tk.Toplevel(root)
        self.win.title(TITLE)
        self.win.attributes("-topmost", True)  # 時鐘是置頂的，設定畫面也要置頂才不會被擋住
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style(self.win)
        style.configure(".", font=(UI_FONT, 10))
        style.configure("Treeview", rowheight=round(tkfont.Font(font=(UI_FONT, 10)).metrics("linespace") * 1.5))

        self.notebook = ttk.Notebook(self.win)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        self.notebook.add(self.build_general(self.notebook), text="一般")
        self.notebook.add(self.build_quotes(self.notebook), text="心情小語")
        self.stats_tab = self.build_stats(self.notebook)
        self.notebook.add(self.stats_tab, text="播放統計")
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        buttons = ttk.Frame(self.win)
        buttons.pack(fill="x", padx=10, pady=10)
        ttk.Button(buttons, text="取消", command=self.close).pack(side="right")
        ttk.Button(buttons, text="儲存", command=self.save).pack(side="right", padx=(0, 8))

        # 開在時鐘所在的螢幕中央
        self.win.update_idletasks()
        left, top, right, bottom = work_area_at(root.winfo_x() + root.winfo_width() // 2,
                                                root.winfo_y() + root.winfo_height() // 2)
        x = left + (right - left - self.win.winfo_reqwidth()) // 2
        y = top + (bottom - top - self.win.winfo_reqheight()) // 3
        self.win.geometry(f"+{x}+{y}")
        self.win.focus_force()

    @property
    def alive(self):
        return bool(self.win.winfo_exists())

    def lift(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def px(self, value):
        return round(value * self.scale)

    # ---- 分頁 1：一般 ----

    def build_general(self, parent):
        frame = ttk.Frame(parent, padding=16)
        self.time_inputs = {}
        for i, key in enumerate(TIME_KEYS):
            row, col = divmod(i, 2)
            c = col * 4
            ttk.Label(frame, text=TIME_LABELS[key]).grid(row=row, column=c, sticky="w",
                                                         padx=(0 if col == 0 else 32, 8), pady=6)
            h, m = self.config[key].split(":")
            hour = ttk.Spinbox(frame, from_=0, to=23, width=3, format="%02.0f", wrap=True, justify="center")
            minute = ttk.Spinbox(frame, from_=0, to=59, increment=5, width=3, format="%02.0f", wrap=True,
                                 justify="center")
            hour.set(h)
            minute.set(m)
            hour.grid(row=row, column=c + 1)
            ttk.Label(frame, text=":").grid(row=row, column=c + 2, padx=2)
            minute.grid(row=row, column=c + 3)
            self.time_inputs[key] = (hour, minute)

        self.fireworks_var = tk.BooleanVar(value=self.config["fireworks"])
        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        ttk.Checkbutton(frame, text="下班時放煙火", variable=self.fireworks_var).grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(20, 4))
        ttk.Button(frame, text="測試煙火", command=lambda: launch_fireworks(self.root)).grid(
            row=2, column=4, columnspan=4, sticky="w", padx=(32, 0), pady=(20, 4))
        ttk.Checkbutton(frame, text="開機自動執行", variable=self.autostart_var).grid(
            row=3, column=0, columnspan=8, sticky="w", pady=4)
        return frame

    # ---- 分頁 2：心情小語 ----

    def build_quotes(self, parent):
        frame = ttk.Frame(parent, padding=16)
        top = ttk.Frame(frame)
        top.pack(fill="x")
        self.show_quotes_var = tk.BooleanVar(value=self.config["show_quotes"])
        ttk.Checkbutton(top, text="顯示心情小語", variable=self.show_quotes_var).pack(side="left")
        seconds = sorted(set(QUOTE_SECONDS) | {self.config["quote_seconds"]})
        self.seconds_box = ttk.Combobox(top, state="readonly", width=8, values=[f"{n} 秒" for n in seconds])
        self.seconds_box.set(f"{self.config['quote_seconds']} 秒")
        self.seconds_box.pack(side="right")
        ttk.Label(top, text="每句至少顯示").pack(side="right", padx=(0, 6))

        period_row = ttk.Frame(frame)
        period_row.pack(fill="x", pady=(14, 6))
        ttk.Label(period_row, text="時段").pack(side="left")
        self.period_var = tk.StringVar(value=PERIODS[0])
        for period in PERIODS:
            ttk.Radiobutton(period_row, text=PERIOD_NAMES[period], value=period, variable=self.period_var,
                            command=self.refresh_quote_list).pack(side="left", padx=(10, 0))
        self.count_label = ttk.Label(period_row)
        self.count_label.pack(side="right")

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(list_frame, height=12, width=52, selectmode="extended", font=(UI_FONT, 10),
                                  activestyle="none", exportselection=False)
        scroll = ttk.Scrollbar(list_frame, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self.on_quote_selected)

        self.entry_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.entry_var).pack(fill="x", pady=(8, 6))
        actions = ttk.Frame(frame)
        actions.pack(fill="x")
        ttk.Button(actions, text="新增", command=self.add_quote).pack(side="left")
        ttk.Button(actions, text="修改選取", command=self.edit_quote).pack(side="left", padx=6)
        ttk.Button(actions, text="刪除選取", command=self.delete_quotes).pack(side="left")
        ttk.Button(actions, text="還原這個時段的預設", command=self.restore_defaults).pack(side="right")
        self.refresh_quote_list()
        return frame

    def current_quotes(self):
        return self.quotes[self.period_var.get()]

    def refresh_quote_list(self, select=None):
        items = self.current_quotes()
        self.listbox.delete(0, "end")
        self.listbox.insert("end", *items)
        self.count_label.configure(text=f"共 {len(items)} 句")
        if select is not None:
            self.listbox.selection_set(select)
            self.listbox.see(select)

    def on_quote_selected(self, event):
        selection = self.listbox.curselection()
        if len(selection) == 1:
            self.entry_var.set(self.listbox.get(selection[0]))

    def entry_text(self):
        text = self.entry_var.get().strip()
        if not text:
            messagebox.showinfo(TITLE, "請先在下方輸入小語內容。", parent=self.win)
        return text

    def add_quote(self):
        text = self.entry_text()
        if not text:
            return
        items = self.current_quotes()
        if text in items:
            messagebox.showinfo(TITLE, "這句已經在清單裡了。", parent=self.win)
            return
        items.append(text)
        self.quotes_changed = True
        self.entry_var.set("")
        self.refresh_quote_list(select=len(items) - 1)

    def edit_quote(self):
        selection = self.listbox.curselection()
        if len(selection) != 1:
            messagebox.showinfo(TITLE, "請先在清單中選取一句要修改的小語。", parent=self.win)
            return
        text = self.entry_text()
        if not text:
            return
        self.current_quotes()[selection[0]] = text
        self.quotes_changed = True
        self.refresh_quote_list(select=selection[0])

    def delete_quotes(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo(TITLE, "請先在清單中選取要刪除的小語（可以按住 Ctrl 多選）。", parent=self.win)
            return
        if not messagebox.askyesno(TITLE, f"確定要刪除選取的 {len(selection)} 句小語嗎？", parent=self.win):
            return
        items = self.current_quotes()
        for index in reversed(selection):
            del items[index]
        self.quotes_changed = True
        self.entry_var.set("")
        self.refresh_quote_list()

    def restore_defaults(self):
        period = self.period_var.get()
        defaults = DEFAULT_QUOTES[period]
        message = f"確定要把「{PERIOD_NAMES[period]}」的小語還原成預設的 {len(defaults)} 句嗎？\n你新增或修改過的內容會被清除。"
        if not messagebox.askyesno(TITLE, message, parent=self.win):
            return
        self.quotes[period] = list(defaults)
        self.quotes_changed = True
        self.refresh_quote_list()

    # ---- 分頁 3：播放統計 ----

    def build_stats(self, parent):
        frame = ttk.Frame(parent, padding=16)
        self.totals_label = ttk.Label(frame)
        self.totals_label.pack(anchor="w")
        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True, pady=8)
        self.tree = ttk.Treeview(table, columns=[c[0] for c in STATS_COLUMNS], show="headings", height=12)
        for key, title, width, anchor in STATS_COLUMNS:
            self.tree.heading(key, text=title, command=lambda k=key: self.sort_stats(k))
            self.tree.column(key, width=self.px(width), anchor=anchor, stretch=key == "quote")
        scroll = ttk.Scrollbar(table, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Button(frame, text="清除統計", command=self.clear_stats).pack(anchor="e")
        self.stats_rows = []
        return frame

    def on_tab_changed(self, event):
        if self.notebook.select() == str(self.stats_tab):
            self.refresh_stats()

    def refresh_stats(self):
        stats = load_stats()
        totals = "　　".join(f"{PERIOD_NAMES[p]} 共 {sum(stats[p].values())} 次" for p in PERIODS)
        self.totals_label.configure(text=totals)
        # 目前清單裡的小語（沒播過的算 0 次），加上已經刪掉但有播放紀錄的
        self.stats_rows = []
        for order, period in enumerate(PERIODS):
            counts = dict.fromkeys(self.quotes[period], 0)
            counts.update(stats[period])
            self.stats_rows += [(order, quote, count) for quote, count in counts.items()]
        self.render_stats()

    def sort_stats(self, column):
        if column == self.sort_column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column, self.sort_reverse = column, column == "count"
        self.render_stats()

    def render_stats(self):
        index = {"period": 0, "quote": 1, "count": 2}[self.sort_column]
        rows = sorted(self.stats_rows, key=lambda r: r[index], reverse=self.sort_reverse)
        self.tree.delete(*self.tree.get_children())
        for order, quote, count in rows:
            self.tree.insert("", "end", values=(PERIOD_NAMES[PERIODS[order]], quote, count))
        for key, title, _, _ in STATS_COLUMNS:
            arrow = (" ▼" if self.sort_reverse else " ▲") if key == self.sort_column else ""
            self.tree.heading(key, text=title + arrow)

    def clear_stats(self):
        if messagebox.askyesno(TITLE, "確定要清除所有播放次數嗎？這個動作無法復原。", parent=self.win):
            clear_stats()
            self.refresh_stats()

    # ---- 儲存 ----

    def read_times(self):
        times = {}
        for key, (hour, minute) in self.time_inputs.items():
            try:
                h, m = int(hour.get()), int(minute.get())
                if not (0 <= h < 24 and 0 <= m < 60):
                    raise ValueError
            except ValueError:
                messagebox.showerror(TITLE, f"「{TIME_LABELS[key]}」的時間格式不正確。", parent=self.win)
                return None
            times[key] = f"{h:02d}:{m:02d}"
        if times["start_time"] >= times["end_time"]:
            messagebox.showerror(TITLE, "上班時間要早於下班時間。", parent=self.win)
            return None
        if times["lunch_start"] >= times["lunch_end"]:
            messagebox.showerror(TITLE, "午休開始要早於午休結束。", parent=self.win)
            return None
        return times

    def save(self):
        times = self.read_times()
        if times is None:
            return
        updates = dict(times, fireworks=self.fireworks_var.get(), show_quotes=self.show_quotes_var.get(),
                       quote_seconds=int(self.seconds_box.get().split()[0]))
        saved = save_config(updates)
        if self.quotes_changed:
            saved = save_quotes(self.quotes) and saved
        if not saved:
            messagebox.showerror(TITLE, "無法寫入設定檔，請確認程式所在的資料夾可以寫入。", parent=self.win)
            return
        try:
            autostart.set_enabled(self.autostart_var.get())
        except OSError:
            messagebox.showwarning(TITLE, "其他設定已儲存，但無法設定開機自動執行。", parent=self.win)
        self.on_saved()
        self.close()

    def close(self):
        self.win.destroy()
