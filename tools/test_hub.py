#!/usr/bin/env python3
"""Unit tests for the GIS Georgia Hub catalog logic (plain Python, no QGIS needed):

    python tools/test_hub.py
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gis_georgia_hub import catalog, ed25519, i18n, signing  # noqa: E402

with open(os.path.join(ROOT, "catalog.json"), encoding="utf-8") as fh:
    RAW = fh.read()
DOC = json.loads(RAW)
PLUGINS = DOC["plugins"]


def entry(**kw):
    base = {"id": "p", "name": "P", "version": "1.0", "qgis_min": "3.40", "qgis_max": "4.99",
            "download": {"url": "https://plugins.qgis.ge/plugins/p.zip", "sha256": "0" * 64}}
    base.update(kw)
    return base


class Versions(unittest.TestCase):
    def test_compare(self):
        c = catalog.compare_versions
        self.assertEqual(c("1.0", "1.0.0"), 0)
        self.assertEqual(c("1.10", "1.9"), 1)
        self.assertEqual(c("0.3.1", "0.3.0"), 1)
        self.assertEqual(c("1.2", "1.2.1"), -1)
        self.assertEqual(c("v2.0", "1.99.9"), 1)
        self.assertEqual(c("1.0", "1.0"), 0)

    def test_qgis_range(self):
        e = entry()
        self.assertTrue(catalog.qgis_compatible(e, "3.44.5"))
        self.assertTrue(catalog.qgis_compatible(e, "4.2.2"))
        self.assertTrue(catalog.qgis_compatible(e, "3.40.0"))
        self.assertFalse(catalog.qgis_compatible(e, "3.34.9"))
        self.assertFalse(catalog.qgis_compatible(e, "5.0.0"))
        self.assertTrue(catalog.qgis_compatible(entry(qgis_min="", qgis_max=""), "2.18"))
        self.assertTrue(catalog.qgis_compatible(e, ""))


class States(unittest.TestCase):
    def test_states(self):
        e = entry()
        self.assertEqual(catalog.plugin_state(e, None, "3.44.5"), catalog.NOT_INSTALLED)
        self.assertEqual(catalog.plugin_state(e, "1.0", "3.44.5"), catalog.INSTALLED)
        self.assertEqual(catalog.plugin_state(e, "1.1", "3.44.5"), catalog.INSTALLED)  # newer local
        self.assertEqual(catalog.plugin_state(e, "0.9", "3.44.5"), catalog.UPDATE)
        self.assertEqual(catalog.plugin_state(e, None, "3.30.0"), catalog.INCOMPATIBLE)
        self.assertEqual(catalog.plugin_state(entry(id=catalog.SELF_ID), "0.1", "3.44.5"), catalog.SELF)

    def test_updates_exclude_self_and_current(self):
        ps = [entry(id="a", version="2.0"), entry(id="b", version="1.0"),
              entry(id=catalog.SELF_ID, version="9.0")]
        got = catalog.updates(ps, {"a": "1.0", "b": "1.0", catalog.SELF_ID: "0.1"}, "3.44.5")
        self.assertEqual([p["id"] for p in got], ["a"])


class Filtering(unittest.TestCase):
    def test_real_catalog_has_the_hub(self):
        self.assertIn(catalog.SELF_ID, [p["id"] for p in PLUGINS])

    def test_search_finds_by_name_tag_algorithm_and_georgian(self):
        def ids(**kw):
            return [p["id"] for p in catalog.filter_plugins(PLUGINS, {}, "3.44.5", **kw)]
        self.assertIn("calculate_geometry", ids(text="calculate geometry"))
        self.assertIn("georgian_cadastre", ids(text="cadastre parcels"))
        self.assertIn("postgis_manager", ids(text="pg_dump"))
        self.assertIn("transliterator", ids(text="transliterate_field"))
        self.assertTrue(ids(text="ტრანსლიტერაცია"))
        self.assertEqual(ids(text="zzzz-no-such-thing"), [])
        self.assertEqual(len(ids()), len(PLUGINS))

    def test_modes_and_category(self):
        installed = {"transliterator": "1.0"}
        by = lambda mode, **kw: [p["id"] for p in catalog.filter_plugins(  # noqa: E731
            PLUGINS, installed, "3.44.5", mode=mode, **kw)]
        # the Hub itself is always "installed" (it is running)
        self.assertEqual(by("installed"), [catalog.SELF_ID, "transliterator"])
        self.assertEqual(by("updates"), ["transliterator"])  # catalog version is newer than 1.0
        self.assertNotIn("transliterator", by("available"))
        cat = PLUGINS[1]["category"]
        self.assertTrue(all(p["category"] == cat for p in catalog.filter_plugins(
            PLUGINS, {}, "3.44.5", category=cat)))
        self.assertIn(cat, catalog.categories(PLUGINS))


class Texts(unittest.TestCase):
    def test_details_html_both_languages_and_escaping(self):
        for lang in ("ka", "en"):
            for p in PLUGINS:
                html = catalog.details_html(p, lang, catalog.NOT_INSTALLED)
                self.assertIn(catalog.escape(p["version"]), html)
                self.assertNotIn("<script", html.lower())
        e = entry(emoji="<b>", summary="x", description={"en": "<script>alert(1)</script>"},
                  processing={"provider_name": "P", "algorithms": [{"id": 'a"b:c', "title": "T<>"}]})
        html = catalog.details_html(e, "en", catalog.INSTALLED, "1.0")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn('href="alg:a&quot;b:c"', html)

    def test_algorithm_links_for_processing_plugins(self):
        p = next(x for x in PLUGINS if x["id"] == "owners_analyzer")
        html = catalog.details_html(p, "en", catalog.INSTALLED, "1.3.1")
        for a in p["processing"]["algorithms"]:
            self.assertIn('href="alg:{}"'.format(a["id"]), html)

    def test_i18n_has_both_languages_and_formats(self):
        self.assertEqual(i18n.t("busy", "xx"), i18n.t("busy", "en"))
        self.assertIn("Calc", i18n.t("done_installed", "en", name="Calc", version="1"))
        self.assertEqual(i18n.t("no_such_key"), "no_such_key")
        self.assertEqual(i18n.resolve_lang("ka_GE"), "ka")
        self.assertEqual(i18n.resolve_lang("en_US"), "en")
        self.assertEqual(i18n.resolve_lang("ka_GE", saved="en"), "en")
        for key, val in i18n._S.items():
            self.assertTrue(val.get("ka") and val.get("en"), key)
            self.assertNotIn(", და", val["ka"], key)

    def test_self_update_note(self):
        me = next(p for p in PLUGINS if p["id"] == catalog.SELF_ID)
        old = catalog.details_html(me, "en", catalog.SELF, "0.0.1")
        self.assertIn("Plugin Manager", old)
        same = catalog.details_html(me, "en", catalog.SELF, me["version"])
        self.assertNotIn("is available", same)

    def test_human_size(self):
        self.assertTrue(catalog.human_size(500, "en").startswith("1 "))
        self.assertIn("MB", catalog.human_size(3 * 1024 * 1024, "en"))


class ParseAndCache(unittest.TestCase):
    def test_parse_real_catalog(self):
        self.assertEqual(len(catalog.parse_catalog(RAW)["plugins"]), len(PLUGINS))

    def test_parse_rejects_bad_input(self):
        for bad in ("not json", "[]", json.dumps({"schema": 99, "plugins": []}),
                    json.dumps({"schema": 1}),
                    json.dumps({"schema": 1, "plugins": [{"id": "x"}]}),
                    json.dumps({"schema": 1, "plugins": [{"id": "x", "name": "n", "version": "1",
                                                           "download": {"url": "u"}}]})):
            with self.assertRaises(catalog.CatalogError, msg=bad):
                catalog.parse_catalog(bad)

    def test_cache_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "catalog.json")
            self.assertIsNone(catalog.load_cache(path))
            catalog.save_cache(path, RAW)
            self.assertEqual(len(catalog.load_cache(path)["plugins"]), len(PLUGINS))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{broken")
            self.assertIsNone(catalog.load_cache(path))



RFC = [  # RFC 8032 section 7.1, tests 1 and 2
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
]


class Ed25519(unittest.TestCase):
    def test_rfc8032_vectors(self):
        for sk, pk, msg, sig in RFC:
            sk, pk, msg, sig = map(bytes.fromhex, (sk, pk, msg, sig))
            self.assertEqual(ed25519.public_key(sk), pk)
            self.assertEqual(ed25519.sign(sk, msg), sig)
            self.assertTrue(ed25519.verify(pk, msg, sig))
            self.assertFalse(ed25519.verify(pk, msg + b"x", sig))

    def test_rejects_garbage_without_raising(self):
        pk = bytes.fromhex(RFC[0][1])
        sig = bytes.fromhex(RFC[0][3])
        for bad_pk, bad_sig in ((pk[:5], sig), (pk, sig[:10]), (b"\xff" * 32, sig), (pk, b"\xff" * 64),
                                (b"", b""), (pk, sig[:32] + b"\xff" * 32)):
            self.assertFalse(ed25519.verify(bad_pk, b"", bad_sig))
        flipped = bytearray(sig)
        flipped[0] ^= 1
        self.assertFalse(ed25519.verify(pk, b"", bytes(flipped)))

    def test_matches_an_independent_implementation(self):
        try:
            from cryptography.hazmat.primitives import serialization as ser
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except ImportError:
            self.skipTest("cryptography is not installed")
        import secrets
        for i in range(12):
            seed, msg = secrets.token_bytes(32), secrets.token_bytes(i * 53)
            key = Ed25519PrivateKey.from_private_bytes(seed)
            pub = key.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
            self.assertEqual(ed25519.public_key(seed), pub)
            self.assertEqual(ed25519.sign(seed, msg), key.sign(msg))
            self.assertTrue(ed25519.verify(pub, msg, key.sign(msg)))


class Signing(unittest.TestCase):
    SEED = bytes.fromhex(RFC[1][0])

    def _keys(self):
        pub = ed25519.public_key(self.SEED)
        return {signing.key_id(pub): pub.hex()}

    def test_roundtrip_and_tamper(self):
        data = b'{"schema": 1}'
        sig = signing.make_signature_file(self.SEED, data)
        self.assertEqual(signing.verify_catalog(data, sig, self._keys()),
                         signing.key_id(ed25519.public_key(self.SEED)))
        with self.assertRaises(signing.SignatureError):
            signing.verify_catalog(data + b" ", sig, self._keys())

    def test_rejections(self):
        data = b"x"
        good = signing.make_signature_file(self.SEED, data)
        cases = {
            "none": None, "empty": "", "not json": "nope", "other alg": good.replace("ed25519", "rsa"),
            "bad base64": good.replace('"signature": "', '"signature": "!!'),
            "unknown key": signing.make_signature_file(bytes(32), data),
        }
        for name, sig in cases.items():
            with self.assertRaises(signing.SignatureError, msg=name):
                signing.verify_catalog(data, sig, self._keys())

    def test_the_published_catalog_verifies_with_the_embedded_key(self):
        with open(os.path.join(ROOT, "catalog.json"), "rb") as fh:
            raw = fh.read()
        with open(os.path.join(ROOT, "catalog.json.sig"), encoding="utf-8") as fh:
            sig = fh.read()
        signing.verify_catalog(raw, sig)
        with self.assertRaises(signing.SignatureError):
            signing.verify_catalog(raw.replace(b"GIS", b"gis", 1), sig)

    def test_trusted_keys_are_well_formed(self):
        for kid, pub in signing.TRUSTED_KEYS.items():
            self.assertEqual(len(bytes.fromhex(pub)), 32)
            self.assertEqual(signing.key_id(bytes.fromhex(pub)), kid)


class SignedCache(unittest.TestCase):
    def setUp(self):
        pub = ed25519.public_key(Signing.SEED)
        self.keys = {signing.key_id(pub): pub.hex()}
        self.verify = lambda data, sig: signing.verify_catalog(data, sig, self.keys)
        self.raw = RAW.replace("\r\n", "\n")
        self.sig = signing.make_signature_file(Signing.SEED, self.raw.encode("utf-8"))

    def test_cache_needs_a_matching_signature(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "catalog.json")
            catalog.save_cache(path, self.raw, self.sig)
            self.assertIsNotNone(catalog.load_cache(path, self.verify))
            with open(path, "a", encoding="utf-8") as fh:  # someone edits the cached catalog
                fh.write(" ")
            self.assertIsNone(catalog.load_cache(path, self.verify))
            catalog.save_cache(path, self.raw)  # signature file removed
            os.remove(path + ".sig")
            self.assertIsNone(catalog.load_cache(path, self.verify))
            self.assertIsNotNone(catalog.load_cache(path))  # without a verifier it still parses

    def test_fetch_verified(self):
        served = {"https://x/catalog.json": self.raw.encode("utf-8"),
                  "https://x/catalog.json.sig": self.sig.encode("utf-8")}
        text, _sig = catalog.fetch_verified(lambda u: served[u], "https://x/catalog.json", self.verify)
        self.assertEqual(text, self.raw)
        served["https://x/catalog.json"] = self.raw.encode("utf-8") + b" "
        with self.assertRaises(signing.SignatureError):
            catalog.fetch_verified(lambda u: served[u], "https://x/catalog.json", self.verify)
        served["https://x/catalog.json"] = b"{}"
        with self.assertRaises(signing.SignatureError):
            catalog.fetch_verified(lambda u: served[u], "https://x/catalog.json", self.verify)


if __name__ == "__main__":
    unittest.main(verbosity=2)
