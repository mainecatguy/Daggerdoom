// [DoomDaggerfall] Terrain treadmill kill test.
//
// Rewrites the floor planes of a fixed triangle grid in place and moves live
// actors back by a whole number of tiles. Does nothing unless the map is
// TREADM01 and the game was started with -ddtreadmill <heights.bin>.
//
// Options: -ddtmlog <frames.csv>, -ddtmnorewrite (baseline), -ddtmverify,
// -ddtmshots (screenshots around the first shifts), -ddtmstop <units>.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <vector>

#include "dd_treadmill.h"
#include "actor.h"
#include "actorinlines.h"
#include "c_cvars.h"
#include "c_dispatch.h"
#include "g_levellocals.h"
#include "m_argv.h"
#include "p_effect.h"
#include "p_local.h"
#include "printf.h"
#include "r_utility.h"

CVAR(Int, dd_tm_originx, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_originy, 0, CVAR_NOSAVE)
CVAR(Int, dd_tm_shifts, 0, CVAR_NOSAVE)

bool DDTreadmill_Active = false;

namespace
{
	constexpr int SHIFT_TILES = 32;

	struct Tri { sector_t *sec; int v[3]; };

	struct Header { char magic[4]; int32_t version, cells, spacing, width, height, globalX, globalY; };

	Header hdr;
	std::vector<float> heights;
	std::vector<Tri> tris;
	int ox, oy, globalTileX, globalTileY, shifts;
	bool noRewrite, verify, screenshots, shotBefore, quitSent;
	int shotAfterTics;
	double stopUnits, startX;
	FILE *frameLog, *shiftLog;

	using Clock = std::chrono::steady_clock;
	Clock::time_point lastFrame, uploadStart;
	int64_t simNs, uploadNs, uploadCount, frameNo;
	int shiftFlag;

	int FindArg(const char *name)
	{
		for (int i = 1; i < Args->NumArgs(); i++)
			if (!stricmp(Args->GetArg(i), name)) return i;
		return 0;
	}

	const char *ArgValue(const char *name)
	{
		const int i = FindArg(name);
		return i && i + 1 < Args->NumArgs() ? Args->GetArg(i + 1) : nullptr;
	}

	int64_t NsSince(Clock::time_point t)
	{
		return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - t).count();
	}

	double LocalCoord(int index) { return index * double(hdr.spacing) - hdr.cells * double(hdr.spacing) / 2; }
	double HeightAt(int i, int j) { return heights[size_t(oy + j) * hdr.width + ox + i]; }

	void RewriteGrid()
	{
		const int row = hdr.cells + 1;
		for (auto &t : tris)
		{
			DVector3 p[3];
			for (int k = 0; k < 3; k++)
			{
				const int i = t.v[k] % row, j = t.v[k] / row;
				p[k] = DVector3(LocalCoord(i), LocalCoord(j), HeightAt(i, j));
			}
			DVector3 n = (p[1] - p[0]) ^ (p[2] - p[0]);
			if (n.Z < 0) n = -n;
			n /= n.Length();
			t.sec->floorplane.set(n.X, n.Y, n.Z, -(n | p[0]));
			// NaN never equals the plane's TexZ, so the renderer re-uploads
			// this floor the next time the sector is actually drawn.
			for (auto &vbo : t.sec->vboheight)
				vbo[sector_t::floor] = std::numeric_limits<double>::quiet_NaN();
		}
	}

	void MoveActors(FLevelLocals *Level, const DVector3 &delta)
	{
		struct Moved { AActor *mo; bool onFloor; };
		static std::vector<Moved> moved;
		static std::vector<AActor *> offGrid;
		moved.clear();
		offGrid.clear();
		const double limit = hdr.cells * double(hdr.spacing) / 2 - 64;

		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			const DVector3 target = mo->Pos() - delta;
			if (!mo->player && (fabs(target.X) > limit || fabs(target.Y) > limit))
			{
				offGrid.push_back(mo);	// Test placeholder. Off-window behavior is an owner decision.
				continue;
			}
			const bool onFloor = mo->Z() <= mo->floorz + 0.01;
			FLinkContext ctx;
			mo->UnlinkFromWorld(&ctx);
			mo->SetXYZ(target);
			mo->LinkToWorld(&ctx);
			mo->Prev -= delta;
			moved.push_back({ mo, onFloor });
		}
		for (auto &m : moved)
		{
			P_FindFloorCeiling(m.mo, FFCF_ONLYSPAWNPOS);
			if (m.onFloor) m.mo->SetZ(m.mo->floorz);
		}
		for (AActor *mo : offGrid) mo->Destroy();
		if (!offGrid.empty()) Printf("DDTM offgrid removed=%d\n", int(offGrid.size()));

		for (uint32_t p = Level->ActiveParticles; p != NO_PARTICLE; p = Level->Particles[p].tnext)
			Level->Particles[p].Pos -= delta;
		R_ShiftPastViewers(delta);
	}

	double ExpectedZ(double x, double y)
	{
		const double s = hdr.spacing, half = hdr.cells * s / 2;
		int i = std::clamp(int(floor((x + half) / s)), 0, hdr.cells - 1);
		int j = std::clamp(int(floor((y + half) / s)), 0, hdr.cells - 1);
		const double fx = (x + half) / s - i, fy = (y + half) / s - j;
		const double a = HeightAt(i, j), b = HeightAt(i + 1, j), c = HeightAt(i + 1, j + 1), d = HeightAt(i, j + 1);
		return fx >= fy ? a + fx * (b - a) + fy * (c - b) : a + fy * (d - a) + fx * (c - d);
	}

	double VerifyGrid(FLevelLocals *Level)
	{
		uint32_t seed = 12345u + shifts;
		const double range = hdr.cells * double(hdr.spacing) - 2;
		double worst = 0;
		for (int n = 0; n < 512; n++)
		{
			seed = seed * 1664525u + 1013904223u;
			const double x = (seed >> 8) / double(1 << 24) * range - range / 2;
			seed = seed * 1664525u + 1013904223u;
			const double y = (seed >> 8) / double(1 << 24) * range - range / 2;
			const double z = Level->PointInSector(DVector2(x, y))->floorplane.ZatPoint(x, y);
			worst = std::max(worst, fabs(z - ExpectedZ(x, y)));
		}
		return worst;
	}

	bool LoadHeights(const char *path)
	{
		FILE *f = fopen(path, "rb");
		if (!f) return false;
		bool ok = fread(&hdr, sizeof(hdr), 1, f) == 1 && !memcmp(hdr.magic, "DDTM", 4) && hdr.version == 1
			&& hdr.width > hdr.cells && hdr.height > hdr.cells;
		if (ok)
		{
			heights.resize(size_t(hdr.width) * hdr.height);
			ok = fread(heights.data(), sizeof(float), heights.size(), f) == heights.size();
		}
		fclose(f);
		return ok;
	}

	bool BuildTriangles(FLevelLocals *Level)
	{
		tris.clear();
		tris.reserve(Level->sectors.Size());
		const double s = hdr.spacing, half = hdr.cells * s / 2;
		for (auto &sec : Level->sectors)
		{
			if (sec.Lines.Size() != 3) return false;
			vertex_t *a = sec.Lines[0]->v1, *b = sec.Lines[0]->v2, *l = sec.Lines[1]->v1;
			vertex_t *c = (l == a || l == b) ? sec.Lines[1]->v2 : l;
			Tri t{ &sec, {} };
			vertex_t *vs[3] = { a, b, c };
			for (int k = 0; k < 3; k++)
			{
				const double fi = (vs[k]->fX() + half) / s, fj = (vs[k]->fY() + half) / s;
				const int i = int(lround(fi)), j = int(lround(fj));
				if (fabs(fi - i) > 1e-6 || fabs(fj - j) > 1e-6 || i < 0 || j < 0 || i > hdr.cells || j > hdr.cells) return false;
				t.v[k] = j * (hdr.cells + 1) + i;
			}
			tris.push_back(t);
		}
		return true;
	}

	void Start(FLevelLocals *Level)
	{
		DDTreadmill_Active = false;
		if (Level->MapName.CompareNoCase("TREADM01") != 0) return;
		const char *path = ArgValue("-ddtreadmill");
		if (!path || (heights.empty() && !LoadHeights(path)) || !BuildTriangles(Level))
		{
			Printf("DDTM failed to start\n");
			return;
		}
		noRewrite = FindArg("-ddtmnorewrite") != 0;
		verify = FindArg("-ddtmverify") != 0;
		screenshots = FindArg("-ddtmshots") != 0;
		if (const char *stop = ArgValue("-ddtmstop")) stopUnits = atof(stop);
		if (Level->Players[consoleplayer]->mo) startX = Level->Players[consoleplayer]->mo->X();
		if (const char *logPath = ArgValue("-ddtmlog"); logPath && !frameLog)
		{
			frameLog = fopen(logPath, "w");
			if (frameLog) fputs("frame,tic,frame_us,sim_us,upload_us,uploads,shift\n", frameLog);
			shiftLog = fopen((FString(logPath) + ".shifts.csv").GetChars(), "w");
			if (shiftLog) fputs("shift,origin_x,origin_y,rewrite_us,total_us,plane_err,window_x\n", shiftLog);
		}
		ox = oy = globalTileX = globalTileY = shifts = 0;
		dd_tm_originx = hdr.globalX;
		dd_tm_originy = hdr.globalY;
		dd_tm_shifts = 0;
		RewriteGrid();
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			P_FindFloorCeiling(mo, FFCF_ONLYSPAWNPOS);
			if (!(mo->flags & MF_NOGRAVITY)) mo->SetZ(mo->floorz);
			mo->ClearInterpolation();
		}
		for (int i = 0; i < MAXPLAYERS; i++)
			if (Level->PlayerInGame(i) && Level->Players[i]->mo)
				Level->Players[i]->viewz = Level->Players[i]->mo->Z() + Level->Players[i]->viewheight;
		lastFrame = Clock::now();
		DDTreadmill_Active = true;
		Printf("DDTM active grid=%dx%d spacing=%d data=%dx%d sectors=%d norewrite=%d\n", hdr.cells, hdr.cells, hdr.spacing,
			hdr.width, hdr.height, int(tris.size()), int(noRewrite));
	}
}

void DDTreadmill_Tick(FLevelLocals *Level)
{
	static const bool requested = FindArg("-ddtreadmill") != 0;
	if (!requested) return;
	if (Level->maptime == 0) Start(Level);
	if (!DDTreadmill_Active || Level != primaryLevel) return;

	AActor *pmo = Level->Players[consoleplayer]->mo;
	if (!pmo) return;

	const double threshold = SHIFT_TILES * double(hdr.spacing) / 2;
	int dx = pmo->X() > threshold ? SHIFT_TILES : pmo->X() < -threshold ? -SHIFT_TILES : 0;
	int dy = pmo->Y() > threshold ? SHIFT_TILES : pmo->Y() < -threshold ? -SHIFT_TILES : 0;
	if (globalTileX + dx < 0 || globalTileX + dx + hdr.cells >= hdr.width) dx = 0;
	if (globalTileY + dy < 0 || globalTileY + dy + hdr.cells >= hdr.height) dy = 0;
	if (stopUnits > 0 && !quitSent && globalTileX * double(hdr.spacing) + pmo->X() - startX >= stopUnits)
	{
		quitSent = true;
		if (frameLog) fflush(frameLog);
		if (shiftLog) fflush(shiftLog);
		Printf("DDTM stop distance reached\n");
		AddCommandString("quit");
	}
	if (screenshots && shifts < 2 && !shotBefore && pmo->X() > threshold - 24)
	{
		shotBefore = true;
		AddCommandString("screenshot");
	}
	if (screenshots && shotAfterTics > 0 && --shotAfterTics == 0) AddCommandString("screenshot");
	if (dx == 0 && dy == 0) return;
	if (screenshots && shifts < 2) { shotBefore = false; shotAfterTics = 2; }

	globalTileX += dx;
	globalTileY += dy;
	const auto start = Clock::now();
	if (!noRewrite)
	{
		ox += dx;
		oy += dy;
		RewriteGrid();
	}
	const int64_t rewriteNs = NsSince(start);
	MoveActors(Level, DVector3(dx * double(hdr.spacing), dy * double(hdr.spacing), 0));
	const int64_t totalNs = NsSince(start);
	simNs += totalNs;
	shiftFlag = 1;
	shifts++;
	dd_tm_shifts = shifts;
	dd_tm_originx = hdr.globalX + globalTileX;
	dd_tm_originy = hdr.globalY + globalTileY;

	const double err = verify && !noRewrite ? VerifyGrid(Level) : -1;
	// Buffered file output, so logging does not add to the frame being measured.
	if (shiftLog)
		fprintf(shiftLog, "%d,%d,%d,%.1f,%.1f,%.6f,%.6f\n", shifts, int(dd_tm_originx), int(dd_tm_originy),
			rewriteNs / 1000.0, totalNs / 1000.0, err, globalTileX * double(hdr.spacing) + pmo->X());
}

void DDTreadmill_UploadBegin() { uploadStart = Clock::now(); }
void DDTreadmill_UploadEnd() { uploadNs += NsSince(uploadStart); uploadCount++; }

void DDTreadmill_FrameEnd()
{
	if (!DDTreadmill_Active) return;
	const auto now = Clock::now();
	const int64_t frameNs = std::chrono::duration_cast<std::chrono::nanoseconds>(now - lastFrame).count();
	lastFrame = now;
	if (frameLog)
	{
		fprintf(frameLog, "%lld,%d,%.1f,%.1f,%.1f,%lld,%d\n", (long long)frameNo++, primaryLevel->maptime, frameNs / 1000.0,
			simNs / 1000.0, uploadNs / 1000.0, (long long)uploadCount, shiftFlag);
		if ((frameNo & 255) == 0) fflush(frameLog);
	}
	simNs = uploadNs = uploadCount = 0;
	shiftFlag = 0;
}
