// [Doomerfall] Skill XP relay. The mod tallies the player's damage (mods/doomerfall/src/zscript/DoomerfallSkillXp.zs)
// and sends "dfs_xp:<xp>:<skill>:<uses>" network events about once a second; this passes each one to Daggerfall as
// DFB_KIND_SKILL_XP. Daggerfall owns the pool, prices and skills. Nothing here runs without a bridge session.

#include <cstdlib>
#include <cstring>

#include "../../bridge/doomerfall_bridge.h"
#include "doomstat.h"
#include "printf.h"
#include "zstring.h"

void DD_BridgeLog(const char *text);

// From DD_BridgeItemNetEvent. True for the Skill XP mod's own events.
bool DD_SkillXpNetEvent(dfb_session *session, const char *name)
{
	if (strncmp(name, "dfs_xp:", 7)) return false;
	char *end = nullptr;
	const unsigned long xp = strtoul(name + 7, &end, 10);
	const long skill = end && *end == ':' ? strtol(end + 1, &end, 10) : -1;
	const unsigned long uses = end && *end == ':' ? strtoul(end + 1, nullptr, 10) : 0;
	if ((xp == 0 && uses == 0) || xp > 1000000 || uses > 100000 || skill < -1 || skill >= 64) return true;
	dfb_event e{};
	e.kind = DFB_KIND_SKILL_XP;
	e.tic = gametic;
	dfb_skill_xp body{};
	body.xp = uint32_t(xp);
	body.skill = uses ? int32_t(skill) : -1;
	body.uses = skill >= 0 ? uint32_t(uses) : 0;
	memcpy(e.payload, &body, sizeof(body));
	const int rc = dfb_send(session, &e);
	DD_BridgeLog(FStringf("skillxp: sent %lu XP, %u uses of skill %d (%d)", xp, body.uses, body.skill, rc).GetChars());
	return true;
}
