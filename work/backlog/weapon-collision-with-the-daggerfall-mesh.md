# Weapon collision with the Daggerfall mesh

**Waiting on:** remaining collision mismatches, since better sector fit may reduce this work.

Bullets, rails, and projectiles should collide with the visible mesh, through engine hooks so weapon mods need no changes. Test hitscan, then projectiles, and measure the cost with large numbers of shots. Then check monster sight, splash damage, bouncing, and impact marks. Currently 142 of 200 test bullets land on the visible surface.
