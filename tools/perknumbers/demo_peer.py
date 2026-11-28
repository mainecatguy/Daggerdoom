"""Demo for the owner's perk numbers (perknumbers 01): UZDoom with a stand-in Daggerfall character.

usage: python demo_peer.py <uzdoom.exe> <doomerfall_bridge.dll> <run folder> <explosives> <shotguns> -- <uzdoom args...>

Plays as Daggerfall's side of the bridge: it sends a character sheet with the given Explosives and Shotguns skills
(every attribute 50, so attributes change nothing) and keeps the session alive until UZDoom closes. Doom's own rules
(DoomerfallRules.zs) turn the skills into the perks, as with a real Daggerfall character. Perk log lines go to UZDoom's
log file in the run folder, not to the screen.
"""
import ctypes as C, struct, subprocess, sys, time, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perknumbers_test import SHEET_INTS, SHEET_FORMAT_VERSION, STATS_LIVE, SKILLS_BASE, SKILLS_LIVE, SHOTGUNS, EXPLOSIVES  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bridge" / "test"))
from save_handshake_test import Event, DfState  # noqa: E402


def main():
    split = sys.argv.index("--")
    exe, dll, run, expl, shot = sys.argv[1:6]
    run = Path(run)
    run.mkdir(parents=True, exist_ok=True)
    b = C.CDLL(dll)
    sid = "dfdemo" + uuid.uuid4().hex[:12]
    host, s = C.c_void_p(), C.c_void_p()
    if b.dfb_create(sid.encode(), C.byref(host)) or b.dfb_attach(sid.encode(), 1, C.byref(s)):
        sys.exit("bridge setup failed")
    v = [0] * SHEET_INTS
    v[0], v[1], v[2] = SHEET_FORMAT_VERSION, 1, 1
    for i in range(8):
        v[STATS_LIVE + i] = v[STATS_LIVE - 8 + i] = 50
    for base in (SKILLS_BASE, SKILLS_LIVE):
        v[base + SHOTGUNS], v[base + EXPLOSIVES] = int(shot), int(expl)
    data = struct.pack(f"<{SHEET_INTS}i", *v)
    version = C.c_uint32()
    b.dfb_bulk_write(s, 0, data, len(data), C.byref(version))
    state = DfState(df_phase=3, hp_current=100, hp_max=100, hp_flags=1)
    args = [exe, *sys.argv[split + 1:], "-dfbridge", sid, "-dfbridgelog", str(run / "bridge.log")]
    with open(run / "uzdoom.log", "wb") as log:
        p = subprocess.Popen(args, cwd=run, stdout=log, stderr=subprocess.STDOUT)
        event = Event()
        while p.poll() is None:
            while b.dfb_receive(s, C.byref(event)) == 1:
                pass
            state.heartbeat += 1
            b.dfb_publish_state(s, C.byref(state), C.sizeof(DfState))
            b.dfb_flush(s)
            time.sleep(0.01)
    b.dfb_close(s)
    b.dfb_close(host)


if __name__ == "__main__":
    main()
