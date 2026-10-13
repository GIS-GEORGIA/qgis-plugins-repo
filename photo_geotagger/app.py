"""Photo Geotagger as a standalone desktop program (Tkinter, nothing to install).

    python app.py        or        python geotag.py        (no arguments)

Same engine as the QGIS plugin: coordinates from a fixed point / the map / a GPX track / a CSV table,
place names from OpenStreetMap or a polygon file, preview, undo, a map with movable points and export
to CSV / GeoJSON / KML / GPX (and GPKG / Shapefile ... when GDAL is available).
"""
import base64
import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from . import core, export, geo_lookup, geocode, i18n, notice, tiles
except ImportError:  # run as a plain script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import core
    import export
    import geo_lookup
    import geocode
    import i18n
    import notice
    import tiles

t = i18n.t
VERSION = "0.8.0"
DEFAULTS = {"lang": "ka", "engine": "auto", "exiftool": "", "raw_embed": False, "backup": True, "tiles": True,
            "notice_ack": "", "nominatim": geocode.PUBLIC_URL, "folder": ""}


def config_dir():
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "PhotoGeotagger")


def cache_dir():
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "PhotoGeotagger", "tiles")


class Settings(dict):
    def __init__(self, path=None):
        super().__init__(DEFAULTS)
        self.path = path or os.path.join(config_dir(), "settings.json")
        try:
            with open(self.path, encoding="utf-8") as f:
                self.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(dict(self), f, ensure_ascii=False, indent=1)
        except OSError:
            pass


class Job:
    """Runs worker(item) for each item on a thread; results come back through a queue polled by the GUI."""

    def __init__(self, items, worker):
        self.items, self.worker = list(items), worker
        self.queue = queue.Queue()
        self.cancel = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        for i, item in enumerate(self.items):
            if self.cancel.is_set():
                self.queue.put(("end", True))
                return
            try:
                result = self.worker(item)
            except Exception as exc:  # a failing photo must not stop the batch
                result = ("error", str(exc))
            self.queue.put(("item", item, result, i + 1))
        self.queue.put(("end", False))


def fmt_pos(pos):
    if not pos:
        return ""
    text = "%.6f, %.6f" % (pos[0], pos[1])
    if len(pos) > 2 and pos[2] is not None:
        text += ", %.1f m" % pos[2]
    if len(pos) > 3 and pos[3] is not None:
        text += ", %.0f°" % pos[3]
    return text


# --------------------------------------------------------------------------- map
class MapView(ttk.Frame):
    COLORS = {"existing": "#1f6fd1", "planned": "#2e9d4a", "moved": "#e08a00"}

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.lat, self.lon, self.zoom = 41.7, 44.8, 7
        self.markers, self.selected = {}, None
        self.images, self.ready = {}, queue.Queue()
        self.cache = tiles.TileCache(cache_dir(), on_ready=lambda z, x, y: self.ready.put((z, x, y)))
        self.pick_var, self.edit_var = tk.BooleanVar(value=False), tk.BooleanVar(value=False)
        self.tiles_var = tk.BooleanVar(value=bool(app.settings["tiles"]))
        self._screen, self._drag = {}, None

        bar = ttk.Frame(self)
        bar.pack(fill="x")
        self.b_zoom_in = ttk.Button(bar, text="+", width=3, command=lambda: self.zoom_by(1))
        self.b_zoom_out = ttk.Button(bar, text="−", width=3, command=lambda: self.zoom_by(-1))
        self.b_fit = ttk.Button(bar, command=self.fit)
        self.c_pick = ttk.Checkbutton(bar, variable=self.pick_var)
        self.c_edit = ttk.Checkbutton(bar, variable=self.edit_var)
        self.c_tiles = ttk.Checkbutton(bar, variable=self.tiles_var, command=self._tiles_changed)
        for w in (self.b_zoom_in, self.b_zoom_out, self.b_fit, self.c_pick, self.c_edit, self.c_tiles):
            w.pack(side="left", padx=3, pady=2)
        self.b_write = ttk.Button(bar, command=app.write_moved)
        self.b_write.pack(side="right", padx=3)
        self.canvas = tk.Canvas(self, bg="#e6e6e6", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<MouseWheel>", lambda e: self._wheel(e, 1 if e.delta > 0 else -1))
        self.canvas.bind("<Button-4>", lambda e: self._wheel(e, 1))
        self.canvas.bind("<Button-5>", lambda e: self._wheel(e, -1))
        self._poll_id = self.after(200, self._poll_tiles)
        self.bind("<Destroy>", lambda e: self.after_cancel(self._poll_id) if e.widget is self else None)

    def retranslate(self):
        self.b_fit.configure(text=t("app_map_fit"))
        self.c_pick.configure(text=t("app_map_pick"))
        self.c_edit.configure(text=t("app_map_move"))
        self.c_tiles.configure(text=t("app_map_tiles"))
        self.b_write.configure(text=t("app_map_write_moved"))
        self.redraw()

    # -- state
    def _tiles_changed(self):
        self.app.settings["tiles"] = self.tiles_var.get()
        self.app.settings.save()
        self.cache.retry_failed()
        self.redraw()

    def set_markers(self, markers, selected=None):
        self.markers, self.selected = dict(markers), selected
        self.redraw()

    def fit(self):
        w, h = max(self.canvas.winfo_width(), 200), max(self.canvas.winfo_height(), 200)
        self.lat, self.lon, self.zoom = tiles.zoom_to_fit([(m[0], m[1]) for m in self.markers.values()], w, h)
        self.redraw()

    def center_on(self, lat, lon):
        self.lat, self.lon = lat, lon
        self.redraw()

    def zoom_by(self, step, anchor=None):
        new = max(1, min(tiles.MAX_ZOOM, self.zoom + step))
        if new == self.zoom:
            return
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        cx, cy = tiles.to_pixel(self.lat, self.lon, self.zoom)
        if anchor:  # keep the point under the cursor fixed
            ax, ay = cx - w / 2 + anchor[0], cy - h / 2 + anchor[1]
            glat, glon = tiles.from_pixel(ax, ay, self.zoom)
            self.zoom = new
            nx, ny = tiles.to_pixel(glat, glon, new)
            self.lat, self.lon = tiles.from_pixel(nx - anchor[0] + w / 2, ny - anchor[1] + h / 2, new)
        else:
            self.zoom = new
        self.redraw()

    # -- drawing
    def _origin(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        cx, cy = tiles.to_pixel(self.lat, self.lon, self.zoom)
        return cx - w / 2, cy - h / 2, w, h

    def _tile_image(self, z, x, y):
        key = (z, x, y)
        if key in self.images:
            return self.images[key]
        data = self.cache.get(z, x, y)
        if data is None:
            return None
        if len(self.images) > 400:
            self.images.clear()
        try:
            self.images[key] = tk.PhotoImage(data=base64.b64encode(data))
        except tk.TclError:
            self.images[key] = None
        return self.images[key]

    def redraw(self):
        c = self.canvas
        c.delete("all")
        left, top, w, h = self._origin()
        if w < 20:
            return
        if self.tiles_var.get():
            n = 2 ** self.zoom
            for tx in range(int(left // 256), int((left + w) // 256) + 1):
                for ty in range(int(top // 256), int((top + h) // 256) + 1):
                    if 0 <= ty < n:
                        x0, y0 = tx * 256 - left, ty * 256 - top
                        img = self._tile_image(self.zoom, tx % n, ty)
                        if img:
                            c.create_image(x0, y0, image=img, anchor="nw")
        self._screen = {}
        for path, (lat, lon, kind) in self.markers.items():
            px, py = tiles.to_pixel(lat, lon, self.zoom)
            x, y = px - left, py - top
            self._screen[path] = (x, y)
            if -20 <= x <= w + 20 and -20 <= y <= h + 20:
                color = self.COLORS.get(kind, "#1f6fd1")
                if path == self.selected:
                    c.create_oval(x - 11, y - 11, x + 11, y + 11, outline="#d12f2f", width=3)
                c.create_oval(x - 6, y - 6, x + 6, y + 6, fill=color, outline="white", width=2)
        credit = t("app_map_credit")
        c.create_rectangle(w - 190, h - 18, w, h, fill="white", outline="")
        c.create_text(w - 4, h - 9, text=credit, anchor="e", font=("TkDefaultFont", 8), fill="#333")

    def _poll_tiles(self):
        redraw = False
        while True:
            try:
                self.ready.get_nowait()
                redraw = True
            except queue.Empty:
                break
        if redraw:
            self.redraw()
        self._poll_id = self.after(250, self._poll_tiles)

    # -- mouse
    def _hit(self, x, y):
        for path, (mx, my) in self._screen.items():
            if (mx - x) ** 2 + (my - y) ** 2 <= 100:
                return path
        return None

    def _geo(self, x, y):
        left, top, _, _ = self._origin()
        return tiles.from_pixel(left + x, top + y, self.zoom)

    def _press(self, e):
        self._drag = {"x": e.x, "y": e.y, "start": (e.x, e.y), "moved": False,
                      "marker": self._hit(e.x, e.y) if self.edit_var.get() else None}

    def _motion(self, e):
        d = self._drag
        if d is None:
            return
        if abs(e.x - d["start"][0]) + abs(e.y - d["start"][1]) > 3:
            d["moved"] = True
        if d["marker"] and d["moved"]:
            lat, lon = self._geo(e.x, e.y)
            self.markers[d["marker"]] = (lat, lon, "moved")
            self.redraw()
        elif d["moved"]:
            cx, cy = tiles.to_pixel(self.lat, self.lon, self.zoom)
            self.lat, self.lon = tiles.from_pixel(cx - (e.x - d["x"]), cy - (e.y - d["y"]), self.zoom)
            d["x"], d["y"] = e.x, e.y
            self.redraw()

    def _release(self, e):
        d, self._drag = self._drag, None
        if d is None:
            return
        if d["marker"] and d["moved"]:
            lat, lon = self._geo(e.x, e.y)
            self.app.on_marker_moved(d["marker"], lat, lon)
        elif not d["moved"]:
            hit = self._hit(e.x, e.y)
            if hit:
                self.app.on_map_select(hit)
            elif self.pick_var.get():
                lat, lon = self._geo(e.x, e.y)
                self.app.on_map_pick(lat, lon)

    def _wheel(self, e, step):
        self.zoom_by(step, (e.x, e.y))


# --------------------------------------------------------------------------- application
class App:
    COLS = ("file", "taken", "existing", "new", "place", "status")

    def __init__(self, root, settings=None, lang=None):
        self.root = root
        self.settings = settings or Settings()
        i18n.set_lang(lang or self.settings["lang"])
        self.rows, self.job, self.job_handlers = {}, None, None
        self.features, self.lookup_fields = None, {}
        self._texts, self._tabs = [], []
        self._apply_engine()
        root.geometry("1380x820")
        root.minsize(1000, 640)
        self._build_menu()
        self._build()
        self.retranslate()
        self.status.set(t("app_ready"))
        root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---------------------------------------------------------------- building
    def _txt(self, widget, key):
        self._texts.append((widget, key))
        return widget

    def _build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.file_menu, self.help_menu, self.lang_menu = tk.Menu(self.menu, tearoff=0), tk.Menu(self.menu, tearoff=0), None
        self.file_menu.add_command(command=self.open_settings)
        self.file_menu.add_separator()
        self.file_menu.add_command(command=self.quit)
        self.help_menu.add_command(command=lambda: self.show_notice(False))
        self.help_menu.add_command(command=self.about)
        self.menu.add_cascade(menu=self.file_menu)
        self.menu.add_cascade(menu=self.help_menu)
        self.lang_var = tk.StringVar(value=i18n.LANG)
        self.lang_menu = tk.Menu(self.menu, tearoff=0)
        for code, name in (("ka", "ქართული"), ("en", "English")):
            self.lang_menu.add_radiobutton(label=name, value=code, variable=self.lang_var, command=self.change_lang)
        self.menu.add_cascade(menu=self.lang_menu)
        self.root.configure(menu=self.menu)

    def _build(self):
        root = self.root
        self.status = tk.StringVar()
        self.recursive = tk.BooleanVar(value=False)
        self.scope = tk.StringVar(value="all")
        self.backup = tk.BooleanVar(value=bool(self.settings["backup"]))
        self.overwrite = tk.BooleanVar(value=False)

        paned = ttk.PanedWindow(root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=6, pady=6)
        left, right = ttk.Frame(paned), ttk.Frame(paned)
        paned.add(left, weight=3)
        paned.add(right, weight=2)
        self.paned = paned
        root.after(150, lambda: paned.sashpos(0, 700))

        # photo list
        bar = ttk.Frame(left)
        bar.pack(fill="x")
        for key, cmd in (("add_files", self.add_files), ("add_folder", self.add_folder),
                         ("app_remove", self.remove_selected), ("clear", self.clear)):
            self._txt(ttk.Button(bar, command=cmd), key).pack(side="left", padx=2, pady=2)
        self._txt(ttk.Checkbutton(bar, variable=self.recursive), "app_recursive").pack(side="left", padx=8)
        frame = ttk.Frame(left)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=self.COLS, show="headings", selectmode="extended")
        for col, width in zip(self.COLS, (130, 120, 170, 170, 160, 130)):
            self.tree.column(col, width=width, anchor="w")
        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Delete>", lambda e: self.remove_selected())

        # right: notebook
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)
        self._build_source_tab()
        self._build_place_tab()
        self.map = MapView(self.notebook, self)
        self._add_tab(self.map, "app_tab_map")
        self._build_export_tab()

        # actions
        actions = ttk.Frame(root)
        actions.pack(fill="x", padx=6)
        self._txt(ttk.Label(actions), "app_scope").pack(side="left")
        self._txt(ttk.Radiobutton(actions, variable=self.scope, value="all"), "app_scope_all").pack(side="left", padx=4)
        self._txt(ttk.Radiobutton(actions, variable=self.scope, value="selected"), "app_scope_selected").pack(side="left")
        self._txt(ttk.Checkbutton(actions, variable=self.backup, command=self._backup_changed), "backup").pack(side="left", padx=10)
        self._txt(ttk.Checkbutton(actions, variable=self.overwrite), "overwrite").pack(side="left")
        self.buttons = []
        for key, cmd in (("restore_btn", self.restore), ("run", self.run), ("preview", self.preview)):
            b = self._txt(ttk.Button(actions, command=cmd), key)
            b.pack(side="right", padx=3, pady=4)
            self.buttons.append(b)
        self.b_cancel = self._txt(ttk.Button(actions, command=self.cancel, state="disabled"), "cancel")
        self.b_cancel.pack(side="right", padx=3)

        self.progress = ttk.Progressbar(root, maximum=100)
        self.progress.pack(fill="x", padx=6)
        self.log = tk.Text(root, height=7, wrap="word", state="disabled")
        self.log.pack(fill="x", padx=6, pady=(4, 0))
        ttk.Label(root, textvariable=self.status, anchor="w").pack(fill="x", padx=6, pady=3)

    def _add_tab(self, frame, key):
        self.notebook.add(frame, text="")
        self._tabs.append((frame, key))

    def _build_source_tab(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self._add_tab(tab, "app_tab_source")
        self.source = tk.StringVar(value="fixed")
        self.v = {k: tk.StringVar() for k in ("lat", "lon", "alt", "dir", "gpx", "csv")}
        self.utc, self.shift, self.gap = tk.StringVar(value="4"), tk.StringVar(value="0"), tk.StringVar(value="600")
        self.use_alt, self.use_dir = tk.BooleanVar(value=False), tk.BooleanVar(value=False)

        def row(parent, r, key, var, check=None):
            if check is None:
                self._txt(ttk.Label(parent), key).grid(row=r, column=0, sticky="w", pady=2)
            else:
                self._txt(ttk.Checkbutton(parent, variable=check), key).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Entry(parent, textvariable=var, width=18).grid(row=r, column=1, sticky="we", pady=2, padx=4)

        self._txt(ttk.Radiobutton(tab, variable=self.source, value="fixed"), "src_coords").grid(row=0, column=0, columnspan=3, sticky="w")
        box = ttk.Frame(tab)
        box.grid(row=1, column=0, columnspan=3, sticky="we", padx=18)
        row(box, 0, "lat", self.v["lat"])
        row(box, 1, "lon", self.v["lon"])
        row(box, 2, "alt", self.v["alt"], self.use_alt)
        row(box, 3, "direction", self.v["dir"], self.use_dir)
        box.columnconfigure(1, weight=1)

        self._txt(ttk.Radiobutton(tab, variable=self.source, value="gpx"), "src_gpx").grid(row=2, column=0, columnspan=3, sticky="w", pady=(12, 0))
        gbox = ttk.Frame(tab)
        gbox.grid(row=3, column=0, columnspan=3, sticky="we", padx=18)
        ttk.Entry(gbox, textvariable=self.v["gpx"]).grid(row=0, column=0, columnspan=2, sticky="we")
        self._txt(ttk.Button(gbox, command=lambda: self._browse(self.v["gpx"], [("GPX", "*.gpx")])), "browse").grid(row=0, column=2, padx=4)
        for r, (key, var) in enumerate((("utc_offset", self.utc), ("shift", self.shift), ("max_gap", self.gap)), start=1):
            self._txt(ttk.Label(gbox), key).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Entry(gbox, textvariable=var, width=8).grid(row=r, column=1, sticky="w", padx=4)
        self._txt(ttk.Button(gbox, command=self.estimate), "estimate").grid(row=1, column=2, rowspan=3, padx=4)
        lbl = self._txt(ttk.Label(gbox, wraplength=420, foreground="#555"), "estimate_hint")
        lbl.grid(row=4, column=0, columnspan=3, sticky="w", pady=2)
        gbox.columnconfigure(1, weight=1)

        self._txt(ttk.Radiobutton(tab, variable=self.source, value="csv"), "src_csv").grid(row=4, column=0, columnspan=3, sticky="w", pady=(12, 0))
        cbox = ttk.Frame(tab)
        cbox.grid(row=5, column=0, columnspan=3, sticky="we", padx=18)
        ttk.Entry(cbox, textvariable=self.v["csv"]).grid(row=0, column=0, sticky="we")
        self._txt(ttk.Button(cbox, command=lambda: self._browse(self.v["csv"], [("CSV", "*.csv *.txt")])), "browse").grid(row=0, column=1, padx=4)
        cbox.columnconfigure(0, weight=1)
        self._txt(ttk.Label(tab, wraplength=460, foreground="#555"), "formats_note").grid(row=6, column=0, columnspan=3, sticky="w", pady=(16, 0))
        tab.columnconfigure(0, weight=1)

    def _build_place_tab(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self._add_tab(tab, "app_tab_place")
        self.place_src = tk.StringVar(value="osm")
        self.place_lang = tk.StringVar(value=i18n.LANG)
        self.place_url = tk.StringVar(value=self.settings["nominatim"])
        self.place_file = tk.StringVar()
        self.place_max = tk.StringVar(value="100")
        self.place_over = tk.BooleanVar(value=False)
        self._txt(ttk.Radiobutton(tab, variable=self.place_src, value="osm"), "place_osm").grid(row=0, column=0, columnspan=3, sticky="w")
        osm = ttk.Frame(tab)
        osm.grid(row=1, column=0, columnspan=3, sticky="we", padx=18)
        self._txt(ttk.Label(osm), "lang").grid(row=0, column=0, sticky="w")
        ttk.Combobox(osm, textvariable=self.place_lang, values=("ka", "en"), width=5, state="readonly").grid(row=0, column=1, sticky="w", padx=4)
        self._txt(ttk.Label(osm), "place_url").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(osm, textvariable=self.place_url).grid(row=1, column=1, sticky="we", padx=4)
        osm.columnconfigure(1, weight=1)

        self._txt(ttk.Radiobutton(tab, variable=self.place_src, value="file"), "app_file_source").grid(row=2, column=0, columnspan=3, sticky="w", pady=(12, 0))
        fb = ttk.Frame(tab)
        fb.grid(row=3, column=0, columnspan=3, sticky="we", padx=18)
        ttk.Entry(fb, textvariable=self.place_file).grid(row=0, column=0, sticky="we")
        self._txt(ttk.Button(fb, command=lambda: self._browse(self.place_file, [("GeoJSON / GPKG / SHP", "*.geojson *.json *.gpkg *.shp")])), "browse").grid(row=0, column=1, padx=4)
        self._txt(ttk.Button(fb, command=self.load_place_file), "app_load").grid(row=0, column=2)
        self.field_vars, self.field_boxes = {}, {}
        for r, key in enumerate(core.PLACE_FIELDS, start=1):
            self._txt(ttk.Label(fb), "place_" + key).grid(row=r, column=0, sticky="w", pady=2)
            self.field_vars[key] = tk.StringVar()
            box = ttk.Combobox(fb, textvariable=self.field_vars[key], state="readonly", values=[""])
            box.grid(row=r, column=1, columnspan=2, sticky="we", padx=4)
            self.field_boxes[key] = box
        self._txt(ttk.Label(fb), "place_max").grid(row=5, column=0, sticky="w", pady=2)
        ttk.Entry(fb, textvariable=self.place_max, width=8).grid(row=5, column=1, sticky="w", padx=4)
        fb.columnconfigure(0, weight=1)
        fb.columnconfigure(1, weight=1)

        self._txt(ttk.Checkbutton(tab, variable=self.place_over), "place_overwrite").grid(row=4, column=0, columnspan=3, sticky="w", pady=(12, 0))
        self._txt(ttk.Label(tab, wraplength=460, foreground="#555"), "place_note").grid(row=5, column=0, columnspan=3, sticky="w", pady=6)
        self._txt(ttk.Button(tab, command=self.write_places), "place_btn").grid(row=6, column=0, columnspan=3, sticky="we", pady=4)
        tab.columnconfigure(0, weight=1)

    def _build_export_tab(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self._add_tab(tab, "app_tab_export")
        self.fmt_vars = {}
        self._txt(ttk.Label(tab), "out_files").grid(row=0, column=0, columnspan=4, sticky="w")
        keys = export.available()
        for i, key in enumerate(keys):
            self.fmt_vars[key] = tk.BooleanVar(value=key in ("csv", "gpkg"))
            ttk.Checkbutton(tab, text=export.FORMATS[key][0], variable=self.fmt_vars[key]).grid(row=1 + i // 3, column=i % 3, sticky="w", padx=4, pady=2)
        row = 2 + (len(keys) - 1) // 3
        if not all(k in keys for k in ("gpkg", "shp")):
            self._txt(ttk.Label(tab, wraplength=460, foreground="#a05a00"), "app_no_gdal").grid(row=row, column=0, columnspan=4, sticky="w", pady=4)
            row += 1
        self.out_dir, self.out_name = tk.StringVar(value=self.settings["folder"]), tk.StringVar(value="geotagged_photos")
        self._txt(ttk.Label(tab), "out_folder").grid(row=row, column=0, sticky="w", pady=(10, 2))
        ttk.Entry(tab, textvariable=self.out_dir).grid(row=row, column=1, columnspan=2, sticky="we", pady=(10, 2))
        self._txt(ttk.Button(tab, command=self._browse_dir), "browse").grid(row=row, column=3, padx=4)
        self._txt(ttk.Label(tab), "out_name").grid(row=row + 1, column=0, sticky="w")
        ttk.Entry(tab, textvariable=self.out_name).grid(row=row + 1, column=1, columnspan=2, sticky="we")
        self._txt(ttk.Button(tab, command=self.export_files), "export_btn").grid(row=row + 2, column=0, columnspan=4, sticky="we", pady=12)
        for c in (1, 2):
            tab.columnconfigure(c, weight=1)

    # ------------------------------------------------------------ language / texts
    def retranslate(self):
        self.root.title("Photo Geotagger %s" % VERSION)
        for widget, key in self._texts:
            widget.configure(text=t(key))
        for frame, key in self._tabs:
            self.notebook.tab(frame, text=t(key))
        self.menu.entryconfigure(0, label=t("app_menu_file"))
        self.menu.entryconfigure(1, label=t("app_menu_help"))
        self.menu.entryconfigure(2, label=t("lang"))
        self.file_menu.entryconfigure(0, label=t("app_settings"))
        self.file_menu.entryconfigure(2, label=t("app_quit"))
        self.help_menu.entryconfigure(0, label=t("app_notice"))
        self.help_menu.entryconfigure(1, label=t("app_about"))
        for col, key in zip(self.COLS, ("col_file", "col_taken", "col_existing", "col_new", "col_place", "col_status")):
            self.tree.heading(col, text=t(key))
        self.map.retranslate()
        for path in self.rows:
            self.refresh_row(path)

    def change_lang(self):
        i18n.set_lang(self.lang_var.get())
        self.settings["lang"] = i18n.LANG
        self.place_lang.set(i18n.LANG)
        self.settings.save()
        self.retranslate()

    # -------------------------------------------------------------- small helpers
    def say(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _browse(self, var, types):
        name = filedialog.askopenfilename(filetypes=types + [("*", "*.*")])
        if name:
            var.set(name)

    def _browse_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.out_dir.set(d)

    def _apply_engine(self):
        core.CONFIG.update({"engine": self.settings["engine"], "exiftool": self.settings["exiftool"],
                            "raw_embed": bool(self.settings["raw_embed"])})

    def _backup_changed(self):
        self.settings["backup"] = self.backup.get()
        self.settings.save()

    @staticmethod
    def _num(text, default=None):
        text = text.strip().replace(",", ".")
        return float(text) if text else default

    # ---------------------------------------------------------------- photo rows
    def add_files(self):
        names = filedialog.askopenfilenames(
            filetypes=[(t("photo_filter"), " ".join("*" + e for e in core.PHOTO_EXT)), ("*", "*.*")])
        self.add_paths(list(names))

    def add_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.add_paths([d])

    def add_paths(self, paths):
        photos = [p for p in core.collect_photos(paths, self.recursive.get()) if p not in self.rows]
        for p in photos:
            self.rows[p] = {"taken": None, "existing": None, "new": None, "place": {}, "status": "", "moved": None}
            self.tree.insert("", "end", iid=p, values=(os.path.basename(p), "", "", "", "", ""))
        if photos:
            self.start_job(photos, self._read_meta, self._meta_item, self._meta_done, show_progress=True)

    @staticmethod
    def _read_meta(path):
        return core.read_gps(path), core.read_datetime(path), core.read_place(path)

    def _meta_item(self, path, result, n):
        if isinstance(result, tuple) and len(result) == 3:
            row = self.rows.get(path)
            if row is not None:
                row["existing"], row["taken"], row["place"] = result
                self.refresh_row(path)

    def _meta_done(self, cancelled):
        self.sync_map(center=True)

    def refresh_row(self, path):
        row = self.rows.get(path)
        if row is None or not self.tree.exists(path):
            return
        place = ", ".join(row["place"].get(k, "") for k in core.PLACE_FIELDS if row["place"].get(k))
        new = fmt_pos(row["new"]) if row["new"] else ""
        if row["moved"]:
            new = "%s (%s)" % (fmt_pos(row["moved"]), t("app_moved_label"))
        self.tree.item(path, values=(os.path.basename(path), row["taken"].isoformat(" ") if row["taken"] else "",
                                     fmt_pos(row["existing"]), new, place, row["status"]))

    def remove_selected(self):
        for p in self.tree.selection():
            self.rows.pop(p, None)
            self.tree.delete(p)
        self.sync_map()

    def clear(self):
        self.rows.clear()
        self.tree.delete(*self.tree.get_children())
        self.sync_map()

    def targets(self):
        if self.scope.get() == "selected" and self.tree.selection():
            return list(self.tree.selection())
        return list(self.tree.get_children())

    # ------------------------------------------------------------------- map sync
    def sync_map(self, center=False, selected=None):
        markers = {}
        for path, row in self.rows.items():
            if row["moved"]:
                markers[path] = (row["moved"][0], row["moved"][1], "moved")
            elif row["new"]:
                markers[path] = (row["new"][0], row["new"][1], "planned")
            elif row["existing"]:
                markers[path] = (row["existing"][0], row["existing"][1], "existing")
        sel = selected or (self.tree.selection()[0] if self.tree.selection() else None)
        self.map.set_markers(markers, sel)
        if center:
            self.map.fit()

    def on_select(self, _event=None):
        sel = self.tree.selection()
        if sel:
            m = self.map.markers.get(sel[0])
            self.map.selected = sel[0]
            if m:
                self.map.center_on(m[0], m[1])
            else:
                self.map.redraw()

    def on_map_select(self, path):
        if self.tree.exists(path):
            self.tree.selection_set(path)
            self.tree.see(path)

    def on_map_pick(self, lat, lon):
        self.v["lat"].set("%.6f" % lat)
        self.v["lon"].set("%.6f" % lon)
        self.source.set("fixed")
        self.say("%s: %.6f, %.6f" % (t("pick"), lat, lon))

    def on_marker_moved(self, path, lat, lon):
        row = self.rows.get(path)
        if row is not None:
            row["moved"] = (lat, lon)
            row["status"] = t("app_moved_label")
            self.refresh_row(path)
            self.sync_map(selected=path)

    # ------------------------------------------------------------------- jobs
    def start_job(self, items, worker, on_item, on_done, show_progress=True):
        if self.job is not None:
            return False
        self.job = Job(items, worker)
        self.job_handlers = (on_item, on_done, len(self.job.items))
        self.progress.configure(value=0)
        self.b_cancel.configure(state="normal")
        for b in self.buttons:
            b.state(["disabled"])
        self.status.set(t("app_working"))
        self.root.after(30, self._poll_job)
        return True

    def _poll_job(self):
        job = self.job
        if job is None:
            return
        on_item, on_done, total = self.job_handlers
        finished = None
        for _ in range(200):
            try:
                msg = job.queue.get_nowait()
            except queue.Empty:
                break
            if msg[0] == "item":
                on_item(msg[1], msg[2], msg[3])
                self.progress.configure(value=100.0 * msg[3] / max(total, 1))
            else:
                finished = msg[1]
                break
        if finished is None:
            self.root.after(30, self._poll_job)
            return
        self.job = None
        self.b_cancel.configure(state="disabled")
        for b in self.buttons:
            b.state(["!disabled"])
        self.progress.configure(value=0)
        self.status.set(t("cancelled") if finished else t("app_ready"))
        on_done(finished)

    def cancel(self):
        if self.job:
            self.job.cancel.set()

    def wait_idle(self, timeout=60):
        """Pump the GUI until the running job has finished (used by tests and scripts)."""
        import time
        end = time.time() + timeout
        while self.job is not None and time.time() < end:
            self.root.update()
            time.sleep(0.01)
        self.root.update()

    # ------------------------------------------------------------------ notice
    def show_notice(self, require_ack):
        win = tk.Toplevel(self.root)
        win.title(t("warn_title"))
        win.geometry("760x640")
        win.transient(self.root)
        text = tk.Text(win, wrap="word", padx=10, pady=8)
        text.insert("1.0", notice.notice_text(i18n.LANG))
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)
        result = {"ok": False}
        bottom = ttk.Frame(win)
        bottom.pack(fill="x", padx=8, pady=8)
        if require_ack:
            ack = tk.BooleanVar(value=False)
            go = ttk.Button(bottom, text=t("warn_continue"), state="disabled", command=lambda: (result.update(ok=True), win.destroy()))
            ttk.Checkbutton(bottom, text=t("warn_ack"), variable=ack,
                            command=lambda: go.configure(state="normal" if ack.get() else "disabled")).pack(side="left")
            go.pack(side="right")
            ttk.Button(bottom, text=t("cancel"), command=win.destroy).pack(side="right", padx=6)
            win.grab_set()
            self.root.wait_window(win)
        else:
            ttk.Button(bottom, text=t("close"), command=win.destroy).pack(side="right")
        return result["ok"]

    def confirm_notice(self):
        if self.settings["notice_ack"] == notice.VERSION:
            return True
        if self.show_notice(True):
            self.settings["notice_ack"] = notice.VERSION
            self.settings.save()
            return True
        return False

    def about(self):
        messagebox.showinfo(t("app_about"), t("app_about_text"))

    # ---------------------------------------------------------------- settings
    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title(t("app_settings"))
        win.transient(self.root)
        engine = tk.StringVar(value=self.settings["engine"])
        path = tk.StringVar(value=self.settings["exiftool"])
        raw = tk.BooleanVar(value=bool(self.settings["raw_embed"]))
        backup = tk.BooleanVar(value=bool(self.settings["backup"]))
        info = tk.StringVar()
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=t("engine")).grid(row=0, column=0, sticky="w")
        names = {"auto": t("engine_auto"), "builtin": t("engine_builtin"), "exiftool": t("engine_exiftool")}
        combo = ttk.Combobox(frame, state="readonly", values=list(names.values()), width=36)
        combo.set(names[engine.get()])
        combo.grid(row=0, column=1, columnspan=2, sticky="we", pady=3)
        ttk.Label(frame, text=t("exiftool_path")).grid(row=1, column=0, sticky="w")
        ttk.Entry(frame, textvariable=path, width=40).grid(row=1, column=1, sticky="we", pady=3)
        ttk.Button(frame, text=t("browse"), command=lambda: self._browse(path, [("exiftool", "*.exe *")])).grid(row=1, column=2, padx=4)
        ttk.Checkbutton(frame, text=t("raw_embed"), variable=raw).grid(row=2, column=0, columnspan=3, sticky="w", pady=3)
        ttk.Checkbutton(frame, text=t("app_default_backup"), variable=backup).grid(row=3, column=0, columnspan=3, sticky="w")
        ttk.Label(frame, textvariable=info, wraplength=420, foreground="#555").grid(row=4, column=0, columnspan=3, sticky="w", pady=6)

        def refresh_info(*_):
            found = core.find_exiftool(path.get().strip() or None)
            info.set(t("exiftool_found", found) if found else t("exiftool_missing"))

        def save():
            chosen = [k for k, v in names.items() if v == combo.get()]
            self.settings.update(engine=chosen[0] if chosen else "auto", exiftool=path.get().strip(),
                                 raw_embed=raw.get(), backup=backup.get())
            self.backup.set(backup.get())
            self.settings.save()
            self._apply_engine()
            win.destroy()

        path.trace_add("write", refresh_info)
        refresh_info()
        ttk.Button(frame, text=t("app_save"), command=save).grid(row=5, column=2, sticky="e", pady=8)
        frame.columnconfigure(1, weight=1)

    # -------------------------------------------------------------- operations
    def build_source(self):
        mode = self.source.get()
        try:
            if mode == "gpx":
                if not self.v["gpx"].get():
                    raise core.GeotagError(t("no_source"))
                return core.load_source("gpx", file=self.v["gpx"].get(), utc_offset=self._num(self.utc.get(), 0),
                                        shift=self._num(self.shift.get(), 0), max_gap=self._num(self.gap.get(), 600))
            if mode == "csv":
                if not self.v["csv"].get():
                    raise core.GeotagError(t("no_source"))
                return core.load_source("csv", file=self.v["csv"].get())
            lat, lon = self._num(self.v["lat"].get()), self._num(self.v["lon"].get())
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise core.GeotagError(t("bad_coords"))
            return core.load_source("fixed", lat=lat, lon=lon,
                                    alt=self._num(self.v["alt"].get()) if self.use_alt.get() else None,
                                    direction=self._num(self.v["dir"].get()) if self.use_dir.get() else None)
        except ValueError:
            raise core.GeotagError(t("bad_coords"))
        except core.GeotagError as exc:
            if mode in ("gpx", "csv") and str(exc) != t("no_source"):
                raise core.GeotagError(t("bad_source", exc))
            raise

    def _prepare(self):
        photos = self.targets()
        if not photos:
            self.say(t("app_nothing_to_do"))
            return None
        try:
            return photos, self.build_source()
        except core.GeotagError as exc:
            self.say(str(exc))
            return None

    def preview(self):
        prepared = self._prepare()
        if not prepared:
            return
        photos, src = prepared
        over = self.overwrite.get()

        def item(path, result, n):
            row = self.rows.get(path)
            if row is None:
                return
            status, pos, taken, existing = result if len(result) == 4 else ("error:" + str(result[1]), None, None, None)
            row["taken"] = taken or row["taken"]
            row["new"] = pos if status == "ok" else None
            row["status"] = t("would_write") if status == "ok" else (t("res_error") + ": " + status[6:] if status.startswith("error") else t("res_" + status))
            self.refresh_row(path)

        self.start_job(photos, lambda p: core.plan_photo(p, src, over), item, lambda c: self.sync_map())

    def run(self):
        if not self.confirm_notice():
            return
        prepared = self._prepare()
        if not prepared:
            return
        photos, src = prepared
        backup, over = self.backup.get(), self.overwrite.get()
        counts = {"ok": 0, "skip": 0, "err": 0}

        def item(path, result, n):
            status, pos, detail = result if len(result) == 3 else ("error", None, str(result[1]))
            row = self.rows.get(path)
            counts["ok" if status in ("ok", "ok_xmp") else ("err" if status == "error" else "skip")] += 1
            if row is not None:
                row["status"] = t("res_" + status) + (" " + detail if detail else "")
                if status in ("ok", "ok_xmp"):
                    row["existing"], row["new"], row["moved"] = pos, None, None
                self.refresh_row(path)
            self.say("%s: %s %s" % (os.path.basename(path), t("res_" + status), fmt_pos(pos) if pos else detail))

        def done(cancelled):
            self.say(t("summary", ok=counts["ok"], skip=counts["skip"], err=counts["err"]))
            self.sync_map()

        self.start_job(photos, lambda p: core.tag_photo(p, src, backup=backup, overwrite=over), item, done)

    def write_moved(self):
        moved = [p for p, r in self.rows.items() if r["moved"]]
        if not moved:
            self.say(t("app_nothing_moved"))
            return
        if not self.confirm_notice():
            return
        backup = self.backup.get()
        counts = {"ok": 0, "same": 0, "err": 0}

        def worker(path):
            lat, lon = self.rows[path]["moved"]
            return core.set_position(path, lat, lon, None, None, backup)

        def item(path, result, n):
            status, detail = result
            row = self.rows.get(path)
            counts["ok" if status in ("ok", "ok_xmp") else ("err" if status == "error" else "same")] += 1
            if row is not None:
                row["status"] = t("res_" + status) + (" " + detail if detail else "")
                if status != "error":
                    row["existing"], row["moved"] = core.read_gps(path), None
                self.refresh_row(path)

        def done(cancelled):
            self.say(t("wb_summary", ok=counts["ok"], same=counts["same"], err=counts["err"]))
            self.sync_map()

        self.start_job(moved, worker, item, done)

    def restore(self):
        photos = self.targets()
        if not photos:
            self.say(t("app_nothing_to_do"))
            return
        if not messagebox.askyesno(t("restore_btn"), t("restore_confirm", len(photos))):
            return
        counts = {"ok": 0, "skip": 0, "err": 0}

        def item(path, result, n):
            status, detail = result
            counts["ok" if status in ("restored", "sidecar_removed") else ("err" if status == "error" else "skip")] += 1
            row = self.rows.get(path)
            if row is not None:
                row["status"] = t("res_" + status)
                self.refresh_row(path)

        def done(cancelled):
            self.say(t("restore_summary", ok=counts["ok"], skip=counts["skip"], err=counts["err"]))
            self.start_job(photos, self._read_meta, self._meta_item, self._meta_done)

        self.start_job(photos, core.restore_photo, item, done)

    def estimate(self):
        sel = self.tree.selection()
        if not self.v["gpx"].get():
            self.say(t("estimate_need_gpx"))
        elif not sel:
            self.say(t("estimate_need_photo"))
        else:
            taken = core.read_datetime(sel[0])
            try:
                lat, lon = self._num(self.v["lat"].get()), self._num(self.v["lon"].get())
                if taken is None:
                    self.say(t("estimate_no_time"))
                    return
                if lat is None or lon is None:
                    self.say(t("bad_coords"))
                    return
                offset, shift, dist = core.estimate_offset(core.parse_gpx(self.v["gpx"].get()), taken, lat, lon)
            except (core.GeotagError, OSError, ValueError) as exc:
                self.say(t("bad_source", exc))
                return
            self.utc.set("%g" % offset)
            self.shift.set("%d" % round(shift))
            self.say(t("estimate_done", offset, round(shift), round(dist)))
            if dist > 100:
                self.say(t("estimate_far", round(dist)))

    # place names
    def load_place_file(self):
        try:
            self.features = geo_lookup.load_features(self.place_file.get())
        except Exception as exc:  # GDAL and JSON errors differ
            self.features = None
            self.say(t("bad_source", exc))
            return
        names = [""] + geo_lookup.property_names(self.features)
        for box in self.field_boxes.values():
            box.configure(values=names)
        self.say(t("app_loaded", len(self.features)))

    def write_places(self):
        if not self.confirm_notice():
            return
        photos = self.targets()
        if not photos:
            self.say(t("app_nothing_to_do"))
            return
        over, backup = self.place_over.get(), self.backup.get()
        if self.place_src.get() == "osm":
            geocoder = geocode.Geocoder(self.place_lang.get(), self.place_url.get().strip() or geocode.PUBLIC_URL)
            self.settings["nominatim"] = self.place_url.get().strip() or geocode.PUBLIC_URL

            def worker(path):
                pos = core.read_gps(path)
                if not pos:
                    return ("no_gps", "", {})
                try:
                    place = geocoder.lookup(pos[0], pos[1])
                except geocode.GeocodeError as exc:
                    return ("error", str(exc), {})
                if not place:
                    return ("no_place", "", {})
                return core.set_place(path, place, over, backup) + (place,)
        else:
            mapping = {k: v.get() for k, v in self.field_vars.items()}
            if self.features is None or not any(mapping.values()):
                self.say(t("app_need_file"))
                return
            lookup = geo_lookup.FeatureLookup(self.features, mapping, self._num(self.place_max.get(), 100))

            def worker(path):
                pos = core.read_gps(path)
                if not pos:
                    return ("no_gps", "", {})
                place = lookup.lookup(pos[0], pos[1])
                if not place:
                    return ("no_place", "", {})
                return core.set_place(path, place, over, backup) + (place,)

        counts = {"ok": 0, "skip": 0, "err": 0}

        def item(path, result, n):
            status, detail, place = result if len(result) == 3 else (result[0], result[1], {})
            counts["ok" if status in ("ok", "ok_xmp") else ("err" if status == "error" else "skip")] += 1
            row = self.rows.get(path)
            if row is not None:
                row["status"] = t("res_" + status)
                if status in ("ok", "ok_xmp"):
                    row["place"] = core.read_place(path)
                self.refresh_row(path)
            self.say("%s: %s %s" % (os.path.basename(path), t("res_" + status), detail))

        self.start_job(photos, worker, item, lambda c: self.say(t("summary", ok=counts["ok"], skip=counts["skip"], err=counts["err"])))

    # export
    def export_files(self):
        chosen = [k for k, v in self.fmt_vars.items() if v.get()]
        if not chosen:
            self.say(t("out_none"))
            return
        if not self.out_dir.get():
            self.say(t("out_no_folder"))
            return
        photos = self.targets()
        folder, base = self.out_dir.get(), self.out_name.get().strip() or "geotagged_photos"
        self.settings["folder"] = folder
        self.settings.save()

        def worker(_):
            records = core.build_records(photos)
            if not records:
                return ["!" + t("layer_none")]
            lines = []
            for key in chosen:
                try:
                    lines.append(t("out_saved", export.export_records(records, key, os.path.join(folder, base))))
                except Exception as exc:  # GDAL raises plain RuntimeError
                    lines.append(t("out_failed", export.FORMATS[key][0], exc))
            return lines

        def item(_, lines, n):
            for line in lines:
                self.say(line.lstrip("!"))

        self.start_job([None], worker, item, lambda c: None)

    def quit(self):
        self.cancel()
        self.settings.save()
        self.root.destroy()


def main(lang=None, argv=None):
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print("No display available:", exc)
        return 1
    App(root, lang=lang)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
