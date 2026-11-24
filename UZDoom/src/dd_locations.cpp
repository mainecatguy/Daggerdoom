// [Doomerfall] Doom's side of Daggerfall's location ledger (bridge kinds 200-205, DoomerfallLocations.cs).
// Daggerfall holds the permanent record of what happened in each dungeon: dead mooks and where their corpses lie,
// monsters that were hurt or moved, pickups taken, items dropped. Doom still decides the physics, and reports the
// place's whole record when the player leaves it and when it saves there. When the player enters a dungeon, Doom asks
// for Daggerfall's record and builds the place from it; the world table is only this session's cache. The record goes
// through the ordered event ring rather than a bulk slot: a slaughter-sized record is larger than one 64 KB slot, and
// the ring keeps it ahead of the save request that follows it.

#include <algorithm>
#include <chrono>
#include <cinttypes>
#include <cmath>
#include <cstring>
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
constexpr int WaitTics = 35 * 5;	// Without an answer, the entered dungeon is built from Doom's cache.

dfb_session *lastSession;
std::vector<dfb_event> outgoing;	// Records built while leaving a dungeon, sent at the next bridge frame.
uint32_t sendGeneration, requestGeneration;
int requestMap = -1, waitUntil;
bool requestPending, waiting;

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
} in;

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
void Build(std::vector<dfb_event> &out, int mapId, uint32_t flags, const std::vector<DDPlaceFact> &facts, int mooks, const std::vector<DDPlanQuest> &plan)
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
	int nameEvents = 0;
	for (const FString &name : names) nameEvents += std::max(1, int((name.Len() + 39) / 40));
	const dfb_place header{ gen, DFB_PLACE_DUNGEON, mapId, flags, uint32_t(rows.size()), uint32_t(names.size()), uint32_t(mooks >= 0 ? plan.size() + 1 : 0), 0 };
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

// Snapshot of the current dungeon, as a record. False when the player is not in one.
bool Report(FLevelLocals *Level, uint32_t flags, std::vector<dfb_event> &out)
{
	int mapId;
	if (!Level || !DDTreadmill_CurrentDungeon(mapId)) return false;
	const auto t0 = std::chrono::steady_clock::now();
	std::vector<DDPlaceFact> facts;
	DDTreadmill_SnapshotPlace(Level, facts);
	int mooks = -1;
	std::vector<DDPlanQuest> plan;
	if (!DD_MonstersPlanOf(mapId, mooks, plan)) mooks = -1;
	const size_t before = out.size();
	Build(out, mapId, flags, facts, mooks, plan);
	const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	int kinds[4] = {};
	for (const DDPlaceFact &f : facts) kinds[std::clamp(f.kind, 0, 3)]++;
	Printf("DDLOC report D%d%s: %d facts (%d monsters, %d corpses, %d items, %d gone), %d events, %d bytes, %.2f ms to build\n", mapId,
		(flags & DFB_PLACE_ON_SAVE) ? " for a save" : " on leaving", int(facts.size()), kinds[0], kinds[1], kinds[2], kinds[3],
		int(out.size() - before), int((out.size() - before) * sizeof(dfb_event)), ms);
	return true;
}

void SendAll(dfb_session *session, std::vector<dfb_event> &events)
{
	if (events.empty()) return;
	const auto t0 = std::chrono::steady_clock::now();
	int queued = 0;
	for (dfb_event &e : events) queued += dfb_send(session, &e) == DFB_QUEUED;
	dfb_flush(session);
	const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	Printf("DDLOC sent %d events (%d through the outbox), %.2f ms\n", int(events.size()), queued, ms);
	events.clear();
}

void SendRequest(dfb_session *session)
{
	requestPending = false;
	dfb_event e{};
	e.kind = DFB_KIND_PLACE_REQUEST;
	e.tic = gametic;
	const dfb_place body{ requestGeneration, DFB_PLACE_DUNGEON, requestMap, 0, 0, 0, 0, 0 };
	memcpy(e.payload, &body, sizeof(body));
	dfb_send(session, &e);
	Printf("DDLOC asked Daggerfall for D%d (request %u)\n", requestMap, requestGeneration);
}
}

void DD_LocationsLeaving(FLevelLocals *Level)
{
	if (!lastSession) return;
	Report(Level, 0, outgoing);
	waiting = false;
}

void DD_LocationsEntered(int mapId)
{
	requestGeneration++;
	requestMap = mapId;
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
		Printf(TEXTCOLOR_ORANGE "DDLOC no record from Daggerfall for D%d; building from Doom's cache\n", requestMap);
		waiting = false;
	}
	return waiting;
}

void DD_LocationsTick(FLevelLocals *Level)
{
	if (!waiting || !in.complete) return;
	in.complete = false;
	waiting = false;
	if (in.header.map_id != requestMap) return;
	const auto t0 = std::chrono::steady_clock::now();
	if (in.mooks >= 0) DD_MonstersSetPlan(requestMap, in.mooks, in.plan);
	if (!(in.header.flags & DFB_PLACE_KNOWN))
	{
		Printf("DDLOC Daggerfall has no record of D%d; first visit\n", requestMap);
		return;
	}
	std::vector<DDPlaceFact> facts;
	facts.reserve(in.facts.size());
	for (const dfb_place_fact &r : in.facts)
	{
		DDPlaceFact f;
		f.id = r.id;
		f.cls = r.cls < in.names.size() ? FName(in.names[r.cls].GetChars()) : FName(NAME_None);
		if (r.death != DFB_PLACE_NO_NAME && r.death < in.names.size()) f.death = in.names[r.death];
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
	DDTreadmill_ApplyPlace(Level, requestMap, facts);
	const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
	Printf("DDLOC applied Daggerfall's record of D%d: %d facts, plan %d mooks, %.2f ms\n", requestMap, int(facts.size()), in.mooks, ms);
}

void DD_LocationsBeforeSave(dfb_session *session)
{
	lastSession = session;
	SendAll(session, outgoing);
	std::vector<dfb_event> now;
	if (gamestate == GS_LEVEL && Report(primaryLevel, DFB_PLACE_ON_SAVE, now)) SendAll(session, now);
}

void DD_LocationsFrame(dfb_session *session)
{
	lastSession = session;
	SendAll(session, outgoing);
	if (requestPending) SendRequest(session);
}

void DD_LocationsResync()
{
	// A load replaced every actor; nothing entered is waiting for a record.
	waiting = requestPending = false;
	in = Incoming();
}

bool DD_LocationsEvent(const dfb_event &e)
{
	switch (e.kind)
	{
	case DFB_KIND_PLACE_BEGIN:
	{
		dfb_place h;
		memcpy(&h, e.payload, sizeof(h));
		in = Incoming();
		if (h.generation == requestGeneration && waiting) { in.generation = h.generation; in.header = h; in.facts.reserve(h.facts); }
		return true;
	}
	case DFB_KIND_PLACE_NAME:
	{
		dfb_place_name n;
		memcpy(&n, e.payload, sizeof(n));
		if (!in.generation || n.generation != in.generation) return true;
		if (n.index >= in.names.size()) in.names.resize(n.index + 1);
		size_t len = 0;
		while (len < sizeof(n.text) && n.text[len]) len++;
		in.names[n.index].AppendCStrPart(n.text, len);
		return true;
	}
	case DFB_KIND_PLACE_PLAN:
	{
		dfb_place_plan p;
		memcpy(&p, e.payload, sizeof(p));
		if (!in.generation || p.generation != in.generation) return true;
		if (p.header) in.mooks = p.value;
		else in.plan.push_back({ p.placement, p.x, p.y, p.z, p.value });
		return true;
	}
	case DFB_KIND_PLACE_FACT:
	{
		dfb_place_fact f;
		memcpy(&f, e.payload, sizeof(f));
		if (in.generation && f.generation == in.generation) in.facts.push_back(f);
		return true;
	}
	case DFB_KIND_PLACE_END:
	{
		dfb_place h;
		memcpy(&h, e.payload, sizeof(h));
		if (!in.generation || h.generation != in.generation) return true;
		if (in.facts.size() != h.facts) Printf(TEXTCOLOR_RED "DDLOC record of D%d arrived with %d of %u facts\n", h.map_id, int(in.facts.size()), h.facts);
		in.complete = true;
		return true;
	}
	default:
		return false;
	}
}
