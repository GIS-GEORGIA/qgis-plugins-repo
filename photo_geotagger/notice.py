"""The warning shown in the dialog, the CLI and the docs. Texts live in i18n.py (Georgian and English)."""
from html import escape

try:
    from . import i18n
except ImportError:  # run as a plain script outside QGIS
    import i18n

VERSION = "1"  # raise it when the text changes in a way people must read again
SECTIONS = tuple("warn_%d" % n for n in range(1, 9))


def notice_text(lang):
    t = i18n.t_lang
    title = t("warn_title", lang)
    parts = [title, "=" * len(title), ""]
    for key in SECTIONS:
        parts += [t(key + "_h", lang), t(key + "_b", lang), ""]
    parts.append(t("warn_not_legal", lang))
    return "\n".join(parts)


def notice_html(lang):
    t = i18n.t_lang
    body = "".join("<h4>%s</h4><p>%s</p>" % (escape(t(k + "_h", lang)), escape(t(k + "_b", lang))) for k in SECTIONS)
    return "<h3>%s</h3>%s<p><i>%s</i></p>" % (escape(t("warn_title", lang)), body, escape(t("warn_not_legal", lang)))
