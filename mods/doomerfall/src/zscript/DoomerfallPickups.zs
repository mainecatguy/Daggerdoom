// Health and cheap ammo that the dungeon converter places in generated Daggerfall maps (PickupExport.cs).
// Each marker becomes one concrete item when the map loads: the DRLA version when DRLA is loaded, else the stock one.
// The concrete class is spawned directly, so DRLA's random spawners (its Clip spawner can give a pistol) never roll,
// and the item exists before the treadmill sorts a revisited space's items (dd_treadmill.cpp StartTown).
// Only generated maps place these editor numbers (MAPINFO.txt).
class DoomerfallPickupMarker : Actor abstract
{
	meta String drlaClass, stockClass;
	property Items: drlaClass, stockClass;

	Default
	{
		+NOBLOCKMAP
		+NOGRAVITY
		+NOINTERACTION
		+NOTONAUTOMAP
		RenderStyle "None";
	}

	override void BeginPlay()
	{
		Super.BeginPlay();
		class<Actor> cls = drlaClass;
		if (cls == null) cls = stockClass;
		if (cls != null) Spawn(cls, Pos, NO_REPLACE);
	}

	States
	{
	Spawn:
		TNT1 A 0;
		Stop;
	}
}

class DoomerfallPickupStimpack : DoomerfallPickupMarker { Default { DoomerfallPickupMarker.Items "RLStimpack", "Stimpack"; } }
class DoomerfallPickupClip : DoomerfallPickupMarker { Default { DoomerfallPickupMarker.Items "RLClip", "Clip"; } }
class DoomerfallPickupShells : DoomerfallPickupMarker { Default { DoomerfallPickupMarker.Items "RLShell", "Shell"; } }
