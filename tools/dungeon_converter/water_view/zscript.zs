version "4.10"

// Tints the view while the player's eyes are under water. The Daggerfall mesh draws without
// sector fog, so the 3D floor's own colormap cannot do this. Load only with converted dungeons.
class DFWaterView : EventHandler
{
	override void RenderUnderlay(RenderEvent e)
	{
		let mo = players[consoleplayer].camera;
		if (mo && mo.waterlevel >= 3)
			Screen.Dim(0x12405f, 0.5, 0, 0, Screen.GetWidth(), Screen.GetHeight());
	}
}
