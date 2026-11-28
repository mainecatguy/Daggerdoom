// [Doomerfall] Debug find-NPC (dd_dev only): Doom's side. Daggerfall finds the NPC (DoomerfallFindNpc.cs); Doom draws
// a chevron over the view that points at the target each frame, with its name and distance, or shows where it is in
// text when it is in another place.
// In:  `dd_findnpc [name]` (no name opens the Doomerfall mod's text box, zscript/DoomerfallFindNpc.zs), the mod's
//      network events "ddfind:<name>", "ddfindlist:<text>" (the box's live pick list) and "ddfindpick:<n>", and
//      Daggerfall's FIND_TEXT / FIND_MATCH / FIND_END.
// Out: DFB_KIND_FIND_NPC, console events "dffind:..." for the mod's pick list, the overlay, and bridge log lines.
// The marker clears on an area change (map, inside/outside, a travel jump, a load) or a new search. It changes no game
// or save state, and nothing here runs without dd_dev, a bridge session and a generated Daggerfall map.

#include <algorithm>
#include <cmath>
#include <cstdarg>
#include <cstring>
#include <string>
#include <vector>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "actorinlines.h"
#include "am_map.h"
#include "c_cvars.h"
#include "c_dispatch.h"
#include "d_player.h"
#include "doomstat.h"
#include "events.h"
#include "g_levellocals.h"
#include "gamestate.h"
#include "menu.h"
#include "p_local.h"
#include "playsim/dd_treadmill.h"
#include "printf.h"
#include "r_utility.h"
#include "v_draw.h"
#include "v_font.h"
#include "v_video.h"

void DD_BridgeLog(const char *text);

namespace
{
constexpr double DoomPerDf = 0.75;
constexpr double DoomPerMeter = 30.0;     // 40 Daggerfall units a meter, at the 75% world scale.
constexpr double TravelJump = 4000.0;     // Daggerfall units in one tic: a fast travel, not walking.
constexpr int MessageTics = 35 * 5;

struct Match { std::string label; uint32_t target = 0; uint64_t id = 0; double x = 0, z = 0; };

dfb_session *lastSession;
uint32_t nextRequest = 1, sentRequest;
bool listRequest;    // the request in flight is the box's pick list (DFB_FIND_LIST): always answered as a list
std::string partial;
std::vector<Match> matches;

// The marker.
bool active;
Match marker;
bool actorFound;
bool haveTarget;
DVector3 target;
FString markerMap;
int markerArea = -1, lastMaptime = -1;
double lastWorldX, lastWorldY;
bool haveWorld;

// A line of text at the top of the view: an "elsewhere" answer, or a search status for a while.
std::string topText;
int topUntil = -1;   // gametic; -1 keeps it while the marker lasts

// The last frame's drawing, for the log.
double drawnX = -1, drawnY = -1;
bool drawnOn, drawn;
DVector3 drawnView;   // the viewpoint that frame was drawn from
double drawnYaw, drawnCentre;
double loggedX = -1e9;
bool loggedOn;
int nextLog;

bool DevMode()
{
	FBaseCVar *cv = FindCVar("dd_dev", nullptr);
	return cv && cv->GetGenericRep(CVAR_Bool).Bool;
}

void Log(const char *format, ...)
{
	char text[512];
	va_list ap;
	va_start(ap, format);
	vsnprintf(text, sizeof(text), format, ap);
	va_end(ap);
	DD_BridgeLog(text);
}

void Status(const std::string &text, bool lasting = false)
{
	topText = text;
	topUntil = lasting ? -1 : gametic + MessageTics;
}

void ToMod(const std::string &text)
{
	staticEventManager.Console(-1, FString(text.c_str()), 0, 0, 0, false, true);
}

void Clear(const char *why)
{
	if (active) Log("findnpc: marker cleared (%s)", why);
	active = false;
	haveTarget = false;
	actorFound = false;
	if (topUntil == -1) topText.clear();
}

void Search(const char *name, bool list = false)
{
	if (!DevMode()) { Printf("dd_findnpc needs dd_dev 1\n"); return; }
	if (!lastSession) { Status("Find NPC: Daggerfall is not running"); return; }
	if (!list) Clear("new search"); // the box's list replaces the marker only when one is picked
	matches.clear();
	partial.clear();
	listRequest = list;
	dfb_info_text q{};
	q.request = sentRequest = nextRequest++;
	q.style = list ? DFB_FIND_LIST : 0;
	strncpy(q.text, name, sizeof(q.text) - 1);
	dfb_event e{};
	e.kind = DFB_KIND_FIND_NPC;
	e.tic = gametic;
	memcpy(e.payload, &q, sizeof(q));
	dfb_send(lastSession, &e);
	if (!list) Status(std::string("Finding \"") + q.text + "\"...");
	Log("findnpc: request %u \"%s\"%s", q.request, q.text, list ? " (list)" : "");
}

// The area the player is in now, as a key; false off a Daggerfall map.
bool AreaNow(int &area, double &wx, double &wy, bool &world)
{
	double z, yaw;
	area = int(DDTreadmill_PlayerWorld(wx, wy, z, yaw));
	world = area == DD_AREA_EXTERIOR;
	return area != DD_AREA_NONE;
}

void Select(size_t index)
{
	if (index >= matches.size()) return;
	marker = matches[index];
	int area;
	if (!primaryLevel || !AreaNow(area, lastWorldX, lastWorldY, haveWorld)) return;
	markerMap = primaryLevel->MapName;
	markerArea = area;
	lastMaptime = primaryLevel->maptime;
	actorFound = false;
	haveTarget = false;
	drawn = false;
	loggedX = -1e9;
	nextLog = 0;
	if (marker.target == DFB_FIND_ELSEWHERE)
	{
		active = true; // keeps the text until the area changes
		Status(marker.label, true);
		Log("findnpc: elsewhere: %s", marker.label.c_str());
		return;
	}
	topText.clear();
	active = true;
	Log("findnpc: marker on %s, target kind %u id %016llx point %.1f %.1f", marker.label.c_str(), marker.target, (unsigned long long)marker.id, marker.x, marker.z);
}

uint64_t ActorId(AActor *mo) { return uint64_t(uint32_t(mo->args[1])) << 32 | uint32_t(mo->args[0]); }

AActor *FindActor(uint64_t id)
{
	auto it = primaryLevel->GetThinkerIterator<AActor>();
	while (AActor *mo = it.Next())
		if ((mo->ddRecordId == id || ActorId(mo) == id) && mo->health > 0 && !(mo->flags & MF_CORPSE)) return mo;
	return nullptr;
}

// Where the marker points this tic, in Doom map units.
bool Resolve(DVector3 &out)
{
	const bool isActor = marker.target == DFB_FIND_ACTOR_WORLD || marker.target == DFB_FIND_ACTOR_LOCAL;
	if (isActor)
	{
		// Searched each tic rather than kept: townspeople come and go as Daggerfall lists them.
		AActor *mo = FindActor(marker.id);
		actorFound = mo != nullptr;
		if (mo)
		{
			out = mo->Pos() + DVector3(0, 0, mo->Height);
			return true;
		}
		if (marker.x == 0 && marker.z == 0) return false;
	}
	DVector2 at;
	if (marker.target == DFB_FIND_WORLD || marker.target == DFB_FIND_ACTOR_WORLD)
	{
		if (!DDTreadmill_WorldToLocal(marker.x, marker.z, at.X, at.Y)) return false;
	}
	else
		at = DVector2(marker.x, marker.z);
	sector_t *sec = primaryLevel->PointInSector(at);
	out = DVector3(at, (sec ? sec->floorplane.ZatPoint(at) : 0) + 56);
	return true;
}

// Screen projection of a map point, as the hardware renderer sets up its view. False when it is behind the camera or
// off the view, with (dx, dy) the screen direction toward it.
bool Project(const DVector3 &p, double &sx, double &sy, double &dx, double &dy)
{
	const FRenderViewpoint &vp = r_viewpoint;
	DVector3 d = p - vp.Pos;
	d.Z *= primaryLevel && primaryLevel->info ? primaryLevel->info->pixelstretch : 1.2;
	const double cy = vp.Angles.Yaw.Cos(), sy_ = vp.Angles.Yaw.Sin();
	const double fwd = d.X * cy + d.Y * sy_, right = d.X * sy_ - d.Y * cy, up = d.Z;
	const double cp = vp.Angles.Pitch.Cos(), sp = vp.Angles.Pitch.Sin();
	const double f2 = fwd * cp - up * sp, u2 = up * cp + fwd * sp;
	const double ratio = r_viewwindow.WidescreenRatio > 0 ? r_viewwindow.WidescreenRatio : 4.0 / 3.0;
	const double fovratio = ratio >= 1.3 ? 1.333333 : ratio;
	const double tanV = tan(vp.FieldOfView.Radians() / 2) / fovratio;
	const double vx = viewwindowx, vy = viewwindowy, vw = viewwidth, vh = viewheight;
	dx = right;
	dy = -u2;
	if (f2 > 1)
	{
		const double nx = right / (f2 * tanV * ratio), ny = u2 / (f2 * tanV);
		sx = vx + vw * 0.5 * (1 + nx);
		sy = vy + vh * 0.5 * (1 - ny);
		if (fabs(nx) <= 0.92 && fabs(ny) <= 0.92) return true;
		dx = nx;
		dy = -ny;
	}
	if (fabs(dx) < 1e-6 && fabs(dy) < 1e-6) dy = 1;
	return false;
}

void Chevron(double cx, double cy, double dx, double dy, double size)
{
	const double len = sqrt(dx * dx + dy * dy);
	dx /= len;
	dy /= len;
	const DVector2 tip(cx + dx * size, cy + dy * size);
	const double c = cos(2.4), s = sin(2.4);
	const DVector2 a(cx + (dx * c - dy * s) * size, cy + (dx * s + dy * c) * size);
	const DVector2 b(cx + (dx * c + dy * s) * size, cy + (-dx * s + dy * c) * size);
	const double t = std::max(2.0, size / 5);
	twod->AddThickLine(a, tip, t + 3, 0xff000000, 200);
	twod->AddThickLine(b, tip, t + 3, 0xff000000, 200);
	twod->AddThickLine(a, tip, t, 0xffffd040, 255);
	twod->AddThickLine(b, tip, t, 0xffffd040, 255);
}

int TextScale() { return std::max(1, twod->GetHeight() / 360); }

void Text(double x, double y, const std::string &text, bool centre = true)
{
	const int scale = TextScale();
	const double w = SmallFont->StringWidth(text.c_str()) * scale;
	DrawText(twod, SmallFont, CR_GOLD, centre ? x - w / 2 : x, y, text.c_str(), DTA_ScaleX, double(scale), DTA_ScaleY, double(scale), TAG_DONE);
}
}

CCMD(dd_findnpc)
{
	if (!DevMode()) { Printf("dd_findnpc needs dd_dev 1\n"); return; }
	if (argv.argc() < 2)
	{
		M_StartControlPanel(false);
		M_SetMenu(FName("DoomerfallFindNpcMenu"), -1);
		return;
	}
	FString name;
	for (int i = 1; i < argv.argc(); i++) { if (i > 1) name += " "; name += argv[i]; }
	Search(name.GetChars());
}

// From DD_BridgeItemNetEvent: the mod's text box and pick list.
bool DD_FindNpcNetEvent(dfb_session *session, const char *name)
{
	if (!strncmp(name, "ddfind:", 7)) { lastSession = session; Search(name + 7); return true; }
	if (!strncmp(name, "ddfindlist:", 11)) { lastSession = session; Search(name + 11, true); return true; }
	if (!strncmp(name, "ddfindpick:", 11)) { Select(size_t(atoi(name + 11))); return true; }
	return false;
}

// Daggerfall's answers. True when the event was one.
bool DD_FindNpcEvent(const dfb_event &e)
{
	if (e.kind == DFB_KIND_FIND_TEXT)
	{
		dfb_info_text t;
		memcpy(&t, e.payload, sizeof(t));
		partial.append(t.text, strnlen(t.text, sizeof(t.text)));
		return true;
	}
	if (e.kind != DFB_KIND_FIND_MATCH && e.kind != DFB_KIND_FIND_END) return false;
	dfb_info_request r;
	memcpy(&r, e.payload, sizeof(r));
	if (r.request != sentRequest) { partial.clear(); return true; }
	if (e.kind == DFB_KIND_FIND_MATCH)
	{
		Match m;
		m.label = partial;
		m.target = r.target;
		m.id = r.id;
		m.x = r.world_x;
		m.z = r.world_z;
		matches.push_back(m);
		partial.clear();
		return true;
	}
	Log("findnpc: request %u answered: %llu found, %u sent", r.request, (unsigned long long)r.id, unsigned(matches.size()));
	if (listRequest)
	{
		ToMod("dffind:clear");
		for (const Match &m : matches) ToMod("dffind:item:" + m.label);
		ToMod("dffind:list");
		return true;
	}
	if (matches.empty())
	{
		Status("Find NPC: no one by that name");
		ToMod("dffind:none");
	}
	else if (matches.size() == 1)
	{
		ToMod("dffind:done");
		Select(0);
	}
	else
	{
		ToMod("dffind:clear");
		for (const Match &m : matches) ToMod("dffind:item:" + m.label);
		ToMod("dffind:list");
		Status(std::to_string(r.id) + " matches: pick one");
		if (menuactive == MENU_Off)
		{
			M_StartControlPanel(false);
			M_SetMenu(FName("DoomerfallFindNpcMenu"), -1);
		}
	}
	return true;
}

// Once per tic from the bridge frame: area changes, and where the marker points.
void DD_FindNpcFrame(dfb_session *session)
{
	static int lastTic = -1;
	lastSession = session;
	if (!session || gametic == lastTic) return;
	lastTic = gametic;
	if (topUntil >= 0 && gametic > topUntil) { topText.clear(); topUntil = -2; }
	if (!active) return;
	int area;
	double wx, wy;
	bool world;
	if (!DevMode() || gamestate != GS_LEVEL || !primaryLevel || !AreaNow(area, wx, wy, world)) { Clear("left the game or dev mode"); return; }
	if (markerMap.CompareNoCase(primaryLevel->MapName) != 0) { Clear("map changed"); return; }
	if (area != markerArea) { Clear("area changed"); return; }
	if (primaryLevel->maptime < lastMaptime) { Clear("game loaded"); return; }
	lastMaptime = primaryLevel->maptime;
	if (world && haveWorld && (fabs(wx - lastWorldX) > TravelJump || fabs(wy - lastWorldY) > TravelJump)) { Clear("travelled"); return; }
	lastWorldX = wx;
	lastWorldY = wy;
	haveWorld = world;
	if (marker.target == DFB_FIND_ELSEWHERE) return;
	haveTarget = Resolve(target);
	if (gametic >= nextLog && drawn && (fabs(drawnX - loggedX) > 8 || drawnOn != loggedOn))
	{
		nextLog = gametic + 17;
		loggedX = drawnX;
		loggedOn = drawnOn;
		Log("findnpc: draw %s screen %.0f %.0f target %.1f %.1f %.1f player %.1f %.1f yaw %.1f distance %.0f actor %d centre %.0f", drawnOn ? "on" : "edge", drawnX, drawnY,
			target.X, target.Y, target.Z, drawnView.X, drawnView.Y, drawnYaw, (target.XY() - drawnView.XY()).Length(), int(actorFound), drawnCentre);
	}
}

// From D_Display, after the HUD. Draws nothing unless a marker or a status line is up.
void DD_FindNpcDraw()
{
	if (gamestate != GS_LEVEL || automapactive || consoleplayer < 0 || (!active && topText.empty())) return;
	player_t *p = &players[consoleplayer];
	if (!p->mo || !p->camera) return;
	const int scale = TextScale();
	if (!topText.empty()) Text(twod->GetWidth() / 2.0, twod->GetHeight() * 0.14, topText);
	if (!active || !haveTarget || marker.target == DFB_FIND_ELSEWHERE) { drawn = false; return; }
	double sx, sy, dx, dy;
	const bool on = Project(target, sx, sy, dx, dy);
	const double size = 10.0 * scale;
	const std::string name = marker.label.substr(0, marker.label.find(" - "));
	char distance[32];
	snprintf(distance, sizeof(distance), "%.0fm", (target.XY() - p->mo->Pos().XY()).Length() / DoomPerMeter);
	const std::string text = name + "  " + distance;
	if (on)
	{
		Chevron(sx, sy - size * 1.2, 0, 1, size);
		Text(sx, sy - size * 2.6 - SmallFont->GetHeight() * scale, text);
	}
	else
	{
		// The edge of the view, inset, in the direction of the target.
		const double cx = viewwindowx + viewwidth / 2.0, cy = viewwindowy + viewheight / 2.0;
		const double hw = viewwidth / 2.0 - size * 3, hh = viewheight / 2.0 - size * 3;
		const double k = std::min(fabs(dx) > 1e-9 ? hw / fabs(dx) : 1e9, fabs(dy) > 1e-9 ? hh / fabs(dy) : 1e9);
		sx = cx + dx * k;
		sy = cy + dy * k;
		Chevron(sx, sy, dx, dy, size);
		const double ty = sy + (dy > 0 ? -size * 2 - SmallFont->GetHeight() * scale : size * 1.6);
		Text(std::clamp(sx, viewwindowx + 80.0 * scale, viewwindowx + viewwidth - 80.0 * scale), ty, text);
	}
	drawnX = sx;
	drawnY = sy;
	drawnOn = on;
	drawnView = r_viewpoint.Pos;
	drawnYaw = r_viewpoint.Angles.Yaw.Degrees();
	drawnCentre = viewwindowx + viewwidth / 2.0;
	drawn = true;
}
