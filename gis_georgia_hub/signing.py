# -*- coding: utf-8 -*-
"""Catalog signature: file format and verification (standard library only).

``catalog.json.sig`` is a small JSON document::

    {"alg": "ed25519", "key_id": "<8 hex>", "signature": "<base64 of 64 bytes>"}

and signs the exact bytes of ``catalog.json``. The Hub trusts only the public keys listed
in TRUSTED_KEYS (add the new key before retiring an old one when rotating).
"""
from __future__ import annotations

import base64
import hashlib
import json

from . import ed25519

SIG_ALG = "ed25519"

# key_id -> 32-byte public key (hex). The matching private key is kept by the maintainer,
# outside the repository.
TRUSTED_KEYS = {
    "672bba13": "de83e274fa8029ca085ee6d7a89268eac5b0dd57e967c0e4517f08df27d30074",
}


class SignatureError(Exception):
    """The catalog is unsigned, tampered with, or signed by an unknown key."""


def key_id(public: bytes) -> str:
    return hashlib.sha256(public).hexdigest()[:8]


def make_signature_file(seed: bytes, data: bytes) -> str:
    public = ed25519.public_key(seed)
    doc = {
        "alg": SIG_ALG,
        "key_id": key_id(public),
        "signature": base64.b64encode(ed25519.sign(seed, data)).decode("ascii"),
    }
    return json.dumps(doc, indent=1) + "\n"


def verify_catalog(data: bytes, sig_text, trusted=None) -> str:
    """Return the key id that signed ``data``, or raise SignatureError."""
    trusted = TRUSTED_KEYS if trusted is None else trusted
    if not sig_text:
        raise SignatureError("the catalog has no signature")
    try:
        doc = json.loads(sig_text if isinstance(sig_text, str) else sig_text.decode("utf-8"))
        if doc.get("alg") != SIG_ALG:
            raise SignatureError("unsupported signature algorithm: {!r}".format(doc.get("alg")))
        kid = str(doc["key_id"])
        signature = base64.b64decode(doc["signature"], validate=True)
    except SignatureError:
        raise
    except Exception:  # noqa: BLE001
        raise SignatureError("the signature file is malformed")
    if kid not in trusted:
        raise SignatureError("the catalog is signed with an unknown key ({})".format(kid))
    if not ed25519.verify(bytes.fromhex(trusted[kid]), data, signature):
        raise SignatureError("the catalog signature does not match: the file was changed")
    return kid
