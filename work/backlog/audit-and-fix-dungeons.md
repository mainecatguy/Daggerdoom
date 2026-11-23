# Audit and fix dungeons

**Waiting on:** the owner being satisfied that all travel methods are implemented correctly. Do this last, or earlier only if we are low on other tasks.

Run the converter on all non-random mainquest dungeons as well as some random dungeons (say 5) and report what breaks, map size, load time, frame rate, and how often each feature appears, such as teleporters, water, lifts, climbing shafts, and special markers. Use the results to recommend priorities for the dungeon work.

The audit includes fixing what it finds, and must be broken down into steps before it starts.

Outside feedback raised these possible problems. Treat them as unverified until the audit or real data confirms them:

- Large multi-block dungeons may hit practical size or performance limits.
- Stacked floors may cause sliver sectors, sound bleeding through rock, automap clutter, or lighting and fog bleeding between floors.
- Tightly stacked sloped 3D floors may snag actors or show seams.
- Dungeon textures may need runtime swaps by region and dungeon type, and some are animated.
- Editor marker flats may carry teleporter destinations, quest anchors, fixed spawns, and ambient sounds.
- Some original blocks have misaligned doorways, small lips that snag movement, or broken action chains.
- Non-door models with Daggerfall's open-door or close-door action may do nothing in Doom, which could leave a passage shut. `RDBLayout.cs:914` gives them `DaggerfallActionDoorSpecial`, but `action_objects.zs:213-214` handles flags 18 and 20 only for records with a `DFDoor`. Count how many exist and whether any gate progress.
