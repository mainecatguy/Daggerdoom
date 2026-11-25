// [Doomerfall] Diagnostic output. Doomerfall's diagnostics always reach stdout and the -logfile/+logfile log, which
// tests read. They reach the console and the on-screen messages only with dd_debugmessages on (launch with
// +dd_debugmessages 1, or set it in the console), so a normal launch shows the player only messages meant for the player.
#pragma once

#include "printf.h"

// The print level for a Doomerfall diagnostic: PRINT_HIGH with dd_debugmessages on, else stdout and log only.
PrintFlag DD_DebugLevel();
void DD_DebugPrintf(const char *format, ...) ATTRIBUTE((format(printf, 1, 2)));
