"""Writes a test mod that hurts or heals the player on every tic, so saves happen while HP events are constantly in flight."""
import sys
import zipfile

SCRIPT = """version "4.10"
class SaveCombatHandler : EventHandler
{
	override void WorldTick()
	{
		let p = players[consoleplayer].mo;
		if (!p || level.maptime < 10) return;
		if (level.maptime & 1) p.DamageMobj(null, null, 1, 'None');
		else p.GiveBody(1);
	}
}
"""
with zipfile.ZipFile(sys.argv[1], "w") as pk3:
    pk3.writestr("zscript.zs", SCRIPT)
    pk3.writestr("mapinfo.txt", 'gameinfo { AddEventHandlers = "SaveCombatHandler" }\n')
