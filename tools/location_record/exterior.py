"""Location record card 6: the ledger's town, house, wilderness and far-overworld route (tools/location_ledger/ledger3.py)
run in paired.py's folder, so the exterior chunks and buildings are checked with saves that keep no world table.

usage: exterior.py run NAME [--load] | report NAME [FIRST]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paired  # noqa: E402,F401  (points ledger2 and its modules at the record's folder first)
import ledger3  # noqa: E402

assert ledger3.REVIEW == paired.REVIEW, ledger3.REVIEW

if __name__ == "__main__":
    sys.argv = [sys.argv[0]] + sys.argv[1:]
    src = Path(ledger3.__file__).read_text()
    main = src[src.index('if __name__ == "__main__":'):]
    exec(compile(main.replace('if __name__ == "__main__":', "if True:"), ledger3.__file__, "exec"), ledger3.__dict__)
