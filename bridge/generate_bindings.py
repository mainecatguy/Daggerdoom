#!/usr/bin/env python3
"""Generates every bridge definition that is not doomerfall_bridge.h from that header.

    python bridge/generate_bindings.py           rewrite the generated files
    python bridge/generate_bindings.py --check   exit 1 if they are out of date

Outputs:
    bridge/doomerfall_bridge_check.g.h                                compile-time proof and schema hash
    daggerfall-unity-master/Assets/Scripts/Doomerfall/DoomerfallBridge.g.cs   C# constants, structs, imports

The parser is deliberately strict. Anything in the header it does not understand is an error, so a
definition can never be silently left out of C#. The layout it computes is checked by the C++ compiler
through the static_asserts in the .g.h file.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = ROOT / "bridge" / "doomerfall_bridge.h"
CHECK_H = ROOT / "bridge" / "doomerfall_bridge_check.g.h"
BINDINGS = ROOT / "daggerfall-unity-master" / "Assets" / "Scripts" / "Doomerfall" / "DoomerfallBridge.g.cs"

# C type: (C# type, size)
SCALARS = {
    "uint8_t": ("byte", 1), "char": ("byte", 1), "uint16_t": ("ushort", 2), "int32_t": ("int", 4),
    "uint32_t": ("uint", 4), "int64_t": ("long", 8), "uint64_t": ("ulong", 8), "float": ("float", 4),
    "double": ("double", 8), "int": ("int", 4),
}

# void pointers carry no type in the header, so C# must be told what each one is.
VOID_PARAMS = {
    ("dfb_publish_state", "state"): "ref DfbDfState",
    ("dfb_read_state", "out"): "ref DfbUzState",
    ("dfb_bulk_write", "data"): "byte[]",
    ("dfb_bulk_read", "out"): "byte[]",
    ("dfb_surface_write", "bgra"): "byte[]",
}

CS_KEYWORDS = {"out", "ref", "in", "object", "string", "base", "params", "event", "lock", "fixed", "checked"}


class HeaderError(Exception):
    pass


def camel(name):
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


def pascal(name):
    return "".join(part.capitalize() for part in name.split("_"))


def ident(name):
    return "@" + name if name in CS_KEYWORDS else name


def eval_size(expr, constants):
    text = re.sub(r"DFB_\w+", lambda m: str(constants[m.group(0)]["value"]), expr)
    if not re.fullmatch(r"[0-9+\-* ()]+", text):
        raise HeaderError("cannot evaluate array size: " + expr)
    return eval(text, {"__builtins__": {}})


def parse_constants(text):
    constants = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not re.match(r"\s*#\s*define\s+DFB_", line) or re.match(r"\s*#\s*define\s+DFB_API\b", line):
            continue
        m = re.fullmatch(r"\s*#\s*define\s+(DFB_\w+)\s+(-?(?:0x[0-9a-fA-F]+|\d+))(u?)\s*(?:/\*\s*(.*?)\s*\*/)?\s*", line)
        if not m:
            raise HeaderError("line %d: unsupported #define: %s" % (number, line.strip()))
        name, value, unsigned, comment = m.groups()
        if name in constants:
            raise HeaderError("line %d: duplicate constant %s" % (number, name))
        kind = name.startswith("DFB_KIND_")
        constants[name] = {"value": int(value, 0), "type": "ushort" if kind else "uint" if unsigned else "int",
                           "literal": value + unsigned, "comment": comment or ""}
    return constants


def parse_structs(text, constants):
    structs = {}
    for m in re.finditer(r"typedef\s+struct\s+(dfb_\w+)\s*\{(.*?)\}\s*(\w+)\s*;", text, re.S):
        name, body, alias = m.groups()
        if alias != name:
            raise HeaderError("struct %s has a different typedef name %s" % (name, alias))
        fields, offset, align = [], 0, 1
        in_comment = False
        for raw in body.splitlines():
            line = raw.strip()
            if in_comment:
                if "*/" not in line:
                    continue
                line = line.split("*/", 1)[1].strip()
                in_comment = False
            if not line:
                continue
            if line.startswith("/*"):
                if "*/" not in line:
                    in_comment = True
                continue
            f = re.fullmatch(r"(\w+)\s+(\w+)(?:\[([^\]]+)\])?\s*;\s*(?:/\*\s*(.*?)\s*\*/)?", line)
            if not f or f.group(1) not in SCALARS:
                raise HeaderError("struct %s: unsupported field: %s" % (name, line))
            ctype, field, count_expr, comment = f.groups()
            cs, size = SCALARS[ctype]
            count = eval_size(count_expr, constants) if count_expr else None
            if count is not None and size != 1:
                raise HeaderError("struct %s: only byte arrays are supported: %s" % (name, line))
            if count is not None and count <= 0:
                raise HeaderError("struct %s: bad array size: %s" % (name, line))
            offset = (offset + size - 1) // size * size
            align = max(align, size)
            fields.append({"name": field, "ctype": ctype, "cs": cs, "size": size, "count": count,
                           "offset": offset, "comment": comment or ""})
            offset += size * (count or 1)
        if not fields:
            raise HeaderError("struct %s has no fields" % name)
        total = (offset + align - 1) // align * align
        structs[name] = {"name": name, "cs": pascal(name), "fields": fields, "size": total, "align": align}
    return structs


def parse_functions(text):
    stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    functions = []
    for m in re.finditer(r"DFB_API\s+([\w ]+?\**)\s*\b(dfb_\w+)\s*\(([^)]*)\)\s*;", stripped):
        ret, name, args = m.groups()
        params = []
        args = " ".join(args.split())
        if args != "void":
            for arg in args.split(","):
                p = re.fullmatch(r"\s*((?:const\s+)?\w+)\s*(\**)\s*(\w+)\s*", arg)
                if not p:
                    raise HeaderError("%s: unsupported parameter: %s" % (name, arg))
                params.append({"type": " ".join(p.group(1).split()), "stars": len(p.group(2)), "name": p.group(3)})
        functions.append({"ret": ret.strip(), "name": name, "params": params})
    declared = len(re.findall(r"^\s*DFB_API\b", stripped, re.M))
    if declared != len(functions):
        raise HeaderError("parsed %d of %d DFB_API functions" % (len(functions), declared))
    return functions


def payload_map(constants, structs):
    """Finds which payload struct each event kind names in its header comment."""
    used = {}
    for name, constant in constants.items():
        if not name.startswith("DFB_KIND_"):
            continue
        m = re.search(r"payload:\s*(dfb_\w+)", constant["comment"])
        if not m:
            continue
        if m.group(1) not in structs:
            raise HeaderError("%s names unknown payload %s" % (name, m.group(1)))
        used.setdefault(m.group(1), []).append(name)
    payload = next((f for f in structs["dfb_event"]["fields"] if f["name"] == "payload"), None)
    if payload is None:
        raise HeaderError("dfb_event has no payload field")
    for struct_name in used:
        if structs[struct_name]["size"] > payload["count"]:
            raise HeaderError("%s does not fit the %d-byte event payload" % (struct_name, payload["count"]))
        if structs[struct_name]["align"] > 8 or payload["offset"] % structs[struct_name]["align"]:
            raise HeaderError("%s is misaligned in the event payload" % struct_name)
    return used


def schema_hash(constants, structs, functions):
    """FNV-1a over everything that affects the wire or the ABI. Comments do not change it."""
    lines = ["doomerfall-schema-v1"]
    lines += ["const %s %d %s" % (n, c["value"], c["type"]) for n, c in sorted(constants.items())]
    for name, s in sorted(structs.items()):
        lines.append("struct %s %d" % (name, s["size"]))
        lines += ["field %s %s %s %s" % (f["name"], f["ctype"], f["count"], f["offset"]) for f in s["fields"]]
    for f in sorted(functions, key=lambda x: x["name"]):
        lines.append("fn %s %s %s" % (f["ret"], f["name"], ",".join("%s%s" % (p["type"], "*" * p["stars"]) for p in f["params"])))
    h = 0xcbf29ce484222325
    for byte in "\n".join(lines).encode():
        h = ((h ^ byte) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def generate_check(constants, structs, digest):
    out = ["// GENERATED by bridge/generate_bindings.py from doomerfall_bridge.h. Do not edit.",
           "// A failure here means the header changed: run python bridge/generate_bindings.py",
           "",
           "#ifndef DOOMERFALL_BRIDGE_CHECK_G_H",
           "#define DOOMERFALL_BRIDGE_CHECK_G_H",
           "",
           "#include <cstddef>",
           "#include <type_traits>",
           "",
           "#define DFB_SCHEMA_HASH 0x%016xULL" % digest,
           "#define DFB_STALE \"bridge bindings are stale: run python bridge/generate_bindings.py\"",
           ""]
    for name, c in constants.items():
        out.append("static_assert((%s) == (%s), DFB_STALE);" % (name, c["literal"]))
    for name, s in structs.items():
        out.append("")
        out.append("static_assert(sizeof(%s) == %d, DFB_STALE);" % (name, s["size"]))
        for f in s["fields"]:
            ctype = f["ctype"] + ("[%d]" % f["count"] if f["count"] else "")
            out.append("static_assert(offsetof(%s, %s) == %d, DFB_STALE);" % (name, f["name"], f["offset"]))
            out.append("static_assert(std::is_same<decltype(%s::%s), %s>::value, DFB_STALE);" % (name, f["name"], ctype))
    out += ["", "#undef DFB_STALE", "", "#endif", ""]
    return "\n".join(out)


def chunks(field):
    """Splits a byte array into the widest aligned integers, because C# has no safe inline arrays."""
    width = 8 if field["offset"] % 8 == 0 and field["count"] % 8 == 0 else 4 if field["offset"] % 4 == 0 and field["count"] % 4 == 0 else 1
    return width, field["count"] // width


def cs_struct(s, used):
    event = s["name"] == "dfb_event"
    out = ["    [StructLayout(LayoutKind.Explicit, Size = %d)]" % s["size"], "    struct %s" % s["cs"], "    {"]
    for f in s["fields"]:
        note = "  // " + f["comment"] if f["comment"] else ""
        if f["count"] is None:
            out.append("        [FieldOffset(%d)] public %s %s;%s" % (f["offset"], f["cs"], ident(camel(f["name"])), note))
        elif f["name"].startswith("reserved"):
            out.append("        // %d reserved bytes at offset %d" % (f["count"], f["offset"]))
        else:
            width, n = chunks(f)
            cs = {8: "ulong", 4: "uint", 1: "byte"}[width]
            base = camel(f["name"])
            for i in range(n):
                out.append("        [FieldOffset(%d)] public %s %s%d;%s" % (f["offset"] + i * width, cs, base, i, note if i == 0 else ""))
            title = base[0].upper() + base[1:]
            out.append("")
            out.append("        // Copies up to %d bytes in. The rest of the field becomes zero." % f["count"])
            out.append("        public void Set%s(byte[] source, int count)" % title)
            out.append("        {")
            for i in range(n):
                out.append("            %s%d = (%s)DfbBytes.Read(source, count, %d, %d);" % (base, i, cs, i * width, width))
            out.append("        }")
            out.append("")
            out.append("        // Copies all %d bytes out." % f["count"])
            out.append("        public void Copy%s(byte[] destination)" % title)
            out.append("        {")
            for i in range(n):
                out.append("            DfbBytes.Write(destination, %d, %d, %s%d);" % (i * width, width, base, i))
            out.append("        }")
    if event:
        payload = next(f for f in s["fields"] if f["name"] == "payload")
        out.append("")
        out.append("        // Typed views of the payload. Read only the one that matches kind.")
        for struct_name, kinds in used.items():
            view = camel(struct_name[len("dfb_"):])
            out.append("        [FieldOffset(%d)] public %s %s;  // %s" % (payload["offset"], pascal(struct_name), ident(view),
                                                                          ", ".join(k[len("DFB_KIND_"):] for k in kinds)))
    out.append("    }")
    return out


def cs_function(fn, structs):
    ret = SCALARS[fn["ret"]][0] if fn["ret"] in SCALARS else "void" if fn["ret"] == "void" else None
    if ret is None:
        return None
    params = []
    for p in fn["params"]:
        base = p["type"].replace("const ", "")
        name = ident(camel(p["name"]))
        if (fn["name"], p["name"]) in VOID_PARAMS and p["stars"] == 1:
            cs = VOID_PARAMS[(fn["name"], p["name"])]
        elif base == "dfb_session" and p["stars"] == 1:
            cs = "IntPtr"
        elif base == "dfb_session" and p["stars"] == 2:
            cs = "out IntPtr"
        elif base == "char" and p["stars"] == 1:
            cs = "[MarshalAs(UnmanagedType.LPStr)] string"
        elif base in structs and p["stars"] == 1:
            cs = "ref " + structs[base]["cs"]
        elif base in SCALARS and p["stars"] == 1 and "const" not in p["type"]:
            cs = "out " + SCALARS[base][0]
        elif base in SCALARS and p["stars"] == 0:
            cs = SCALARS[base][0]
        else:
            return None
        params.append(cs + " " + name)
    return "        [DllImport(Dll)] public static extern %s %s(%s);" % (ret, fn["name"], ", ".join(params))


def generate_cs(constants, structs, functions, used, digest):
    out = ["// GENERATED by bridge/generate_bindings.py from bridge/doomerfall_bridge.h. Do not edit.",
           "// To change the bridge, edit the header and run: python bridge/generate_bindings.py",
           "",
           "using System;",
           "using System.Runtime.InteropServices;",
           "",
           "namespace DaggerfallWorkshop.Game.Doomerfall",
           "{",
           "    static class Dfb",
           "    {",
           "        public const ulong SchemaHash = 0x%016xUL;" % digest,
           ""]
    for name, c in constants.items():
        note = "  // " + c["comment"] if c["comment"] else ""
        value = c["literal"][:-1] if c["literal"].endswith("u") else c["literal"]
        out.append("        public const %s %s = %s;%s" % (c["type"], name[len("DFB_"):], value, note))
    out += ["", "        // Native size of every generated struct, for the attach check.",
            "        public static readonly Type[] StructTypes = { %s };" % ", ".join("typeof(%s)" % s["cs"] for s in structs.values()),
            "        public static readonly int[] StructSizes = { %s };" % ", ".join(str(s["size"]) for s in structs.values()),
            "    }", "",
            "    static class DfbBytes", "    {",
            "        public static ulong Read(byte[] source, int count, int offset, int width)", "        {",
            "            ulong value = 0;",
            "            for (int i = 0; i < width && offset + i < count && offset + i < source.Length; i++)",
            "                value |= (ulong)source[offset + i] << (8 * i);",
            "            return value;", "        }", "",
            "        public static void Write(byte[] destination, int offset, int width, ulong value)", "        {",
            "            for (int i = 0; i < width; i++)",
            "                destination[offset + i] = (byte)(value >> (8 * i));",
            "        }", "    }"]
    for s in structs.values():
        out.append("")
        out += cs_struct(s, used if s["name"] == "dfb_event" else {})
    out += ["", "    static class DfbNative", "    {", "        const string Dll = \"doomerfall_bridge\";", ""]
    skipped = []
    for fn in functions:
        line = cs_function(fn, structs)
        if line:
            out.append(line)
        else:
            skipped.append(fn["name"])
    if skipped:
        out += ["", "        // Not imported, because their pointers have no safe C# form: " + ", ".join(skipped)]
    out += ["    }", "}", ""]
    return "\n".join(out)


def build(header):
    text = header.read_text(encoding="utf-8")
    constants = parse_constants(text)
    structs = parse_structs(text, constants)
    functions = parse_functions(text)
    if "dfb_event" not in structs:
        raise HeaderError("dfb_event not found")
    used = payload_map(constants, structs)
    digest = schema_hash(constants, structs, functions)
    return {CHECK_H: generate_check(constants, structs, digest),
            BINDINGS: generate_cs(constants, structs, functions, used, digest)}


def version_mismatch(generated):
    """Names both protocol versions when the C# bindings on disk were generated for another one."""
    if not BINDINGS.exists():
        return ""
    pattern = r"PROTOCOL_VERSION = (\d+);"
    built = re.search(pattern, BINDINGS.read_text(encoding="utf-8"))
    wanted = re.search(pattern, generated)
    if not built or not wanted or built.group(1) == wanted.group(1):
        return ""
    return " (protocol version mismatch: header %s, generated bindings %s)" % (wanted.group(1), built.group(1))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail if the generated files are out of date")
    parser.add_argument("--header", type=Path, default=HEADER, help="header to read (for testing drift on a scratch copy)")
    args = parser.parse_args()
    try:
        outputs = build(args.header)
    except (HeaderError, KeyError, OSError) as error:
        print("bridge bindings: error: %s" % error, file=sys.stderr)
        return 2
    if args.check:
        stale = []
        for path, content in outputs.items():
            current = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else None
            if current != content:
                stale.append(path.relative_to(ROOT).as_posix())
        if stale:
            print("bridge bindings are STALE%s: %s" % (version_mismatch(outputs[BINDINGS]), ", ".join(stale)),
                  file=sys.stderr)
            print("doomerfall_bridge.h changed. Run: python bridge/generate_bindings.py", file=sys.stderr)
            return 1
        print("bridge bindings are up to date")
        return 0
    for path, content in outputs.items():
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        print("wrote", path.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
