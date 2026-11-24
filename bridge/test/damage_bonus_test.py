"""Daggerfall's damage bonus scales the damage the player deals in Doom. This script is Daggerfall's side of the bridge.

The fake peer publishes dfb_df_state.damage_bonus_bp. A control PWAD spawns a stock Cyberdemon (4000 health) in front
of the player and hurts it through Doom's real code, logging the health it lost:
  direct    target.DamageMobj(player, player, 10)   the call a projectile or melee hit makes
  hitscan   player.LineAttack(..., 10, ...)          a bullet, with the puff as inflictor
  monster   target.DamageMobj(other monster, ..., 10) not the player's damage, so never scaled
Runs: +100% (10000 bp), +50% (5000 bp), 0 bp, and no bridge session at all.

With --drla it runs on DOOM.WAD E1M1 with DRLA, DRLA Monsters and DRLAX instead of the generated IWAD.

usage: damage_bonus_test.py <uzdoom.exe> <doomerfall_bridge.dll> <empty work folder> [--drla <DOOM.WAD> <GameMods folder>]
"""
import ctypes as C, struct, subprocess, sys, time, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from save_handshake_test import Event, DfState, make_iwad  # noqa: E402

LAUNCH_TIMEOUT = 30

ZSCRIPT = b'''version "4.10"
class DfDamageTest : EventHandler
{
    int t;

    Actor Target()
    {
        let mo = players[consoleplayer].mo;
        return Actor.Spawn("Cyberdemon", mo.Vec3Angle(96, mo.angle));
    }

    void Report(String label, Actor victim, int before)
    {
        Console.Printf("DMGTEST %s lost=%d", label, before - victim.health);
        victim.Destroy();
    }

    override void WorldTick()
    {
        let mo = players[consoleplayer].mo;
        if (!mo) return;
        switch (++t)
        {
        case 70:
        {
            let v = Target();
            int h = v.health;
            v.DamageMobj(mo, mo, 10, 'None');
            Report("direct", v, h);
            break;
        }
        case 75:
        {
            let v = Target();
            int h = v.health;
            mo.LineAttack(mo.angle, 512, 0, 10, 'Hitscan', "BulletPuff");
            Report("hitscan", v, h);
            break;
        }
        case 80:
        {
            let v = Target();
            let other = Actor.Spawn("Cyberdemon", mo.Vec3Angle(400, mo.angle + 180));
            int h = v.health;
            v.DamageMobj(other, other, 10, 'None');
            Report("monster", v, h);
            other.Destroy();
            break;
        }
        case 85: Console.Printf("DMGTEST done"); break;
        }
    }
}
'''


def make_control_wad(path):
    lumps = [("MAPINFO", b'GameInfo { AddEventHandlers = "DfDamageTest" }\n'), ("ZSCRIPT", ZSCRIPT)]
    body, directory, offset = b"", b"", 12
    for name, data in lumps:
        directory += struct.pack("<ii8s", offset, len(data), name.encode())
        body += data
        offset += len(data)
    path.write_bytes(b"PWAD" + struct.pack("<ii", len(lumps), offset) + body + directory)


class Peer:
    """Publishes a live player at 100/100 with a fixed damage bonus, and applies Doom's HP events."""

    def __init__(self, dll, bp):
        self.b = C.CDLL(str(dll))
        self.id = "dfdamage" + uuid.uuid4().hex[:12]
        self.host, self.s = C.c_void_p(), C.c_void_p()
        for rc in (self.b.dfb_create(self.id.encode(), C.byref(self.host)), self.b.dfb_attach(self.id.encode(), 1, C.byref(self.s))):
            if rc != 0:
                sys.exit(f"bridge setup failed: {rc}")
        self.state = DfState(df_phase=3, hp_current=100, hp_max=100, hp_flags=1, damage_bonus_bp=bp)

    def close(self):
        self.b.dfb_close(self.s)
        self.b.dfb_close(self.host)

    def pump(self):
        event = Event()
        while self.b.dfb_receive(self.s, C.byref(event)) == 1:
            if event.kind == 11:  # DFB_KIND_HP
                self.state.hp_applied = struct.unpack_from("<I", bytes(event.payload))[0]
        self.state.heartbeat += 1
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
                if "DMGTEST done" in text or "Execution could not continue" in text:
                    break
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    text = out.read_text(errors="replace")
    reports = {}
    for line in text.splitlines():
        if line.startswith("DMGTEST ") and "lost=" in line:
            parts = line.split()
            reports[parts[1]] = int(parts[2].split("=")[1])
    return reports, text, log.read_text(errors="replace") if log.exists() else ""


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    control = work / "dfdamagecontrol.wad"
    make_control_wad(control)
    if len(sys.argv) == 7 and sys.argv[4] == "--drla":
        mods = Path(sys.argv[6])
        game = (Path(sys.argv[5]), [mods / n for n in ("DoomRL_Arsenal_1.1.5.pk3", "DoomRL_Monsters_Beta_7.3.pk3", "drlax_1.2b.pk3")] + [control], "E1M1")
    else:
        make_iwad(work / "dfsavetest.wad")
        game = (work / "dfsavetest.wad", [control], "MAP01")
    results = []

    def check(name, ok, detail=""):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)

    runs = {}
    for name, bp in (("bonus100", 10000), ("bonus50", 5000), ("bonus0", 0), ("nobridge", None)):
        peer = Peer(dll, bp) if bp is not None else None
        try:
            r, text, log = launch(exe, work, game, peer, name)
        finally:
            if peer:
                peer.close()
        if "DMGTEST done" not in text:
            print(text[-3000:])
        runs[name] = r
        print(f"{name}: {r}", flush=True)
        for line in log.splitlines():
            if "damage bonus:" in line:
                print("   ", line)

    base = runs["nobridge"]
    check("no bridge: direct 10 takes 10", base.get("direct") == 10, str(base))
    check("no bridge: hitscan 10 takes 10", base.get("hitscan") == 10, str(base))
    check("0 bp: exactly the same as no bridge", runs["bonus0"] == base, f"{runs['bonus0']} vs {base}")
    for name, factor in (("bonus100", 2.0), ("bonus50", 1.5)):
        r = runs[name]
        for kind in ("direct", "hitscan"):
            want = int(base.get(kind, -1) * factor)
            check(f"{name}: {kind} scaled x{factor}", r.get(kind) == want, f"got {r.get(kind)}, want {want}")
        check(f"{name}: a monster's damage is not scaled", r.get("monster") == base.get("monster"), f"{r.get('monster')} vs {base.get('monster')}")

    failed = results.count(False)
    print(f"\n{len(results) - failed} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
