// Doomerfall launcher. Starts UZDoom and Daggerfall Unity in one Job Object and ends both when
// either exits. If the launcher itself dies, Windows closes the job and ends both games.
//
// Exit code: the code of the game that exited first, 2 for bad arguments, 3 for a failed launch.

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <shellapi.h>

#include "doomerfall_bridge.h"

#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

namespace
{
constexpr int ExitUsage = 2;
constexpr int ExitLaunchFailed = 3;
constexpr DWORD QuietPollMs = 20;
constexpr DWORD ClosePollMs = 100;

const wchar_t Usage[] =
	L"doomerfall-launcher --uzdoom <exe> --dfu <exe> [options]\n\n"
	L"--iwad <wad>         IWAD for UZDoom\n"
	L"--mod <path>         Add a mod to UZDoom's -file list (repeatable, keeps order)\n"
	L"--mod-list <file>    Add mods from a file: one path per line, # for comments,\n"
	L"                     relative paths resolve against the list file\n"
	L"--uzdoom-arg <arg>   Pass one argument to UZDoom (repeatable)\n"
	L"--dfu-arg <arg>      Pass one argument to Daggerfall Unity (repeatable)\n"
	L"--uzdoom-cwd <dir>   UZDoom working directory (default: its exe folder)\n"
	L"--grace-ms <n>       Time the other game gets to close (default 5000)\n"
	L"--log <file>         Log file (default: doomerfall-launcher.log beside the launcher)\n"
	L"--minimized          For tests: keep both games silent and unfocused, with no dialogs. UZDoom stays\n"
	L"                     minimized and Daggerfall Unity runs on a private desktop the user never sees\n"
	L"--show-dfu           For debugging: show Daggerfall Unity's window. By default it runs on a private\n"
	L"                     desktop, because Doom shows Daggerfall's UI and reads all input\n"
	L"--no-bridge          Do not create a bridge session\n"
	L"--nodraw             Daggerfall keeps its world loaded but does not draw it in 3D\n";

struct Options
{
	std::wstring uzdoom, dfu, iwad, uzdoomCwd, log;
	std::vector<std::wstring> mods, uzdoomArgs, dfuArgs;
	DWORD graceMs = 5000;
	bool minimized = false;
	bool showDfu = false;
	bool bridge = true;
};

struct Game
{
	const wchar_t *name;
	PROCESS_INFORMATION process{};
};

std::wstring logPath;
bool showDialogs = true;

std::string Utf8(const std::wstring &text)
{
	if (text.empty()) return {};
	int size = WideCharToMultiByte(CP_UTF8, 0, text.data(), (int)text.size(), nullptr, 0, nullptr, nullptr);
	std::string out(size, '\0');
	WideCharToMultiByte(CP_UTF8, 0, text.data(), (int)text.size(), out.data(), size, nullptr, nullptr);
	return out;
}

void Log(const std::wstring &message)
{
	SYSTEMTIME t;
	GetLocalTime(&t);
	char stamp[32];
	snprintf(stamp, sizeof(stamp), "%02d:%02d:%02d.%03d ", t.wHour, t.wMinute, t.wSecond, t.wMilliseconds);
	std::ofstream file(logPath, std::ios::app | std::ios::binary);
	file << stamp << Utf8(message) << "\r\n";
}

int Fail(int code, const std::wstring &message)
{
	Log(L"error: " + message);
	if (showDialogs) MessageBoxW(nullptr, message.c_str(), L"Doomerfall launcher", MB_OK | MB_ICONERROR);
	return code;
}

std::wstring LastError()
{
	wchar_t *text = nullptr;
	DWORD code = GetLastError();
	FormatMessageW(FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
		nullptr, code, 0, (LPWSTR)&text, 0, nullptr);
	std::wstring out = text ? text : L"unknown error";
	if (text) LocalFree(text);
	while (!out.empty() && (out.back() == L'\r' || out.back() == L'\n')) out.pop_back();
	return out + L" (" + std::to_wstring(code) + L")";
}

std::wstring FullPath(const std::wstring &path)
{
	DWORD size = GetFullPathNameW(path.c_str(), 0, nullptr, nullptr);
	if (!size) return path;
	std::wstring out(size, L'\0');
	DWORD written = GetFullPathNameW(path.c_str(), size, out.data(), nullptr);
	out.resize(written);
	return out;
}

std::wstring ParentDir(const std::wstring &path)
{
	size_t slash = path.find_last_of(L"\\/");
	return slash == std::wstring::npos ? L"." : path.substr(0, slash);
}

bool PathExists(const std::wstring &path)
{
	return GetFileAttributesW(path.c_str()) != INVALID_FILE_ATTRIBUTES;
}

bool IsAbsolute(const std::wstring &path)
{
	return (path.size() > 1 && path[1] == L':') || (path.size() > 1 && (path[0] == L'\\' || path[0] == L'/'));
}

// Quotes one argument by the CommandLineToArgvW rules.
void AppendArg(std::wstring &line, const std::wstring &arg)
{
	if (!line.empty()) line += L' ';
	if (!arg.empty() && arg.find_first_of(L" \t\n\v\"") == std::wstring::npos)
	{
		line += arg;
		return;
	}
	line += L'"';
	for (size_t i = 0;; i++)
	{
		size_t slashes = 0;
		while (i < arg.size() && arg[i] == L'\\') { i++; slashes++; }
		if (i == arg.size())
		{
			line.append(slashes * 2, L'\\');
			break;
		}
		if (arg[i] == L'"')
			line.append(slashes * 2 + 1, L'\\');
		else
			line.append(slashes, L'\\');
		line += arg[i];
	}
	line += L'"';
}

bool ReadModList(const std::wstring &listPath, std::vector<std::wstring> &mods, std::wstring &error)
{
	std::ifstream file(listPath, std::ios::binary);
	if (!file)
	{
		error = L"Cannot read mod list: " + listPath;
		return false;
	}
	std::string bytes((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
	if (bytes.rfind("\xEF\xBB\xBF", 0) == 0) bytes.erase(0, 3);

	std::wstring text;
	if (!bytes.empty())
	{
		int size = MultiByteToWideChar(CP_UTF8, 0, bytes.data(), (int)bytes.size(), nullptr, 0);
		text.resize(size);
		MultiByteToWideChar(CP_UTF8, 0, bytes.data(), (int)bytes.size(), text.data(), size);
	}

	const std::wstring base = ParentDir(FullPath(listPath));
	size_t start = 0;
	while (start <= text.size())
	{
		size_t end = text.find(L'\n', start);
		if (end == std::wstring::npos) end = text.size();
		std::wstring line = text.substr(start, end - start);
		start = end + 1;

		size_t first = line.find_first_not_of(L" \t\r");
		if (first == std::wstring::npos || line[first] == L'#') continue;
		line = line.substr(first, line.find_last_not_of(L" \t\r") - first + 1);
		mods.push_back(IsAbsolute(line) ? line : FullPath(base + L"\\" + line));
	}
	return true;
}

bool ParseArgs(int argc, wchar_t **argv, Options &options, std::wstring &error)
{
	for (int i = 1; i < argc; i++)
	{
		const std::wstring arg = argv[i];
		if (arg == L"--minimized")
		{
			options.minimized = true;
			continue;
		}
		if (arg == L"--show-dfu")
		{
			options.showDfu = true;
			continue;
		}
		if (arg == L"--no-bridge")
		{
			options.bridge = false;
			continue;
		}
		if (arg == L"--nodraw")
		{
			options.dfuArgs.push_back(L"-dfnodraw");
			continue;
		}
		if (i + 1 >= argc)
		{
			error = L"Unknown or incomplete argument: " + arg;
			return false;
		}
		const std::wstring value = argv[i + 1];
		if (arg == L"--uzdoom") options.uzdoom = value;
		else if (arg == L"--dfu") options.dfu = value;
		else if (arg == L"--iwad") options.iwad = value;
		else if (arg == L"--mod") options.mods.push_back(value);
		else if (arg == L"--mod-list") { if (!ReadModList(value, options.mods, error)) return false; }
		else if (arg == L"--uzdoom-arg") options.uzdoomArgs.push_back(value);
		else if (arg == L"--dfu-arg") options.dfuArgs.push_back(value);
		else if (arg == L"--uzdoom-cwd") options.uzdoomCwd = value;
		else if (arg == L"--log") options.log = value;
		else if (arg == L"--grace-ms")
		{
			wchar_t *end = nullptr;
			unsigned long ms = wcstoul(value.c_str(), &end, 10);
			if (value.empty() || *end || value[0] == L'-')
			{
				error = L"Invalid --grace-ms value: " + value;
				return false;
			}
			options.graceMs = ms;
		}
		else
		{
			error = L"Unknown argument: " + arg;
			return false;
		}
		i++;
	}
	if (options.uzdoom.empty() || options.dfu.empty())
	{
		error = L"--uzdoom and --dfu are required.";
		return false;
	}
	return true;
}

bool CheckPaths(const Options &options, std::wstring &error)
{
	std::vector<std::wstring> required{ options.uzdoom, options.dfu };
	if (!options.iwad.empty()) required.push_back(options.iwad);
	if (!options.uzdoomCwd.empty()) required.push_back(options.uzdoomCwd);
	required.insert(required.end(), options.mods.begin(), options.mods.end());
	for (const std::wstring &path : required)
	{
		if (!PathExists(path))
		{
			error = L"File not found: " + path;
			return false;
		}
	}
	return true;
}

std::wstring UZDoomCommandLine(const Options &options)
{
	std::wstring line;
	AppendArg(line, options.uzdoom);
	if (!options.iwad.empty())
	{
		AppendArg(line, L"-iwad");
		AppendArg(line, options.iwad);
	}
	if (!options.mods.empty())
	{
		AppendArg(line, L"-file");
		for (const std::wstring &mod : options.mods) AppendArg(line, mod);
	}
	// Doomerfall's graphics settings (architecture.md, Graphics), before the caller's own so those can override them.
	for (const wchar_t *arg : { L"+gl_bloom", L"1", L"+gl_light_shadowmap", L"1", L"+gl_ssao", L"2", L"+gl_lens", L"1" })
		AppendArg(line, arg);
	for (const std::wstring &arg : options.uzdoomArgs) AppendArg(line, arg);
	return line;
}

std::wstring DfuCommandLine(const Options &options)
{
	std::wstring line;
	AppendArg(line, options.dfu);
	for (const std::wstring &arg : options.dfuArgs) AppendArg(line, arg);
	return line;
}

// Starts a game suspended and inside the job, so it cannot spawn anything outside it.
// A desktop name puts the game, and anything it starts, on that desktop instead of the user's.
bool StartSuspended(Game &game, const std::wstring &exe, std::wstring commandLine, const std::wstring &cwd,
	HANDLE job, bool minimized, std::wstring desktop, std::wstring &error)
{
	STARTUPINFOW startup{};
	startup.cb = sizeof(startup);
	if (minimized)
	{
		startup.dwFlags = STARTF_USESHOWWINDOW;
		startup.wShowWindow = SW_SHOWMINNOACTIVE;
	}
	if (!desktop.empty()) startup.lpDesktop = desktop.data();
	if (!CreateProcessW(exe.c_str(), commandLine.data(), nullptr, nullptr, FALSE,
		CREATE_SUSPENDED | CREATE_DEFAULT_ERROR_MODE, nullptr, cwd.c_str(), &startup, &game.process))
	{
		error = std::wstring(L"Could not start ") + game.name + L": " + LastError();
		return false;
	}
	if (!AssignProcessToJobObject(job, game.process.hProcess))
	{
		error = std::wstring(L"Could not add ") + game.name + L" to the job: " + LastError();
		TerminateProcess(game.process.hProcess, 1);
		return false;
	}
	Log(std::wstring(L"started ") + game.name + L" pid " + std::to_wstring(game.process.dwProcessId) + L": " + commandLine);
	return true;
}

struct QuietState
{
	DWORD pids[2];
	HWND previous;
};

BOOL CALLBACK MinimizeWindow(HWND hwnd, LPARAM param)
{
	auto *state = reinterpret_cast<QuietState *>(param);
	DWORD pid = 0;
	GetWindowThreadProcessId(hwnd, &pid);
	if ((pid == state->pids[0] || pid == state->pids[1]) && IsWindowVisible(hwnd) && !IsIconic(hwnd))
		ShowWindow(hwnd, SW_SHOWMINNOACTIVE);
	return TRUE;
}

void KeepQuiet(QuietState &state)
{
	EnumWindows(MinimizeWindow, reinterpret_cast<LPARAM>(&state));
	HWND foreground = GetForegroundWindow();
	if (state.previous && foreground && foreground != state.previous)
	{
		DWORD pid = 0;
		GetWindowThreadProcessId(foreground, &pid);
		if (pid == state.pids[0] || pid == state.pids[1]) SetForegroundWindow(state.previous);
	}
}

BOOL CALLBACK PostClose(HWND hwnd, LPARAM param)
{
	DWORD pid = 0;
	GetWindowThreadProcessId(hwnd, &pid);
	if (pid == static_cast<DWORD>(param) && IsWindowVisible(hwnd) && !GetWindow(hwnd, GW_OWNER))
		PostMessageW(hwnd, WM_CLOSE, 0, 0);
	return TRUE;
}

DWORD ActiveProcesses(HANDLE job)
{
	JOBOBJECT_BASIC_ACCOUNTING_INFORMATION info{};
	if (!QueryInformationJobObject(job, JobObjectBasicAccountingInformation, &info, sizeof(info), nullptr)) return 0;
	return info.ActiveProcesses;
}

// Asks the surviving game to close, then lets the job drain so a crash handler can finish its dump.
// A game on a private desktop has its windows looked up there.
void ShutDown(HANDLE job, Game &survivor, HDESK desktop, DWORD graceMs)
{
	const ULONGLONG deadline = GetTickCount64() + graceMs;
	while (GetTickCount64() < deadline)
	{
		if (WaitForSingleObject(survivor.process.hProcess, 0) == WAIT_OBJECT_0)
		{
			if (ActiveProcesses(job) == 0) break;
		}
		else if (desktop)
		{
			EnumDesktopWindows(desktop, PostClose, static_cast<LPARAM>(survivor.process.dwProcessId));
		}
		else
		{
			EnumWindows(PostClose, static_cast<LPARAM>(survivor.process.dwProcessId));
		}
		Sleep(ClosePollMs);
	}

	const bool clean = WaitForSingleObject(survivor.process.hProcess, 0) == WAIT_OBJECT_0;
	const DWORD remaining = ActiveProcesses(job);
	if (remaining)
	{
		Log(L"force-ending " + std::to_wstring(remaining) + L" process(es) after the grace period");
		TerminateJobObject(job, 1);
		WaitForSingleObject(survivor.process.hProcess, 2000);
	}
	Log(std::wstring(survivor.name) + (clean ? L" closed on request" : L" was force-ended"));
}

int Run(Options options)
{
	// The launcher holds the session open for the games' whole lifetime.
	dfb_session *bridge = nullptr;
	if (options.bridge)
	{
		char id[40];
		snprintf(id, sizeof(id), "%08lx-%016llx", GetCurrentProcessId(), (unsigned long long)dfb_now_ns());
		const int rc = dfb_create(id, &bridge);
		if (rc != DFB_OK)
			return Fail(ExitLaunchFailed, L"Could not create the bridge session (error " + std::to_wstring(rc) + L")");
		const std::wstring wideId(id, id + strlen(id));
		options.uzdoomArgs.push_back(L"-dfbridge");
		options.uzdoomArgs.push_back(wideId);
		options.dfuArgs.push_back(L"-dfbridge");
		options.dfuArgs.push_back(wideId);
		Log(L"bridge session " + wideId);
	}

	// Daggerfall Unity's loose texture pack folder (<exe>_Data\StreamingAssets\Textures), so Doom draws Daggerfall's
	// people and corpses with the same replacements (UZDoom/src/playsim/dd_dftextures.cpp).
	{
		std::wstring exe = options.dfu.substr(options.dfu.find_last_of(L"\\/") + 1);
		const size_t dot = exe.find_last_of(L'.');
		if (dot != std::wstring::npos) exe.resize(dot);
		options.uzdoomArgs.push_back(L"-ddtextures");
		options.uzdoomArgs.push_back(ParentDir(options.dfu) + L"\\" + exe + L"_Data\\StreamingAssets\\Textures");
	}

	// Daggerfall runs on a desktop nobody sees, because Unity shows and activates its window on start whatever
	// it is asked, and in play Doom shows Daggerfall's UI and reads all input. So only Doom's window ever appears.
	// Test mode also keeps both games silent, and UZDoom minimized here, so it renders as before.
	if (options.minimized)
	{
		options.uzdoomArgs.push_back(L"-nosound");
		options.uzdoomArgs.push_back(L"-noactivate");
		options.dfuArgs.push_back(L"-dfmute");
	}
	HDESK desktop = nullptr;
	std::wstring desktopName;
	if (options.minimized || !options.showDfu)
	{
		desktopName = L"doomerfall-dfu-" + std::to_wstring(GetCurrentProcessId());
		desktop = CreateDesktopW(desktopName.c_str(), nullptr, nullptr, 0, GENERIC_ALL, nullptr);
		if (!desktop) return Fail(ExitLaunchFailed, L"Could not create Daggerfall's desktop: " + LastError());
		Log(L"Daggerfall desktop " + desktopName);
	}

	HANDLE job = CreateJobObjectW(nullptr, nullptr);
	if (!job) return Fail(ExitLaunchFailed, L"Could not create the job object: " + LastError());

	JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
	limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
	if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof(limits)))
		return Fail(ExitLaunchFailed, L"Could not configure the job object: " + LastError());

	Game games[2] = { { L"UZDoom" }, { L"Daggerfall Unity" } };
	const std::wstring uzdoomCwd = options.uzdoomCwd.empty() ? ParentDir(options.uzdoom) : options.uzdoomCwd;
	HWND previous = GetForegroundWindow();

	std::wstring error;
	if (!StartSuspended(games[0], options.uzdoom, UZDoomCommandLine(options), uzdoomCwd, job, options.minimized, L"", error) ||
		!StartSuspended(games[1], options.dfu, DfuCommandLine(options), ParentDir(options.dfu), job, options.minimized, desktopName, error))
	{
		TerminateJobObject(job, 1);
		return Fail(ExitLaunchFailed, error);
	}
	if (!options.minimized) AllowSetForegroundWindow(games[0].process.dwProcessId); // Doom's window comes up in front.
	ResumeThread(games[0].process.hThread);
	ResumeThread(games[1].process.hThread);

	HANDLE handles[2] = { games[0].process.hProcess, games[1].process.hProcess };
	QuietState quiet{ { games[0].process.dwProcessId, games[1].process.dwProcessId }, previous };
	DWORD wait;
	do
	{
		if (options.minimized) KeepQuiet(quiet);
		wait = WaitForMultipleObjects(2, handles, FALSE, options.minimized ? QuietPollMs : INFINITE);
	} while (wait == WAIT_TIMEOUT);

	if (wait != WAIT_OBJECT_0 && wait != WAIT_OBJECT_0 + 1)
	{
		const std::wstring waitError = LastError();
		TerminateJobObject(job, 1);
		return Fail(ExitLaunchFailed, L"Waiting on the games failed: " + waitError);
	}

	const int first = wait - WAIT_OBJECT_0;
	DWORD exitCode = 0;
	GetExitCodeProcess(handles[first], &exitCode);
	wchar_t hex[16];
	swprintf_s(hex, L"0x%08X", exitCode);
	Log(std::wstring(games[first].name) + L" exited first with code " + std::to_wstring(exitCode) + L" (" + hex + L")");

	ShutDown(job, games[1 - first], first == 0 ? desktop : nullptr, options.graceMs);
	CloseHandle(job);
	if (desktop) CloseDesktop(desktop);
	dfb_close(bridge);
	Log(L"launcher done");
	return static_cast<int>(exitCode);
}
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int)
{
	wchar_t self[MAX_PATH * 4];
	GetModuleFileNameW(nullptr, self, ARRAYSIZE(self));
	logPath = ParentDir(self) + L"\\doomerfall-launcher.log";

	int argc = 0;
	wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
	if (!argv) return Fail(ExitUsage, L"Could not read the command line.");

	Options options;
	std::wstring error;
	const bool parsed = ParseArgs(argc, argv, options, error);
	LocalFree(argv);

	if (!options.log.empty()) logPath = options.log;
	showDialogs = !options.minimized;
	if (!parsed) return Fail(ExitUsage, error + L"\n\n" + Usage);

	options.uzdoom = FullPath(options.uzdoom);
	options.dfu = FullPath(options.dfu);
	if (!options.uzdoomCwd.empty()) options.uzdoomCwd = FullPath(options.uzdoomCwd);
	if (!CheckPaths(options, error)) return Fail(ExitUsage, error);

	Log(L"launcher start");
	return Run(options);
}
