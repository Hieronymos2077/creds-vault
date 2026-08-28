#!/usr/bin/env python3
r"""creds: a local, offline secrets broker for AI coding agents on one machine.

Secrets are stored DPAPI-encrypted (bound to the current Windows user account)
in store.bin next to this file. Every access is appended to access.log. Nothing
in this file talks to any network; encryption and decryption are performed
entirely locally by Windows CryptProtectData / CryptUnprotectData.

Why this exists: coding agents constantly need API keys. Pasting them into chat,
committing them to .env files, or scattering them across project folders is how
keys leak. With this broker, agents never see a secret until the moment they
need it, they fetch it by NAME, and every fetch is logged.

Usage:
    creds get <key>              print one secret value to stdout
    creds set <key>              read value from stdin (echo VALUE | creds set my-key)
    creds set <key> --value V    value on the command line (avoid for real secrets)
    creds list [prefix]          list key names (never values)
    creds delete <key>           remove a key
    creds import-json <file>     bulk import {"key": "value", ...}
    creds export-json <file>     decrypt ALL into a plaintext json (emergency use)

Created by Alorny AI (https://alorny.cloud) - Hieronymos Junior Starch, Founder.
Contact: contact@alorny.cloud | WhatsApp +263 71 441 2862
MIT licensed.
"""

import sys
import os
import json
import ctypes
import ctypes.wintypes
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(BASE, "store.bin")
LOG = os.path.join(BASE, "access.log")


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> DATA_BLOB:
    buf = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _crypt(data: bytes, protect: bool) -> bytes:
    inp = _blob(data)
    out = DATA_BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI call failed (wrong Windows user or corrupt store)")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _load() -> dict:
    if not os.path.exists(STORE):
        return {}
    with open(STORE, "rb") as f:
        raw = f.read()
    if not raw:
        return {}
    return json.loads(_crypt(raw, protect=False).decode("utf-8"))


def _save(d: dict):
    enc = _crypt(json.dumps(d, ensure_ascii=False).encode("utf-8"), protect=True)
    tmp = STORE + ".tmp"
    with open(tmp, "wb") as f:
        f.write(enc)
    os.replace(tmp, STORE)


def _log(action: str, key: str):
    try:
        caller = os.environ.get("CREDS_CALLER", "")
        line = f"{datetime.datetime.now().isoformat(timespec='seconds')}\t{action}\t{key}\tpid={os.getppid()}\t{caller}\n"
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd = args[0]

    if cmd == "get":
        if len(args) < 2:
            print("usage: creds get <key>", file=sys.stderr)
            return 1
        key = args[1]
        store = _load()
        if key not in store:
            _log("get-MISS", key)
            print(f"creds: no such key: {key}", file=sys.stderr)
            near = [k for k in store if key.lower() in k.lower()]
            if near:
                print("did you mean: " + ", ".join(sorted(near)[:8]), file=sys.stderr)
            return 2
        _log("get", key)
        print(store[key], end="")
        return 0

    if cmd == "set":
        if len(args) < 2:
            print("usage: creds set <key> [--value V]", file=sys.stderr)
            return 1
        key = args[1]
        if len(args) >= 4 and args[2] == "--value":
            value = args[3]
        else:
            value = sys.stdin.read().strip()
        if not value:
            print("creds: empty value refused", file=sys.stderr)
            return 1
        store = _load()
        action = "set-update" if key in store else "set-new"
        store[key] = value
        _save(store)
        _log(action, key)
        print(f"ok: {key}")
        return 0

    if cmd == "list":
        prefix = args[1] if len(args) > 1 else ""
        store = _load()
        _log("list", prefix or "*")
        for k in sorted(store):
            if k.startswith(prefix):
                print(k)
        return 0

    if cmd == "delete":
        if len(args) < 2:
            print("usage: creds delete <key>", file=sys.stderr)
            return 1
        key = args[1]
        store = _load()
        if key not in store:
            print(f"creds: no such key: {key}", file=sys.stderr)
            return 2
        del store[key]
        _save(store)
        _log("delete", key)
        print(f"deleted: {key}")
        return 0

    if cmd == "import-json":
        if len(args) < 2:
            print("usage: creds import-json <file>", file=sys.stderr)
            return 1
        with open(args[1], "r", encoding="utf-8") as f:
            incoming = json.load(f)
        store = _load()
        added = updated = 0
        for k, v in incoming.items():
            if not isinstance(v, str) or not v:
                continue
            if k in store:
                updated += 1
            else:
                added += 1
            store[k] = v
        _save(store)
        _log("import-json", f"{added}new/{updated}upd")
        print(f"imported: {added} new, {updated} updated, total {len(store)}")
        return 0

    if cmd == "export-json":
        if len(args) < 2:
            print("usage: creds export-json <file>", file=sys.stderr)
            return 1
        store = _load()
        with open(args[1], "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
        _log("export-json", f"{len(store)}keys")
        print(f"WARNING: plaintext export of {len(store)} secrets written to {args[1]}. Delete it when done.")
        return 0

    print(f"creds: unknown command: {cmd}", file=sys.stderr)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
