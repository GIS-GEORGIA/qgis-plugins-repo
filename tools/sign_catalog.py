#!/usr/bin/env python3
"""Sign catalog.json -> catalog.json.sig (Ed25519).

The Hub refuses a catalog whose signature does not verify, so this must be run after every
change to catalog.json. tools/build.py does it automatically when the private key is found.

The private key is a 32-byte seed in a one-line hex file, kept OUTSIDE the repository:
  - $GIS_GEORGIA_SIGNING_KEY (path), else
  - ~/.gis_georgia/catalog_signing.key

    python tools/sign_catalog.py            # sign (or re-sign) catalog.json
    python tools/sign_catalog.py --verify   # only verify the current signature
    python tools/sign_catalog.py --new-key  # create a key pair (prints the PUBLIC key only)
"""
from __future__ import annotations

import os
import secrets
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gis_georgia_hub import ed25519, signing  # noqa: E402

CATALOG = os.path.join(ROOT, "catalog.json")
SIGNATURE = CATALOG + ".sig"
DEFAULT_KEY = os.path.join(os.path.expanduser("~"), ".gis_georgia", "catalog_signing.key")


def key_path() -> str:
    return os.environ.get("GIS_GEORGIA_SIGNING_KEY") or DEFAULT_KEY


def load_seed(path: str | None = None):
    """The secret seed, or None when there is no key on this machine."""
    path = path or key_path()
    try:
        with open(path, encoding="ascii") as fh:
            seed = bytes.fromhex(fh.read().strip())
    except (OSError, ValueError):
        return None
    return seed if len(seed) == 32 else None


def read_catalog() -> bytes:
    with open(CATALOG, "rb") as fh:
        return fh.read()


def signature_state() -> str:
    """'ok', 'missing', or the reason it does not verify."""
    if not os.path.isfile(SIGNATURE):
        return "missing"
    try:
        with open(SIGNATURE, encoding="utf-8") as fh:
            signing.verify_catalog(read_catalog(), fh.read())
    except signing.SignatureError as exc:
        return str(exc)
    return "ok"


def sign(seed: bytes) -> str:
    """Write catalog.json.sig; return the key id. Refuses a key the Hub does not trust."""
    kid = signing.key_id(ed25519.public_key(seed))
    if kid not in signing.TRUSTED_KEYS:
        raise SystemExit("key {} is not in gis_georgia_hub/signing.py TRUSTED_KEYS - the Hub "
                         "would reject this signature".format(kid))
    text = signing.make_signature_file(seed, read_catalog())
    with open(SIGNATURE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return kid


def main(argv) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    if "--new-key" in argv:
        path = key_path()
        if os.path.exists(path):
            print("a key already exists at {} - not overwriting".format(path))
            return 1
        os.makedirs(os.path.dirname(path), exist_ok=True)
        seed = secrets.token_bytes(32)
        with open(path, "w", encoding="ascii") as fh:
            fh.write(seed.hex() + "\n")
        pub = ed25519.public_key(seed)
        print("private key written to {} (back it up, never commit it)".format(path))
        print('add to TRUSTED_KEYS:  "{}": "{}"'.format(signing.key_id(pub), pub.hex()))
        return 0
    if "--verify" in argv:
        state = signature_state()
        print("catalog.json.sig:", state)
        return 0 if state == "ok" else 1
    seed = load_seed()
    if seed is None:
        print("no signing key at {} (set GIS_GEORGIA_SIGNING_KEY)".format(key_path()))
        return 1
    print("signed catalog.json with key", sign(seed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
