// Draws a Skyrim UI menu converted from its SWF at pk3 build time (tools/skyrim_ui/convert.py): one texture per vector
// shape under graphics/skyrimui/<menu>/, and skyrimui/<menu>.txt with the display lists of every frame.
// DDSwfMovie is the generic part: any converted menu can be drawn with it. The SWF's ActionScript is not converted, so
// each menu's behaviour (which frames play, what a choice does) is written in its own Menu class, as
// DoomerfallTweenMenu does. Text fields are drawn with a Doom font; "$KEY" texts read the LANGUAGE string SKYUI_KEY.

class DDSwfPlace ui
{
	int depth, chr;
	double a, b, c, d, tx, ty, alpha, r, g, bl;
	bool clip;
	String name;
}

class DDSwfSprite ui
{
	int frameCount;
	Array<DDSwfPlace> places;
	Array<int> placeFrame;      // the frame each entry of places belongs to
	Array<String> labelNames;
	Array<int> labelFrames;
}

class DDSwfImage ui
{
	TextureID tex;
	double x, y, w, h;          // in the shape's own space
	Shape2D quad;
}

class DDSwfText ui
{
	double x0, y0, x1, y1, height;
	int align;
	Color col;
	String text;
}

// One instance's playhead, by instance name: a frame or a run of frames played at the SWF's frame rate.
class DDSwfPlayhead ui
{
	String name;
	int from, to;
	double startMs;
}

class DDSwfMovie ui
{
	double stageW, stageH, rate;
	int root;
	Array<DDSwfSprite> sprites;   // by character id; null for other characters
	Array<DDSwfImage> images;
	Array<DDSwfText> texts;
	Array<DDSwfPlayhead> playheads;
	Array<String> hidden;
	Array<String> textNames, textValues;
	Font textFont;

	// Screen transform of the stage, set each Draw.
	double scale, offX, offY;

	static DDSwfMovie Load(String menuName)
	{
		int lump = Wads.CheckNumForFullName("skyrimui/" .. menuName .. ".txt");
		if (lump < 0) return null;
		let m = new("DDSwfMovie");
		m.Parse(Wads.ReadLump(lump));
		if (m.root <= 0) return null;
		m.textFont = NewSmallFont;
		int valid = 0, total = 0;
		for (int i = 0; i < m.images.Size(); i++) if (m.images[i]) { total++; if (m.images[i].tex.IsValid()) valid++; }
		DDLog.Debug(String.Format("Doomerfall: %s menu loaded, %d of %d shape textures found", menuName, valid, total));
		return m;
	}

	private void Parse(String data)
	{
		Array<String> lines;
		data.Split(lines, "\n");
		for (int i = 0; i < lines.Size(); i++)
		{
			Array<String> f;
			lines[i].Split(f, " ");
			if (f.Size() < 2) continue;
			if (f[0] == "swfui" && f.Size() >= 6)
			{
				stageW = f[2].ToDouble();
				stageH = f[3].ToDouble();
				rate = f[4].ToDouble();
				root = f[5].ToInt();
			}
			else if (f[0] == "image" && f.Size() >= 6)
			{
				let img = new("DDSwfImage");
				img.tex = TexMan.CheckForTexture(f[2], TexMan.Type_Any);
				Vector2 size = TexMan.GetScaledSize(img.tex);
				double ppu = f[5].ToDouble();
				img.x = f[3].ToDouble();
				img.y = f[4].ToDouble();
				img.w = size.X / ppu;
				img.h = size.Y / ppu;
				img.quad = new("Shape2D");
				img.quad.PushCoord((0, 0));
				img.quad.PushCoord((1, 0));
				img.quad.PushCoord((1, 1));
				img.quad.PushCoord((0, 1));
				img.quad.PushTriangle(0, 1, 2);
				img.quad.PushTriangle(0, 2, 3);
				int id = f[1].ToInt();
				if (images.Size() <= id) images.Resize(id + 1);
				images[id] = img;
			}
			else if (f[0] == "text" && f.Size() >= 12)
			{
				let t = new("DDSwfText");
				t.x0 = f[2].ToDouble();
				t.y0 = f[3].ToDouble();
				t.x1 = f[4].ToDouble();
				t.y1 = f[5].ToDouble();
				t.height = f[6].ToDouble();
				t.align = f[7].ToInt();
				t.col = Color(f[11].ToInt(), f[8].ToInt(), f[9].ToInt(), f[10].ToInt());
				for (int k = 12; k < f.Size(); k++) t.text = k == 12 ? f[k] : t.text .. " " .. f[k];
				int id = f[1].ToInt();
				if (texts.Size() <= id) texts.Resize(id + 1);
				texts[id] = t;
			}
			else if (f[0] == "sprite" && f.Size() >= 3)
			{
				int id = f[1].ToInt();
				if (sprites.Size() <= id) sprites.Resize(id + 1);
				sprites[id] = new("DDSwfSprite");
				sprites[id].frameCount = f[2].ToInt();
			}
			else if (f[0] == "label" && f.Size() >= 4)
			{
				let s = GetSprite(f[1].ToInt());
				if (!s) continue;
				s.labelFrames.Push(f[2].ToInt());
				s.labelNames.Push(f[3]);
			}
			else if (f[0] == "place" && f.Size() >= 17)
			{
				let s = GetSprite(f[1].ToInt());
				if (!s) continue;
				let p = new("DDSwfPlace");
				p.depth = f[3].ToInt();
				p.chr = f[4].ToInt();
				p.a = f[5].ToDouble();
				p.b = f[6].ToDouble();
				p.c = f[7].ToDouble();
				p.d = f[8].ToDouble();
				p.tx = f[9].ToDouble();
				p.ty = f[10].ToDouble();
				p.alpha = f[11].ToDouble();
				p.r = f[12].ToDouble();
				p.g = f[13].ToDouble();
				p.bl = f[14].ToDouble();
				p.clip = f[15] == "1";
				p.name = f[16] == "-" ? "" : f[16];
				s.places.Push(p);
				s.placeFrame.Push(f[2].ToInt());
			}
		}
	}

	DDSwfSprite GetSprite(int id) { return id >= 0 && id < sprites.Size() ? sprites[id] : null; }

	// The first frame of a label in the sprite an instance shows, or -1.
	int LabelFrame(int spriteId, String label)
	{
		let s = GetSprite(spriteId);
		if (!s) return -1;
		for (int i = 0; i < s.labelNames.Size(); i++) if (s.labelNames[i] == label) return s.labelFrames[i];
		return -1;
	}

	// Plays frames from..to of the named instance ("" is the root) at the movie's frame rate, then holds the last.
	void PlayFrames(String instance, int from, int to)
	{
		DDSwfPlayhead h = null;
		for (int i = 0; i < playheads.Size() && !h; i++) if (playheads[i].name == instance) h = playheads[i];
		if (!h)
		{
			h = new("DDSwfPlayhead");
			h.name = instance;
			playheads.Push(h);
		}
		h.from = from;
		h.to = to;
		h.startMs = MSTimeF();
	}

	void GotoFrame(String instance, int frame) { PlayFrames(instance, frame, frame); }

	// True while any playhead is still moving.
	bool Playing()
	{
		double now = MSTimeF();
		for (int i = 0; i < playheads.Size(); i++)
		{
			let h = playheads[i];
			if (h.to > h.from && (now - h.startMs) * rate / 1000 < h.to - h.from) return true;
		}
		return false;
	}

	int FrameOf(String instance)
	{
		for (int i = 0; i < playheads.Size(); i++)
		{
			let h = playheads[i];
			if (h.name != instance) continue;
			int n = int((MSTimeF() - h.startMs) * rate / 1000);
			return h.to > h.from ? min(h.from + n, h.to) : h.from;
		}
		return 0;
	}

	// The frame a sprite instance shows: the root's playhead, a named instance's own, or the first frame for the rest.
	int InstanceFrame(int id, String instance)
	{
		if (instance == "" && id != root) return 0;
		let s = GetSprite(id);
		return s ? clamp(FrameOf(instance), 0, max(s.frameCount - 1, 0)) : 0;
	}

	void SetHidden(String instance) { if (hidden.Find(instance) == hidden.Size()) hidden.Push(instance); }

	void SetText(String instance, String text)
	{
		int i = textNames.Find(instance);
		if (i == textNames.Size())
		{
			textNames.Push(instance);
			textValues.Push(text);
		}
		else textValues[i] = text;
	}

	// The stage fitted inside the screen, centred, keeping its shape.
	void FitScreen()
	{
		scale = min(Screen.GetWidth() / stageW, Screen.GetHeight() / stageH);
		offX = (Screen.GetWidth() - stageW * scale) / 2;
		offY = (Screen.GetHeight() - stageH * scale) / 2;
	}

	// The root symbol at the middle of the stage, where the Skyrim menus place theirs.
	void Draw(double alpha = 1)
	{
		FitScreen();
		DrawChar(root, "", scale, 0, 0, scale, offX + stageW / 2 * scale, offY + stageH / 2 * scale, alpha, 1, 1, 1);
	}

	private void DrawChar(int id, String instance, double a, double b, double c, double d, double tx, double ty, double alpha, double cr, double cg, double cb)
	{
		if (alpha <= 0.002) return;
		if (id < images.Size() && images[id])
		{
			let img = images[id];
			Color tint = Color(255, int(255 * clamp(cr, 0, 1)), int(255 * clamp(cg, 0, 1)), int(255 * clamp(cb, 0, 1)));
			if (b == 0 && c == 0) // Scaled and moved only, as almost every shape is.
			{
				double x = img.x * a + tx, y = img.y * d + ty, w = img.w * a, h = img.h * d;
				Screen.DrawTexture(img.tex, false, w < 0 ? x + w : x, h < 0 ? y + h : y, DTA_DestWidthF, abs(w), DTA_DestHeightF, abs(h),
					DTA_FlipX, w < 0, DTA_FlipY, h < 0, DTA_Alpha, alpha, DTA_Color, tint, DTA_TopOffset, 0, DTA_LeftOffset, 0);
				return;
			}
			let q = img.quad;
			q.Clear(Shape2D.C_Verts);
			for (int k = 0; k < 4; k++)
			{
				double x = img.x + (k == 1 || k == 2 ? img.w : 0), y = img.y + (k >= 2 ? img.h : 0);
				q.PushVertex((x * a + y * c + tx, x * b + y * d + ty));
			}
			Screen.DrawShape(img.tex, false, q, DTA_Alpha, alpha, DTA_Color, tint);
			return;
		}
		if (id < texts.Size() && texts[id])
		{
			DrawTextField(texts[id], instance, a, b, c, d, tx, ty, alpha);
			return;
		}
		let s = GetSprite(id);
		if (!s) return;
		int frame = InstanceFrame(id, instance);
		for (int i = 0; i < s.places.Size(); i++)
		{
			if (s.placeFrame[i] != frame) continue;
			let p = s.places[i];
			if (p.clip || (p.name != "" && hidden.Find(p.name) != hidden.Size())) continue; // Mask layers are not drawn; nothing is masked.
			DrawChar(p.chr, p.name, a * p.a + c * p.b, b * p.a + d * p.b, a * p.c + c * p.d, b * p.c + d * p.d,
				a * p.tx + c * p.ty + tx, b * p.tx + d * p.ty + ty, alpha * p.alpha, cr * p.r, cg * p.g, cb * p.bl);
		}
	}

	private void DrawTextField(DDSwfText t, String instance, double a, double b, double c, double d, double tx, double ty, double alpha)
	{
		String text = t.text;
		int i = textNames.Find(instance);
		if (instance != "" && i != textNames.Size()) text = textValues[i];
		else if (text.Left(1) == "$") text = StringTable.Localize("$SKYUI_" .. text.Mid(1));
		if (text == "") return;
		Font f = textFont;
		double sx = sqrt(a * a + b * b), sy = sqrt(c * c + d * d);
		double k = t.height * sy / f.GetHeight();
		double w = f.StringWidth(text) * k;
		double boxL = t.x0 * a + t.y0 * c + tx, boxR = t.x1 * a + t.y0 * c + tx;
		double x = t.align == 1 ? boxR - w : t.align == 2 ? (boxL + boxR - w) / 2 : boxL;
		double y = t.x0 * b + t.y0 * d + ty + (t.y1 - t.y0) * sy / 2 - f.GetHeight() * k / 2;
		Screen.DrawText(f, Font.CR_WHITE, x, y, text, DTA_ScaleX, k, DTA_ScaleY, k, DTA_Alpha, alpha * t.col.a / 255.0, DTA_Color, Color(255, t.col.r, t.col.g, t.col.b));
	}

	// The named instance's drawn shapes, as a screen rectangle (after the last Draw), or false when it is not shown.
	bool, double, double, double, double InstanceRect(String instance)
	{
		double x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
		[x0, y0, x1, y1] = Bounds(root, "", false, instance, scale, 0, 0, scale, offX + stageW / 2 * scale, offY + stageH / 2 * scale, x0, y0, x1, y1);
		return x1 > x0, x0, y0, x1, y1;
	}

	private double, double, double, double Bounds(int id, String name, bool inside, String want, double a, double b, double c, double d, double tx, double ty, double x0, double y0, double x1, double y1)
	{
		inside = inside || (name != "" && name == want);
		if (id < images.Size() && images[id])
		{
			if (!inside) return x0, y0, x1, y1;
			let img = images[id];
			for (int k = 0; k < 4; k++)
			{
				double x = img.x + (k == 1 || k == 2 ? img.w : 0), y = img.y + (k >= 2 ? img.h : 0);
				double px = x * a + y * c + tx, py = x * b + y * d + ty;
				x0 = min(x0, px); y0 = min(y0, py); x1 = max(x1, px); y1 = max(y1, py);
			}
			return x0, y0, x1, y1;
		}
		let s = GetSprite(id);
		if (!s) return x0, y0, x1, y1;
		int frame = InstanceFrame(id, name);
		for (int i = 0; i < s.places.Size(); i++)
		{
			if (s.placeFrame[i] != frame || s.places[i].clip) continue;
			let p = s.places[i];
			[x0, y0, x1, y1] = Bounds(p.chr, p.name, inside, want, a * p.a + c * p.b, b * p.a + d * p.b, a * p.c + c * p.d, b * p.c + d * p.d,
				a * p.tx + c * p.ty + tx, b * p.tx + d * p.ty + ty, x0, y0, x1, y1);
		}
		return x0, y0, x1, y1;
	}
}
