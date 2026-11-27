// Exports a dungeon's real Daggerfall models, placement, textures, and UVs for UZDoom's opt-in mesh layer.
// Output is <slug>_mesh.pk3: a DFMESH lump plus dfmesh/aAAArRR.png textures. It is derived from game data, so keep it outside the repo.
//
// DFMESH (little endian): "DFM1", char map[8], int textures, batches, vertices;
//   char name[32] per texture; int texture, first, count per batch; float x, up, north, u, v, nx, nup, nnorth per vertex.
// Positions are in the renderer's axis order (Doom x, height, Doom y). Triangles keep Daggerfall Unity's winding.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using DaggerfallConnect;
using DaggerfallConnect.Arena2;
using DaggerfallConnect.Utility;
using DaggerfallWorkshop;

static partial class Program
{
    // DungeonTextureTables.RandomTextureTableClassic with RandomDungeonTextures=0, the default setting.
    static int[] ClassicTextureTable(DFLocation location)
    {
        byte[] indices = { 0, 0, 1, 4, 4, 0, 3, 3, 3, 0 };
        byte[] climateIndices = { 0, 0, 0, 1, 2, 3, 4, 5, 5, 5 };
        short[] archives = { 19, 119, 319, 419, 119 };
        int climate = location.Climate.WorldClimate;
        if (climate == (int)MapsFile.Climates.Ocean) climate = (int)MapsFile.Climates.Swamp;
        int classic = climateIndices[climate - (int)MapsFile.Climates.Ocean];
        int archiveIndex = indices[classic];
        DFRandom.srand(location.Dungeon.RecordElement.Header.LocationId);
        var table = new int[6];
        for (int i = 0; i < 5; i++)
        {
            int offset = DFRandom.random_range_inclusive(0, 4);
            if (offset == 2) offset = 4;
            table[i] = archives[archiveIndex] + offset;
        }
        table[5] = (int)DFLocation.ClimateTextureSet.Interior_Sewer + 100 * indices[climate - (int)MapsFile.Climates.Desert];
        return table;
    }

    // DungeonTextureTables.ApplyTextureTable.
    static int SwapArchive(int archive, int[] table, DFLocation location) => archive switch
    {
        74 => archive + (int)location.Climate.ClimateType,
        119 => table[0], 120 => table[1], 122 => table[2], 123 => table[3], 124 => table[4], 168 => table[5],
        _ => archive,
    };

    const int RuntimeDoorSlots = 2;
    static bool runtimeDungeon;
    static StringBuilder dungeonInfo;

    static int ExportMesh(string arena2, DFLocation location, string outDir, string slug, string[] args)
    {
        int tableAt = Array.IndexOf(args, "--texture-table");
        int[] table = tableAt >= 0 ? args[tableAt + 1].Split(',').Select(int.Parse).ToArray() : ClassicTextureTable(location);
        // --runtime-dungeon: the package loads beside ddruntime.pk3, which already holds the door runtime and two gate models.
        runtimeDungeon = args.Contains("--runtime-dungeon");
        dungeonInfo = new StringBuilder($"map {OutputMapName}\nmapid {location.MapTableData.MapId}\n");
        Console.WriteLine($"climate {location.Climate.WorldClimate} base {location.Climate.ClimateType} texture table {string.Join(",", table)}");

        var blocks = new BlocksFile(Path.Combine(arena2, "BLOCKS.BSA"), FileUsage.UseMemory, true);
        var arch = new Arch3dFile(Path.Combine(arena2, "ARCH3D.BSA"), FileUsage.UseMemory, true);
        var files = new Dictionary<int, TextureFile>();
        TextureFile Archive(int a)
        {
            if (!files.TryGetValue(a, out var f))
                files[a] = f = new TextureFile(Path.Combine(arena2, TextureFile.IndexToFileName(a)), FileUsage.UseMemory, true);
            return f;
        }

        var batches = new Dictionary<(int archive, int record), List<float>>();
        int models = 0, missing = 0;
        var doorModels = new Dictionary<(uint, bool), DoorModel>();
        var doorPlacements = new List<string>();
        const double toRad = Math.PI / 180;
        var actions = new ActionPackage();
        actions.Records.AddRange(ReadActionRecords(arena2, location));
        var actionAt = actions.Records.ToDictionary(r => (r.Block, r.FilePosition));
        int blockNumber = -1;
        foreach (var dungeonBlock in location.Dungeon.Blocks)
        {
            blockNumber++;
            var block = blocks.GetBlock(dungeonBlock.BlockName);
            var offset = new V3(dungeonBlock.X * BlockSide, 0, dungeonBlock.Z * BlockSide);
            if (block.RdbBlock.ObjectRootList == null) continue;
            foreach (var group in block.RdbBlock.ObjectRootList)
            {
                if (group.RdbObjects == null) continue;
                foreach (var obj in group.RdbObjects)
                {
                    if (obj.Type != DFBlock.RdbResourceTypes.Model) continue;
                    var reference = block.RdbBlock.ModelReferenceList[obj.Resources.ModelResource.ModelIndex];
                    uint id = reference.ModelIdNum;
                    int recordIndex = arch.GetRecordIndex(id);
                    if (recordIndex < 0) { missing++; continue; }
                    models++;
                    var mesh = arch.GetMesh(recordIndex);
                    double rx = -obj.Resources.ModelResource.XRotation / BlocksFile.RotationDivisor * toRad;
                    double ry = -obj.Resources.ModelResource.YRotation / BlocksFile.RotationDivisor * toRad;
                    double rz = -obj.Resources.ModelResource.ZRotation / BlocksFile.RotationDivisor * toRad;
                    var position = new V3(obj.XPos, -obj.YPos, obj.ZPos) + offset;
                    if (runtimeDungeon)
                        foreach (var exit in City.DoorPlanes(mesh).Where(q => q.Type == City.DoorExit))
                        {
                            var at = ToDoom(Rotate(exit.Centre, rx, ry, rz) + position);
                            var n = Rotate(exit.Normal, rx, ry, rz);
                            dungeonInfo.Append(FormattableString.Invariant($"exit {at.X:F3} {at.Y:F3} {at.Z - exit.HalfHeight * PlayerScale.DoomUnitsPerDaggerfallUnit:F3} {n.X:F4} {n.Z:F4}\n"));
                        }
                    actionAt.TryGetValue((blockNumber, obj.Position), out var actionRecord);
                    if (actionRecord != null)
                    {
                        PrepareActionModel(actions, actionRecord, obj, mesh, -ry / toRad, Archive, table, location);
                        if (actionRecord.IsDoor) actionRecord.Door = doorPlacements.Count;
                        else if (actionRecord.Kind == 1) continue; // drawn and collided by its action object
                    }
                    if (IsActionDoorModel(id, reference.Description))
                    {
                        // Any rotation that keeps the vertical axis vertical is R = Ry(phi) * F, where F is nothing or a 180 degree roll
                        // (upside down or mirrored doors). F is baked into the model, and phi is the closed angle.
                        var up = Rotate(new V3(0, 1, 0), rx, ry, rz);
                        if (Math.Abs(up.Y) < 0.999) throw new InvalidDataException($"door {id} is tilted by {rx / toRad:F2},{ry / toRad:F2},{rz / toRad:F2}; only yaw and a 180 degree flip are supported");
                        bool flipped = up.Y < 0;
                        var east = Rotate(new V3(1, 0, 0), rx, ry, rz);
                        double phi = Math.Atan2(-east.Z, east.X);
                        if (!doorModels.TryGetValue((id, flipped), out var doorModel))
                            doorModels[(id, flipped)] = doorModel = BuildDoorModel(id, doorModels.Count + (runtimeDungeon ? RuntimeDoorSlots : 0), mesh, Archive, table, location, flipped);
                        var pivot = ToDoom(position);
                        // Unity swings about the door's own Y axis, which points down on a flipped door, so the swing reverses.
                        double closed = -phi / toRad;
                        doorPlacements.Add(FormattableString.Invariant($"{doorModel.Token} {pivot.X:F3} {pivot.Y:F3} {pivot.Z:F3} {closed:F3} {doorModel.X0:F3} {doorModel.X1:F3} {doorModel.Y0:F3} {doorModel.Y1:F3} {doorModel.Z0:F3} {doorModel.Z1:F3} {(flipped ? -1 : 1)} {DoorLockValues[(obj.Resources.ModelResource.TriggerFlag_StartingLock >> 4) & 15]} {(long)block.Position + obj.Position}"));
                        continue;
                    }
                    foreach (var sub in mesh.SubMeshes)
                    {
                        // UVs are normalized by the unswapped texture, as in MeshReader.LoadVertices.
                        var source = Archive(sub.TextureArchive);
                        double w = source.GetWidth(sub.TextureRecord), h = source.GetHeight(sub.TextureRecord);
                        var key = (SwapArchive(sub.TextureArchive, table, location), sub.TextureRecord);
                        if (!batches.TryGetValue(key, out var v)) batches[key] = v = new List<float>();
                        foreach (var plane in sub.Planes)
                        {
                            void Emit(DFMesh.DFPoint p)
                            {
                                var at = Rotate(new V3(p.X, -p.Y, p.Z), rx, ry, rz) + position;
                                var n = Rotate(new V3(p.NX, -p.NY, p.NZ), rx, ry, rz);
                                double length = Math.Sqrt(n.X * n.X + n.Y * n.Y + n.Z * n.Z);
                                if (length < 1e-6) length = 1;
                                double scale = PlayerScale.DoomUnitsPerDaggerfallUnit;
                                v.Add((float)(at.X * scale)); v.Add((float)(at.Y * scale)); v.Add((float)(at.Z * scale));
                                v.Add((float)(p.U / w)); v.Add((float)(p.V / h));
                                v.Add((float)(n.X / length)); v.Add((float)(n.Y / length)); v.Add((float)(n.Z / length));
                            }
                            // Same fan and winding as MeshReader.LoadIndices.
                            for (int i = 1; i + 1 < plane.Points.Length; i++)
                            {
                                Emit(plane.Points[0]); Emit(plane.Points[i + 1]); Emit(plane.Points[i]);
                            }
                        }
                    }
                }
            }
        }

        var keys = batches.Keys.OrderBy(k => k.archive).ThenBy(k => k.record).ToList();
        string path = Path.Combine(outDir, slug + "_mesh.pk3");
        if (File.Exists(path)) File.Delete(path);
        int vertices = 0, badTextures = 0;
        using (var zip = ZipFile.Open(path, ZipArchiveMode.Create))
        {
            var body = new MemoryStream();
            var writer = new BinaryWriter(body);
            writer.Write(Encoding.ASCII.GetBytes("DFM1"));
            writer.Write(Encoding.ASCII.GetBytes(OutputMapName.PadRight(8, '\0').Substring(0, 8)));
            writer.Write(keys.Count); writer.Write(keys.Count); writer.Write(batches.Values.Sum(b => b.Count) / 8);
            foreach (var k in keys)
                writer.Write(Encoding.ASCII.GetBytes($"dfmesh/a{k.archive:D3}r{k.record:D2}.png".PadRight(32, '\0')));
            for (int t = 0; t < keys.Count; t++)
            {
                int count = batches[keys[t]].Count / 8;
                writer.Write(t); writer.Write(vertices); writer.Write(count);
                vertices += count;
            }
            foreach (var k in keys)
                foreach (float f in batches[k]) writer.Write(f);
            writer.Flush();
            using (var s = zip.CreateEntry("DFMESH", CompressionLevel.Fastest).Open()) { body.Position = 0; body.CopyTo(s); }
            // Daggerfall has square pixels. Doom's default 1.2 vertical stretch would distort the real mesh.
            using (var s = new StreamWriter(zip.CreateEntry("MAPINFO", CompressionLevel.Fastest).Open()))
                s.Write($"map {OutputMapName} \"{location.Name}\"\n{{\n\tpixelratio = 1.0\n{(runtimeDungeon ? "\tkeepfullinventory\n\tUsePlayerStartZ\n" : "")}}}\n");

            var animdefs = new StringBuilder();
            foreach (var k in keys)
            {
                var file = Archive(k.archive);
                var image = k.record < file.RecordCount ? file.GetDFBitmap(k.record, 0) : null;
                if (image?.Data == null || image.Width == 0) { badTextures++; Console.WriteLine($"missing texture {k.archive}:{k.record}"); continue; }
                using (var s = zip.CreateEntry($"dfmesh/a{k.archive:D3}r{k.record:D2}.png", CompressionLevel.Fastest).Open())
                    WriteTexturePng(s, image, file.Palette);
                WriteModelTextureFrames(zip, animdefs, file, k.archive, k.record);
            }
            if (animdefs.Length > 0)
                using (var s = new StreamWriter(zip.CreateEntry("ANIMDEFS", CompressionLevel.Fastest).Open()))
                    s.Write(animdefs.ToString());
        }
        PrepareActionFlats(actions, Archive);
        CollectDungeonFlats(actions, blocks, location, Archive);
        WriteDoorPackage(Path.Combine(outDir, slug + "_doors.pk3"), doorModels.Values.OrderBy(m => m.Slot).ToList(), doorPlacements, Archive, actions);
        Console.WriteLine($"doors: {doorPlacements.Count} placed, {doorModels.Count} models");
        Console.WriteLine($"actions: {actions.Records.Count} records, {actions.Records.Count(r => r.Kind == 1)} moving models, {actions.Models.Count} models, {actions.Records.Where(r => r.Kind == 1).Sum(r => actions.Cells[r.Model].Count)} collision cells, {actions.Flats.Count} flat sprites");
        Console.WriteLine($"mesh: {models} models ({missing} missing), {vertices / 3} triangles, {keys.Count} textures/batches ({badTextures} unreadable), {new FileInfo(path).Length / 1024} KiB -> {path}");
        return badTextures == 0 && missing == 0 ? 0 : 1;
    }

    // transparentZero writes RGBA with palette index 0 clear, as Daggerfall Unity does for billboards (alphaIndex 0).
    // grab stores a sprite anchor, in pixels from the top left.
    static void WriteTexturePng(Stream output, DFBitmap image, DFPalette palette, bool transparentZero = false, (int x, int y)? grab = null)
    {
        byte[] buffer = palette.PaletteBuffer;
        int head = palette.HeaderLength, w = image.Width, h = image.Height, bytes = transparentZero ? 4 : 3;
        var raw = new byte[(w * bytes + 1) * h];
        for (int y = 0, at = 0; y < h; y++)
        {
            raw[at++] = 0;
            for (int x = 0; x < w; x++)
            {
                int c = image.Data[y * w + x] * 3 + head;
                raw[at++] = buffer[c]; raw[at++] = buffer[c + 1]; raw[at++] = buffer[c + 2];
                if (transparentZero) raw[at++] = image.Data[y * w + x] == 0 ? (byte)0 : (byte)255;
            }
        }
        var packed = new MemoryStream();
        using (var z = new ZLibStream(packed, CompressionLevel.Fastest, true)) z.Write(raw, 0, raw.Length);
        void Chunk(string kind, byte[] data)
        {
            var name = Encoding.ASCII.GetBytes(kind);
            WriteBig(output, (uint)data.Length);
            output.Write(name); output.Write(data);
            WriteBig(output, Crc(name, data));
        }
        output.Write(new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A });
        var header = new byte[13];
        header[0] = (byte)(w >> 24); header[1] = (byte)(w >> 16); header[2] = (byte)(w >> 8); header[3] = (byte)w;
        header[4] = (byte)(h >> 24); header[5] = (byte)(h >> 16); header[6] = (byte)(h >> 8); header[7] = (byte)h;
        header[8] = 8; header[9] = (byte)(transparentZero ? 6 : 2);
        Chunk("IHDR", header);
        if (grab is (int gx, int gy))
            Chunk("grAb", new[] { gx, gy }.SelectMany(q => new[] { (byte)(q >> 24), (byte)(q >> 16), (byte)(q >> 8), (byte)q }).ToArray());
        Chunk("IDAT", packed.ToArray());
        Chunk("IEND", new byte[0]);
    }

    static void WriteBig(Stream s, uint v) { s.WriteByte((byte)(v >> 24)); s.WriteByte((byte)(v >> 16)); s.WriteByte((byte)(v >> 8)); s.WriteByte((byte)v); }

    static uint Crc(byte[] a, byte[] b)
    {
        uint crc = 0xffffffff;
        foreach (var data in new[] { a, b })
            foreach (byte x in data)
            {
                crc ^= x;
                for (int k = 0; k < 8; k++) crc = (crc & 1) != 0 ? 0xedb88320 ^ (crc >> 1) : crc >> 1;
            }
        return ~crc;
    }
}
