"""Health pickups follow Daggerfall's max HP. This script is Daggerfall's side of the bridge.

Uses the generated IWAD from save_handshake_test.py, so it needs no game data. A control PWAD spawns pickups on
the player and touches them through Doom's real pickup code: the stock Stimpack (a Health item) and DfTestDrlaStim,
DRLA's RLStimpack logic cut down to its health check (A_JumpIfHealthLower (100, 1) / Fail / HealThing(10, 0)).
The fake peer clamps HP to 0..max as Daggerfall's SetHealth does, and changes max HP partway through.

With --drla it runs the same steps on DOOM.WAD E1M1 with DRLA, DRLA Monsters and DRLAX, using DRLA's real
RLStimpack (the "DRLA-style" lines then mean that class).

usage: maxhp_pickup_test.py <uzdoom.exe> <doomerfall_bridge.dll> <empty work folder> [--drla <DOOM.WAD> <GameMods folder>]
"""
import ctypes as C, struct, subprocess, sys, time, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from save_handshake_test import Event, DfState, make_iwad  # noqa: E402

KIND_HP = 11
LAUNCH_TIMEOUT = 30

DECORATE = b'''
ACTOR DfTestDrlaStim : CustomInventory
{
  States
  {
  Spawn:
    TNT1 A -1
    Stop
  Pickup:
    TNT1 A 0 A_JumpIfHealthLower (100, 1)
    Fail
    TNT1 A 0 HealThing(10, 0)
    Stop
  }
}
'''

# Steps run by tic. Each report counts the pickups still on the floor, then removes them.
ZSCRIPT = b'''version "4.10"
class DfMaxHpTest : EventHandler
{
    int t;
    Array<Inventory> items;

    void Put(class<Inventory> cls, int n)
    {
        let mo = players[consoleplayer].mo;
        for (int i = 0; i < n; i++)
        {
            let it = Inventory(Actor.Spawn(cls, mo.pos));
            items.Push(it);
            it.Touch(mo); // The call P_TouchSpecialThing makes when the player walks over it
        }
    }

    void Report(String label)
    {
        int left = 0;
        for (int i = 0; i < items.Size(); i++)
        {
            if (items[i] && !items[i].Owner) left++;
            if (items[i]) items[i].Destroy();
        }
        items.Clear();
        let mo = players[consoleplayer].mo;
        Console.Printf("MAXHP %s left=%d health=%d max=%d", label, left, mo.health, mo.GetMaxHealth(true));
    }

    override void WorldTick()
    {
        let mo = players[consoleplayer].mo;
        if (!mo) return;
        switch (++t)
        {
        case 70: Put("DfTestDrlaStim", 1); break;
        case 75: Report("full_drla"); break;
        case 80: Put("Stimpack", 1); break;
        case 85: Report("full_stock"); break;
        case 90: mo.DamageMobj(null, null, 5, 'None'); break;
        case 120: Put("Stimpack", 3); break;
        case 125: Report("cluster_stock"); break;
        case 150: mo.DamageMobj(null, null, 10, 'None'); break;
        case 180: Put("DfTestDrlaStim", 3); break;
        case 185: Report("cluster_drla"); break;
        case 220: Report("raised_probe"); break;
        case 222: Put("DfTestDrlaStim", 1); break;
        case 227: Report("raised_drla"); break;
        case 260: Put("DfTestDrlaStim", 1); break;
        case 265: Report("over100_drla"); break;
        case 300: Put("Stimpack", 1); break;
        case 305: Report("lowered_stock"); break;
        case 310: Console.Printf("MAXHP done"); break;
        }
    }
}
'''


def make_control_wad(path, drla_class=None):
    """drla_class: test that real class (DRLA's RLStimpack) instead of the cut-down copy."""
    lumps = [("MAPINFO", b'GameInfo { AddEventHandlers = "DfMaxHpTest" }\n')]
    if drla_class:
        lumps.append(("ZSCRIPT", ZSCRIPT.replace(b'"DfTestDrlaStim"', b'"' + drla_class.encode() + b'"')))
    else:
        lumps += [("DECORATE", DECORATE), ("ZSCRIPT", ZSCRIPT)]
    body, directory, offset = b"", b"", 12
    for name, data in lumps:
        directory += struct.pack("<ii8s", offset, len(data), name.encode())
        body += data
        offset += len(data)
    path.write_bytes(b"PWAD" + struct.pack("<ii", len(lumps), offset) + body + directory)


class Peer:
    """Applies Doom's HP events with Daggerfall's clamp. After given events, changes max HP (and HP) like a level up."""

    def __init__(self, dll, hp, hp_max, changes):
        self.b = C.CDLL(str(dll))
        self.id = "dfmaxhp" + uuid.uuid4().hex[:12]
        self.host, self.s = C.c_void_p(), C.c_void_p()
        for rc in (self.b.dfb_create(self.id.encode(), C.byref(self.host)), self.b.dfb_attach(self.id.encode(), 1, C.byref(self.s))):
            if rc != 0:
                sys.exit(f"bridge setup failed: {rc}")
        self.state = DfState(df_phase=3, hp_current=hp, hp_max=hp_max, hp_flags=1)
        self.applied = 0
        self.changes = changes  # {event number: (hp, hp_max)}
        self.events = []

    def close(self):
        self.b.dfb_close(self.s)
        self.b.dfb_close(self.host)

    def pump(self):
        event = Event()
        while self.b.dfb_receive(self.s, C.byref(event)) == 1:
            if event.kind != KIND_HP:
                continue
            number, kind, amount = struct.unpack_from("<IIi", bytes(event.payload))
            if number != self.applied + 1:
                raise RuntimeError(f"hp event {number} after {self.applied}")
            self.applied = number
            hp = self.state.hp_current + (-amount if kind == 1 else amount)
            self.state.hp_current = max(0, min(hp, self.state.hp_max))
            self.events.append(("hit" if kind == 1 else "heal", amount, self.state.hp_current))
            if number in self.changes:
                self.state.hp_current, self.state.hp_max = self.changes[number]
        self.state.heartbeat += 1
        self.state.hp_applied = self.applied
        self.b.dfb_publish_state(self.s, C.byref(self.state), C.sizeof(DfState))
        self.b.dfb_flush(self.s)


def launch(exe, work, game, peer, name):
    out = work / f"{name}.out"
    log = work / f"{name}.log"
    iwad, files, start_map = game
    args = [str(exe), "-iwad", str(iwad), "-file"] + [str(f) for f in files] + ["-config", str(work / "test.ini"),
            "-nosound", "-noautoload", "-noactivate", "-stdout", "-nomonsters", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
            "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "-width", "320", "-height", "200", "-skill", "3", "+map", start_map]
    if peer:
        args += ["-dfbridge", peer.id, "-dfbridgelog", str(log)]
    info = subprocess.STARTUPINFO()
    info.dwFlags = subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 7  # minimized, without activation
    with open(out, "wb") as f:
        process = subprocess.Popen(args, cwd=work, startupinfo=info, stdout=f, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + LAUNCH_TIMEOUT
        try:
            while process.poll() is None and time.monotonic() < deadline:
                if peer:
                    peer.pump()
                time.sleep(0.004)
                text = out.read_text(errors="replace")
                if "MAXHP done" in text or "Execution could not continue" in text:  # The test IWAD's menus also log script errors
                    break
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    text = out.read_text(errors="replace")
    reports = {}
    for line in text.splitlines():
        if line.startswith("MAXHP ") and "left=" in line:
            parts = line.split()
            reports[parts[1]] = {k: int(v) for k, v in (p.split("=") for p in parts[2:])}
    return reports, text, log.read_text(errors="replace") if log.exists() else ""


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    control = work / "dfmaxhpcontrol.wad"
    if len(sys.argv) == 7 and sys.argv[4] == "--drla":
        # Real DOOM.WAD E1M1 with the play folder's DRLA set, testing DRLA's own RLStimpack.
        mods = Path(sys.argv[6])
        make_control_wad(control, "RLStimpack")
        game = (Path(sys.argv[5]), [mods / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")] + [control], "E1M1")
    else:
        make_iwad(work / "dfsavetest.wad")
        make_control_wad(control)
        game = (work / "dfsavetest.wad", [control], "MAP01")
    results = []

    def check(name, ok, detail=""):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)

    def rep(reports, label):
        return reports.get(label, {"left": -1, "health": -1, "max": -1})

    # Daggerfall: 30/30. Events 1-4 are hit 5, heal 5, hit 10, heal 10. Then max HP 50 (a level up), then 120/150,
    # then 20/20 (max lowered).
    peer = Peer(dll, 30, 30, {4: (30, 50), 5: (120, 150), 6: (20, 20)})
    try:
        r, text, log = launch(exe, work, game, peer, "bridge")
    finally:
        peer.close()
    if "MAXHP done" not in text:
        print(text[-3000:])
    check("full HP: DRLA-style stimpack stays on the floor", rep(r, "full_drla")["left"] == 1, str(rep(r, "full_drla")))
    check("full HP: stock stimpack stays on the floor", rep(r, "full_stock")["left"] == 1, str(rep(r, "full_stock")))
    check("Doom's max health is Daggerfall's 30", rep(r, "full_drla")["max"] == 30, str(rep(r, "full_drla")))
    check("3 stock stimpacks at 25/30 in one tic: only 1 taken", rep(r, "cluster_stock")["left"] == 2, str(rep(r, "cluster_stock")))
    check("3 DRLA-style stimpacks at 20/30 in one tic: only 1 taken", rep(r, "cluster_drla")["left"] == 2, str(rep(r, "cluster_drla")))
    check("max HP raised to 50 follows into Doom", rep(r, "raised_probe")["max"] == 50 and rep(r, "raised_probe")["health"] == 30, str(rep(r, "raised_probe")))
    check("after the raise, a DRLA-style stimpack heals at 30/50", rep(r, "raised_drla")["left"] == 0, str(rep(r, "raised_drla")))
    # The peer moves on to 20/20 as soon as it applies this heal, so the report shows that; its event log shows 130.
    check("at 120/150 a DRLA-style stimpack heals (its check says 100)", rep(r, "over100_drla")["left"] == 0 and ("heal", 10, 130) in peer.events,
          str(rep(r, "over100_drla")))
    check("max HP lowered to 20 at 20/20: stock stimpack stays", rep(r, "lowered_stock")["left"] == 1 and rep(r, "lowered_stock")["max"] == 20, str(rep(r, "lowered_stock")))
    heals = [e for e in peer.events if e[0] == "heal"]
    check("Daggerfall got exactly the useful heals: 5, 10, 10, 10", [e[1] for e in heals] == [5, 10, 10, 10], str(peer.events))

    # No bridge: Doom's own rules are unchanged (100 max; at full HP both stay; clusters take one).
    r, text, _ = launch(exe, work, game, None, "stock")
    check("no bridge: max health 100", rep(r, "full_drla")["max"] == 100, str(rep(r, "full_drla")))
    check("no bridge: full HP leaves both stimpacks", rep(r, "full_drla")["left"] == 1 and rep(r, "full_stock")["left"] == 1)
    check("no bridge: clusters take one each", rep(r, "cluster_stock")["left"] == 2 and rep(r, "cluster_drla")["left"] == 2,
          f"{rep(r, 'cluster_stock')} {rep(r, 'cluster_drla')}")

    failed = results.count(False)
    print(f"\n{len(results) - failed} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
