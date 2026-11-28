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

// The player's attacks, found from when the ready weapon was last ready. readySpans: runs of tics in which the weapon
// was seen ready (A_WeaponReady had set WF_WEAPONREADY), newest last. The attack a noise or hit belongs to began at the
// last moment the weapon was ready at or before it. Every way out of the ready state passes through DPSprite::SetState
// with the flag still set (DD_BackstabWeaponReady), so a shot fired on the very first ready frame still starts its own
// attack, and so do a weapon switch and a reload begun from the ready state.
struct Span { int start, end; };
constexpr int SpanCount = 16;
Span readySpans[SpanCount];
int spanNext, spansKept;
// Only an attack's opening noise is excused: noise up to this long after the attack began (a wind-up, the first shots).
constexpr int OpeningTics = TICRATE;
TMap<const AActor *, int> lastHeard; // when each monster last heard the player

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
	lastHeard.Clear();
	spansKept = spanNext = 0;
	heardLevel = level;
	heardMaptime = level->maptime;
}

void NoteReady(int t)
{
	Span *last = spansKept ? &readySpans[(spanNext + SpanCount - 1) % SpanCount] : nullptr;
	if (last && t >= last->start && t - last->end <= 1) { last->end = std::max(last->end, t); return; }
	readySpans[spanNext] = { t, t };
	spanNext = (spanNext + 1) % SpanCount;
	spansKept = std::min(spansKept + 1, SpanCount);
}

bool Ready(player_t *player)
{
	return !player->ReadyWeapon || (player->WeaponState & (WF_WEAPONREADY | WF_WEAPONREADYALT));
}

// When the attack under way at time t began: the last time at or before t that the weapon was ready, or -1 if unknown.
int AttackStart(int t)
{
	for (int i = 0; i < spansKept; i++)
	{
		const Span &s = readySpans[(spanNext + SpanCount - 1 - i) % SpanCount];
		if (s.start <= t) return std::min(s.end, t);
	}
	return -1;
}

void SampleNow(FLevelLocals *level)
{
	AActor *pawn = BridgedPawn();
	if (pawn && pawn->player && pawn->Level == level && Ready(pawn->player)) NoteReady(level->totaltime);
}
}

// p_pspr.cpp DPSprite::SetState, before a weapon state change clears WF_WEAPONREADY: the weapon was ready until now.
void DD_BackstabWeaponReady(player_t *player)
{
	if (!active || !player->mo || player->mo != BridgedPawn()) return;
	ResetLevel(player->mo->Level);
	NoteReady(player->mo->Level->totaltime);
}

// From DD_BridgeHpThink, at the start of each player's tic: notes a weapon left ready by the previous tic.
void DD_BackstabTic(player_t *player)
{
	if (!active || !player->mo || player->mo != BridgedPawn()) return;
	ResetLevel(player->mo->Level);
	if (Ready(player)) NoteReady(player->mo->Level->totaltime);
}

// p_enemy.cpp NoiseMarkSector, just before a monster's LastHeard is set to soundtarget. Records when a monster starts
// hearing the bridged player, and when it last heard the player.
void DD_BackstabHeard(AActor *actor, AActor *soundtarget)
{
	if (!active || !soundtarget || soundtarget != BridgedPawn() || !actor) return;
	ResetLevel(actor->Level);
	SampleNow(actor->Level);
	const int now = actor->Level->totaltime;
	if (actor->LastHeard != soundtarget) firstHeard[actor] = now;
	lastHeard[actor] = now;
}

// Unaware: an enemy (a monster not friendly to the player) that has not noticed the player: it has no live target and
// is not alerted. Alerted means it heard someone (LastHeard), with one exception: the opening noise of the very attack
// that is hitting it (what it made in its first second: a wind-up, the opening shots). A gun alerts every monster in
// earshot as it starts firing, before its bullets land, so that noise is too late to count. Noise from before the
// attack began counts, however long ago, and so does noise later in a long burst or after a reload in it; a hit that
// comes while the weapon is ready (no attack) excuses nothing.
// attackTime: when the hit left the player: a projectile's spawn time, or now for an instant hit.
bool DD_BackstabUnaware(AActor *player, AActor *target, int attackTime)
{
	if (!target || target == player || !(target->flags3 & MF3_ISMONSTER) || !Live(target)) return false;
	if (target->IsFriend(player)) return false;
	if (Live(target->target)) return false;
	AActor *heard = target->LastHeard;
	if (!Live(heard)) return true;
	if (heard != player || target->Level != heardLevel) return false;
	const int *since = firstHeard.CheckKey(target);
	const int *last = lastHeard.CheckKey(target);
	const int start = AttackStart(attackTime);
	return since && last && start >= 0 && *since >= start && *last <= start + OpeningTics;
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
