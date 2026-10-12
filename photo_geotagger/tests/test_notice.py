"""The warning must exist in both languages and the Georgian text must follow the house style."""
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import i18n  # noqa: E402
import notice  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KA_DA = "და"  # the conjunction "da"


class NoticeTests(unittest.TestCase):
    def test_every_section_exists_in_both_languages(self):
        for lang in ("ka", "en"):
            for key in notice.SECTIONS:
                self.assertGreater(len(i18n.t_lang(key + "_h", lang)), 3)
                self.assertGreater(len(i18n.t_lang(key + "_b", lang)), 80)

    def test_covers_the_important_topics(self):
        text = notice.notice_text("en")
        for needle in ("evidence", "forgery", "fraud", "personal data", "critical infrastructure", "_original",
                       "C2PA", "ODbL", "OpenStreetMap", "not legal advice"):
            self.assertIn(needle, text)

    def test_html_escapes_markup(self):
        self.assertNotIn("<script", notice.notice_html("en"))
        self.assertIn("OpenStreetMap contributors", notice.notice_html("en"))

    def test_georgian_strings_have_no_comma_before_da(self):
        for key, (ka, _) in i18n.STRINGS.items():
            self.assertIsNone(re.search(r",\s*" + KA_DA + r"\b", ka), key)

    def test_cli_prints_the_notice(self):
        out = subprocess.run([sys.executable, "-X", "utf8", os.path.join(HERE, "geotag.py"), "--notice", "--lang", "en"],
                             capture_output=True, timeout=60)
        self.assertEqual(out.returncode, 0)
        self.assertIn("Legal risks", out.stdout.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
