"""Georgian / English strings shared by the QGIS dialog, the CLI and the Tk window."""

LANG = "ka"

STRINGS = {
    "title": ("ფოტოს გეოტეგირება", "Photo Geotagger"),
    "lang": ("ენა", "Language"),
    "photos": ("ფოტოები", "Photos"),
    "add_files": ("ფაილების დამატება", "Add files"),
    "add_folder": ("საქაღალდის დამატება", "Add folder"),
    "clear": ("გასუფთავება", "Clear"),
    "src_coords": ("ერთი და იგივე კოორდინატები", "Fixed coordinates"),
    "src_gpx": ("GPX ტრეკი (დროის მიხედვით)", "GPX track (by time)"),
    "src_csv": ("CSV ცხრილი (ფაილის სახელით)", "CSV table (by file name)"),
    "lat": ("განედი", "Latitude"),
    "lon": ("გრძედი", "Longitude"),
    "alt": ("სიმაღლე (მ)", "Altitude (m)"),
    "pick": ("აიღე რუკიდან", "Pick on map"),
    "pick_hint": ("დააწკაპუნე რუკაზე წერტილის ასარჩევად", "Click on the map to choose a point"),
    "browse": ("არჩევა...", "Browse..."),
    "utc_offset": ("კამერის საათის სხვაობა UTC-სგან (სთ)", "Camera clock offset from UTC (h)"),
    "shift": ("დროის კორექცია (წმ)", "Time correction (s)"),
    "max_gap": ("დროის მაქსიმალური ხარვეზი (წმ)", "Maximum time gap (s)"),
    "backup": ("ორიგინალის ასლის შენახვა", "Keep a backup of the original"),
    "run": ("კოორდინატების ჩაწერა", "Write coordinates"),
    "add_layer": ("ფოტოები შრედ", "Photos as a layer"),
    "close": ("დახურვა", "Close"),
    "photo_filter": ("JPEG ფოტოები (*.jpg *.jpeg)", "JPEG photos (*.jpg *.jpeg)"),
    "res_ok": ("ჩაიწერა", "written"),
    "res_no_time": ("ფოტოს გადაღების დრო არ არის", "no capture time in the photo"),
    "res_no_match": ("ტრეკში შესაბამისი წერტილი არ არის", "no matching track point"),
    "res_no_csv": ("ფაილი CSV-ში არ არის", "file is not listed in the CSV"),
    "res_error": ("შეცდომა", "error"),
    "has_gps": ("კოორდინატები უკვე აქვს", "already has coordinates"),
    "no_gps": ("კოორდინატები არ აქვს", "no coordinates"),
    "summary": ("დასრულდა. ჩაიწერა: {ok}; გამოტოვდა: {skip}; შეცდომა: {err}.",
                "Done. Written: {ok}; skipped: {skip}; errors: {err}."),
    "no_files": ("ფოტო არ არის არჩეული.", "No photos selected."),
    "bad_coords": ("კოორდინატები არასწორია.", "Invalid coordinates."),
    "no_source": ("მიუთითე GPX ან CSV ფაილი.", "Choose a GPX or CSV file."),
    "bad_source": ("წყაროს ფაილი ვერ წაიკითხა: {0}", "Could not read the source file: {0}"),
    "layer_added": ("შრეში დაემატა {0} წერტილი.", "Added {0} points to the layer."),
    "layer_name": ("გეოტეგირებული ფოტოები", "Geotagged photos"),
    "layer_none": ("არცერთ ფოტოს კოორდინატები არ აქვს.", "None of the photos has coordinates."),
    "cli_desc": ("JPEG ფოტოს EXIF-ში GPS კოორდინატების ჩაწერა.",
                 "Write GPS coordinates into the EXIF of JPEG photos."),
    "cli_paths": ("ფოტოები ან საქაღალდეები", "photos or folders"),
    "cli_recursive": ("ქვესაქაღალდეებშიც", "include sub-folders"),
    "cli_read": ("მხოლოდ წაკითხვა, ფაილი არ იცვლება", "read only, do not modify files"),
    "cli_out": ("შედეგის საქაღალდე (ორიგინალი უცვლელი რჩება)", "output folder (originals stay untouched)"),
    "cli_nobackup": ("ასლი არ შეინახო", "do not keep a backup copy"),
    "cli_gui": ("გაშვება ფანჯრით", "open the window"),
    "cli_need_source": ("მიუთითე --lat და --lon, --gpx ან --csv.", "Give --lat and --lon, --gpx or --csv."),
}


def set_lang(lang):
    global LANG
    LANG = "en" if lang == "en" else "ka"


def t(key, *args, **kw):
    ka, en = STRINGS[key]
    text = en if LANG == "en" else ka
    return text.format(*args, **kw) if (args or kw) else text
