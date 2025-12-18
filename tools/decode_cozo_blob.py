#!/usr/bin/env python3
"""Quick decoder for CozoDB blob files to try to recover JSON/relations.

Usage: python tools\decode_cozo_blob.py C:\path\to\cozo_blob_0.bin C:\path\to\cozo_blob_1.bin

It attempts: UTF-8 decode, zlib.inflate, gzip, zstd (if installed), base64 decode, and searches for JSON-like markers.
"""
import sys
import json
import zlib
import gzip
import base64
import bz2
import lzma
from pathlib import Path

# Optional compressors
try:
    import zstandard as zstd
except Exception:
    zstd = None

try:
    import brotli
except Exception:
    brotli = None

try:
    import lz4.frame as lz4frame
except Exception:
    lz4frame = None


def hexdump(b, length=64):
    return ' '.join(f"{x:02x}" for x in b[:length])


def try_utf8(b):
    try:
        s = b.decode('utf-8', errors='replace')
        return s
    except Exception:
        return None


def try_zlib(b):
    try:
        return zlib.decompress(b)
    except Exception:
        return None


def try_gzip(b):
    try:
        return gzip.decompress(b)
    except Exception:
        return None


def try_base64(b):
    try:
        s = b.decode('ascii', errors='ignore').strip()
        s2 = ''.join(s.split())
        dec = base64.b64decode(s2)
        return dec
    except Exception:
        return None


def try_bz2(b):
    try:
        return bz2.decompress(b)
    except Exception:
        return None


def try_lzma(b):
    try:
        return lzma.decompress(b)
    except Exception:
        return None


def try_brotli(b):
    if not brotli:
        return None
    try:
        return brotli.decompress(b)
    except Exception:
        return None


def try_lz4(b):
    if not lz4frame:
        return None
    try:
        return lz4frame.decompress(b)
    except Exception:
        return None


def try_zstd(b):
    if not zstd:
        return None
    try:
        dctx = zstd.ZstdDecompressor()
        return dctx.decompress(b)
    except Exception:
        return None


def find_json_in_bytes(b):
    try:
        txt = b.decode('utf-8', errors='ignore')
    except Exception:
        txt = None
    if not txt:
        return None
    idx = txt.find('{')
    if idx >= 0:
        # Try progressive parse
        for end in range(idx+100, min(len(txt), idx+20000), 100):
            try:
                candidate = txt[idx:end]
                parsed = json.loads(candidate)
                return parsed
            except Exception:
                continue
    if 'relations' in txt or 'memory' in txt or 'NamedRows' in txt:
        return txt
    return None


def analyze(path: Path):
    print(f"\n=== Analyzing: {path} ===")
    b = path.read_bytes()
    print(f"Size: {len(b)} bytes")
    print("Hex (first 64 bytes):", hexdump(b, 64))

    s = try_utf8(b)
    if s and ('{' in s or 'relations' in s or 'memory' in s or 'NamedRows' in s):
        print("\n-- UTF-8 text looks promising (preview):\n")
        print(s[:2000])
        return

    z = try_zlib(b)
    if z:
        print("\n-- zlib decompressed (first 2000 chars):\n")
        try:
            txt = z.decode('utf-8', errors='ignore')
            print(txt[:2000])
        except Exception:
            print(repr(z[:200]))
        return

    g = try_gzip(b)
    if g:
        print("\n-- gzip decompressed (first 2000 chars):\n")
        try:
            txt = g.decode('utf-8', errors='ignore')
            print(txt[:2000])
        except Exception:
            print(repr(g[:200]))
        return

    zd = try_zstd(b)
    if zd:
        print("\n-- zstd decompressed (first 2000 chars):\n")
        try:
            txt = zd.decode('utf-8', errors='ignore')
            print(txt[:2000])
        except Exception:
            print(repr(zd[:200]))
        return

    bz = try_bz2(b)
    if bz:
        print("\n-- bz2 decompressed (first 2000 chars):\n")
        try:
            txt = bz.decode('utf-8', errors='ignore')
            print(txt[:2000])
        except Exception:
            print(repr(bz[:200]))
        return

    lz = try_lzma(b)
    if lz:
        print("\n-- lzma decompressed (first 2000 chars):\n")
        try:
            txt = lz.decode('utf-8', errors='ignore')
            print(txt[:2000])
        except Exception:
            print(repr(lz[:200]))
        return

    br = try_brotli(b)
    if br:
        print("\n-- brotli decompressed (first 2000 chars):\n")
        try:
            txt = br.decode('utf-8', errors='ignore')
            print(txt[:2000])
        except Exception:
            print(repr(br[:200]))
        return

    l4 = try_lz4(b)
    if l4:
        print("\n-- lz4 decompressed (first 2000 chars):\n")
        try:
            txt = l4.decode('utf-8', errors='ignore')
            print(txt[:2000])
        except Exception:
            print(repr(l4[:200]))
        return

    bb = try_base64(b)
    if bb:
        print("\n-- base64 decoded (preview):\n")
        try:
            txt = bb.decode('utf-8', errors='ignore')
            print(txt[:2000])
        except Exception:
            print(repr(bb[:200]))
        return

    found = find_json_in_bytes(b)
    if found:
        print("\n-- Found JSON-like content:\n")
        if isinstance(found, str):
            print(found[:2000])
        else:
            print(json.dumps(found, indent=2)[:4000])
        return

    out = path.with_suffix(path.suffix + '.raw')
    out.write_bytes(b)
    print(f"\nNo decode succeeded. Wrote raw blob to {out}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python tools\\decode_cozo_blob.py C:\\path\\to\\blob1 [blob2 ...]')
        sys.exit(1)
    for p in sys.argv[1:]:
        analyze(Path(p))