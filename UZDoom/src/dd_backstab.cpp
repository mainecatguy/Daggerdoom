// [Doomerfall] Backstabbing: the player's hits on unaware enemies. Daggerfall tabulates the backstab element of the damage
// bonus from its Backstabbing skill (dfb_df_state.backstab_bonus_bp); Doom applies it, on top of the rest of the damage
// bonus, only to hits on enemies that have not noticed the player, and reports those hits so Daggerfall can tally
// Backstabbing uses (DoomerfallBackstab.cs).
// DD_BackstabUnaware is the one place that decides "unaware"; the detection bar (gamedesign.md) will refine it there.
// Nothing here runs without a bridge session: DD_BridgeDamageBonus calls in only for the bridged player's hits, and the
// hearing hook (DD_BackstabHeard, from p_enemy.cpp) and the tic hook (DD_BackstabTic) return at once unless
// DD_BackstabFrame saw a session this frame.

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
constexpr int SpanCount = 8;

bool active;              // a bridge session existed at the last frame
uint32_t pendingHits;
// The enemies hit while unaware in this tic. Every hit of one attack lands in one tic (a shotgun's pellets, a rocket's
// blast), in any order across enemies (A, B, A), and the first hit already makes an enemy notice the player
// (P_DamageMobj sets its target), so the rest of that tic's hits on each of them are part of the same sneak attack.
// Cleared when the tic changes. Compared only, never dereferenced.
TArray<const AActor *> sneakTargets;
int sneakTic = -1;

// Times are level totaltime (the clock of AActor::SpawnTime).
// firstHeard: when each monster started hearing the player (its LastHeard became the player); keys are compared only,
// never dereferenced.
TMap<const AActor *, int> firstHeard;
const FLevelLocals *heardLevel;
int heardMaptime;

// The player's attacks: spans while the ready weapon is out of its ready state (it left A_WeaponReady to fire, wind up,
// refire or reload) until it is ready again. One attack holds all its own noise: a wind-up's alert, the firing alert,
// every refire of a held burst. end is -1 while it lasts.
struct Span { int start, end; };
Span spans[SpanCount];
int spanNext, spansKept;
bool inAttack;

bool Live(AActor *a)
{
	return a && a->health > 0;
}

AActor *BridgedPawn()
{
	return playeringame[consoleplayer] ? players[consoleplayer].mo : nullptr;
}

void ResetLevel(FLevelLocals *level)
{
	if (level == heardLevel && level->maptime >= heardMaptime) { heardMaptime = level->maptime; return; }
	firstHeard.Clear();
	spansKept = spanNext = 0;
	inAttack = false;
	heardLevel = level;
	heardMaptime = level->maptime;
}

// Follows the bridged player's weapon: an attack starts when the weapon is out of its ready state (setting any weapon
// state clears WF_WEAPONREADY; A_WeaponReady sets it again) and ends when it is ready again. at: the time to stamp.
void Sample(player_t *player, int at)
{
	const bool ready = !player->ReadyWeapon || (player->WeaponState & (WF_WEAPONREADY | WF_WEAPONREADYALT));
	if (ready && inAttack)
	{
		spans[(spanNext + SpanCount - 1) % SpanCount].end = at;
		inAttack = false;
	}
	else if (!ready && !inAttack)
	{
		spans[spanNext] = { at, -1 };
		spanNext = (spanNext + 1) % SpanCount;
		spansKept = std::min(spansKept + 1, SpanCount);
		inAttack = true;
	}
}

// The start of the player's attack under way at time t, or -1 if the player was not attacking then.
int AttackAt(int t)
{
	for (int i = 0; i < spansKept; i++)
	{
		const Span &s = spans[(spanNext + SpanCount - 1 - i) % SpanCount];
		if (s.start <= t && (s.end < 0 || t < s.end)) return s.start;
	}
	return -1;
}

// Samples the weapon now, from inside the playsim (a weapon that fires on its first frame leaves the ready state and
// alerts or hits in the same tic).
void SampleNow(FLevelLocals *level)
{
	AActor *pawn = BridgedPawn();
	if (pawn && pawn->player && pawn->Level == level) Sample(pawn->player, level->totaltime);
}
}

// From DD_BridgeHpThink, at the start of each player's tic (P_PlayerThink): the weapon as the previous tic left it. A
// weapon that left its ready state during the previous tic did so at time - 1, where its first noise came from.
void DD_BackstabTic(player_t *player)
{
	if (!active || !player->mo || player->mo != BridgedPawn()) return;
	ResetLevel(player->mo->Level);
	Sample(player, inAttack ? player->mo->Level->totaltime : player->mo->Level->totaltime - 1);
}

// p_enemy.cpp NoiseMarkSector, just before a monster's LastHeard is set to soundtarget. Records when a monster starts
// hearing the bridged player.
void DD_BackstabHeard(AActor *actor, AActor *soundtarget)
{
	if (!active || !soundtarget || soundtarget != BridgedPawn() || !actor) return;
	ResetLevel(actor->Level);
	SampleNow(actor->Level);
	if (actor->LastHeard != soundtarget) firstHeard[actor] = actor->Level->totaltime;
}

// Unaware: an enemy (a monster not friendly to the player) that has not noticed the player: it has no live target and
// is not alerted. Alerted means it heard someone (LastHeard), with one exception: the noise of the very attack that is
// hitting it. A gun alerts every monster in earshot when it starts firing (and some wind up with an alert first), before
// its bullets land, so that noise is too late to count; any noise from the player before the current attack began does
// count, however long ago it was, and so does every noise when the hit comes from no attack of the player's.
// attackTime: when the attack's hit left the player: a projectile's spawn time, or now for an instant hit.
bool DD_BackstabUnaware(AActor *player, AActor *target, int attackTime)
{
	if (!target || target == player || !(target->flags3 & MF3_ISMONSTER) || !Live(target)) return false;
	if (target->IsFriend(player)) return false;
	if (Live(target->target)) return false;
	AActor *heard = target->LastHeard;
	if (!Live(heard)) return true;
	if (heard != player || target->Level != heardLevel) return false;
	const int *since = firstHeard.CheckKey(target);
	const int start = AttackAt(attackTime);
	return since && start >= 0 && *since >= start; // it first heard the player during this attack
}

// From DD_BridgeDamageBonus, for a hit by the bridged player: the backstab factor for this hit (1 when it is not a sneak
// hit), counting each sneak hit once for Daggerfall.
double DD_BackstabFactor(AActor *player, AActor *target, AActor *inflictor, int32_t backstabBp)
{
	if (gametic != sneakTic)
	{
		sneakTargets.Clear();
		sneakTic = gametic;
	}
	const bool sameAttack = sneakTargets.Find(target) < sneakTargets.Size();
	if (!sameAttack)
	{
		if (!target) return 1.0;
		ResetLevel(target->Level);
		SampleNow(target->Level);
		const int now = target->Level->totaltime;
		const int attackTime = inflictor && inflictor != player && !inflictor->player ? inflictor->SpawnTime : now;
		if (!DD_BackstabUnaware(player, target, attackTime)) return 1.0;
		sneakTargets.Push(target);
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
