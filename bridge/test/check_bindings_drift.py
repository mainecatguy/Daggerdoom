"""Proves the generated-bindings check catches drift. Only scratch copies of the header are changed.

Usage: python bridge/test/check_bindings_drift.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BRIDGE = Path(__file__).resolve().parents[1]
GENERATOR = BRIDGE / "generate_bindings.py"

# name, text to find, replacement, expected exit code (1 stale, 2 refused by the parser)
CASES = [
    ("constant value", "#define DFB_KIND_HP         11", "#define DFB_KIND_HP         99", 1),
    ("new constant", "#define DFB_HP_HIT ", "#define DFB_NEW_VALUE 7u\n#define DFB_HP_HIT ", 1),
    ("field retyped", "\tint32_t hp_current;       /* Daggerfall's", "\tuint32_t hp_current;      /* Daggerfall's", 1),
    ("fields reordered", "\tint32_t map_pixel_x;\n\tint32_t map_pixel_y;\n\tuint32_t area_seq;\n\tint64_t sent_ns;",
     "\tint32_t map_pixel_y;\n\tint32_t map_pixel_x;\n\tuint32_t area_seq;\n\tint64_t sent_ns;", 1),
    ("field removed", "\tuint32_t committed;   /* 1 if the bundle replaced the save file */\n", "", 1),
    ("function changed", "DFB_API int dfb_flush(dfb_session *session);", "DFB_API int dfb_flush(dfb_session *session, int extra);", 1),
    ("unsupported field", "\tuint32_t committed;", "\tuint16_t values[2];\n\tuint32_t committed;", 2),
    ("unsupported constant", "#define DFB_HP_HIT ", "#define DFB_BAD (1u << 3)\n#define DFB_HP_HIT ", 2),
]


def version_case(source):
    """Bumps whatever protocol version the header has now, so this case cannot fall behind it."""
    found = re.search(r"#define DFB_PROTOCOL_VERSION (\d+)u", source)
    if not found:
        sys.exit("FAIL protocol version: DFB_PROTOCOL_VERSION not found in the header")
    version = int(found.group(1))
    bumped = "#define DFB_PROTOCOL_VERSION %du" % (version + 1)
    message = "protocol version mismatch: header %d, generated bindings %d" % (version + 1, version)
    return ("protocol version", found.group(0), bumped, 1, message)


def check(header):
    run = subprocess.run([sys.executable, str(GENERATOR), "--check", "--header", str(header)], capture_output=True, text=True)
    return run.returncode, (run.stderr or run.stdout).strip().splitlines()[0]


def main():
    source = (BRIDGE / "doomerfall_bridge.h").read_text(encoding="utf-8").replace("\r\n", "\n")
    failed = 0
    with tempfile.TemporaryDirectory() as folder:
        scratch = Path(folder) / "doomerfall_bridge.h"
        scratch.write_text(source, encoding="utf-8", newline="\n")
        code, line = check(scratch)
        print("%s unchanged copy: exit %d (%s)" % ("PASS" if code == 0 else "FAIL", code, line))
        failed += code != 0
        for name, old, new, expected, *message in [version_case(source)] + CASES:
            if source.count(old) != 1:
                print("FAIL %s: test text found %d times" % (name, source.count(old)))
                failed += 1
                continue
            scratch.write_text(source.replace(old, new), encoding="utf-8", newline="\n")
            code, line = check(scratch)
            ok = code == expected and all(text in line for text in message)
            failed += not ok
            print("%s %s: exit %d (%s)" % ("PASS" if ok else "FAIL", name, code, line))
    print("drift check:", "FAILED" if failed else "all cases caught")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
