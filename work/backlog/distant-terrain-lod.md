# Distant terrain LOD

**Waiting on:** the town stitching task.

Show distant terrain, such as mountains, beyond the loaded treadmill window. The owner's idea is one LOD object in a Source-style 3D skybox. Both the overworld treadmill and dedicated town maps load the same LOD based on the player's true world XY position, so the horizon stays consistent between them.

Check whether UZDoom's sky viewpoints or the existing static-mesh pass is the better way to draw it. Key risks are the seam and popping where the LOD meets real terrain, and keeping parallax correct as the treadmill shifts. A rough seam is acceptable at first. The long-term aim is to hide it by making Doom terrain match Daggerfall's precisely, since terrain is a simple height field with no rooms.
