# -*- coding: utf-8 -*-
"""Ed25519 (RFC 8032) in pure Python: sign and verify, standard library only.

QGIS's Python does not ship ``cryptography``, and the Hub must verify the catalog signature
inside QGIS, so this follows the reference algorithm of RFC 8032 section 6. It is checked
against the RFC test vectors and against an independent implementation (tools/test_hub.py).
Speed is irrelevant here (one verification per catalog download, a few milliseconds).

Verification only needs ``verify``; ``sign`` is used by tools/sign_catalog.py on the
maintainer's machine. The private key (a 32-byte seed) never belongs in the repository.
"""
from __future__ import annotations

import hashlib

_P = 2 ** 255 - 19
_Q = 2 ** 252 + 27742317777372353535851937790883648493


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _sha512_modq(data: bytes) -> int:
    return int.from_bytes(_sha512(data), "little") % _Q


def _inv(x: int) -> int:
    return pow(x, _P - 2, _P)


_D = -121665 * _inv(121666) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)


def _add(P, Q):
    a = (P[1] - P[0]) * (Q[1] - Q[0]) % _P
    b = (P[1] + P[0]) * (Q[1] + Q[0]) % _P
    c = 2 * P[3] * Q[3] * _D % _P
    d = 2 * P[2] * Q[2] % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _mul(s: int, P):
    Q = (0, 1, 1, 0)  # neutral element
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _equal(P, Q) -> bool:
    return ((P[0] * Q[2] - Q[0] * P[2]) % _P == 0
            and (P[1] * Q[2] - Q[1] * P[2]) % _P == 0)


def _recover_x(y: int, sign: int):
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _SQRT_M1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_GY = 4 * _inv(5) % _P
_GX = _recover_x(_GY, 0)
_G = (_GX, _GY, 1, _GX * _GY % _P)


def _compress(P) -> bytes:
    zinv = _inv(P[2])
    x = P[0] * zinv % _P
    y = P[1] * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(data: bytes):
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _expand(seed: bytes):
    h = _sha512(seed)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(seed: bytes) -> bytes:
    """The 32-byte public key for a 32-byte secret seed."""
    if len(seed) != 32:
        raise ValueError("the secret seed must be 32 bytes")
    a, _ = _expand(seed)
    return _compress(_mul(a, _G))


def sign(seed: bytes, message: bytes) -> bytes:
    """A 64-byte signature of ``message``."""
    if len(seed) != 32:
        raise ValueError("the secret seed must be 32 bytes")
    a, prefix = _expand(seed)
    A = _compress(_mul(a, _G))
    r = _sha512_modq(prefix + message)
    R = _compress(_mul(r, _G))
    h = _sha512_modq(R + A + message)
    s = (r + h * a) % _Q
    return R + int.to_bytes(s, 32, "little")


def verify(public: bytes, message: bytes, signature: bytes) -> bool:
    """True only for a valid signature; never raises on malformed input."""
    try:
        if len(public) != 32 or len(signature) != 64:
            return False
        A = _decompress(public)
        if A is None:
            return False
        Rs = signature[:32]
        R = _decompress(Rs)
        if R is None:
            return False
        s = int.from_bytes(signature[32:], "little")
        if s >= _Q:
            return False
        h = _sha512_modq(Rs + public + message)
        return _equal(_mul(s, _G), _add(R, _mul(h, A)))
    except Exception:  # noqa: BLE001 - a verifier answers yes or no
        return False
