// [Doomerfall] Backstabbing: the player's hits on unaware enemies. Daggerfall tabulates the backstab element of the damage
// bonus from its Backstabbing skill (dfb_df_state.backstab_bonus_bp); Doom applies it, on top of the rest of the damage
// bonus, only to hits on enemies that have not noticed the player, and reports those hits so Daggerfall can tally
// Backstabbing uses (DoomerfallBackstab.cs).
// DD_BackstabUnaware is the one place that decides "unaware"; the detection bar (gamedesign.md) will refine it there.
// Nothing here runs without a bridge session: DD_BridgeDamageBonus calls in only for the bridged player's hits.

#include <algorithm>
#include <cstring>

#include "../../bridge/doomerfall_bridge.h"
#include "actor.h"
#include "d_player.h"
#include "doomstat.h"
#include "printf.h"
#include "zstring.h"

void DD_BridgeLog(const char *text);

namespace
{
uint32_t pendingHits;
// The enemy last hit while unaware, and the tic. Every hit of one attack lands in one tic (a shotgun's pellets, a
// rocket's blast), and the first hit already makes the enemy notice the player (P_DamageMobj sets its target), so the
// rest of that tic's hits on the same enemy are part of the same sneak attack. Compared only, never dereferenced.
const AActor *sneakTarget;
int sneakTic = -1;

bool Live(AActor *a)
{
	return a && a->health > 0;
}
}

// Unaware: an enemy (a monster not friendly to the player) that has no live target, so it has not noticed the player or
// anyone else. A noise it heard but has not reacted to yet (LastHeard) does not count until it looks and takes a target:
// the player's own gunshot sets LastHeard on every monster in earshot before its bullets land, so counting it would make
// nearly every shot an aware one.
bool DD_BackstabUnaware(AActor *player, AActor *target)
{
	if (!target || target == player || !(target->flags3 & MF3_ISMONSTER) || !Live(target)) return false;
	if (target->IsFriend(player)) return false;
	return !Live(target->target);
}

// From DD_BridgeDamageBonus, for a hit by the bridged player: the backstab factor for this hit (1 when it is not a sneak
// hit), counting each sneak hit once for Daggerfall.
double DD_BackstabFactor(AActor *player, AActor *target, int32_t backstabBp)
{
	const bool sameAttack = target == sneakTarget && gametic == sneakTic;
	if (!sameAttack && !DD_BackstabUnaware(player, target)) return 1.0;
	if (!sameAttack)
	{
		sneakTarget = target;
		sneakTic = gametic;
		pendingHits++;
	}
	return 1.0 + std::max(backstabBp, 0) / 10000.0;
}

// Once a frame from DD_BridgeFrame: sends the sneak hits counted since the last frame.
void DD_BackstabFrame(dfb_session *session)
{
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
