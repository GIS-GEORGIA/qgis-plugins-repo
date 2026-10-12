"""Standalone command line / Tk entry point. Works without QGIS:

    python geotag.py --lang en --lat 41.7151 --lon 44.8271 photo.jpg folder/
    python geotag.py --gpx track.gpx --utc-offset 4 -r photos/
    python geotag.py --csv points.csv photos/
    python geotag.py --read photos/
    python geotag.py            (no arguments: opens a small window)
"""
import argparse
import os
import sys

try:
    from . import core, i18n
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import core
    import i18n

t = i18n.t


def _lang_from_argv(argv):
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--lang="):
            return a.split("=", 1)[1]
    return os.environ.get("GEOTAG_LANG", "ka")


def _fmt_pos(pos):
    alt = "" if pos[2] is None else ", %.1f m" % pos[2]
    return "%.6f, %.6f%s" % (pos[0], pos[1], alt)


def run_cli(argv):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    i18n.set_lang(_lang_from_argv(argv))
    ap = argparse.ArgumentParser(description=t("cli_desc"))
    ap.add_argument("paths", nargs="*", help=t("cli_paths"))
    ap.add_argument("--lang", choices=("ka", "en"), default=i18n.LANG)
    ap.add_argument("--lat", type=float, help=t("lat"))
    ap.add_argument("--lon", type=float, help=t("lon"))
    ap.add_argument("--alt", type=float, help=t("alt"))
    ap.add_argument("--gpx", help=t("src_gpx"))
    ap.add_argument("--csv", help=t("src_csv"))
    ap.add_argument("--utc-offset", type=float, default=0, help=t("utc_offset"))
    ap.add_argument("--shift", type=float, default=0, help=t("shift"))
    ap.add_argument("--max-gap", type=float, default=600, help=t("max_gap"))
    ap.add_argument("-r", "--recursive", action="store_true", help=t("cli_recursive"))
    ap.add_argument("--read", action="store_true", help=t("cli_read"))
    ap.add_argument("--out", help=t("cli_out"))
    ap.add_argument("--no-backup", action="store_true", help=t("cli_nobackup"))
    ap.add_argument("--gui", action="store_true", help=t("cli_gui"))
    args = ap.parse_args(argv)

    if args.gui or not argv:
        return run_gui(args.lang)
    photos = core.collect_photos(args.paths, args.recursive)
    if not photos:
        print(t("no_files"))
        return 2

    if args.read:
        for p in photos:
            pos = core.read_gps(p)
            print("%s: %s" % (p, _fmt_pos(pos) if pos else t("no_gps")))
        return 0

    try:
        if args.gpx:
            src = core.load_source("gpx", file=args.gpx, utc_offset=args.utc_offset,
                                   shift=args.shift, max_gap=args.max_gap)
        elif args.csv:
            src = core.load_source("csv", file=args.csv)
        elif args.lat is not None and args.lon is not None:
            src = core.load_source("fixed", lat=args.lat, lon=args.lon, alt=args.alt)
        else:
            print(t("cli_need_source"))
            return 2
    except core.GeotagError as exc:
        print(t("bad_source", exc))
        return 2

    ok = skip = err = 0
    for p in photos:
        status, pos, detail = core.tag_photo(p, src, backup=not args.no_backup, out_dir=args.out)
        info = _fmt_pos(pos) if pos else detail
        print("%s: %s %s" % (p, t("res_" + status), info))
        if status == "ok":
            ok += 1
        elif status == "error":
            err += 1
        else:
            skip += 1
    print(t("summary", ok=ok, skip=skip, err=err))
    return 1 if err else 0


def run_gui(lang="ka"):
    import tkinter as tk
    from tkinter import filedialog, ttk

    i18n.set_lang(lang)
    root = tk.Tk()
    files, widgets = [], {}
    var = {k: tk.StringVar() for k in ("lat", "lon", "alt", "lang")}
    var["lang"].set(i18n.LANG)
    backup = tk.BooleanVar(value=True)
    log = tk.Text(root, height=10, width=70)

    def add():
        files.extend(filedialog.askopenfilenames(filetypes=[(t("photo_filter"), "*.jpg *.jpeg")]))
        listing.configure(text="\n".join(os.path.basename(f) for f in files[-6:]))

    def folder():
        d = filedialog.askdirectory()
        if d:
            files.extend(core.collect_photos([d]))
            listing.configure(text="%d" % len(files))

    def write():
        try:
            src = core.load_source("fixed", lat=float(var["lat"].get().replace(",", ".")),
                                   lon=float(var["lon"].get().replace(",", ".")),
                                   alt=float(var["alt"].get().replace(",", ".")) if var["alt"].get() else None)
        except ValueError:
            log.insert("end", t("bad_coords") + "\n")
            return
        if not files:
            log.insert("end", t("no_files") + "\n")
            return
        ok = 0
        for p in files:
            status, pos, detail = core.tag_photo(p, src, backup=backup.get())
            ok += status == "ok"
            log.insert("end", "%s: %s %s\n" % (os.path.basename(p), t("res_" + status), detail))
        log.insert("end", t("summary", ok=ok, skip=0, err=len(files) - ok) + "\n")

    def retitle(*_):
        i18n.set_lang(var["lang"].get())
        root.title(t("title"))
        for key, w in widgets.items():
            w.configure(text=t(key))

    frm = ttk.Frame(root, padding=8)
    frm.pack(fill="both", expand=True)
    widgets["lang"] = ttk.Label(frm)
    widgets["lang"].grid(row=0, column=0, sticky="w")
    ttk.Combobox(frm, textvariable=var["lang"], values=("ka", "en"), width=5, state="readonly"
                 ).grid(row=0, column=1, sticky="w")
    widgets["add_files"] = ttk.Button(frm, command=add)
    widgets["add_files"].grid(row=1, column=0, sticky="we")
    widgets["add_folder"] = ttk.Button(frm, command=folder)
    widgets["add_folder"].grid(row=1, column=1, sticky="we")
    listing = ttk.Label(frm, justify="left")
    listing.grid(row=2, column=0, columnspan=2, sticky="w")
    for r, key in enumerate(("lat", "lon", "alt"), start=3):
        widgets[key] = ttk.Label(frm)
        widgets[key].grid(row=r, column=0, sticky="w")
        ttk.Entry(frm, textvariable=var[key]).grid(row=r, column=1, sticky="we")
    widgets["backup"] = ttk.Checkbutton(frm, variable=backup)
    widgets["backup"].grid(row=6, column=0, columnspan=2, sticky="w")
    widgets["run"] = ttk.Button(frm, command=write)
    widgets["run"].grid(row=7, column=0, columnspan=2, sticky="we")
    log.pack(fill="both", expand=True, padx=8, pady=8)
    var["lang"].trace_add("write", retitle)
    retitle()
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(run_cli(sys.argv[1:]))
