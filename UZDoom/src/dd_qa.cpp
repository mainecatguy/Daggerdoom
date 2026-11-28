// [Doomerfall] QA bot channel prototype (tools/qa, work/notes/20261124-120622-qa-bot.md). Claude-run QA only.
// Inactive unless UZDoom is started with -ddqa <folder>: every function returns at once otherwise.
//
// qa.py appends one command per line to <folder>/inbox.txt: "<id> <command> [args]". Answers and events are JSON
// lines appended to <folder>/outbox.jsonl. Commands run inside the game tic (DD_QaTick), so world reads are
// consistent and nothing is changed from between tics. move_to is honest: it steers through the player's own
// input (DD_QaInput, called from G_BuildTiccmd), so Doom's real physics move the player. fly_to is the QA bot's own
// flight, standing in for Levitate (which Doomerfall does not have yet): Doom flight on for that one job only.

#include <algorithm>
#include <cinttypes>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <string>
#include <vector>

#include "actor.h"
#include "actorinlines.h"
#include "c_dispatch.h"
#include "d_player.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "i_interface.h"
#include "i_time.h"
#include "d_protocol.h"
#include "d_event.h"
#include "m_argv.h"
#include "menustate.h"
#include "p_local.h"
#include "printf.h"
#include "dd_guards.h"
#include "playsim/dd_treadmill.h"

extern int forwardmove[2], sidemove[2];
EXTERN_CVAR(Int, dd_sync_df_phase)

namespace
{
FString qaDir;
long inboxPos;
uint64_t nextPoll;
std::deque<std::string> pending;	// Read between tics, run in the next tic.
bool lastPaused, lastInLevel;

struct MoveJob
{
	std::string id;
	bool active = false;
	DVector2 goal;
	double tolerance = 24;
	int startTic = 0, limitTics = 0, lastProgressTic = 0;
	double bestDist = 1e30;
	DVector3 start;
	bool fly = false;	// fly_to: the QA bot's own flight, in place of Levitate (which Doomerfall does not have yet).
	bool landing = false;	// Over the goal with flight off, falling onto it.
	double goalZ = 0;
} move;

int qaPress;	// Buttons pressed for one built command (use).

void Out(const FString &line)
{
	FString path = qaDir + "/outbox.jsonl";
	if (FILE *f = fopen(path.GetChars(), "ab"))
	{
		fputs(line.GetChars(), f);
		fputc('\n', f);
		fclose(f);
	}
}

FString Quote(const char *s)
{
	FString r = "\"";
	for (; *s; s++)
	{
		if (*s == '"' || *s == '\\') r += '\\';
		if ((unsigned char)*s >= 32) r += *s;
	}
	return r + "\"";
}

void Reply(const std::string &id, const char *fields)
{
	Out(FStringf("{\"id\":%s,\"tic\":%d,%s}", Quote(id.c_str()).GetChars(), gametic, fields));
}

void Event(const char *name, const char *fields)
{
	Out(FStringf("{\"event\":\"%s\",\"tic\":%d%s%s}", name, gametic, *fields ? "," : "", fields));
}

FString Where(AActor *mo)
{
	FString s = FStringf("\"x\":%.1f,\"y\":%.1f,\"z\":%.1f,\"angle\":%.1f,\"floorz\":%.1f,\"ceilingz\":%.1f", mo->X(), mo->Y(), mo->Z(),
		mo->Angles.Yaw.Normalized360().Degrees(), mo->floorz, mo->ceilingz);
	if (mo->Sector) s.AppendFormat(",\"sector\":%d", mo->Sector->Index());
	return s;
}

const char *Kind(AActor *mo)
{
	if (DD_IsGuardBot(mo)) return "guard";
	const char *name = mo->GetClass()->TypeName.GetChars();
	if (!strnicmp(name, "DFTownsperson", 13) || !strnicmp(name, "DFNpc", 5) || !strnicmp(name, "DFDungeonNpc", 12)) return "npc";
	if (mo->flags3 & MF3_ISMONSTER) return mo->ddRecordId ? "mook" : "monster";
	if (mo->flags & MF_SPECIAL) return "item";
	return nullptr;
}

void CmdPos(FLevelLocals *Level, const std::string &id, AActor *pmo)
{
	FString f = FStringf("\"ok\":true,\"map\":%s,%s,\"health\":%d,\"god\":%d,\"df_phase\":%d", Quote(Level->MapName.GetChars()).GetChars(), Where(pmo).GetChars(),
		pmo->health, (pmo->player->cheats & CF_GODMODE) != 0, *dd_sync_df_phase);
	double x, y, z, yaw;
	int target;
	if (DDTreadmill_PlayerSpace(x, y, z, yaw, target)) f.AppendFormat(",\"df_space\":[%.1f,%.1f,%.1f],\"df_target\":%d", x, y, z, target);
	Reply(id, f.GetChars());
}

// Lists actors by distance: kind, class, Daggerfall record id, position, health, distance and line of sight.
void CmdActors(FLevelLocals *Level, const std::string &id, AActor *pmo, double radius, int limit, const char *only)
{
	struct Seen { AActor *mo; double d; const char *kind; };
	std::vector<Seen> seen;
	auto it = Level->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
	{
		if (mo == pmo || (mo->renderflags & RF_INVISIBLE)) continue;
		const char *kind = Kind(mo);
		if (!kind) continue;
		if (mo->health <= 0 && strcmp(kind, "item")) continue;
		if (*only && stricmp(only, kind)) continue;
		const double d = (mo->Pos() - pmo->Pos()).Length();
		if (d <= radius) seen.push_back({ mo, d, kind });
	}
	std::sort(seen.begin(), seen.end(), [](const Seen &a, const Seen &b) { return a.d < b.d; });
	FString list = "[";
	int shown = 0;
	for (const Seen &s : seen)
	{
		if (shown == limit) break;
		AActor *mo = s.mo;
		list.AppendFormat("%s{\"ref\":\"%" PRIxPTR "\",\"kind\":\"%s\",\"class\":%s,\"df\":\"%016" PRIx64 "\",\"x\":%.0f,\"y\":%.0f,\"z\":%.0f,\"health\":%d,\"dist\":%.0f,\"los\":%d}",
			shown ? "," : "", (uintptr_t)mo, s.kind, Quote(mo->GetClass()->TypeName.GetChars()).GetChars(), mo->ddRecordId, mo->X(), mo->Y(), mo->Z(),
			mo->health, s.d, P_CheckSight(pmo, mo, SF_IGNOREVISIBILITY) ? 1 : 0);
		shown++;
	}
	list += "]";
	Reply(id, FStringf("\"ok\":true,\"total\":%d,\"shown\":%d,\"actors\":%s", (int)seen.size(), shown, list.GetChars()).GetChars());
}

AActor *FindRef(FLevelLocals *Level, const char *ref)
{
	// A ref from actors (the actor's address, compared only with live actors) or a 16-digit Daggerfall record id.
	const uint64_t want = strtoull(ref, nullptr, 16);
	const bool record = strlen(ref) == 16;
	auto it = Level->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
		if (record ? mo->ddRecordId == want : (uintptr_t)mo == (uintptr_t)want) return mo;
	return nullptr;
}

// The QA bot's flight is the player's own Doom flight (the fly cheat's flags), steered by the fly input like the
// fly-up and fly-down keys. It is on only during a fly_to job and always ends with it.
void SetFlight(AActor *pmo, bool on)
{
	if (on) { pmo->flags2 |= MF2_FLY; pmo->flags |= MF_NOGRAVITY; }
	else { pmo->flags2 &= ~MF2_FLY; pmo->flags &= ~MF_NOGRAVITY; }
}

// Every flight ends here or in TickMove, and both report it as a flew event, which the run summary lists.
void FlewEvent(AActor *pmo, const char *result)
{
	Event("flew", FStringf("\"result\":\"%s\",\"from\":[%.1f,%.1f,%.1f],\"to\":[%.1f,%.1f,%.1f]", result, move.start.X, move.start.Y, move.start.Z,
		pmo->X(), pmo->Y(), pmo->Z()).GetChars());
}

void EndJob(AActor *pmo, const char *result)
{
	if (move.active && move.fly && pmo) { SetFlight(pmo, false); FlewEvent(pmo, result ? result : "ended"); }
	if (move.active && result) Reply(move.id, FStringf("\"done\":true,\"result\":\"%s\"", result).GetChars());
	move.active = false;
}

void Run(FLevelLocals *Level, const std::string &line)
{
	AActor *pmo = Level->Players[consoleplayer]->mo;
	char id[64] = "", cmd[32] = "";
	int used = 0;
	if (sscanf(line.c_str(), "%63s %31s %n", id, cmd, &used) < 2) { Event("bad_line", FStringf("\"line\":%s", Quote(line.c_str()).GetChars()).GetChars()); return; }
	const char *rest = line.c_str() + used;
	if (!pmo) { Reply(id, "\"ok\":false,\"error\":\"no player\""); return; }
	Printf("DDQA %s\n", line.c_str());

	if (!stricmp(cmd, "pos")) CmdPos(Level, id, pmo);
	else if (!stricmp(cmd, "actors"))
	{
		double radius = 4096;
		int limit = 40;
		char only[32] = "";
		sscanf(rest, "%lf %d %31s", &radius, &limit, only);
		CmdActors(Level, id, pmo, radius, limit, only);
	}
	else if (!stricmp(cmd, "move_to") || !stricmp(cmd, "fly_to"))
	{
		// fly_to x y z: rise to z, cross to (x, y), turn flight off and land there. Only for spots that would need
		// Levitate; qa.py goto uses it on the walk graph's levitation links only, and lists every flight.
		const bool fly = !stricmp(cmd, "fly_to");
		double x, y, z = 0, tolerance = fly ? 12 : 24, seconds = 30;
		const int got = fly ? sscanf(rest, "%lf %lf %lf %lf %lf", &x, &y, &z, &tolerance, &seconds) : sscanf(rest, "%lf %lf %lf %lf", &x, &y, &tolerance, &seconds);
		if (got < (fly ? 3 : 2)) { Reply(id, fly ? "\"ok\":false,\"error\":\"fly_to x y z [tolerance] [seconds]\"" : "\"ok\":false,\"error\":\"move_to x y [tolerance] [seconds]\""); return; }
		EndJob(pmo, "replaced");
		move = MoveJob();
		move.id = id;
		move.active = true;
		move.goal = { x, y };
		move.tolerance = tolerance;
		move.start = pmo->Pos();
		move.startTic = move.lastProgressTic = Level->maptime;
		move.limitTics = int(seconds * TICRATE);
		move.fly = fly;
		move.goalZ = z;
		if (fly) SetFlight(pmo, true);
		Reply(id, FStringf("\"ok\":true,\"job\":\"%s\",\"fly\":%d,\"from\":[%.1f,%.1f,%.1f]", id, fly, pmo->X(), pmo->Y(), pmo->Z()).GetChars());
	}
	else if (!stricmp(cmd, "stop"))
	{
		EndJob(pmo, "stopped");
		Reply(id, "\"ok\":true");
	}
	else if (!stricmp(cmd, "use"))	// One press of the player's own Use button.
	{
		qaPress |= BT_USE;
		Reply(id, "\"ok\":true");
	}
	else if (!stricmp(cmd, "god"))	// Setup: the player's god mode flag.
	{
		const bool on = strstr(rest, "off") == nullptr;
		if (on) pmo->player->cheats |= CF_GODMODE;
		else pmo->player->cheats &= ~CF_GODMODE;
		Reply(id, FStringf("\"ok\":true,\"setup\":true,\"god\":%d", on).GetChars());
	}
	else if (!stricmp(cmd, "teleport"))	// Setup movement: not honest, and recorded as such.
	{
		double x, y, z = NAN, angle = NAN;
		if (sscanf(rest, "%lf %lf %lf %lf", &x, &y, &z, &angle) < 2) { Reply(id, "\"ok\":false,\"error\":\"teleport x y [z|nan] [angle]\""); return; }
		const DVector3 old = pmo->Pos();
		pmo->SetOrigin(DVector3(x, y, std::isnan(z) ? pmo->Z() : z), false);
		if (std::isnan(z)) pmo->SetZ(pmo->floorz);
		pmo->Vel.Zero();
		if (!std::isnan(angle)) pmo->Angles.Yaw = DAngle::fromDeg(angle);
		const bool fits = P_TestMobjLocation(pmo);
		if (!fits) pmo->SetOrigin(old, false);
		Reply(id, FStringf("\"ok\":%s,\"setup\":true,%s", fits ? "true" : "false,\"error\":\"blocked\"", Where(pmo).GetChars()).GetChars());
	}
	else if (!stricmp(cmd, "kill"))	// Setup: the normal damage path with the player as inflictor and source.
	{
		char ref[32] = "";
		sscanf(rest, "%31s", ref);
		AActor *mo = FindRef(Level, ref);
		if (!mo || mo->health <= 0) { Reply(id, "\"ok\":false,\"error\":\"no living actor with that ref or Daggerfall id\""); return; }
		const int before = mo->health;
		const int taken = P_DamageMobj(mo, pmo, pmo, 100000, NAME_None);
		Reply(id, FStringf("\"ok\":true,\"setup\":true,\"class\":%s,\"taken\":%d,\"health\":[%d,%d],\"dead\":%d", Quote(mo->GetClass()->TypeName.GetChars()).GetChars(),
			taken, before, mo->health, mo->health <= 0).GetChars());
	}
	else Reply(id, FStringf("\"ok\":false,\"error\":\"unknown command %s\"", cmd).GetChars());
}

void TickMove(FLevelLocals *Level, AActor *pmo)
{
	if (!move.active) return;
	const double d = (move.goal - pmo->Pos().XY()).Length();
	const int now = Level->maptime;
	const char *result = nullptr;
	if (move.fly && d <= move.tolerance && !move.landing && pmo->Z() >= move.goalZ - 2)
	{
		SetFlight(pmo, false);	// Over the goal: flight off, and gravity lands the player.
		move.landing = true;
		move.lastProgressTic = now;
	}
	if (move.landing)
	{
		if (pmo->Z() <= pmo->floorz + 1 && pmo->Vel.Z == 0) result = pmo->floorz >= move.goalZ - 8 ? "arrived" : "missed";
		else if (now - move.lastProgressTic > TICRATE * 3) result = "stuck";
	}
	else if (d <= move.tolerance && !move.fly) result = "arrived";
	else if (now - move.startTic > move.limitTics) result = "timeout";
	else
	{
		// A flight counts climbing toward the goal height as progress too.
		const double left = move.fly ? d + fabs(move.goalZ + 8 - pmo->Z()) : d;
		if (left < move.bestDist - 2) { move.bestDist = left; move.lastProgressTic = now; }
		if (now - move.lastProgressTic > TICRATE * 2) result = "stuck";
	}
	if (pmo->health <= 0) result = "died";
	if (!result) return;
	if (move.fly) SetFlight(pmo, false);
	move.active = false;
	FString flew = move.fly ? FStringf(",\"flew\":true,\"fly_from\":[%.1f,%.1f,%.1f],\"goal_z\":%.1f", move.start.X, move.start.Y, move.start.Z, move.goalZ) : FString();
	Reply(move.id, FStringf("\"done\":true,\"result\":\"%s\",\"honest\":true%s,\"dist\":%.1f,\"tics\":%d,\"travelled\":%.1f,%s", result, flew.GetChars(), d,
		now - move.startTic, (pmo->Pos() - move.start).Length(), Where(pmo).GetChars()).GetChars());
	if (move.fly) FlewEvent(pmo, result);
}
}

// Between tics, from DD_BridgeFrame: reads new inbox lines and reports pauses (a menu or a Daggerfall window).
void DD_QaFrame()
{
	static bool inited;
	if (!inited)
	{
		inited = true;
		const char *dir = nullptr;
		for (int i = 1; i + 1 < Args->NumArgs(); i++)
			if (!stricmp(Args->GetArg(i), "-ddqa")) dir = Args->GetArg(i + 1);
		if (dir)
		{
			qaDir = dir;
			Printf("DDQA channel %s\n", dir);
			Event("hello", FStringf("\"inbox\":%s", Quote((qaDir + "/inbox.txt").GetChars()).GetChars()).GetChars());
		}
	}
	if (qaDir.IsEmpty()) return;

	const bool pausedNow = paused || menuactive != 0;
	if (pausedNow != lastPaused) { lastPaused = pausedNow; Event(pausedNow ? "paused" : "resumed", FStringf("\"menu\":%d", (int)menuactive).GetChars()); }
	const bool inLevel = gamestate == GS_LEVEL;
	if (inLevel != lastInLevel) { lastInLevel = inLevel; Event(inLevel ? "level" : "left_level", ""); }

	const uint64_t now = I_msTime();
	if (now < nextPoll) return;
	nextPoll = now + 25;
	FILE *f = fopen((qaDir + "/inbox.txt").GetChars(), "rb");
	if (!f) return;
	fseek(f, 0, SEEK_END);
	const long size = ftell(f);
	if (size < inboxPos) inboxPos = 0;
	std::string chunk(size_t(size - inboxPos), '\0');
	fseek(f, inboxPos, SEEK_SET);
	const size_t got = chunk.empty() ? 0 : fread(&chunk[0], 1, chunk.size(), f);
	fclose(f);
	chunk.resize(got);
	size_t start = 0, end;
	while ((end = chunk.find('\n', start)) != std::string::npos)
	{
		std::string line = chunk.substr(start, end - start);
		start = end + 1;
		while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
		if (line.empty()) continue;
		const size_t space = line.find(' ');
		if (space != std::string::npos && line.compare(space + 1, 4, "con ") == 0)	// Console command, e.g. screenshot.
		{
			AddCommandString(line.c_str() + space + 5);
			Out(FStringf("{\"id\":%s,\"ok\":true,\"console\":true}", Quote(line.substr(0, space).c_str()).GetChars()));
		}
		else pending.push_back(line);
	}
	inboxPos += long(start);
}

// Inside the tic, from DDTreadmill_Tick.
void DD_QaTick(FLevelLocals *Level)
{
	if (qaDir.IsEmpty() || Level != primaryLevel) return;
	AActor *pmo = Level->Players[consoleplayer]->mo;
	while (!pending.empty())
	{
		const std::string line = pending.front();
		pending.pop_front();
		Run(Level, line);
	}
	if (pmo) TickMove(Level, pmo);
}

// From G_BuildTiccmd: adds the QA job's steering to the player's own input, as keys and a mouse would.
void DD_QaInput(int &forward, int &side, int &fly, uint32_t &buttons, uint32_t &viewAngle)
{
	if (qaDir.IsEmpty()) return;
	buttons |= qaPress;
	qaPress = 0;
	if (!move.active || move.landing || gamestate != GS_LEVEL || !players[consoleplayer].mo) return;
	AActor *pmo = players[consoleplayer].mo;
	const DVector2 to = move.goal - pmo->Pos().XY();
	if (move.fly)	// Fly up or down to just over the goal's floor, as the fly keys would, and cross only once above it.
	{
		const double dz = move.goalZ + 8 - pmo->Z();
		fly += int(clamp(dz * 64, -768., 768.));
		if (dz > 6)	// Rising: hold the take-off spot with the move and strafe keys, so drift cannot carry it under the ledge.
		{
			const DVector2 off = move.start.XY() - pmo->Pos().XY();
			const double len = off.Length(), yaw = pmo->Angles.Yaw.Radians();
			if (len > 3)
			{
				forward += int(forwardmove[0] * (off.X * cos(yaw) + off.Y * sin(yaw)) / len);
				side += int(sidemove[0] * (off.X * sin(yaw) - off.Y * cos(yaw)) / len);
			}
			return;
		}
	}
	const double want = atan2(to.Y, to.X) * 57.29577951308232;
	double delta = remainder(want - pmo->Angles.Yaw.Degrees(), 360.);
	delta = clamp(delta * 0.6, -60., 60.);	// Commands are built ahead of the tic that applies them, so turn part way.
	viewAngle += uint32_t(int(delta / 360. * 4294967296.));
	if (fabs(delta) >= 45) return;
	if (move.tolerance <= 8 && !move.fly)	// A precise stop: release, or tap back, when the slide (about 10x speed) would overshoot.
	{
		const double slide = (pmo->Vel.X * to.X + pmo->Vel.Y * to.Y) / std::max(to.Length(), 1e-6) * 10;
		if (slide > to.Length() + 16) forward -= forwardmove[0];
		else if (slide < to.Length()) forward += forwardmove[0];
		return;
	}
	if (move.fly) forward += forwardmove[0] / (to.Length() > 64 ? 1 : 2);	// Cross slowly: the landing has no friction to stop a slide.
	else forward += forwardmove[to.Length() > 96 ? 1 : 0];	// Run once roughly facing the goal; walk the last stretch.
}
