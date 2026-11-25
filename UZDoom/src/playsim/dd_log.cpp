// [Doomerfall] Diagnostic output; see dd_log.h.

#include <cstdarg>

#include "c_cvars.h"
#include "playsim/dd_log.h"

// Off by default: diagnostics show in the console and on screen only when asked for. Never saved to the ini.
CVAR(Bool, dd_debugmessages, false, CVAR_NOSAVE)

PrintFlag DD_DebugLevel()
{
	return dd_debugmessages ? PRINT_HIGH : PrintFlag(PRINT_HIGH | PRINT_NONOTIFY | PRINT_NOCONSOLE);
}

void DD_DebugPrintf(const char *format, ...)
{
	va_list args;
	va_start(args, format);
	VPrintf(DD_DebugLevel(), format, args);
	va_end(args);
}
