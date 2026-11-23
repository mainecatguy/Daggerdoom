"""Drives the real UZDoom through the synchronized save, with this script as Daggerfall's side of the bridge.

Uses a small generated IWAD, so it needs no game data. It proves Doom's half, the wire protocol, and failure
handling. It does not prove Daggerfall Unity's half.

usage: save_handshake_test.py <uzdoom.exe> <doomerfall_bridge.dll> <empty work folder>
"""
import ctypes as C, hashlib, json, os, re, struct, subprocess, sys, time, uuid, zipfile
from pathlib import Path

KIND_HP, KIND_REQUEST, KIND_PREPARED, KIND_DONE = 11, 12, 13, 14
LAUNCH_TIMEOUT = 30
START_HP = 100


class Event(C.Structure):
    _fields_ = [("seq", C.c_uint32), ("tic", C.c_uint32), ("kind", C.c_uint16), ("flags", C.c_uint16),
                ("reserved", C.c_uint32), ("payload", C.c_ubyte * 48)]


class DfState(C.Structure):
    _fields_ = [("publish_seq", C.c_uint32), ("df_phase", C.c_uint32), ("heartbeat", C.c_uint64), ("published_ns", C.c_int64),
                ("df_frame", C.c_uint32), ("demo", C.c_uint32), ("hp_current", C.c_int32), ("hp_max", C.c_int32),
                ("hp_applied", C.c_uint32), ("hp_flags", C.c_uint32), ("reserved", C.c_ubyte * 208)]


def make_iwad(path):
    """One square room with a player start. Original test data."""
    info = b'IWad { Name="Doomerfall Save Test" Autoname="dfsavetest" Game="Doom" Config="Doom" Mapinfo="mapinfo/doom2.txt" MustContain="MAP01","DFSAVTST" BannerColors="ff ff ff","00 00 00" }\n'
    verts = [(0, 0), (0, 512), (512, 512), (512, 0)]
    lumps = [("IWADINFO", info), ("DFSAVTST", b"x"), ("PLAYPAL", bytes(i % 256 for i in range(768)) * 14),
             ("COLORMAP", bytes(range(256)) * 34), ("F_START", b""), ("FLOOR0_1", bytes([4]) * 4096), ("F_SKY1", bytes([8]) * 4096),
             ("F_END", b""), ("MAP01", b""), ("THINGS", struct.pack("<hhhhh", 256, 256, 0, 1, 7)),
             ("LINEDEFS", b"".join(struct.pack("<hhhhhhh", i, (i + 1) % 4, 1, 0, 0, i, -1) for i in range(4))),
             ("SIDEDEFS", b"".join(struct.pack("<hh8s8s8sh", 0, 0, b"-", b"-", b"-", 0) for _ in range(4))),
             ("VERTEXES", b"".join(struct.pack("<hh", *v) for v in verts)),
             ("SECTORS", struct.pack("<hh8s8shhh", 0, 128, b"FLOOR0_1", b"FLOOR0_1", 192, 0, 0))]
    body, directory, offset = b"", b"", 12
    for name, data in lumps:
        directory += struct.pack("<ii8s", offset, len(data), name.encode())
        body += data
        offset += len(data)
    path.write_bytes(b"IWAD" + struct.pack("<ii", len(lumps), offset) + body + directory)


def make_control_wad(path):
    """Two seconds into a level, saves once through the function Doom's save menu calls."""
    script = b'''version "4.10"
class DfSaveControl : StaticEventHandler
{
    ui int ticks;
    ui bool done;
    override void UiTick()
    {
        if (done || gamestate != GS_LEVEL || ++ticks < 70) return;
        done = true;
        let saves = SavegameManager.GetManager();
        saves.ReadSaveStrings();
        saves.InsertNewSaveNode();
        saves.DoSave(0, "control");
        saves.RemoveNewSaveNode();
    }
}
'''
    lumps = [("MAPINFO", b'GameInfo { AddEventHandlers = "DfSaveControl" }\n'), ("ZSCRIPT", script)]
    body, directory, offset = b"", b"", 12
    for name, data in lumps:
        directory += struct.pack("<ii8s", offset, len(data), name.encode())
        body += data
        offset += len(data)
    path.write_bytes(b"PWAD" + struct.pack("<ii", len(lumps), offset) + body + directory)


class Peer:
    def __init__(self, dll):
        self.b = C.CDLL(str(dll))
        self.b.dfb_now_ns.restype = C.c_int64
        self.id = "dfsave" + uuid.uuid4().hex[:12]
        self.host, self.s = C.c_void_p(), C.c_void_p()
        for rc in (self.b.dfb_create(self.id.encode(), C.byref(self.host)), self.b.dfb_attach(self.id.encode(), 1, C.byref(self.s))):
            if rc != 0:
                sys.exit(f"bridge setup failed: {rc}")
        self.state = DfState(df_phase=3, hp_current=START_HP, hp_max=100, hp_flags=1)
        self.applied = 0
        self.done = None
        self.request = None

    def close(self):
        self.b.dfb_close(self.s)
        self.b.dfb_close(self.host)

    def pump(self, mode):
        event = Event()
        # A slow reader, so hits are still in the ring when Doom sends its request.
        for _ in range(4):
            if self.b.dfb_receive(self.s, C.byref(event)) != 1:
                break
            payload = bytes(event.payload)
            if event.kind == KIND_HP:
                number, kind, amount = struct.unpack_from("<IIi", payload)
                if number != self.applied + 1:
                    raise RuntimeError(f"hp event {number} after {self.applied}")
                self.applied = number
                self.state.hp_current += -amount if kind == 1 else amount
            elif event.kind == KIND_REQUEST:
                self.request = struct.unpack_from("<II", payload)
                self.answer(mode)
            elif event.kind == KIND_DONE:
                self.done = struct.unpack_from("<II", payload)
        self.state.heartbeat += 1
        self.state.hp_applied = self.applied
        self.b.dfb_publish_state(self.s, C.byref(self.state), C.sizeof(DfState))
        self.b.dfb_flush(self.s)

    def answer(self, mode):
        txn, hp_through = self.request
        if self.applied != hp_through:
            raise RuntimeError(f"barrier broken: applied {self.applied}, Doom sent {hp_through}")
        if mode == "timeout":
            return
        status, count, size = 0, 0, 0
        if mode == "refuse":
            status = 1
        else:
            buffer, got, version = C.create_string_buffer(4096), C.c_uint32(), C.c_uint32()
            if self.b.dfb_bulk_read(self.s, 4, buffer, 4096, C.byref(got), C.byref(version)) != 1:
                raise RuntimeError("no staging path")
            stage = Path(buffer.value.decode())
            (stage / "SaveData.txt").write_text(f'{{"hp":{self.state.hp_current}}}')
            if mode == "df_fail":
                status = 2
            else:
                (stage / "SaveInfo.txt").write_text("character info " * 50)
                (stage / "sub").mkdir()
                (stage / "sub" / "Quest.txt").write_bytes(bytes(range(256)) * 8)
                files = [f for f in stage.rglob("*") if f.is_file()]
                count, size = len(files), sum(f.stat().st_size for f in files)
                if mode == "bad_count":
                    count += 1
        applied = self.applied - 1 if mode == "lost_hp" else self.applied
        body = struct.pack("<IIiiIIiiQ", txn, status, self.state.hp_current, 100, applied, count, 4321, -8765, size)
        event = Event(kind=KIND_PREPARED)
        C.memmove(event.payload, body, len(body))
        self.b.dfb_send(self.s, C.byref(event))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


class Run:
    def __init__(self, exe, dll, work):
        self.exe, self.dll, self.work = exe, dll, work
        self.iwad = work / "dfsavetest.wad"
        make_iwad(self.iwad)
        self.control_wad = work / "dfsavecontrol.wad"
        make_control_wad(self.control_wad)
        self.results = []

    def control_save(self, name, peer=None, load=None):
        """Makes one save through the function Doom's save menu calls, and returns the new file or None."""
        folder = self.work / f"saves_{name}"
        folder.mkdir(exist_ok=True)
        extra = ["-file", str(self.control_wad)]
        if load:
            (folder / load.name).write_bytes(load.read_bytes())
            extra += ["-loadgame", load.name]
        known = {p.name for p in folder.glob("*.zds")}
        self.launch(extra, peer, "ok", name, start_map=not load, savedir=folder, stop_when=lambda: [p for p in folder.glob("*.zds") if p.name not in known])
        new = [p for p in folder.glob("*.zds") if p.name not in known]
        return new[0] if new else None

    def launch(self, extra, peer=None, mode="ok", name="run", start_map=True, savedir=None, stop_when=None):
        log = self.work / f"{name}.log"
        log.unlink(missing_ok=True)
        args = [str(self.exe), "-iwad", str(self.iwad), "-config", str(self.work / "test.ini"), "-savedir", str(savedir or self.work / "saves"),
                "-nosound", "-noautoload", "-noactivate", "+i_pauseinbackground", "0", "+vid_activeinbackground", "1",
                "+vid_lowerinbackground", "0", "+vid_fullscreen", "0", "-width", "320", "-height", "200"] + (["-skill", "3", "+map", "MAP01"] if start_map else []) + extra
        if peer:
            args += ["-dfbridge", peer.id, "-dfbridgelog", str(log)]
        info = subprocess.STARTUPINFO()
        info.dwFlags = subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = 7  # minimized, without activation
        process = subprocess.Popen(args, cwd=self.work, startupinfo=info, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + LAUNCH_TIMEOUT
        try:
            while process.poll() is None and time.monotonic() < deadline:
                if peer:
                    peer.pump(mode)
                time.sleep(0.004)
                if stop_when and stop_when():
                    settle = time.monotonic() + 1.5  # Let the write finish, with the peer still answering.
                    while time.monotonic() < settle:
                        if peer:
                            peer.pump(mode)
                        time.sleep(0.004)
                    process.kill()
                    process.wait()
                    break
        finally:
            timed_out = process.poll() is None
            if timed_out:
                process.kill()
                process.wait()
        return process.returncode, timed_out, log.read_text(errors="replace") if log.exists() else ""

    def check(self, name, ok, detail=""):
        self.results.append((name, bool(ok)))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)

    def save_case(self, name, mode, target, fail=None):
        peer = Peer(self.dll)
        before = sha(target)
        extra = ["-dfsavetest", str(target)] + (["-dfsavetestfail", fail] if fail else [])
        try:
            code, timed_out, log = self.launch(extra, peer, mode, name)
        finally:
            peer.close()
        return before, code, timed_out, log, peer


def main():
    exe, dll, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    work.mkdir(parents=True, exist_ok=True)
    (work / "saves").mkdir(exist_ok=True)
    run = Run(exe, dll, work)
    target = work / "saves" / "bundle.zds"

    before, code, timed_out, log, peer = run.save_case("first_save", "ok", target)
    run.check("first save commits", "committed" in log and target.exists() and not timed_out, f"exit {code}")
    if not target.exists():
        print(log[-1500:])
        return 1
    with zipfile.ZipFile(target) as z:
        names = z.namelist()
        manifest = json.loads(z.read("doomerfall/manifest.json"))
        run.check("zip is valid", z.testzip() is None)
        run.check("Doom parts present", {"info.json", "globals.json", "savepic.png"} <= set(names))
        run.check("Daggerfall files carried", {"doomerfall/daggerfall/SaveData.txt", "doomerfall/daggerfall/SaveInfo.txt", "doomerfall/daggerfall/sub/Quest.txt"} <= set(names))
        run.check("nested file is byte exact", z.read("doomerfall/daggerfall/sub/Quest.txt") == bytes(range(256)) * 8)
        run.check("all 20 in-flight hits were applied before the save", manifest["hp_applied"] == 20 and manifest["hp"] == START_HP - 20, str(manifest["hp"]))
        run.check("Doom's half holds Daggerfall's HP", manifest["doom_hp"] == START_HP - 20, str(manifest["doom_hp"]))
        snapshot = next(z.read(n).decode("utf-8", "replace") for n in names if n.endswith(".map.json"))
        run.check("level snapshot holds the same HP", re.search(r'"health"\s*:\s*80\b', snapshot) is not None)
        run.check("Daggerfall position recorded", manifest["df_world"] == [4321, -8765])
    run.check("no temp file or staging left", not list((work / "saves").glob("*.tmp")) and not list((work / "saves").glob("*.dfstage")))

    good = sha(target)
    for name, mode, fail, expect in [("refused", "refuse", None, "cannot save"), ("daggerfall_write_fails", "df_fail", None, "could not write its save"),
                                     ("daggerfall_silent", "timeout", None, "did not answer"), ("file_count_mismatch", "bad_count", None, "do not match"),
                                     ("hp_barrier_mismatch", "lost_hp", None, "had not applied"), ("doom_zip_fails", "ok", "uz_zip", "could not write"),
                                     ("doom_commit_fails", "ok", "uz_commit", "could not write")]:
        _, code, timed_out, log, peer = run.save_case(name, mode, target, fail)
        run.check(f"{name}: reported", expect in log and "FAILED" in log and not timed_out, f"exit {code}")
        run.check(f"{name}: previous save byte identical", sha(target) == good)
        run.check(f"{name}: Daggerfall told to resume", peer.done is not None and peer.done[1] == 0)
        run.check(f"{name}: cleaned up", not list((work / "saves").glob("*.tmp")) and not list((work / "saves").glob("*.dfstage")))

    _, code, timed_out, log, _ = run.save_case("doom_crash", "ok", target, "uz_crash")
    run.check("crash before the replace: Doom died at the test point", code == 3 and "test crash" in log, f"exit {code}")
    run.check("crash before the replace: previous save byte identical", sha(target) == good)

    _, code, timed_out, log, _ = run.save_case("after_crash", "ok", target)
    run.check("save after the crash commits and replaces", "committed" in log and sha(target) != good)
    run.check("leftovers from the crash are gone", not list((work / "saves").glob("*.tmp")) and not list((work / "saves").glob("*.dfstage")))

    # The bundle must load through UZDoom's stock loader, which ignores the extra entries.
    # Saving again after the load proves the restored player has the bundle's HP (a fresh map has 100).
    resaved = run.control_save("reload", load=target)
    restored = False
    if resaved:
        with zipfile.ZipFile(resaved) as z:
            text = next(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".map.json"))
            restored = re.search(r'"health"\s*:\s*80\b', text) is not None
    run.check("stock loader restores the bundle's Doom half with HP 80", restored, str(resaved))

    # A bridge session on a non-Daggerfall map keeps normal Doom saves.
    peer = Peer(dll)
    try:
        plain = run.control_save("plain_bridge", peer=peer)
    finally:
        peer.close()
    has_extra = True
    if plain:
        with zipfile.ZipFile(plain) as z:
            has_extra = any(n.startswith("doomerfall/") for n in z.namelist())
    run.check("regular map over the bridge: normal save, no handshake", plain and not has_extra and peer.request is None, str(plain))

    # No bridge session at all.
    stock = run.control_save("stock")
    has_extra = True
    if stock:
        with zipfile.ZipFile(stock) as z:
            has_extra = any(n.startswith("doomerfall/") for n in z.namelist())
    run.check("no bridge: normal save", stock and not has_extra, str(stock))

    failed = [n for n, ok in run.results if not ok]
    print(f"\n{len(run.results) - len(failed)} of {len(run.results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
