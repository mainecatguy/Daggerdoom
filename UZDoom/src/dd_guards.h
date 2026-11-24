#pragma once
// [Doomerfall] Guard bots: UZDoom bots that Daggerfall's guard spawns create (dd_guards.cpp). The bot code checks
// this to hunt players with them. Only Doomerfall sets the guard tag, so stock games never see a guard bot.

#include <cstdint>

class AActor;
class FCajunMaster;

inline bool DD_IsGuardId(uint64_t id) { return (id >> 61) == 4u; }	// DFB_GUARD_TAG
#define DD_IsGuardBot(mo) ((mo) != nullptr && DD_IsGuardId((mo)->ddRecordId))

void DD_GuardsLeaveLevel(FCajunMaster &bots);
