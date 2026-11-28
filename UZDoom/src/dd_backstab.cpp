// [Doomerfall] Backstabbing: the player's hits on unaware enemies. Daggerfall tabulates the backstab element of the damage
// bonus from its Backstabbing skill (dfb_df_state.backstab_bonus_bp); Doom applies it, on top of the rest of the damage
// bonus, only to hits on enemies that have not noticed the player, and reports those hits so Daggerfall can tally
// Backstabbing uses (DoomerfallBackstab.cs).
// DD_BackstabUnaware is the one place that decides "unaware"; the detection bar (gamedesign.md) will refine it there.
// Nothing here runs without a bridge session: DD_BridgeDamageBonus calls in only for the bridged player's hits, and the
// hearing hook (DD_BackstabHeard, from p_enemy.cpp) returns at once unless DD_BackstabFrame saw a session this frame.

#include <algorithm>
#include <cstring>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "d_player.h"
#include "doomstat.h"
#include "g_levellocals.h"
#include "printf.h"
#include "tarray.h"
#include "zstring.h"

void DD_BridgeLog(const char *text);

namespace
{
constexpr int AttackWindow = TICRATE; // tics from an attack's own noise to its hit (wind-up and bullet or rocket flight)
constexpr int AlertCount = 8;

bool active;              // a bridge session existed at the last frame
uint32_t pendingHits;
// The enemy last hit while unaware, and the tic. Every hit of one attack lands in one tic (a shotgun's pellets, a
// rocket's blast), and the first hit already makes the enemy notice the player (P_DamageMobj sets its target), so the
// rest of that tic's hits on the same enemy are part of the same sneak attack. Compared only, never dereferenced.
const AActor *sneakTarget;
int sneakTic = -1;

// Hearing, in level totaltime (the clock of AActor::SpawnTime). firstHeard: when each monster started hearing the player
// (its LastHeard became the player); keys are compared only, never dereferenced. alerts: the tics of the player's latest
// noise alerts (gunshots and other noise the player makes).
TMap<const AActor *, int> firstHeard;
int alerts[AlertCount];
int alertNext, alertsKept;
const FLevelLocals *heardLevel;
int heardMaptime;

bool Live(AActor *a)
{
	return a && a->health > 0;
}

AActor *BridgedPawn()
{
	return playeringame[consoleplayer] ? players[consoleplayer].mo : nullptr;
}

// The tic of the noise the current attack itself raised: the player's newest alert at or before the attack began and
// at most AttackWindow before it, or -1 if the attack made no noise.
int AttackAlert(int attackStart)
{
	int best = -1;
	for (int i = 0; i < alertsKept; i++)
	{
		const int t = alerts[i];
		if (t <= attackStart && attackStart - t <= AttackWindow && t > best) best = t;
	}
	return best;
}
}

// p_enemy.cpp NoiseMarkSector, just before a monster's LastHeard is set to soundtarget. Records when a monster starts
// hearing the bridged player, and the player's alert itself.
void DD_BackstabHeard(AActor *actor, AActor *soundtarget)
{
	if (!active || !soundtarget || soundtarget != BridgedPawn() || !actor) return;
	FLevelLocals *level = actor->Level;
	if (level != heardLevel || level->maptime < heardMaptime)
	{
		firstHeard.Clear();
		alertsKept = alertNext = 0;
		heardLevel = level;
	}
	heardMaptime = level->maptime;
	const int now = level->totaltime;
	const int newest = alertsKept ? alerts[(alertNext + AlertCount - 1) % AlertCount] : -1;
	if (newest != now)
	{
		alerts[alertNext] = now;
		alertNext = (alertNext + 1) % AlertCount;
		alertsKept = std::min(alertsKept + 1, AlertCount);
	}
	if (actor->LastHeard != soundtarget) firstHeard[actor] = now;
}

// Unaware: an enemy (a monster not friendly to the player) that has not noticed the player: it has no live target and
// is not alerted. Alerted means it heard someone (LastHeard), with one exception: the noise of the very attack that is
// hitting it. A gun alerts every monster in earshot when it fires, before its bullets land, so that noise is too late
// to count; any noise from the player before the current attack does count, however long ago it was.
// attackStart: when the attack began (level totaltime): a projectile's spawn time, or now for an instant hit.
bool DD_BackstabUnaware(AActor *player, AActor *target, int attackStart)
{
	if (!target || target == player || !(target->flags3 & MF3_ISMONSTER) || !Live(target)) return false;
	if (target->IsFriend(player)) return false;
	if (Live(target->target)) return false;
	AActor *heard = target->LastHeard;
	if (!Live(heard)) return true;
	if (heard != player || target->Level != heardLevel) return false;
	const int *since = firstHeard.CheckKey(target);
	const int own = AttackAlert(attackStart);
	return since && own >= 0 && *since >= own; // it first heard the player at this attack's own noise
}

// From DD_BridgeDamageBonus, for a hit by the bridged player: the backstab factor for this hit (1 when it is not a sneak
// hit), counting each sneak hit once for Daggerfall.
double DD_BackstabFactor(AActor *player, AActor *target, AActor *inflictor, int32_t backstabBp)
{
	const bool sameAttack = target == sneakTarget && gametic == sneakTic;
	if (!sameAttack)
	{
		const int now = target ? target->Level->totaltime : 0;
		const int attackStart = inflictor && inflictor != player && !inflictor->player ? inflictor->SpawnTime : now;
		if (!DD_BackstabUnaware(player, target, attackStart)) return 1.0;
		sneakTarget = target;
		sneakTic = gametic;
		pendingHits++;
	}
	return 1.0 + std::max(backstabBp, 0) / 10000.0;
}

// Once a frame from DD_BridgeFrame: sends the sneak hits counted since the last frame.
void DD_BackstabFrame(dfb_session *session)
{
	active = session != nullptr;
	if (!session || pendingHits == 0) return;
	dfb_event e{};
	e.kind = DFB_KIND_SNEAK_HITS;
	e.tic = gametic;
	dfb_sneak_hits body{};
	body.hits = pendingHits;
	memcpy(e.payload, &body, sizeof(body));
	const int rc = dfb_send(session, &e);
	DD_BridgeLog(FStringf("backstab: sent %u sneak hits (%d)", pendingHits, rc).GetChars());
	pendingHits = 0;
}
