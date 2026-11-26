// [Doomerfall] The mook placer (encounter card 5; design sections 6.6 and 9.3 of
// work/notes/20261123-205402-fractal-encounter-variety.md). Given the placements of a converted dungeon, it measures
// each one for the planner (walking distance from the entrance, walking distance to the nearest treasure marker, and
// what fits at the origin), plans them (EncounterLeaders.zs), and finds a spot for every planned mook:
//
// - The leader (member 0) is the highest-point mook that fits at the origin, by Doom's own position check. It stands
//   exactly on the origin. If none fits, the pool's cheapest monster becomes the leader there.
// - The others spread out from the origin over a 16-unit walk grid, breadth first in a fixed neighbour order, so the
//   rings and their order are fixed. A grid step is walkable when a small body fits there by P_CheckPosition (walls,
//   blocking lines, floor and ceiling; actors are ignored, so doors and decorations do not cut the graph) and the
//   floor changes by at most a step. A spot is valid when the mook's own body fits there by P_CheckPosition, actors
//   included, and it keeps dd_enc_spacing times the sum of the two radii from every other mook on that floor.
// - Points are never lost: when a placement's whole walkable area is full, the planner promotes its mooks to fewer,
//   stronger ones (up to three times), then the rest move to the nearest placement with room. Points are dropped
//   only when every placement is full, and the summary reports them.
//
// Everything runs in one call with a fixed order, so the same map and request give the same spots.

#include <algorithm>
#include <chrono>
#include <cinttypes>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "dd_encounter_placer.h"
#include "vm.h"
#include "actor.h"
#include "c_cvars.h"
#include "g_levellocals.h"
#include "p_local.h"
#include "p_checkposition.h"
#include "p_maputl.h"
#include "m_bbox.h"
#include "printf.h"
#include "playsim/dd_log.h" // [Doomerfall]

CVAR(Float, dd_enc_spacing, 3.f, CVAR_NOSAVE | CVAR_MOD)	// centre distance between mooks, in sums of their radii (3: a gap of two body widths)
CVAR(Float, dd_enc_min_spacing, 1.f, CVAR_NOSAVE | CVAR_MOD)	// used when an area is full at dd_enc_spacing, before promoting (1: bodies may not overlap)
CVAR(Bool, dd_enc_log, false, CVAR_NOSAVE | CVAR_MOD)		// logs every mook's spot

namespace
{
// The walk probe is more than half a grid step, so a wall between two grid points always touches one of them. A 16
// grid with a radius-10 probe missed most 24-unit doorways (a grid line must fall within 2 units of the doorway's
// centre), which cut Privateer's Hold's entrance off from 97% of the map; 8 and 5 always find a grid line through.
constexpr double Grid = 8;
constexpr double WalkRadius = 5;
constexpr double WalkHeight = 32;
constexpr double Step = 24;
constexpr double Bucket = 128;
constexpr int TreasureMagic = 7366;	// EnemyRoster.TreasureMagic in the converter
constexpr int PromoteTries = 3;
const int Di[4] = { 1, 0, -1, 0 }, Dj[4] = { 0, 1, 0, -1 };

struct Node { int i, j; double z; };
int64_t Key(int i, int j, double z) { return (int64_t(i & 0xFFFFF) << 40) | (int64_t(j & 0xFFFFF) << 20) | int64_t((int(lround(z)) + 0x80000) & 0xFFFFF); }

struct Mook { int member; PClassActor *cls; uint64_t id; int cost; };
struct Search
{
	std::vector<Node> order;
	size_t head = 0;
	std::unordered_set<int64_t> seen;
	std::map<std::pair<int, int>, size_t> cursor;	// per body size: how far along the order spots are used up
};
struct State
{
	DVector3 origin;
	Node start{};
	bool hasStart = false, processed = false, full = false;
	FString role;
	std::vector<Mook> mooks;
	std::vector<int> spot;	// per member: index into the spots, -1 when not placed
	std::vector<DVector3> pos;
	int placed = 0;			// members 0 .. placed-1 have spots
	Search search;
};
struct Spot { double x, y, z, r, h; bool alive; };

class Placer
{
public:
	FLevelLocals *Level;
	AActor *probe = nullptr;
	DObject *plan = nullptr;
	std::vector<State> st;
	std::vector<Spot> spots;
	std::unordered_map<int64_t, std::vector<int>> buckets;
	std::unordered_map<int64_t, double> walkCache;	// NaN when the step is blocked
	std::unordered_map<std::string, PClassActor *> classes;
	double maxR = 0;
	// Per body size, the nodes of searches that found no spot: everything walkable from such a start. A start among
	// them reaches only part of that area, so it is full for that size too, until spots are freed (Unplace).
	std::map<std::pair<int, int>, std::unordered_set<int64_t>> fullNodes;
	int skippedFull = 0, crowded = 0;
	int checks = 0, promotes = 0, moves = 0, cheapestLeaders = 0, cheapestPoints = 0, stuckLeaders = 0, droppedPoints = 0;
	VMFunction *fMooks = nullptr, *fMakeLeader = nullptr, *fCheapest = nullptr, *fPromote = nullptr, *fDrop = nullptr, *fMove = nullptr;

	explicit Placer(FLevelLocals *l) : Level(l) {}

	// A body of stock radius r. With squeeze, as P_TryMove moves monsters: where it is stuck on level geometry or a door
	// leaf in a gap narrower than itself, it may stand at its squeeze width (DD_InGap, AActor::SqueezeRadius). Leaders
	// on their markers and the fit measurement squeeze; spread mooks take only spots their stock body fits.
	double lastCeiling = 0;	// ceiling at the last spot Check passed

	bool Check(double x, double y, double z, double r, double h, bool actors, double &floorz, bool squeeze = true)
	{
		probe->radius = r;
		probe->Height = h;
		if (actors) probe->flags2 &= ~MF2_THRUACTORS;
		else probe->flags2 |= MF2_THRUACTORS;
		probe->SetXYZ(DVector3(x, y, z));
		FCheckPosition tm;
		checks++;
		bool ok = P_CheckPosition(probe, DVector2(x, y), tm);
		AActor *blocker = probe->BlockingMobj.ForceGet();
		if (!ok && squeeze && probe->SqueezeRadius() < r && (!blocker || DD_IsDoorLeaf(blocker)) && DD_InGap(probe, DVector2(x, y)))
		{
			DD_SqueezeActor = probe;
			checks++;
			ok = P_CheckPosition(probe, DVector2(x, y), tm);
			DD_SqueezeActor = nullptr;
		}
		if (ok) { floorz = tm.floorz; lastCeiling = tm.ceilingz; }
		return ok;
	}

	bool Walk(int i, int j, double fromZ, double &z)
	{
		const int64_t key = Key(i, j, fromZ);
		auto it = walkCache.find(key);
		if (it == walkCache.end())
		{
			double f = 0;
			// Up by at most a step; down by any height, since a body walking away from the start can drop off a ledge.
			const bool ok = Check(i * Grid, j * Grid, fromZ, WalkRadius, WalkHeight, false, f, false) && f - fromZ <= Step;
			it = walkCache.emplace(key, ok ? f : NAN).first;
		}
		if (std::isnan(it->second)) return false;
		z = it->second;
		return true;
	}

	// The walk grid point next to a position: the nearest of the four around it that a body fits at.
	bool StartNode(const DVector3 &at, Node &n)
	{
		const int i0 = int(floor(at.X / Grid)), j0 = int(floor(at.Y / Grid));
		std::pair<double, int> order[4];
		for (int k = 0; k < 4; k++)
		{
			const double dx = (i0 + (k & 1)) * Grid - at.X, dy = (j0 + (k >> 1)) * Grid - at.Y;
			order[k] = { dx * dx + dy * dy, k };
		}
		std::sort(order, order + 4);
		for (auto &o : order)
		{
			const int i = i0 + (o.second & 1), j = j0 + (o.second >> 1);
			double z;
			if (Walk(i, j, at.Z, z)) { n = { i, j, z }; return true; }
		}
		return false;
	}

	void Flood(const std::vector<Node> &seeds, std::unordered_map<int64_t, int> &dist)
	{
		std::vector<Node> queue;
		for (const Node &s : seeds)
			if (dist.emplace(Key(s.i, s.j, s.z), 0).second) queue.push_back(s);
		for (size_t h = 0; h < queue.size(); h++)
		{
			const Node n = queue[h];
			const int d = dist[Key(n.i, n.j, n.z)];
			for (int k = 0; k < 4; k++)
			{
				double z;
				if (!Walk(n.i + Di[k], n.j + Dj[k], n.z, z)) continue;
				if (dist.emplace(Key(n.i + Di[k], n.j + Dj[k], z), d + 1).second) queue.push_back({ n.i + Di[k], n.j + Dj[k], z });
			}
		}
	}

	bool NodeAt(Search &s, size_t k)
	{
		while (s.order.size() <= k && s.head < s.order.size())
		{
			const Node n = s.order[s.head++];
			for (int d = 0; d < 4; d++)
			{
				double z;
				if (!Walk(n.i + Di[d], n.j + Dj[d], n.z, z)) continue;
				if (s.seen.insert(Key(n.i + Di[d], n.j + Dj[d], z)).second) s.order.push_back({ n.i + Di[d], n.j + Dj[d], z });
			}
		}
		return k < s.order.size();
	}

	static int64_t BucketKey(int bx, int by) { return (int64_t(bx) << 32) ^ int64_t(uint32_t(by)); }

	int AddSpot(double x, double y, double z, double r, double h)
	{
		spots.push_back({ x, y, z, r, h, true });
		buckets[BucketKey(int(floor(x / Bucket)), int(floor(y / Bucket)))].push_back(int(spots.size() - 1));
		maxR = std::max(maxR, r);
		return int(spots.size() - 1);
	}

	// A body here would touch something that can move: a line with a special (a switch, door or lift trigger) or a
	// sector that is already moving. Escorts never stand there, because the placer runs a few tics after load, when
	// such geometry may already move.
	bool NearMover(double x, double y, double r)
	{
		FBoundingBox box(x, y, r + 4);
		FBlockLinesIterator it(Level, box);
		while (line_t *ld = it.Next())
		{
			if (!inRange(box, ld) || BoxOnLineSide(box, ld) != -1) continue;
			if (ld->special) return true;
			for (sector_t *sec : { ld->frontsector, ld->backsector })
				if (sec && Moving(sec)) return true;
		}
		return Moving(Level->PointInSector(DVector2(x, y)));
	}

	// Moving now, or one of its 3D floors is. (Tags alone are no sign: every 3D floor's target sector is tagged, and
	// rejecting them removed about half of Privateer's Hold.)
	static bool Moving(sector_t *sec)
	{
		if (sec->floordata || sec->ceilingdata) return true;
		for (F3DFloor *rover : sec->e->XFloor.ffloors)
			if (rover->model && (rover->model->floordata || rover->model->ceilingdata)) return true;
		return false;
	}

	double spacing = 3;	// the spacing in use: dd_enc_spacing, or dd_enc_min_spacing when an area is full

	bool Spaced(double x, double y, double z, double r, double h)
	{
		const double k = std::max(1., spacing);
		const double reach = k * (r + maxR);
		const int bx0 = int(floor((x - reach) / Bucket)), bx1 = int(floor((x + reach) / Bucket));
		const int by0 = int(floor((y - reach) / Bucket)), by1 = int(floor((y + reach) / Bucket));
		for (int bx = bx0; bx <= bx1; bx++)
			for (int by = by0; by <= by1; by++)
			{
				auto it = buckets.find(BucketKey(bx, by));
				if (it == buckets.end()) continue;
				for (int idx : it->second)
				{
					const Spot &q = spots[idx];
					if (!q.alive || fabs(z - q.z) >= std::max(h, q.h)) continue;
					const double need = k * (r + q.r), dx = x - q.x, dy = y - q.y;
					if (dx * dx + dy * dy < need * need) return false;
					// Doom bodies are squares: whatever the spacing, the boxes must not touch.
					if (std::max(fabs(dx), fabs(dy)) < r + q.r + 1) return false;
				}
			}
		return true;
	}

	PClassActor *Class(const char *name)
	{
		auto it = classes.find(name);
		if (it != classes.end()) return it->second;
		return classes[name] = PClass::FindActor(name);
	}

	// ---- The planner ----

	VMFunction *Find(const char *name)
	{
		VMFunction *f = nullptr;
		PClass::FindFunction(&f, "DoomerfallEncounterLeaders", name);
		return f;
	}

	// Calls a hook taking (plan, index[, arg]); returns its int result, or 0 for a void hook.
	int CallInt(VMFunction *f, int index, int arg, int nargs = 3, bool returns = true)
	{
		int result = 0;
		VMValue params[] = { (void *)plan, index, arg };
		VMReturn ret(&result);
		VMCall(f, params, nargs, returns ? &ret : nullptr, returns ? 1 : 0);
		return result;
	}

	FString CallText(const char *name)
	{
		FString answer;
		VMFunction *f = Find(name);
		if (!f) return answer;
		VMValue params[] = { (void *)plan };
		VMReturn ret(&answer);
		VMCall(f, params, 1, &ret, 1);
		return answer;
	}

	// Reads a placement's mooks from the plan. Spots already found for the leading members are kept.
	void ReadMooks(int p)
	{
		State &s = st[p];
		FString answer;
		VMValue params[] = { (void *)plan, p };
		VMReturn ret(&answer);
		VMCall(fMooks, params, 2, &ret, 1);
		s.mooks.clear();
		bool first = true;
		for (auto &line : answer.Split("\n"))
		{
			if (first) { s.role = line; first = false; continue; }
			int member, hi, lo, cost;
			char cls[96];
			if (sscanf(line.GetChars(), "%d %95s %d %d %d", &member, cls, &hi, &lo, &cost) != 5) continue;
			s.mooks.push_back({ member, Class(cls), (uint64_t(uint32_t(hi)) << 32) | uint32_t(lo), cost });
		}
		s.spot.resize(s.mooks.size(), -1);
		s.pos.resize(s.mooks.size());
		s.placed = std::min(s.placed, int(s.mooks.size()));
	}

	// ---- Spots ----

	void Body(PClassActor *cls, double &r, double &h) const
	{
		const AActor *def = cls ? GetDefaultByType(cls) : nullptr;
		r = def ? std::max(1., def->radius) : 20;	// stock: monsters squeeze only in gaps (Check)
		h = def ? std::max(1., def->Height) : 56;
	}

	bool FitsAtOrigin(const State &s, PClassActor *cls)
	{
		double r, h, f;
		Body(cls, r, h);
		return Check(s.origin.X, s.origin.Y, s.origin.Z, r, h, true, f) && fabs(f - s.origin.Z) <= Step;
	}

	// Spread wider first at the preferred spacing; when the whole walkable area is used up, crowd in at the minimum
	// spacing before the placement asks the planner to promote (6.6).
	bool TryPlace(State &s, int m)
	{
		const double tiers[2] = { std::max(1.f, *dd_enc_spacing), std::max(1.f, std::min(*dd_enc_spacing, *dd_enc_min_spacing)) };
		for (int tier = 0; tier < 2; tier++)
		{
			if (tier && tiers[1] >= tiers[0]) break;
			spacing = tiers[tier];
			if (TryPlaceAt(s, m, tier)) { crowded += tier; return true; }
		}
		return false;
	}

	bool TryPlaceAt(State &s, int m, int tier)
	{
		if (!s.hasStart) return false;
		double r, h;
		Body(s.mooks[m].cls, r, h);
		const std::pair<int, int> size{ int(r * 4) + tier * 1000000, int(h) };
		auto full = fullNodes.find(size);
		if (full != fullNodes.end() && full->second.count(Key(s.start.i, s.start.j, s.start.z))) { skippedFull++; return false; }
		size_t &c = s.search.cursor[size];
		for (; NodeAt(s.search, c); c++)
		{
			const Node n = s.search.order[c];
			const double x = n.i * Grid, y = n.j * Grid;
			double f;
			if (!Spaced(x, y, n.z, r, h) || !Check(x, y, n.z, r, h, true, f, false) || fabs(f - n.z) > Step || !Spaced(x, y, f, r, h) || NearMover(x, y, r)) continue;
			s.spot[m] = AddSpot(x, y, f, r, h);
			s.pos[m] = DVector3(x, y, f);
			c++;
			return true;
		}
		// Used up: remember the area, so other starts inside it skip the search for this size.
		auto &done = fullNodes[size];
		for (const Node &n : s.search.order) done.insert(Key(n.i, n.j, n.z));
		return false;
	}

	bool PlaceRest(State &s)
	{
		while (s.placed < int(s.mooks.size()))
		{
			if (!TryPlace(s, s.placed)) return false;
			s.placed++;
		}
		return true;
	}

	void Unplace(State &s)
	{
		for (int m = 1; m < s.placed; m++)
			if (s.spot[m] >= 0) { spots[s.spot[m]].alive = false; s.spot[m] = -1; }
		s.placed = std::min(s.placed, 1);
		s.search.cursor.clear();
		fullNodes.clear();
	}

	FString FullMask()
	{
		FString mask;
		for (const State &s : st) mask += s.full ? '1' : '0';
		return mask;
	}

	void MovePoints(int from, int points)
	{
		while (points > 0)
		{
			const FString mask = FullMask();
			int best = -1;
			{
				VMValue params[] = { (void *)plan, from, points, &mask };
				VMReturn ret(&best);
				VMCall(fMove, params, 4, &ret, 1);
			}
			moves++;
			if (best < 0) { droppedPoints += points; return; }
			points = 0;
			State &b = st[best];
			if (!b.processed) return;	// placed when its turn comes
			ReadMooks(best);
			if (!PlaceRest(b))
			{
				b.full = true;
				points = CallInt(fDrop, best, b.placed);
				ReadMooks(best);
			}
		}
	}

	void Process(int p)
	{
		State &s = st[p];
		s.processed = true;
		// Card 7: points moved here from an earlier placement were added to the plan after ChooseLeader read it.
		ReadMooks(p);
		if (s.mooks.empty() || PlaceRest(s)) return;
		int pending = 0;
		for (int tries = 0;; tries++)
		{
			const int k = s.placed;
			if (tries < PromoteTries && k > 1)
			{
				Unplace(s);
				pending += CallInt(fPromote, p, k);
				promotes++;
				ReadMooks(p);
				if (PlaceRest(s)) break;
				continue;
			}
			pending += CallInt(fDrop, p, std::max(1, k));
			ReadMooks(p);
			break;
		}
		s.full = true;
		MovePoints(p, pending);
	}

	void ChooseLeader(int p)
	{
		State &s = st[p];
		ReadMooks(p);
		if (s.mooks.empty()) return;
		std::vector<int> order(s.mooks.size());
		for (size_t i = 0; i < order.size(); i++) order[i] = int(i);
		std::stable_sort(order.begin(), order.end(), [&](int a, int b) { return s.mooks[a].cost > s.mooks[b].cost; });
		std::unordered_map<PClassActor *, bool> fit;
		int which = -1;
		for (int m : order)
		{
			auto it = fit.find(s.mooks[m].cls);
			const bool ok = it != fit.end() ? it->second : (fit[s.mooks[m].cls] = FitsAtOrigin(s, s.mooks[m].cls));
			if (ok) { which = m; break; }
		}
		if (which > 0) { CallInt(fMakeLeader, p, which, 3, false); ReadMooks(p); }
		else if (which < 0)
		{
			cheapestPoints += CallInt(fCheapest, p, 0, 2);
			cheapestLeaders++;
			ReadMooks(p);
			if (!FitsAtOrigin(s, s.mooks[0].cls)) stuckLeaders++;
		}
		double r, h;
		Body(s.mooks[0].cls, r, h);
		s.spot[0] = AddSpot(s.origin.X, s.origin.Y, s.origin.Z, r, h);
		s.pos[0] = s.origin;
		s.placed = 1;
	}

	void Measure(int p, const std::unordered_map<int64_t, int> &entrance, const std::unordered_map<int64_t, int> &treasure, double &walk, double &near,
		double &fitRadius, double &fitHeight)
	{
		State &s = st[p];
		walk = near = -1;
		if (s.hasStart)
		{
			const int64_t key = Key(s.start.i, s.start.j, s.start.z);
			auto a = entrance.find(key);
			if (a != entrance.end()) walk = a->second * Grid;
			auto t = treasure.find(key);
			if (t != treasure.end()) near = t->second * Grid;
		}
		static const double radii[] = { 128, 96, 64, 48, 40, 32, 24, 20, 16, 12, 8 };
		fitRadius = 1;	// nothing fits: the planner's cheapest-monster fallback
		for (double r : radii)
		{
			double f;
			if (Check(s.origin.X, s.origin.Y, s.origin.Z, r, 1, true, f) && fabs(f - s.origin.Z) <= Step) { fitRadius = r; break; }
		}
		fitHeight = 0;
		double f;
		if (Check(s.origin.X, s.origin.Y, s.origin.Z, std::min(fitRadius, 16.), 1, true, f)) fitHeight = std::max(1., lastCeiling - std::max(f, s.origin.Z));
	}
};
}

bool DD_PlaceEncounters(FLevelLocals *Level, const FString &header, const std::vector<DDEncPlacementIn> &list, std::vector<DDEncMookOut> &out)
{
	out.clear();
	VMFunction *fPlan = nullptr;
	PClass::FindFunction(&fPlan, "DoomerfallEncounterLeaders", "PlanObject");
	PClassActor *spotClass = PClass::FindActor("MapSpot");
	if (!fPlan || !spotClass) return false;
	const auto t0 = std::chrono::steady_clock::now();

	Placer pl(Level);
	pl.fMooks = pl.Find("Mooks");
	pl.fMakeLeader = pl.Find("MakeLeader");
	pl.fCheapest = pl.Find("CheapestLeader");
	pl.fPromote = pl.Find("Promote");
	pl.fDrop = pl.Find("Drop");
	pl.fMove = pl.Find("Move");
	VMFunction *fFaction = pl.Find("Faction");	// card 6: Civil War side and stance
	if (!pl.fMooks || !pl.fMakeLeader || !pl.fCheapest || !pl.fPromote || !pl.fDrop || !pl.fMove) return false;

	// One invisible probe body, never linked into the blockmap, so nothing else can touch it.
	pl.probe = Spawn(Level, spotClass, DVector3(0, 0, 0), NO_REPLACE);
	if (!pl.probe) return false;
	pl.probe->flags |= MF_SOLID;
	pl.probe->flags2 |= MF2_PASSMOBJ;
	pl.probe->flags3 |= MF3_ISMONSTER;	// lines that block monsters block it too
	pl.probe->flags &= ~(MF_NOCLIP);

	// Walking distances from the entrance (the player start) and from every treasure marker.
	std::unordered_map<int64_t, int> entrance, treasure;
	bool hasEntrance = false;
	{
		const FPlayerStart *ps = Level->playerstarts[0].type != 0 ? &Level->playerstarts[0] : (Level->AllPlayerStarts.Size() ? &Level->AllPlayerStarts[0] : nullptr);
		Node n;
		if (ps)
		{
			const DVector2 xy = ps->pos.XY();
			const double z = Level->PointInSector(xy)->floorplane.ZatPoint(xy) + ps->pos.Z;
			if (pl.StartNode(DVector3(xy, z), n)) { pl.Flood({ n }, entrance); hasEntrance = true; }
		}
	}
	std::vector<Node> chests;
	int piles = 0;
	{
		auto it = Level->GetThinkerIterator<AActor>();
		while (AActor *mo = it.Next())
		{
			if (mo->GetClass() != spotClass || mo->args[0] != TreasureMagic) continue;
			piles++;
			Node n;
			if (pl.StartNode(mo->Pos(), n)) chests.push_back(n);
		}
		std::sort(chests.begin(), chests.end(), [](const Node &a, const Node &b) { return Key(a.i, a.j, a.z) < Key(b.i, b.j, b.z); });
		if (!chests.empty()) pl.Flood(chests, treasure);
	}

	// The request, with each placement's measurements.
	pl.st.resize(list.size());
	FString text = header;
	int walkKnown = 0;
	for (size_t i = 0; i < list.size(); i++)
	{
		State &s = pl.st[i];
		s.origin = list[i].pos;
		s.hasStart = pl.StartNode(s.origin, s.start);
		if (s.hasStart) { s.search.order.push_back(s.start); s.search.seen.insert(Key(s.start.i, s.start.j, s.start.z)); }
		double walk, near, fitRadius, fitHeight;
		pl.Measure(int(i), entrance, treasure, walk, near, fitRadius, fitHeight);
		walkKnown += walk >= 0;
		const DDEncPlacementIn &p = list[i];
		text.AppendFormat("p\t%d\t%d\t%.3f\t%.3f\t%.3f\t%d\t%d\t%.1f\t%.1f\t%.1f\t%.1f\n", int32_t(uint32_t(p.placement >> 32)), int32_t(uint32_t(p.placement)),
			p.pos.X, p.pos.Y, p.pos.Z, p.enemyType, p.quest ? 1 : 0, walk, near, fitRadius, fitHeight);
	}
	const auto t1 = std::chrono::steady_clock::now();

	{
		DObject *planObject = nullptr;
		VMValue params[] = { &text };
		VMReturn ret((void **)&planObject);
		VMCall(fPlan, params, 1, &ret, 1);
		pl.plan = planObject;
	}
	if (!pl.plan) { pl.probe->Destroy(); return false; }
	GC::AddSoftRoot(pl.plan);
	const auto t2 = std::chrono::steady_clock::now();

	for (size_t i = 0; i < list.size(); i++) pl.ChooseLeader(int(i));
	for (size_t i = 0; i < list.size(); i++) pl.Process(int(i));
	const auto t3 = std::chrono::steady_clock::now();

	// Re-read every placement (moves may have added to any of them) and hand back the spots.
	uint64_t digest = 14695981039346656037ULL;
	auto mix = [&](int64_t v) { for (int k = 0; k < 8; k++) { digest ^= uint8_t(v >> (8 * k)); digest *= 1099511628211ULL; } };
	int unplaced = 0, emptyPlacements = 0;
	int64_t placedCost = 0;
	size_t cells = 0;
	for (size_t i = 0; i < list.size(); i++)
	{
		State &s = pl.st[i];
		cells += s.search.order.size();
		// -1 in a united dungeon; else side | stance << 4 (EncounterLeaders.zs Faction).
		const int faction = fFaction ? pl.CallInt(fFaction, int(i), 0, 2) : -1;
		for (size_t m = 0; m < s.mooks.size(); m++)
		{
			if (int(m) >= s.placed || s.spot[m] < 0) { unplaced++; continue; }
			out.push_back({ s.mooks[m].id, s.mooks[m].cls, s.pos[m], int(i), int(m), faction < 0 ? -1 : (faction & 15), faction < 0 ? 0 : (faction >> 4) });
			placedCost += s.mooks[m].cost;
			mix(int64_t(s.mooks[m].id));
			mix(lround(s.pos[m].X * 8)); mix(lround(s.pos[m].Y * 8)); mix(lround(s.pos[m].Z * 8));
			if (dd_enc_log)
				DD_DebugPrintf("DDENC mook %016" PRIx64 " %s p %d m %d at %.1f,%.1f,%.1f%s cost %d\n", s.mooks[m].id, s.mooks[m].cls ? s.mooks[m].cls->TypeName.GetChars() : "?",
					int(i), int(m), s.pos[m].X, s.pos[m].Y, s.pos[m].Z, m == 0 ? " leader" : "", s.mooks[m].cost);
		}
		if (s.placed < 1 || s.mooks.empty() || s.spot[0] < 0) emptyPlacements++;
	}
	const FString summary = pl.CallText("Summary");
	for (auto &line : summary.Split("\n")) DD_DebugPrintf("DDENC %s\n", line.GetChars());
	GC::DelSoftRoot(pl.plan);
	pl.probe->Destroy();
	const auto t4 = std::chrono::steady_clock::now();
	auto ms = [](std::chrono::steady_clock::duration d) { return std::chrono::duration<double, std::milli>(d).count(); };
	DD_DebugPrintf("DDENC placer placements %d mooks %d unplaced %d entrance %s (%d nodes) walk-known %d treasure-markers %d (%d on the walk grid, %d nodes) cheapest-leaders %d (+%d pts) "
		"stuck-leaders %d promotes %d moves %d dropped-points (map full) %d spacing %.2f crowded-at-%.2f %d grid-nodes %d checks %d full-skips %d\n",
		int(list.size()), int(out.size()), unplaced, hasEntrance ? "yes" : "none", int(entrance.size()), walkKnown, piles, int(chests.size()), int(treasure.size()),
		pl.cheapestLeaders, pl.cheapestPoints,
		pl.stuckLeaders, pl.promotes, pl.moves, pl.droppedPoints, *dd_enc_spacing, std::min(*dd_enc_spacing, *dd_enc_min_spacing), pl.crowded, int(cells), pl.checks, pl.skippedFull);
	// Card 7 contract check: the plan's spent points must equal the summed cost of the mooks actually handed out.
	DD_DebugPrintf("DDENC contract placed-cost %lld empty-placements %d\n", (long long)placedCost, emptyPlacements);
	if (!hasEntrance) DD_DebugPrintf("DDENC warning: no entrance marker (player start); bosses use the planner's fallback\n");
	DD_DebugPrintf("DDENC timing measure %.1f ms plan %.1f ms place %.1f ms finish %.1f ms total %.1f ms digest %016" PRIx64 "\n",
		ms(t1 - t0), ms(t2 - t1), ms(t3 - t2), ms(t4 - t3), ms(t4 - t0), digest);
	return true;
}
