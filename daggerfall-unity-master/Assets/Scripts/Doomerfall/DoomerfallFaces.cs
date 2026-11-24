// Doomerfall: mirrors the quest follower faces of Daggerfall's HUD (EscortingNPCFacePanel) to Doom's HUD.
// Daggerfall stays the owner: quests add and drop faces, and its saves and loads restore them, exactly as before. This
// only watches the panel's refresh count each frame and, when it changed, writes the faces it now shows (at most three,
// as Daggerfall draws them) into DFB_FACES_SLOT, pixels included. Doom draws whatever the newest version holds.

using System;
using System.Collections.Generic;
using DaggerfallWorkshop.Game.UserInterface;
using UnityEngine;

namespace DaggerfallWorkshop.Game.Doomerfall
{
    internal sealed class DoomerfallFaces
    {
        const int HeaderBytes = 8, FaceHeaderBytes = 16;

        readonly DoomerfallBridge bridge;
        readonly byte[] buffer = new byte[HeaderBytes + Dfb.FACES_MAX * (FaceHeaderBytes + Dfb.FACE_MAX_SIDE * Dfb.FACE_MAX_SIDE * 4)];
        EscortingNPCFacePanel panel;
        int publishedRefresh = -1;
        bool written;

        public DoomerfallFaces(DoomerfallBridge owner)
        {
            bridge = owner;
        }

        /// <summary>Writes the faces if Daggerfall's panel refreshed since the last write. Runs every frame.</summary>
        internal void Publish()
        {
            EscortingNPCFacePanel current = DaggerfallUI.Instance != null && DaggerfallUI.Instance.DaggerfallHUD != null ?
                DaggerfallUI.Instance.DaggerfallHUD.EscortingFaces : null;
            if (current != panel)
            {
                panel = current;
                publishedRefresh = -1;
            }
            int refresh = panel != null ? panel.RefreshCount : 0;
            if (written && refresh == publishedRefresh)
                return;

            int size = Build(out int count);
            uint version;
            if (DfbNative.dfb_bulk_write(bridge.Session, Dfb.FACES_SLOT, buffer, (uint)size, out version) != Dfb.OK)
                return; // Retried next frame.
            publishedRefresh = refresh;
            written = true;
            if (bridge.LogEnabled)
                bridge.LogLine(string.Format("faces: published v{0}, {1} face(s), {2} bytes, panel refresh {3}", version, count, size, refresh));
        }

        int Build(out int count)
        {
            count = 0;
            int at = HeaderBytes;
            IList<Panel> panels = panel != null ? panel.FacePanels : null;
            if (panels != null)
            {
                foreach (Panel face in panels)
                {
                    if (count >= Dfb.FACES_MAX)
                        break;
                    Texture2D texture = face.BackgroundTexture;
                    if (texture == null)
                        continue;
                    int w = Math.Min(texture.width, (int)Dfb.FACE_MAX_SIDE);
                    int h = Math.Min(texture.height, (int)Dfb.FACE_MAX_SIDE);
                    Put(at, (uint)w);
                    Put(at + 4, (uint)h);
                    Put(at + 8, (uint)Mathf.RoundToInt(face.Size.x));
                    Put(at + 12, (uint)Mathf.RoundToInt(face.Size.y));
                    at += FaceHeaderBytes;
                    Color32[] pixels = Pixels(texture, w, h);
                    for (int y = 0; y < h; y++)
                    {
                        int row = (h - 1 - y) * w; // Unity's rows run bottom up, the slot's top down.
                        for (int x = 0; x < w; x++)
                        {
                            Color32 c = pixels[row + x];
                            buffer[at++] = c.b;
                            buffer[at++] = c.g;
                            buffer[at++] = c.r;
                            buffer[at++] = c.a;
                        }
                    }
                    count++;
                }
            }
            Put(0, Dfb.FACES_FORMAT_VERSION);
            Put(4, (uint)count);
            return at;
        }

        // The texture's own pixels when they can be read at full size, else a copy drawn through the GPU (mods may
        // replace a portrait with an unreadable or larger texture).
        static Color32[] Pixels(Texture2D texture, int w, int h)
        {
            if (texture.isReadable && w == texture.width && h == texture.height)
            {
                try { return texture.GetPixels32(); }
                catch (Exception) { } // Compressed formats cannot be read this way.
            }
            RenderTexture target = RenderTexture.GetTemporary(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            RenderTexture previous = RenderTexture.active;
            Graphics.Blit(texture, target);
            RenderTexture.active = target;
            Texture2D copy = new Texture2D(w, h, TextureFormat.RGBA32, false);
            copy.ReadPixels(new Rect(0, 0, w, h), 0, 0, false);
            RenderTexture.active = previous;
            RenderTexture.ReleaseTemporary(target);
            Color32[] pixels = copy.GetPixels32();
            UnityEngine.Object.Destroy(copy);
            return pixels;
        }

        void Put(int at, uint value)
        {
            buffer[at] = (byte)value;
            buffer[at + 1] = (byte)(value >> 8);
            buffer[at + 2] = (byte)(value >> 16);
            buffer[at + 3] = (byte)(value >> 24);
        }
    }
}
