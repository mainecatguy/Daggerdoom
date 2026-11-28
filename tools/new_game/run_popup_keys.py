"""Keyboard answers in Daggerfall's yes/no popups shown in Doom, in a real paired New Game.

  run_popup_keys.py [run_new_game options]   e.g. --review DIR --inside-quiet --drla (run it under quiet_run.py)

Uses run_new_game.py's driver, but answers each message box with one key only, the way a player would:
  1st box ("Is this your race?" Yes/No): N alone. Daggerfall must go back to the race list.
  every later yes/no box: Y alone. Race box -> gender, class box -> bio.
  the reputation box after the bio (no buttons, so Y does nothing there, as in Daggerfall): Enter alone -> name. Each answer must change Daggerfall's top window within 3 s, or the run fails.
Prints one line per box and a final PASS/FAIL. Logs are run_new_game's (test-run\\create-df.log, create-uz.log).
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_new_game as ng  # noqa: E402  (window, key and wizard helpers)

VK_Y, VK_N, VK_ENTER = 0x59, 0x4E, 0x0D
NAMES = {VK_Y: "Y", VK_N: "N", VK_ENTER: "Enter"}
EXPECT_AFTER_N = "CreateCharRaceSelect"
INFO_BOX_AFTER = "CreateCharChooseBio"  # The reputation box has no buttons: Enter, Escape or a click closes it, not Y.
answers = []  # (key, window before the box, window after)
failures = []
plain_act = ng.act


def boxes_and_after(df_log):
    """Each message box in order: (window before it, window after it or '')."""
    tops = re.findall(r"ui: top window is (\w+)", ng.read(df_log))
    out = []
    for i, top in enumerate(tops):
        if top == "DaggerfallMessageBox":
            out.append((tops[i - 1] if i else "", tops[i + 1] if i + 1 < len(tops) else ""))
    return out


def act(hwnd, top, tries):
    if "MessageBox" not in top:
        return plain_act(hwnd, top, tries)
    df_log = act.df_log
    seen = boxes_and_after(df_log)
    if tries == 0 or len(answers) < len(seen):
        before = seen[-1][0] if seen else ""
        vk = VK_N if not answers else VK_ENTER if before == INFO_BOX_AFTER else VK_Y
        answers.append((vk, seen[-1][0] if seen else ""))
        act.sent = time.time()
        time.sleep(0.4)  # The box is on screen for a moment, as for a player.
        ng.key(hwnd, vk)
    elif time.time() - act.sent > 3.0:
        failures.append(f"box {len(answers)} ({NAMES[answers[-1][0]]}, after {answers[-1][1]}): did not close in 3 s")
        raise SystemExit(report())
    else:
        time.sleep(0.1)


act.sent = 0.0
act.watched = False  # run_new_game's act reads this through its module's act, which is this function.


def report():
    seen = boxes_and_after(act.df_log)
    for i, (vk, before) in enumerate(answers):
        after = seen[i][1] if i < len(seen) else ""
        print(f"box {i + 1}: after {before}, pressed {NAMES[vk]} alone -> {after or '(still open)'}")
        if vk == VK_N and after != EXPECT_AFTER_N:
            failures.append(f"box {i + 1}: N should go back to {EXPECT_AFTER_N}, went to {after or 'nothing'}")
        if vk != VK_N and after in ("", "DaggerfallMessageBox"):
            failures.append(f"box {i + 1}: {NAMES[vk]} did not close the box")
    if len(answers) < 3:
        failures.append(f"only {len(answers)} boxes answered (expected at least 3: race No, race Yes, class Yes)")
    print("popup keys:", "PASS" if not failures else "FAIL " + "; ".join(failures))
    return 0 if not failures else 1


def main():
    ng.act = act
    act.df_log = ng.REVIEW / "test-run" / "create-df.log"
    sys.argv[1:] = ["create"]
    ng.main()
    return report()


if __name__ == "__main__":
    sys.exit(main())
