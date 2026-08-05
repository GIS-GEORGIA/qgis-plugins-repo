# -*- coding: utf-8 -*-
"""Final step: generate and package the deliverable.

Creates one folder named "<interested party> <today>", exports the A4 layout to
PDF, writes the Excel attachment and copies the user's photos into it.
"""

import datetime
import os
import re
import shutil

from qgis.core import QgsProject, QgsLayoutExporter

from . import layout as layout_mod
from . import excel as excel_mod


def _safe_name(text):
    text = (text or "").strip()
    text = re.sub(r"[<>:\"/\\|?*]+", "_", text)
    return text or "cadastre"


def interested_party(project=None):
    """Read the interested party's name from nakveti.INT_PER_ID."""
    from .styles import normalise
    from .excel import _parse_int_person
    project = project or QgsProject.instance()
    for layer in project.mapLayers().values():
        if normalise(layer.name()) != "nakveti":
            continue
        if "INT_PER_ID" not in layer.fields().names():
            continue
        feat = next(layer.getFeatures(), None)
        if feat is not None:
            name, _ = _parse_int_person(feat["INT_PER_ID"])
            return name
    return ""


def package(out_root, photos=None, excel_data=None, scale=1000,
            layout_name=None, today=None):
    """Build the deliverable folder. Returns (folder, warnings)."""
    warnings = []
    today = today or datetime.date.today().strftime("%Y-%m-%d")
    party = _safe_name(interested_party())
    folder = os.path.join(out_root, f"{party} {today}")
    os.makedirs(folder, exist_ok=True)

    project = QgsProject.instance()
    manager = project.layoutManager()
    layout = manager.layoutByName(layout_name or layout_mod.LAYOUT_NAME)
    if layout is None:
        layout = layout_mod.build_layout(scale=scale)

    # PDF
    pdf_path = os.path.join(folder, f"{party} {today}.pdf")
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.PdfExportSettings()
    settings.dpi = 300
    res = exporter.exportToPdf(pdf_path, settings)
    if res != QgsLayoutExporter.Success:
        warnings.append("PDF export failed.")

    # Excel attachment
    if excel_mod.openpyxl_available():
        try:
            data = excel_data or excel_mod.gather_from_project()
            excel_mod.write_attachment(
                os.path.join(folder, f"danarti_{party} {today}.xlsx"), data)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Excel: {exc}")
    else:
        warnings.append("openpyxl not installed — Excel attachment skipped.")

    # Photos
    if photos:
        photo_dir = os.path.join(folder, "suratebi")
        os.makedirs(photo_dir, exist_ok=True)
        for src in photos:
            try:
                shutil.copy2(src, os.path.join(photo_dir, os.path.basename(src)))
            except OSError as exc:
                warnings.append(f"Photo {os.path.basename(src)}: {exc}")

    return folder, warnings
