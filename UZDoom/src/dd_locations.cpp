// [Doomerfall] Doom's side of Daggerfall's location ledger (bridge kinds 200-205, DoomerfallLocations.cs).
// Daggerfall holds the permanent record of what happened in each place: dead monsters and where their corpses lie,
// monsters that were hurt or moved, pickups taken, items dropped. Doom still decides the physics, and reports a
// place's whole record when the player leaves it and when it saves. Doom's world table is only this session's cache.
// The record goes through the ordered event ring rather than a bulk slot: a slaughter-sized record is larger than one
// 64 KB slot, and the ring keeps it ahead of the save request that follows it.
//
// Places: a dungeon (map id) or a building interior (map id and building key) is reported when the player leaves it
// and when Doom saves inside it, and asked for when the player enters it. The exterior (towns and the overworld, one
// world table area in world units) is reported per world chunk: every chunk whose facts changed, on leaving an exterior
// map and with every save. After a load Doom asks for every exterior chunk at once and rebuilds what its cache lacks.

#include <algorithm>
#include <chrono>
#include <cinttypes>
#include <cmath>
#include <cstring>
#include <deque>
#include <string>
#include <unordered_map>
#include <vector>

#include "../../bridge/doomerfall_bridge.h"
#include "dd_locations.h"
#include "doomstat.h"
#include "gamestate.h"
#include "g_levellocals.h"
#include "printf.h"

namespace
{
constexpr int WaitTics = 35 * 5;	// Without an answer, the entered place is built from Doom's cache.

constexpr size_t PacePerFrame = 2048;	// Half the ring, so a slaughter-sized record never overflows the outbox.

dfb_session *lastSession;
std::deque<dfb_event> outgoing;	// Records (and a save request behind its record), sent a share per bridge frame.
uint32_t sendGeneration, nextGeneration, requestGeneration, worldGeneration;	// one counter for both requests, so their answers never mix
DDPlaceKey requestPlace;
int waitUntil, worldWaitUntil;
bool requestPending, waiting, worldPending, worldWaiting, worldDone;

// The record being received.
struct Incoming
{
	uint32_t generation = 0;
	dfb_place header{};
	std::vector<FString> names;
	std::vector<dfb_place_fact> facts;
	int mooks = -1;
	std::vector<DDPlanQuest> plan;
	bool complete = false;
};
Incoming in;					// the entered dungeon or interior
std::vector<Incoming> chunksIn;	// exterior chunk records of the world answer, complete, waiting for the playsim

const char *KindName(uint32_t kind)
{
	return kind == DFB_PLACE_DUNGEON ? "D" : kind == DFB_PLACE_INTERIOR ? "B" : kind == DFB_PLACE_CHUNK ? "O" : "?";
}

FString PlaceName(const DDPlaceKey &k)
{
	if (k.kind == DFB_PLACE_DUNGEON) return FStringf("D%d", k.mapId);
	if (k.kind == DFB_PLACE_INTERIOR) return FStringf("B%d:%d", k.mapId, k.key);
	return FStringf("%s%d,%d", KindName(k.kind), k.mapId, k.key);
}

uint16_t NameIndex(std::unordered_map<std::string, uint16_t> &index, std::vector<FString> &names, const FString &name)
{
	auto it = index.find(name.GetChars());
	if (it != index.end()) return it->second;
	const uint16_t n = uint16_t(names.size());
	names.push_back(name);
	index.emplace(name.GetChars(), n);
	return n;
}

template <typename T> void Push(std::vector<dfb_event> &out, uint16_t kind, const T &body)
{
	dfb_event e{};
	e.kind = kind;
	e.tic = gametic;
	static_assert(sizeof(T) <= sizeof(e.payload), "payload too large");
	memcpy(e.payload, &body, sizeof(body));
	out.push_back(e);
}

// One place's record as events: BEGIN, NAMEs, PLANs, FACTs, END.
void Build(std::vector<dfb_event> &out, const DDPlaceKey &place, uint32_t flags, const std::vector<DDPlaceFact> &facts, int mooks, const std::vector<DDPlanQuest> &plan)
{
	const uint32_t gen = ++sendGeneration;
	std::unordered_map<std::string, uint16_t> index;
	std::vector<FString> names;
	std::vector<dfb_place_fact> rows;
	rows.reserve(facts.size());
	for (const DDPlaceFact &f : facts)
	{
		dfb_place_fact r{};
		r.id = f.id;
		r.generation = gen;
		r.x = float(f.x);
		r.y = float(f.y);
		r.z = float(f.z);
		r.height = float(f.height);
		r.health = f.health;
		r.amount = f.amount;
		r.cls = NameIndex(index, names, f.cls.GetChars());
		r.death = f.death.IsEmpty() ? uint16_t(DFB_PLACE_NO_NAME) : NameIndex(index, names, f.death);
		double turns = f.angle / 360.0;
		turns -= floor(turns);
		r.angle = uint16_t(llround(turns * 65536) & 0xFFFF);
		r.kind = uint8_t(f.kind);
		r.flags = uint8_t((f.dropped ? DFB_FACT_DROPPED : 0) | (f.session ? DFB_FACT_SESSION : 0));
		rows.push_back(r);
	}
	const dfb_place header{ gen, place.kind, place.mapId, flags, uint32_t(rows.size()), uint32_t(names.size()), uint32_t(mooks >= 0 ? plan.size() + 1 : 0), place.key };
	Push(out, DFB_KIND_PLACE_BEGIN, header);
	for (size_t n = 0; n < names.size(); n++)
	{
		const FString &name = names[n];
		size_t at = 0;
		do
		{
			dfb_place_name e{};
			e.generation = gen;
			e.index = uint16_t(n);
			const size_t count = std::min<size_t>(40, name.Len() - at);
			memcpy(e.text, name.GetChars() + at, count);
			at += count;
			Push(out, DFB_KIND_PLACE_NAME, e);
		} while (at < name.Len());
	}
	if (mooks >= 0)
	{
		Push(out, DFB_KIND_PLACE_PLAN, dfb_place_plan{ 0, gen, 1, 0, 0, 0, mooks });
		for (const DDPlanQuest &q : plan)
			Push(out, DFB_KIND_PLACE_PLAN, dfb_place_plan{ q.placement, gen, 0, float(q.x), float(q.y), float(q.z), q.enemyType });
	}
	for (const dfb_place_fact &r : rows) Push(out, DFB_KIND_PLACE_FACT, r);
	Push(out, DFB_KIND_PLACE_END, header);
}

void CountKinds(const std::vector<DDPlaceFact> &facts, int kinds[4])
{
	for (const DDPlaceFact &f : facts) kinds[std::clamp(f.kind, 0, 3)]++;
}

// Snapshot of the current dungeon or interior, as a record. False when the player is in neither.
bool Report(FLevelLocals *Level, uint32_t flags, std::vector<dfb_event> &out)
{
	DDPlaceKey place;
	if (!Level || !DDTreadmill_CurrentSpace(place)) return false;
	const auto t0 = std::chrono::steady_clock::now();
	std::vector<DDPlaceFact> facts;
	DDTreadmill_SnapshotPlace(Level, facts);
	int mooks = -1;
	std::vector<DDPlanQuest> plan;
	if (place.kind != DFB_PLACE_DUNGEON || !DD_MonstersPlanOf(place.mapId, mooks, plan)) mooks = -1;
	const size_t before = out.size();
	Build(out, place, flags, facts, mooks, plan);
	const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	int kinds[4] = {};
	CountKinds(facts, kinds);
	Printf("DDLOC report %s%s: %d facts (%d monsters, %d corpses, %d items, %d gone), %d events, %d bytes, %.2f ms to build\n", PlaceName(place).GetChars(),
		(flags & DFB_PLACE_ON_SAVE) ? " for a save" : " on leaving", int(facts.size()), kinds[0], kinds[1], kinds[2], kinds[3],
		int(out.size() - before), int((out.size() - before) * sizeof(dfb_event)), ms);
	return true;
}

// Every exterior chunk whose facts changed since the last report, as one record each.
void ReportChunks(FLevelLocals *Level, uint32_t flags, std::vector<dfb_event> &out)
{
	const auto t0 = std::chrono::steady_clock::now();
	std::vector<DDChunkFacts> chunks;
	DDTreadmill_SnapshotChunks(Level, chunks);
	if (chunks.empty()) return;
	const size_t before = out.size();
	int kinds[4] = {}, facts = 0;
	FString list;
	for (const DDChunkFacts &c : chunks)
	{
		Build(out, DDPlaceKey{ DFB_PLACE_CHUNK, c.cx, c.cy }, flags, c.facts, -1, {});
		CountKinds(c.facts, kinds);
		facts += int(c.facts.size());
		if (list.Len() < 120) list.AppendFormat(" O%d,%d:%d", c.cx, c.cy, int(c.facts.size()));
	}
	const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	Printf("DDLOC report %d exterior chunks%s: %d facts (%d monsters, %d corpses, %d items, %d gone), %d events, %.2f ms to build;%s\n", int(chunks.size()),
		(flags & DFB_PLACE_ON_SAVE) ? " for a save" : " on leaving", facts, kinds[0], kinds[1], kinds[2], kinds[3], int(out.size() - before), ms, list.GetChars());
}

// Sends up to PacePerFrame queued events, and only when the outbox is empty. The ring keeps them in order.
void Pump(dfb_session *session)
{
	if (outgoing.empty() || dfb_flush(session) > 0) return;
	const auto t0 = std::chrono::steady_clock::now();
	size_t sent = 0;
	for (; sent < PacePerFrame && !outgoing.empty(); sent++)
	{
		dfb_send(session, &outgoing.front());
		outgoing.pop_front();
	}
	dfb_flush(session);
	const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	Printf("DDLOC sent %d events, %d still queued, %.2f ms\n", int(sent), int(outgoing.size()), ms);
}

void SendPlaceRequest(dfb_session *session, uint32_t generation, const DDPlaceKey &place)
{
	dfb_event e{};
	e.kind = DFB_KIND_PLACE_REQUEST;
	e.tic = gametic;
	const dfb_place body{ generation, place.kind, place.mapId, 0, 0, 0, 0, place.key };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
}

void SendRequest(dfb_session *session)
{
	requestPending = false;
	SendPlaceRequest(session, requestGeneration, requestPlace);
	Printf("DDLOC asked Daggerfall for %s (request %u)\n", PlaceName(requestPlace).GetChars(), requestGeneration);
}

void SendWorldRequest(dfb_session *session)
{
	worldPending = false;
	SendPlaceRequest(session, worldGeneration, DDPlaceKey{ DFB_PLACE_WORLD, 0, 0 });
	Printf("DDLOC asked Daggerfall for every exterior chunk (request %u)\n", worldGeneration);
}

std::vector<DDPlaceFact> Facts(const Incoming &rec)
{
	std::vector<DDPlaceFact> facts;
	facts.reserve(rec.facts.size());
	for (const dfb_place_fact &r : rec.facts)
	{
		DDPlaceFact f;
		f.id = r.id;
		f.cls = r.cls < rec.names.size() ? FName(rec.names[r.cls].GetChars()) : FName(NAME_None);
		if (r.death != DFB_PLACE_NO_NAME && r.death < rec.names.size()) f.death = rec.names[r.death];
		f.x = r.x;
		f.y = r.y;
		f.z = r.z;
		f.height = r.height;
		f.angle = r.angle * (360.0 / 65536);
		f.health = r.health;
		f.amount = r.amount;
		f.kind = r.kind;
		f.dropped = (r.flags & DFB_FACT_DROPPED) != 0;
		f.session = (r.flags & DFB_FACT_SESSION) != 0;
		facts.push_back(f);
	}
	return facts;
}

void ApplySpace(FLevelLocals *Level)
{
	if (!waiting || !in.complete) return;
	in.complete = false;
	waiting = false;
	const DDPlaceKey got{ in.header.place_kind, in.header.map_id, in.header.key };
	if (!(got == requestPlace)) return;
	const auto t0 = std::chrono::steady_clock::now();
	if (got.kind == DFB_PLACE_DUNGEON && in.mooks >= 0) DD_MonstersSetPlan(got.mapId, in.mooks, in.plan);
	if (!(in.header.flags & DFB_PLACE_KNOWN))
	{
		Printf("DDLOC Daggerfall has no record of %s; first visit\n", PlaceName(got).GetChars());
		return;
	}
	const std::vector<DDPlaceFact> facts = Facts(in);
	DDTreadmill_ApplyPlace(Level, got, facts);
	const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	Printf("DDLOC applied Daggerfall's record of %s: %d facts, plan %d mooks, %.2f ms\n", PlaceName(got).GetChars(), int(facts.size()), in.mooks, ms);
}

void ApplyWorld(FLevelLocals *Level)
{
	if (chunksIn.empty() && !worldDone) return;
	const auto t0 = std::chrono::steady_clock::now();
	DDChunkApplyStats stats;
	int facts = 0;
	for (const Incoming &rec : chunksIn)
	{
		const std::vector<DDPlaceFact> f = Facts(rec);
		facts += int(f.size());
		DDTreadmill_ApplyChunk(Level, rec.header.map_id, rec.header.key, f, stats);
	}
	const int count = int(chunksIn.size());
	chunksIn.clear();
	if (count)
	{
		const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
		Printf("DDLOC applied %d exterior chunk records (%d facts): %d matched Doom's cache, %d rebuilt (%d rows stored, %d kept live, %d stale rows removed), %.2f ms\n",
			count, facts, stats.matched, stats.rebuilt, stats.stored, stats.keptLive, stats.removed, ms);
	}
	if (worldDone)
	{
		worldDone = false;
		worldWaiting = false;
		Printf("DDLOC exterior ledger received\n");
	}
}
}

void DD_LocationsLeaving(FLevelLocals *Level)
{
	if (!lastSession) return;
	std::vector<dfb_event> now;
	Report(Level, 0, now);
	outgoing.insert(outgoing.end(), now.begin(), now.end());
	waiting = false;
}

void DD_LocationsLeftExterior(FLevelLocals *Level)
{
	if (!lastSession) return;
	std::vector<dfb_event> now;
	ReportChunks(Level, 0, now);
	outgoing.insert(outgoing.end(), now.begin(), now.end());
}

void DD_LocationsEntered(const DDPlaceKey &place)
{
	requestGeneration = ++nextGeneration;
	requestPlace = place;
	waiting = true;
	waitUntil = gametic + WaitTics;
	in = Incoming();
	requestPending = true;
	if (lastSession) SendRequest(lastSession);
}

bool DD_LocationsWaiting()
{
	if (waiting && gametic > waitUntil)
	{
		Printf(TEXTCOLOR_ORANGE "DDLOC no record from Daggerfall for %s; building from Doom's cache\n", PlaceName(requestPlace).GetChars());
		waiting = false;
	}
	return waiting;
}

bool DD_LocationsWorldWaiting()
{
	if (worldWaiting && gametic > worldWaitUntil)
	{
		Printf(TEXTCOLOR_ORANGE "DDLOC Daggerfall's exterior ledger did not arrive; the overworld is built from Doom's cache\n");
		worldWaiting = false;
	}
	return worldWaiting;
}

void DD_LocationsTick(FLevelLocals *Level)
{
	ApplyWorld(Level);
	ApplySpace(Level);
}

void DD_LocationsSave(dfb_session *session, const dfb_event &request)
{
	lastSession = session;
	std::vector<dfb_event> now;
	if (gamestate == GS_LEVEL)
	{
		Report(primaryLevel, DFB_PLACE_ON_SAVE, now);
		ReportChunks(primaryLevel, DFB_PLACE_ON_SAVE, now);
	}
	outgoing.insert(outgoing.end(), now.begin(), now.end());
	outgoing.push_back(request);
	Pump(session);
}

void DD_LocationsFrame(dfb_session *session)
{
	lastSession = session;
	Pump(session);
	if (requestPending) SendRequest(session);
	if (worldPending) SendWorldRequest(session);
}

void DD_LocationsResync()
{
	// A load replaced every actor; nothing entered is waiting for a record. Daggerfall's exterior ledger came from the
	// same save; it is asked for so that whatever Doom's world table lacks is rebuilt from it.
	waiting = requestPending = false;
	in = Incoming();
	chunksIn.clear();
	worldGeneration = ++nextGeneration;
	worldPending = worldWaiting = true;
	worldDone = false;
	worldWaitUntil = gametic + WaitTics;
	DDTreadmill_ForgetDirtyChunks();
}

bool DD_LocationsEvent(const dfb_event &e)
{
	static Incoming chunk;	// an exterior chunk record of the world answer, being received
	auto current = [&](uint32_t generation) -> Incoming * {
		if (in.generation && generation == in.generation) return &in;
		if (chunk.generation && generation == chunk.generation) return &chunk;
		return nullptr;
	};
	switch (e.kind)
	{
	case DFB_KIND_PLACE_BEGIN:
	{
		dfb_place h;
		memcpy(&h, e.payload, sizeof(h));
		if (h.place_kind == DFB_PLACE_CHUNK || h.place_kind == DFB_PLACE_WORLD)
		{
			chunk = Incoming();
			if (worldWaiting && h.generation == worldGeneration) { chunk.generation = h.generation; chunk.header = h; chunk.facts.reserve(h.facts); }
			return true;
		}
		in = Incoming();
		if (h.generation == requestGeneration && waiting) { in.generation = h.generation; in.header = h; in.facts.reserve(h.facts); }
		return true;
	}
	case DFB_KIND_PLACE_NAME:
	{
		dfb_place_name n;
		memcpy(&n, e.payload, sizeof(n));
		Incoming *rec = current(n.generation);
		if (!rec) return true;
		if (n.index >= rec->names.size()) rec->names.resize(n.index + 1);
		size_t len = 0;
		while (len < sizeof(n.text) && n.text[len]) len++;
		rec->names[n.index].AppendCStrPart(n.text, len);
		return true;
	}
	case DFB_KIND_PLACE_PLAN:
	{
		dfb_place_plan p;
		memcpy(&p, e.payload, sizeof(p));
		Incoming *rec = current(p.generation);
		if (!rec) return true;
		if (p.header) rec->mooks = p.value;
		else rec->plan.push_back({ p.placement, p.x, p.y, p.z, p.value });
		return true;
	}
	case DFB_KIND_PLACE_FACT:
	{
		dfb_place_fact f;
		memcpy(&f, e.payload, sizeof(f));
		if (Incoming *rec = current(f.generation)) rec->facts.push_back(f);
		return true;
	}
	case DFB_KIND_PLACE_END:
	{
		dfb_place h;
		memcpy(&h, e.payload, sizeof(h));
		Incoming *rec = current(h.generation);
		if (!rec) return true;
		if (rec->facts.size() != h.facts) Printf(TEXTCOLOR_RED "DDLOC record of %s%d,%d arrived with %d of %u facts\n", KindName(h.place_kind), h.map_id, h.key, int(rec->facts.size()), h.facts);
		if (rec == &chunk)
		{
			if (h.place_kind == DFB_PLACE_WORLD) worldDone = true;
			else chunksIn.push_back(std::move(chunk));
			chunk = Incoming();
		}
		else in.complete = true;
		return true;
	}
	default:
		return false;
	}
}
