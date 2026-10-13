"""Standalone command line / Tk entry point. Works without QGIS:

    python geotag.py --lang en --lat 41.7151 --lon 44.8271 photo.jpg folder/
    python geotag.py --gpx track.gpx --utc-offset 4 -r photos/
    python geotag.py --csv points.csv photos/
    python geotag.py --dry-run --gpx track.gpx photos/
    python geotag.py --place-names --place-lang ka photos/
    python geotag.py --notice
    python geotag.py --restore photos/
    python geotag.py --engine exiftool --raw-embed --lat 41.7 --lon 44.8 raw_photos/
    python geotag.py --read photos/
    python geotag.py --lat 41.7 --lon 44.8 photos/ --export gpkg,shp,geojson,csv --export-dir out/
    python geotag.py            (no arguments: opens the full window; same as python app.py)
"""
import argparse
import os
import sys

try:
    from . import core, export, geocode, i18n, notice
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import core
    import export
    import geocode
    import i18n
    import notice

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
    heading = "" if len(pos) < 4 or pos[3] is None else ", %.0f°" % pos[3]
    return "%.6f, %.6f%s%s" % (pos[0], pos[1], alt, heading)


def run_cli(argv):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    i18n.set_lang(_lang_from_argv(argv))
    ap = argparse.ArgumentParser(description=t("cli_desc"), epilog=t("cli_note"))
    ap.add_argument("--notice", action="store_true", help=t("cli_notice"))
    ap.add_argument("paths", nargs="*", help=t("cli_paths"))
    ap.add_argument("--lang", choices=("ka", "en"), default=i18n.LANG)
    ap.add_argument("--lat", type=float, help=t("lat"))
    ap.add_argument("--lon", type=float, help=t("lon"))
    ap.add_argument("--alt", type=float, help=t("alt"))
    ap.add_argument("--direction", type=float, help=t("direction"))
    ap.add_argument("--overwrite", action="store_true", help=t("overwrite"))
    ap.add_argument("--dry-run", action="store_true", help=t("cli_dry"))
    ap.add_argument("--gpx", help=t("src_gpx"))
    ap.add_argument("--csv", help=t("src_csv"))
    ap.add_argument("--utc-offset", type=float, default=0, help=t("utc_offset"))
    ap.add_argument("--shift", type=float, default=0, help=t("shift"))
    ap.add_argument("--max-gap", type=float, default=600, help=t("max_gap"))
    ap.add_argument("-r", "--recursive", action="store_true", help=t("cli_recursive"))
    ap.add_argument("--read", action="store_true", help=t("cli_read"))
    ap.add_argument("--out", help=t("cli_out"))
    ap.add_argument("--no-backup", action="store_true", help=t("cli_nobackup"))
    ap.add_argument("--export", help=t("cli_export"))
    ap.add_argument("--export-dir", default=".", help=t("cli_export_dir"))
    ap.add_argument("--export-name", default="photos", help=t("cli_export_name"))
    ap.add_argument("--engine", choices=("auto", "builtin", "exiftool"), default="auto", help=t("cli_engine"))
    ap.add_argument("--exiftool", default="", help=t("cli_exiftool"))
    ap.add_argument("--raw-embed", action="store_true", help=t("cli_raw_embed"))
    ap.add_argument("--restore", action="store_true", help=t("cli_restore"))
    ap.add_argument("--place-names", action="store_true", help=t("cli_place"))
    ap.add_argument("--place-lang", choices=("ka", "en"), default=None, help=t("cli_place_lang"))
    ap.add_argument("--place-url", default=geocode.PUBLIC_URL, help=t("cli_place_url"))
    ap.add_argument("--place-overwrite", action="store_true", help=t("cli_place_overwrite"))
    ap.add_argument("--gui", action="store_true", help=t("cli_gui"))
    args = ap.parse_args(argv)

    if args.notice:
        print(notice.notice_text(i18n.LANG))
        return 0
    core.CONFIG.update({"engine": args.engine, "exiftool": args.exiftool, "raw_embed": args.raw_embed})
    if args.gui or not argv:
        return run_gui(args.lang)
    photos = core.collect_photos(args.paths, args.recursive)
    if not photos:
        print(t("no_files"))
        return 2

    if not (args.read or args.dry_run):
        print(t("cli_note"), file=sys.stderr)

    if args.restore:
        counts = {"restored": 0, "sidecar_removed": 0, "nothing": 0, "error": 0}
        for p in photos:
            status, detail = core.restore_photo(p)
            counts[status] += 1
            print("%s: %s %s" % (p, t("res_" + status), detail))
        print(t("restore_summary", ok=counts["restored"] + counts["sidecar_removed"], skip=counts["nothing"],
                err=counts["error"]))
        return 1 if counts["error"] else 0

    formats = [k.strip().lower() for k in args.export.split(",") if k.strip()] if args.export else []
    bad = [k for k in formats if k not in export.available()]
    if bad:
        print(t("cli_bad_format", ", ".join(bad)))
        print(t("cli_formats", ", ".join(export.available())))
        return 2

    if args.read:
        for p in photos:
            pos = core.read_gps(p)
            place = ", ".join(core.read_place(p).get(k, "") for k in core.PLACE_FIELDS if core.read_place(p).get(k))
            print("%s: %s%s" % (p, _fmt_pos(pos) if pos else t("no_gps"), " | " + place if place else ""))
        return _export(photos, formats, args)

    has_source = bool(args.gpx or args.csv or (args.lat is not None and args.lon is not None))
    if args.place_names and not has_source:
        _place(photos, args)
        return _export(photos, formats, args)

    try:
        if args.gpx:
            src = core.load_source("gpx", file=args.gpx, utc_offset=args.utc_offset,
                                   shift=args.shift, max_gap=args.max_gap)
        elif args.csv:
            src = core.load_source("csv", file=args.csv)
        elif args.lat is not None and args.lon is not None:
            src = core.load_source("fixed", lat=args.lat, lon=args.lon, alt=args.alt, direction=args.direction)
        else:
            print(t("cli_need_source"))
            return 2
    except core.GeotagError as exc:
        print(t("bad_source", exc))
        return 2

    ok = skip = err = 0
    for p in photos:
        if args.dry_run:
            status, pos, _, existing = core.plan_photo(p, src, args.overwrite)
            detail = status[6:] if status.startswith("error") else ""
            status = "error" if status.startswith("error") else status
            print("%s: %s %s" % (p, t("res_" + status) if status != "ok" else t("would_write"),
                                 _fmt_pos(pos) if pos else detail))
            continue
        status, pos, detail = core.tag_photo(p, src, backup=not args.no_backup, out_dir=args.out,
                                             overwrite=args.overwrite)
        info = _fmt_pos(pos) if pos else detail
        print("%s: %s %s" % (p, t("res_" + status), info))
        if status in ("ok", "ok_xmp"):
            ok += 1
        elif status == "error":
            err += 1
        else:
            skip += 1
    if args.dry_run:
        return 0
    print(t("summary", ok=ok, skip=skip, err=err))
    tagged = [os.path.join(args.out, os.path.basename(p)) if args.out else p for p in photos]
    if args.place_names:
        _place([p for p in tagged if os.path.exists(p)], args)
    if formats:
        _export(tagged, formats, args)
    return 1 if err else 0


def _place(photos, args):
    geocoder = geocode.Geocoder(args.place_lang or i18n.LANG, args.place_url)
    ok = skip = err = 0
    for p in photos:
        pos = core.read_gps(p)
        if not pos:
            print("%s: %s" % (p, t("res_no_gps")))
            skip += 1
            continue
        try:
            place = geocoder.lookup(pos[0], pos[1])
        except geocode.GeocodeError as exc:
            print("%s: %s %s" % (p, t("res_error"), exc))
            err += 1
            continue
        status, detail = core.set_place(p, place, args.place_overwrite, not args.no_backup) if place else ("no_place", "")
        label = t("res_ok") if status in ("ok", "ok_xmp") else (t("res_error") if status == "error" else t("res_" + status))
        print("%s: %s %s" % (p, label, detail or ", ".join(place.values())))
        ok += status in ("ok", "ok_xmp")
        err += status == "error"
        skip += status not in ("ok", "ok_xmp", "error")
    print(t("summary", ok=ok, skip=skip, err=err))


def _export(photos, formats, args):
    if not formats:
        return 0
    records = core.build_records(photos)
    if not records:
        print(t("layer_none"))
        return 1
    os.makedirs(args.export_dir, exist_ok=True)
    for key in formats:
        try:
            path = export.export_records(records, key, os.path.join(args.export_dir, args.export_name))
            print(t("out_saved", path))
        except Exception as exc:  # GDAL raises plain RuntimeError
            print(t("out_failed", key, exc))
    return 0


def run_gui(lang="ka"):
    try:
        from . import app
    except ImportError:
        import app
    return app.main(lang)


if __name__ == "__main__":
    sys.exit(run_cli(sys.argv[1:]))
