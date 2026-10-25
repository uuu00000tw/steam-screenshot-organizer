"""Window for choosing a screenshot folder and sorting it by Steam game."""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from import_screenshots import import_images, preview_import
from sort_screenshots import (
    SorterError,
    app_dir,
    detect_steam,
    load_settings,
    move_files,
    new_log_path,
    resolve,
    resource_dir,
    save_settings,
    steam_files,
)

PAPER = "#f6f3ee"
RAIL = "#ebe4da"
INK = "#241f1b"
MUTED = "#6f675f"
LINE = "#ddd4c8"
ENTRY = "#fffcf8"
ACTION = "#241f1b"


def enable_dpi():
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Steam.ScreenshotOrganizer")
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        icon = resource_dir() / "app.ico"
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except tk.TclError:
                pass
        self.title("Steam 截圖整理工具")
        self.geometry("980x640")
        self.minsize(820, 500)
        self.configure(bg=PAPER)
        self.queue = queue.Queue()
        self.busy = False
        self.plan = None
        self._ready = False

        settings = load_settings()
        steam = settings.get("steam") or ""
        if not steam:
            found = detect_steam()
            steam = str(found) if found else ""
        shots = settings.get("screenshots") or ""
        if not shots and Path(r"D:\SteamScreenshots").is_dir():
            shots = r"D:\SteamScreenshots"

        self.shot_var = tk.StringVar(value=shots)
        self.steam_var = tk.StringVar(value=steam)
        self.import_source_var = tk.StringVar(value=settings.get("import_source") or "")
        self.import_dest_var = tk.StringVar(value=settings.get("import_dest") or "")
        self.status_var = tk.StringVar(value="")
        self.summary_var = tk.StringVar(value="")
        self.import_summary_var = tk.StringVar(value="")
        self.import_plan = None

        self._style()
        self._build()
        self.shot_var.trace_add("write", self._paths_changed)
        self.steam_var.trace_add("write", self._paths_changed)
        self.import_source_var.trace_add("write", self._import_paths_changed)
        self.import_dest_var.trace_add("write", self._import_paths_changed)
        self._ready = True
        self._refresh_steam_hint()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(80, self._poll)

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=PAPER, foreground=INK, font=("Segoe UI", 10))
        style.configure("TFrame", background=PAPER)
        style.configure("Rail.TFrame", background=RAIL)
        style.configure("TLabel", background=PAPER, foreground=INK)
        style.configure("Muted.TLabel", background=PAPER, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Summary.TLabel", background=PAPER, foreground=INK, font=("Segoe UI", 11))
        style.configure("RailTitle.TLabel", background=RAIL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("TEntry", fieldbackground=ENTRY, foreground=INK, insertcolor=INK, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, padding=6)
        style.configure("TButton", background=ENTRY, foreground=INK, bordercolor=LINE, lightcolor=ENTRY, darkcolor=ENTRY, padding=(12, 6))
        style.map("TButton", background=[("active", "#f0ebe3"), ("disabled", "#f3efe9")])
        style.configure("Action.TButton", background=ACTION, foreground=PAPER, bordercolor=ACTION, lightcolor=ACTION, darkcolor=ACTION, padding=(16, 6))
        style.map(
            "Action.TButton",
            background=[("active", "#3c342e"), ("disabled", "#e6dfd6")],
            foreground=[("disabled", "#a3988d")],
        )
        style.configure("Nav.TButton", background=RAIL, foreground=INK, bordercolor=RAIL, lightcolor=RAIL, darkcolor=RAIL, padding=(12, 10), anchor="w", font=("Segoe UI", 10))
        style.map("Nav.TButton", background=[("active", "#e0d8cc")])
        style.configure("NavOn.TButton", background=INK, foreground=PAPER, bordercolor=INK, lightcolor=INK, darkcolor=INK, padding=(12, 10), anchor="w", font=("Segoe UI", 10))
        style.map("NavOn.TButton", background=[("active", "#3c342e")])
        style.configure(
            "Treeview",
            background=ENTRY,
            fieldbackground=ENTRY,
            foreground=INK,
            bordercolor=LINE,
            lightcolor=ENTRY,
            darkcolor=ENTRY,
            rowheight=30,
            font=("Segoe UI", 10),
        )
        style.configure("Treeview.Heading", background=RAIL, foreground=INK, relief="flat", borderwidth=0, font=("Segoe UI", 10))
        style.map("Treeview", background=[("selected", "#e7efe8")], foreground=[("selected", INK)])
        style.configure("Horizontal.TProgressbar", background=INK, troughcolor=RAIL, bordercolor=PAPER, lightcolor=INK, darkcolor=INK)
        style.configure("Vertical.TScrollbar", background=LINE, troughcolor=PAPER, bordercolor=PAPER, arrowcolor=MUTED, lightcolor=LINE, darkcolor=LINE)

    def _build(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        rail = ttk.Frame(body, style="Rail.TFrame", width=280)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        ttk.Label(rail, text="Steam 截圖整理工具", style="RailTitle.TLabel").pack(anchor="w", padx=16, pady=(18, 16))
        self.nav_buttons = {}
        self.pages = {}
        for key, label in (("import", "匯入截圖"), ("sort", "自動分類外部螢幕截圖")):
            button = ttk.Button(rail, text=label, style="Nav.TButton", command=lambda name=key: self._show_page(name))
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = button

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        self.page_host = ttk.Frame(right, padding=(22, 16, 22, 8))
        self.page_host.pack(fill="both", expand=True)
        self._build_sort_tab()
        self._build_import_tab()
        self._show_page("import")

        self.footer = ttk.Frame(right, padding=(22, 0, 22, 12))
        self.footer.pack(fill="x")
        self.footer.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(self.footer, mode="indeterminate")
        self.status_label = ttk.Label(self.footer, textvariable=self.status_var, style="Muted.TLabel")
        self.status_var.trace_add("write", self._toggle_status)

    def _show_page(self, name):
        for key, page in self.pages.items():
            if key == name:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        for key, button in self.nav_buttons.items():
            button.configure(style="NavOn.TButton" if key == name else "Nav.TButton")

    def _build_sort_tab(self):
        page = ttk.Frame(self.page_host)
        self.pages["sort"] = page
        form = self._form(page)
        self._path_row(form, 0, "外部螢幕截圖資料夾", self.shot_var, self._browse_shots)
        self._path_row(form, 1, "Steam 目錄", self.steam_var, self._browse_steam)
        self.steam_hint = ttk.Label(form, style="Muted.TLabel")
        self._action_row(page, self.summary_var, "整理", self._move, "preview")
        columns = ("appid", "name", "files", "folder")
        self.tree = self._table(
            page,
            columns,
            headings=(("appid", "遊戲編號", False), ("name", "遊戲名稱", False), ("files", "張數", True), ("folder", "資料夾", False)),
            widths={"appid": 110, "files": 70},
            anchors={"files": "e"},
        )
        self.tree.tag_configure("unknown", foreground="#8a3d24")

    def _build_import_tab(self):
        page = ttk.Frame(self.page_host)
        self.pages["import"] = page
        form = self._form(page)
        self._path_row(form, 0, "圖片來源", self.import_source_var, self._browse_import_source)
        self._path_row(form, 1, "遊戲截圖資料夾", self.import_dest_var, self._browse_import_dest)
        self._action_row(page, self.import_summary_var, "匯入", self._import, "import")
        self.import_tree = self._table(
            page,
            ("name",),
            headings=(("name", "檔名", False),),
        )

    def _form(self, parent):
        form = ttk.Frame(parent)
        form.pack(fill="x", pady=(0, 8))
        form.columnconfigure(1, weight=1)
        return form

    def _action_row(self, parent, summary, action, command, kind):
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, textvariable=summary, style="Summary.TLabel").pack(side="left")
        action_btn = ttk.Button(bar, text=action, style="Action.TButton", command=command, state="disabled")
        action_btn.pack(side="right")
        preview = ttk.Button(bar, text="預覽")
        preview.pack(side="right", padx=(0, 8))
        if kind == "preview":
            self.move_btn = action_btn
            self.preview_btn = preview
            preview.configure(command=self._preview)
        else:
            self.import_btn = action_btn
            self.import_preview_btn = preview
            preview.configure(command=self._import_preview)

    def _table(self, parent, columns, headings, widths=None, anchors=None):
        widths = widths or {}
        anchors = anchors or {}
        table = ttk.Frame(parent)
        table.pack(fill="both", expand=True)
        tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        for column, title, numeric in headings:
            tree.heading(column, text=title, command=lambda col=column, num=numeric: self._sort_tree(tree, col, num))
            tree.column(column, width=widths.get(column, 280), anchor=anchors.get(column, "w"), stretch=column not in widths)
        scroll = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def _path_row(self, form, row, label, variable, command):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(form, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(form, text="瀏覽", command=command).grid(row=row, column=2, padx=(8, 0), pady=4)

    def _browse_shots(self):
        current = self.shot_var.get().strip()
        picked = filedialog.askdirectory(title="選擇外部螢幕截圖資料夾", initialdir=current or None)
        if picked:
            self.shot_var.set(picked)

    def _browse_steam(self):
        current = self.steam_var.get().strip()
        picked = filedialog.askdirectory(title="選擇 Steam 目錄", initialdir=current or None)
        if picked:
            self.steam_var.set(picked)

    def _browse_import_source(self):
        current = self.import_source_var.get().strip()
        picked = filedialog.askdirectory(title="選擇圖片來源", initialdir=current or None)
        if picked:
            self.import_source_var.set(picked)

    def _browse_import_dest(self):
        current = self.import_dest_var.get().strip()
        picked = filedialog.askdirectory(title="選擇遊戲截圖資料夾", initialdir=current or None)
        if picked:
            self.import_dest_var.set(picked)

    def _paths_changed(self, *_args):
        if not self._ready:
            return
        self.plan = None
        self.move_btn.state(["disabled"])
        self._clear_table()
        self.summary_var.set("請重新預覽")
        self._refresh_steam_hint()

    def _import_paths_changed(self, *_args):
        if not self._ready:
            return
        self.import_plan = None
        self.import_btn.state(["disabled"])
        self._clear_tree(self.import_tree)
        self.import_summary_var.set("請重新預覽")

    def _refresh_steam_hint(self):
        steam = self.steam_var.get().strip()
        appinfo, _library = steam_files(steam) if steam else (None, None)
        if not steam:
            text = "未填寫 Steam 目錄，將從登錄檔讀取。"
        elif appinfo:
            text = ""
        else:
            text = "此目錄沒有遊戲清單，將改查 Steam 商店。"
        if text:
            self.steam_hint.configure(text=text)
            self.steam_hint.grid(row=2, column=0, columnspan=3, sticky="w", pady=(2, 0))
        else:
            if self.steam_hint.winfo_ismapped():
                self.steam_hint.grid_remove()

    def _toggle_status(self, *_args):
        if self.status_var.get():
            self.status_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        elif self.status_label.winfo_ismapped():
            self.status_label.grid_remove()

    def _clear_table(self):
        self._clear_tree(self.tree)

    def _clear_tree(self, tree):
        children = tree.get_children()
        if children:
            tree.delete(*children)

    def _set_busy(self, busy, indeterminate=True):
        self.busy = busy
        buttons = (self.preview_btn, self.move_btn, self.import_preview_btn, self.import_btn)
        if busy:
            for button in buttons:
                button.state(["disabled"])
            if not self.progress.winfo_ismapped():
                self.progress.grid(row=0, column=0, sticky="ew", pady=(8, 0))
            if indeterminate:
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
            if self.progress.winfo_ismapped():
                self.progress.grid_remove()
            self.preview_btn.state(["!disabled"])
            self.import_preview_btn.state(["!disabled"])
            if self.plan and self.plan["files"]:
                self.move_btn.state(["!disabled"])
            if self.import_plan and self.import_plan["pending"]:
                self.import_btn.state(["!disabled"])

    def _preview(self):
        root = self.shot_var.get().strip()
        if not root:
            messagebox.showwarning("未選擇資料夾", "請選擇外部螢幕截圖資料夾。")
            return
        steam = self.steam_var.get().strip() or None
        self._set_busy(True)
        self.status_var.set("正在預覽…")
        threading.Thread(target=self._preview_worker, args=(root, steam), daemon=True).start()

    def _preview_worker(self, root, steam):
        try:
            plan = resolve(root, steam, on_status=lambda msg: self.queue.put(("status", msg)))
        except SorterError as exc:
            self.queue.put(("error", str(exc)))
            return
        except OSError as exc:
            self.queue.put(("error", f"無法讀取資料夾：{exc}"))
            return
        self.queue.put(("preview", plan))

    def _show_preview(self, plan):
        self.plan = plan
        self._clear_table()
        for appid, info in plan["apps"].items():
            name = info["name"] or "（名稱不明）"
            tag = "unknown" if not info["name"] else ""
            self.tree.insert("", "end", values=(appid, name, info["files"], info["folder"]), tags=(tag,))
        games = len(plan["apps"])
        files = plan["files"]
        unknown = len(plan["unknown"])
        if files == 0:
            self.summary_var.set("沒有符合的檔案")
            self.status_var.set("")
            self.move_btn.state(["disabled"])
        else:
            extra = f"，{unknown} 個名稱不明" if unknown else ""
            self.summary_var.set(f"{games} 款遊戲，{files} 張{extra}")
            self.status_var.set("")
            self.move_btn.state(["!disabled"])
        save_settings({"screenshots": self.shot_var.get().strip(), "steam": self.steam_var.get().strip()})

    def _move(self):
        if not self.plan or self.plan["files"] == 0:
            return
        files = self.plan["files"]
        games = len(self.plan["apps"])
        root = self.shot_var.get().strip()
        if not messagebox.askyesno("整理", f"將 {files} 張圖片移入 {games} 個遊戲資料夾？\n\n{root}"):
            return
        total = files
        self._set_busy(True, indeterminate=False)
        self.progress.configure(mode="determinate", maximum=max(total, 1), value=0)
        self.status_var.set("正在移動…")
        threading.Thread(target=self._move_worker, args=(root, dict(self.plan["apps"]), total), daemon=True).start()

    def _move_worker(self, root, apps, total):
        def on_status(message):
            moved = 0
            if message.startswith("已移動 "):
                moved = int(message.split()[1])
            self.queue.put(("tick", moved, total, message))

        try:
            outcome = move_files(root, apps, new_log_path(), on_status=on_status)
        except OSError as exc:
            self.queue.put(("error", f"無法移動檔案：{exc}"))
            return
        self.queue.put(("done", outcome))

    def _import_preview(self):
        source = self.import_source_var.get().strip()
        dest = self.import_dest_var.get().strip()
        if not source or not dest:
            messagebox.showwarning("未選擇資料夾", "請選擇圖片來源與遊戲截圖資料夾。")
            return
        self._set_busy(True)
        self.status_var.set("正在預覽…")
        threading.Thread(target=self._import_preview_worker, args=(source, dest), daemon=True).start()

    def _import_preview_worker(self, source, dest):
        try:
            plan = preview_import(source, dest)
        except SorterError as exc:
            self.queue.put(("error", str(exc)))
            return
        except OSError as exc:
            self.queue.put(("error", f"無法讀取資料夾：{exc}"))
            return
        self.queue.put(("import_preview", plan))

    def _show_import_preview(self, plan):
        self.import_plan = plan
        self._clear_tree(self.import_tree)
        for row in plan["rows"]:
            if row["status"] == "將匯入":
                self.import_tree.insert("", "end", values=(row["name"],))
        if plan["pending"] == 0:
            self.import_summary_var.set("沒有可匯入的圖片" if not plan["skipped"] else f"{plan['skipped']} 張已有 _vr.jpg")
            self.status_var.set("")
            self.import_btn.state(["disabled"])
        else:
            note = "，將刪除不是 JPG 的原檔" if plan["same_folder"] else ""
            self.import_summary_var.set(f"將匯入 {plan['pending']} 張，略過 {plan['skipped']} 張{note}")
            self.status_var.set("")
            self.import_btn.state(["!disabled"])
        save_settings(
            {
                "import_source": self.import_source_var.get().strip(),
                "import_dest": self.import_dest_var.get().strip(),
            }
        )

    def _import(self):
        if not self.import_plan or self.import_plan["pending"] == 0:
            return
        source = self.import_source_var.get().strip()
        dest = self.import_dest_var.get().strip()
        pending = self.import_plan["pending"]
        if self.import_plan["same_folder"]:
            message = f"將 {pending} 張圖片匯入此資料夾？\n\n轉換完成後，會刪除不是 JPG 的原檔。\n\n{dest}"
        else:
            message = f"將 {pending} 張圖片複製到遊戲截圖資料夾？\n\n來源檔案會保留。\n\n{dest}"
        if not messagebox.askyesno("匯入", message):
            return
        self._set_busy(True, indeterminate=False)
        self.progress.configure(mode="determinate", maximum=max(pending, 1), value=0)
        self.status_var.set("正在匯入…")
        threading.Thread(target=self._import_worker, args=(source, dest, pending), daemon=True).start()

    def _import_worker(self, source, dest, total):
        def on_status(message):
            current = 0
            whole = total
            if message.startswith("正在匯入 "):
                current_text, whole_text = message.split()[1].split("/")
                current = int(current_text)
                whole = int(whole_text)
            self.queue.put(("tick", current, whole, message))

        try:
            outcome = import_images(source, dest, on_status=on_status)
        except SorterError as exc:
            self.queue.put(("error", str(exc)))
            return
        except OSError as exc:
            self.queue.put(("error", f"無法匯入圖片：{exc}"))
            return
        self.queue.put(("import_done", outcome))

    def _sort_tree(self, tree, column, numeric):
        state_name = "_sort_state_" + str(tree)
        previous = getattr(self, state_name, None)
        if previous and previous[0] == column:
            reverse = not previous[1]
        else:
            reverse = bool(numeric)
        rows = [(tree.set(item, column), item) for item in tree.get_children("")]
        if numeric:
            rows.sort(key=lambda row: int(row[0] or 0), reverse=reverse)
        else:
            rows.sort(key=lambda row: row[0].casefold(), reverse=reverse)
        for index, (_value, item) in enumerate(rows):
            tree.move(item, "", index)
        setattr(self, state_name, (column, reverse))

    def _poll(self):
        try:
            while True:
                event = self.queue.get_nowait()
                kind = event[0]
                if kind == "status":
                    self.status_var.set(event[1])
                elif kind == "tick":
                    _kind, moved, total, message = event
                    self.progress.configure(maximum=max(total, 1), value=moved)
                    self.status_var.set(message)
                elif kind == "preview":
                    self._set_busy(False)
                    self._show_preview(event[1])
                elif kind == "done":
                    outcome = event[1]
                    self.plan = None
                    self._set_busy(False)
                    self._clear_table()
                    parts = [f"已移動 {outcome['moved']} 張"]
                    if outcome["skipped"]:
                        parts.append(f"略過 {outcome['skipped']} 張")
                    if outcome["errors"]:
                        parts.append(f"失敗 {outcome['errors']} 張")
                    self.summary_var.set("，".join(parts))
                    self.status_var.set("")
                elif kind == "import_preview":
                    self._set_busy(False)
                    self._show_import_preview(event[1])
                elif kind == "import_done":
                    outcome = event[1]
                    self.import_plan = None
                    self._set_busy(False)
                    self._clear_tree(self.import_tree)
                    parts = [f"已匯入 {outcome['made']} 張"]
                    if outcome["skipped"]:
                        parts.append(f"略過 {outcome['skipped']} 張")
                    if outcome["errors"]:
                        parts.append(f"失敗 {outcome['errors']} 張")
                    if outcome["same_folder"]:
                        parts.append("已刪除不是 JPG 的原檔")
                    self.import_summary_var.set("，".join(parts))
                    self.status_var.set("")
                elif kind == "error":
                    self._set_busy(False)
                    self.status_var.set(event[1])
                    messagebox.showerror("錯誤", event[1])
        except queue.Empty:
            pass
        self.after(80, self._poll)

    def _close(self):
        if self.busy and not messagebox.askokcancel("作業進行中", "作業尚未完成。關閉後會停在目前進度。"):
            return
        save_settings(
            {
                "screenshots": self.shot_var.get().strip(),
                "steam": self.steam_var.get().strip(),
                "import_source": self.import_source_var.get().strip(),
                "import_dest": self.import_dest_var.get().strip(),
            }
        )
        self.destroy()


def run():
    enable_dpi()
    try:
        app = App()
    except Exception:
        import traceback

        log = app_dir() / "launch-error.txt"
        detail = traceback.format_exc()
        log.write_text(detail, encoding="utf-8")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Steam 截圖整理工具", "程式無法啟動。\n\n" + detail[-800:])
            root.destroy()
        except Exception:
            pass
        return 1
    app.mainloop()
    return 0


if __name__ == "__main__":
    run()
