"""Writes a test mod that places COUNT dormant monsters around the player, to measure saves in a large fight's state."""
import sys
import zipfile
from pathlib import Path

out, count = Path(sys.argv[1]), int(sys.argv[2])
ZSCRIPT = """version "4.10"
class SaveHordeHandler : EventHandler
{
	override void WorldLoaded(WorldEvent e)
	{
		PlayerPawn pawn = players[consoleplayer].mo;
		if (!pawn) return;
		int side = int(ceil(sqrt(%d))), placed = 0;
		for (int x = 0; x < side && placed < %d; x++)
			for (int y = 0; y < side && placed < %d; y++)
			{
				Vector3 at = (pawn.pos.x + (x - side / 2) * 48 + 96, pawn.pos.y + (y - side / 2) * 48 + 96, pawn.pos.z);
				Actor imp = Actor.Spawn("DoomImp", at);
				if (!imp) continue;
				imp.bSOLID = false;
				imp.bSHOOTABLE = false;
				imp.Deactivate(null);
				placed++;
			}
		Console.Printf("SAVEHORDE placed %%d", placed);
	}
}
""" % (count, count, count)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as pk3:
    pk3.writestr("zscript.zs", ZSCRIPT)
    pk3.writestr("mapinfo.txt", 'gameinfo { AddEventHandlers = "SaveHordeHandler" }\n')
print("wrote", out)
