"""Copy DFU's DFBlock.cs to build output without its FullSerializer (JSON modding) code.

The source file stays untouched. The removed code is not used to read game data.
"""
import re
import sys

source, target = sys.argv[1:3]
text = open(source, encoding="utf-8-sig").read()
text, regions = re.subn(
    r"#region FullSerializer Custom Processors.*?#endregion", "", text, flags=re.S
)
if regions != 1:
    sys.exit("expected exactly one FullSerializer region in DFBlock.cs")
text = re.sub(r"^\s*using FullSerializer;\s*$", "", text, flags=re.M)
text = re.sub(r"\[fsObject\([^\n]*?\)\]", "", text)
open(target, "w", encoding="utf-8").write(text)
