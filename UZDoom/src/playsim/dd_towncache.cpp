// [Doomerfall] Disk cache and background converter for generated Daggerfall locations.
//
// A location is one file, T<group>.ddt. The converter writes it to a temporary name and renames it, so a
// partial file is never read. Files are decompressed on a worker thread. Files are disposable: they are
// rebuilt from game data on demand, and no player progress is stored in them.
//
// One converter runs at a time, below normal priority, and is killed if the game exits.

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <future>
#include <map>
#include <thread>

#include <miniz.h>

#include "dd_towncache.h"
#include "m_argv.h"
#include "printf.h"
#include "playsim/dd_log.h"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif

namespace fs = std::filesystem;

namespace DDTownCache
{
	namespace
	{
		constexpr size_t MAX_IN_MEMORY = 4;
		constexpr int MAX_READS = 2;
		constexpr int BLOCKING_LIMIT_MS = 120000;
		using Clock = std::chrono::steady_clock;

		struct Slot
		{
			State state = State::Missing;
			EntryPtr entry;
			std::future<EntryPtr> reading;
			uint64_t lastUse = 0;
			bool retried = false;
		};

		bool enabled, winter;
		fs::path cacheDir, converter, arena2;
		uint64_t capBytes = uint64_t(2048) << 20;
		std::unordered_map<int, Slot> slots;
		std::map<int, double> wanted;
		int forced = -1, pinned = -1, activeReads;
		uint64_t useClock;

		int running = -1;
		bool runningWinter;	// [Doomerfall] the season the running conversion is for
		Clock::time_point runStart;
#ifdef _WIN32
		HANDLE process, job;
#endif

#ifdef _WIN32
		// Test option -ddcrashexit <file>: an automated run records a crash and exits, instead of opening the crash dialog, which takes focus.
		wchar_t crashPath[512];
		LONG WINAPI CrashExit(EXCEPTION_POINTERS *info)
		{
			const DWORD code = info->ExceptionRecord->ExceptionCode;
			if (code != EXCEPTION_ACCESS_VIOLATION && code != EXCEPTION_STACK_OVERFLOW && code != EXCEPTION_ILLEGAL_INSTRUCTION && code != EXCEPTION_INT_DIVIDE_BY_ZERO) return EXCEPTION_CONTINUE_SEARCH;
			const uintptr_t base = uintptr_t(GetModuleHandleW(nullptr));
			FILE *f = nullptr;
			_wfopen_s(&f, crashPath, L"w");
			if (f)
			{
				fprintf(f, "code=%08lx rip_offset=%llx read=%llx\n", code, (unsigned long long)(info->ContextRecord->Rip - base), (unsigned long long)info->ExceptionRecord->ExceptionInformation[1]);
				const uint64_t *sp = (const uint64_t *)info->ContextRecord->Rsp;
				MEMORY_BASIC_INFORMATION region{};
				if (VirtualQuery(sp, &region, sizeof(region)))
				{
					const uint64_t *end = (const uint64_t *)(uintptr_t(region.BaseAddress) + region.RegionSize);
					for (int n = 0; sp < end && n < 1500; sp++, n++)
						if (*sp > base && *sp < base + 0x8000000) fprintf(f, "stack %llx\n", (unsigned long long)(*sp - base));
				}
				fclose(f);
			}
			TerminateProcess(GetCurrentProcess(), 3);
			return EXCEPTION_CONTINUE_SEARCH;
		}
#endif

		const char *ArgAfter(const char *name)
		{
			for (int i = 1; i + 1 < Args->NumArgs(); i++)
				if (!stricmp(Args->GetArg(i), name)) return Args->GetArg(i + 1);
			return nullptr;
		}

		// Only outdoor places have a winter look: interiors and dungeons (space ids) are the same in every season.
		bool Winter(int group) { return winter && group < 1000000; }

		fs::path FileFor(int group)
		{
			char name[32];
			snprintf(name, sizeof(name), "T%05d%s.ddt", group, Winter(group) ? "W" : "");	// Daggerfall's winter textures: their own file
			return cacheDir / name;
		}

		// Runs on a worker thread, so it must not touch engine state.
		EntryPtr ReadCacheFile(const fs::path &path)
		{
			FILE *f = nullptr;
#ifdef _WIN32
			_wfopen_s(&f, path.c_str(), L"rb");
#else
			f = fopen(path.c_str(), "rb");
#endif
			if (!f) return nullptr;
			auto fail = [f]() -> EntryPtr { fclose(f); return nullptr; };
			char magic[4];
			int32_t count = 0;
			if (fread(magic, 1, 4, f) != 4 || memcmp(magic, "DDT3", 4) || fread(&count, 4, 1, f) != 1 || count <= 0 || count > 16) return fail();
			struct Head { char name[9]; uint32_t raw, packed; };
			std::vector<Head> heads(count);
			for (auto &h : heads)
			{
				memset(h.name, 0, sizeof(h.name));
				if (fread(h.name, 1, 8, f) != 8 || fread(&h.raw, 4, 1, f) != 1 || fread(&h.packed, 4, 1, f) != 1) return fail();
			}
			auto entry = std::make_shared<Entry>();
			const std::wstring stem = path.stem().wstring();
			entry->winter = !stem.empty() && stem.back() == L'W';
			std::vector<uint8_t> packed;
			for (auto &h : heads)
			{
				packed.resize(h.packed);
				if (h.packed && fread(packed.data(), 1, h.packed, f) != h.packed) return fail();
				std::vector<uint8_t> raw(h.raw);
				mz_ulong size = h.raw;
				if (h.raw && (mz_uncompress(raw.data(), &size, packed.data(), h.packed) != MZ_OK || size != h.raw)) return fail();
				entry->lumps.emplace(h.name, std::move(raw));
			}
			fclose(f);
			// A building interior from a converter without Daggerfall place keys (dd_treadmill.cpp TownForSpace) is
			// treated as unreadable, so it is rebuilt once instead of attaching history by the space id.
			if (const auto *town = entry->Find("DDTOWN"))
			{
				const std::string body(town->begin(), town->end());
				if (body.rfind("space\n", 0) == 0 && body.find("\nplace ") == std::string::npos) return nullptr;
			}
			return entry;
		}

		void StartRead(int group, Slot &slot)
		{
			slot.state = State::Reading;
			activeReads++;
			std::error_code ec;
			fs::last_write_time(FileFor(group), fs::file_time_type::clock::now(), ec);	// The disk cache evicts by this time.
			slot.reading = std::async(std::launch::async, ReadCacheFile, FileFor(group));
		}

		// Removes the least recently used files over the cap. They are rebuilt if needed again.
		void TrimDisk()
		{
			struct Item { fs::path path; fs::file_time_type time; uint64_t size; };
			std::vector<Item> items;
			uint64_t total = 0;
			std::error_code ec;
			for (auto &e : fs::directory_iterator(cacheDir, ec))
			{
				if (e.path().extension() != ".ddt") continue;
				const uint64_t size = e.file_size(ec);
				total += size;
				items.push_back({ e.path(), e.last_write_time(ec), size });
			}
			if (total <= capBytes) return;
			std::sort(items.begin(), items.end(), [](const Item &a, const Item &b) { return a.time < b.time; });
			int removed = 0;
			for (auto &item : items)
			{
				if (total <= capBytes) break;
				const int group = atoi(item.path.stem().string().c_str() + 1);
				auto slot = slots.find(group);
				if (group == running || (slot != slots.end() && slot->second.state == State::Reading)) continue;
				if (fs::remove(item.path, ec)) { total -= item.size; removed++; }
			}
			DD_DebugPrintf("DDTCACHE evicted %d files, %.1f MB in use\n", removed, total / 1048576.0);
		}

		void TrimMemory()
		{
			for (;;)
			{
				int oldest = -1, ready = 0;
				uint64_t best = UINT64_MAX;
				for (auto &kv : slots)
				{
					if (kv.second.state != State::Ready) continue;
					ready++;
					if (kv.first == pinned) continue;	// The town the player will walk back out to.
					// An entry still held by the current map or the distant view stays alive through its shared pointer.
					if (kv.second.lastUse < best) { best = kv.second.lastUse; oldest = kv.first; }
				}
				if (ready <= int(MAX_IN_MEMORY) || oldest < 0) return;
				slots.erase(oldest);
			}
		}

		bool StartConverter(int group)
		{
#ifdef _WIN32
			std::error_code ec;
			const fs::path work = cacheDir / "work" / ("T" + std::to_string(group));
			fs::create_directories(work, ec);
			std::wstring command = L"\"" + converter.wstring() + L"\" --group " + std::to_wstring(group) + L" --ddt \"" + FileFor(group).wstring()
				+ L"\" --out \"" + work.wstring() + L"\" --arena2 \"" + arena2.wstring() + L"\"" + (Winter(group) ? L" --winter" : L"");
			SECURITY_ATTRIBUTES inherit{ sizeof(inherit), nullptr, TRUE };
			const fs::path logPath = work / "convert.log";
			HANDLE log = CreateFileW(logPath.c_str(), GENERIC_WRITE, FILE_SHARE_READ, &inherit, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
			STARTUPINFOW si{};
			si.cb = sizeof(si);
			si.dwFlags = STARTF_USESTDHANDLES;
			si.hStdOutput = si.hStdError = log;
			si.hStdInput = INVALID_HANDLE_VALUE;
			PROCESS_INFORMATION pi{};
			const BOOL ok = CreateProcessW(nullptr, command.data(), nullptr, nullptr, TRUE, CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS | CREATE_SUSPENDED, nullptr, nullptr, &si, &pi);
			if (log != INVALID_HANDLE_VALUE) CloseHandle(log);
			if (!ok)
			{
				DD_DebugPrintf("DDTCONV group=%d could not start the converter (error %lu)\n", group, GetLastError());
				return false;
			}
			if (!job)
			{
				job = CreateJobObjectW(nullptr, nullptr);
				JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
				limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
				if (job) SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof(limits));
			}
			if (job) AssignProcessToJobObject(job, pi.hProcess);
			ResumeThread(pi.hThread);
			CloseHandle(pi.hThread);
			process = pi.hProcess;
			running = group;
			runningWinter = Winter(group);
			runStart = Clock::now();
			return true;
#else
			DD_DebugPrintf("DDTCONV background conversion is only implemented on Windows\n");
			return false;
#endif
		}

		void PollConverter()
		{
#ifdef _WIN32
			if (running < 0 || WaitForSingleObject(process, 0) != WAIT_OBJECT_0) return;
			DWORD code = 1;
			GetExitCodeProcess(process, &code);
			CloseHandle(process);
			process = nullptr;
			const int group = running;
			running = -1;
			const double ms = std::chrono::duration<double, std::milli>(Clock::now() - runStart).count();
			Slot &slot = slots[group];
			std::error_code ec;
			if (runningWinter != Winter(group))	// [Doomerfall] the season changed during the conversion: convert again
			{
				fs::remove_all(cacheDir / "work" / ("T" + std::to_string(group)), ec);
				slot.state = State::Missing;
				DD_DebugPrintf("DDTCONV group=%d finished in the previous season, converting again\n", group);
				return;
			}
			if (code == 0 && fs::exists(FileFor(group), ec))
			{
				DD_DebugPrintf("DDTCONV group=%d ok ms=%.0f bytes=%llu\n", group, ms, (unsigned long long)fs::file_size(FileFor(group), ec));
				fs::remove_all(cacheDir / "work" / ("T" + std::to_string(group)), ec);
				StartRead(group, slot);
				TrimDisk();
			}
			else
			{
				DD_DebugPrintf("DDTCONV group=%d failed exit=%lu ms=%.0f. The overworld stays playable here.\n", group, code, ms);
				slot.state = State::Failed;
			}
#endif
		}

		void PollReads()
		{
			for (auto &kv : slots)
			{
				Slot &slot = kv.second;
				if (slot.state != State::Reading || slot.reading.wait_for(std::chrono::seconds(0)) != std::future_status::ready) continue;
				activeReads--;
				slot.entry = slot.reading.get();
				if (slot.entry && slot.entry->winter != Winter(kv.first))	// [Doomerfall] the season changed during the read
				{
					slot.entry = nullptr;
					slot.state = State::Missing;
					continue;
				}
				if (slot.entry)
				{
					slot.state = State::Ready;
					slot.lastUse = ++useClock;
					continue;
				}
				// A damaged cache file is deleted and rebuilt once.
				std::error_code ec;
				fs::remove(FileFor(kv.first), ec);
				slot.state = slot.retried ? State::Failed : State::Missing;
				slot.retried = true;
				DD_DebugPrintf("DDTCACHE group=%d unreadable, %s\n", kv.first, slot.state == State::Failed ? "giving up" : "rebuilding");
			}
		}

		void StartNext()
		{
			int best = -1;
			double bestDistance = 1e30;
			auto consider = [&](int group, double distance)
			{
				auto it = slots.find(group);
				if (it != slots.end() && it->second.state != State::Missing) return;
				if (distance < bestDistance) { best = group; bestDistance = distance; }
			};
			if (forced >= 0) consider(forced, -1);
			for (auto &kv : wanted) consider(kv.first, kv.second);
			if (best < 0) return;
			Slot &slot = slots[best];
			std::error_code ec;
			if (fs::exists(FileFor(best), ec))
			{
				if (activeReads < MAX_READS) StartRead(best, slot);
				return;
			}
			if (running >= 0) return;
			if (StartConverter(best)) slot.state = State::Converting;
			else slot.state = State::Failed;
		}
	}

	bool Init()
	{
		if (enabled) return true;
#ifdef _WIN32
		if (const char *crash = ArgAfter("-ddcrashexit"))
		{
			MultiByteToWideChar(CP_UTF8, 0, crash, -1, crashPath, 512);
			AddVectoredExceptionHandler(1, CrashExit);
		}
#endif
		const char *dir = ArgAfter("-ddtowncache"), *exe = ArgAfter("-ddconverter"), *data = ArgAfter("-ddarena2");
		if (!dir || !exe || !data) return false;
		cacheDir = dir;
		converter = exe;
		arena2 = data;
		if (const char *cap = ArgAfter("-ddtowncachemb")) capBytes = uint64_t(std::max(16, atoi(cap))) << 20;
		std::error_code ec;
		fs::create_directories(cacheDir, ec);
		fs::remove_all(cacheDir / "work", ec);	// Left behind if a previous session was killed.
		enabled = fs::is_directory(cacheDir, ec);
		if (enabled) DD_DebugPrintf("DDTCACHE dir=%s cap=%llu MB\n", dir, (unsigned long long)(capBytes >> 20));
		return enabled;
	}

	State Status(int group)
	{
		auto it = slots.find(group);
		return it == slots.end() ? State::Missing : it->second.state;
	}

	// Daggerfall's season (dd_weather.cpp). Places loaded from now on use the other texture set; loaded data is dropped
	// unless a map holds it, so the next area load picks the new season. The treadmill re-requests the town in view or
	// underfoot and swaps it in once ready (dd_treadmill.cpp: ScanLocations, RefreshTownSeason).
	void SetWinter(bool on)
	{
		if (on == winter) return;
		winter = on;
		for (auto it = slots.begin(); it != slots.end();)
			it = it->second.state == State::Ready || it->second.state == State::Failed ? slots.erase(it) : std::next(it);
		DD_DebugPrintf("DDTCACHE season %s: places load with %s textures from now on\n", on ? "winter" : "summer", on ? "winter" : "summer");
	}

	bool IsWinter() { return winter; }	// [Doomerfall] the season the nature flats use (dd_nature.cpp)
	void Pin(int group) { pinned = group; }
	bool Converting() { return running >= 0; }
	void BeginScan() { wanted.clear(); }
	void Request(int group, double distance) { if (enabled) wanted[group] = distance; }

	void Poll()
	{
		if (!enabled) return;
		PollConverter();
		PollReads();
		StartNext();
		TrimMemory();
	}

	EntryPtr Get(int group)
	{
		auto it = slots.find(group);
		if (it == slots.end() || it->second.state != State::Ready) return nullptr;
		it->second.lastUse = ++useClock;
		return it->second.entry;
	}

	EntryPtr GetBlocking(int group)
	{
		if (!enabled) return nullptr;
		if (EntryPtr ready = Get(group)) return ready;
		auto it = slots.find(group);
		if (it != slots.end() && it->second.state == State::Failed) it->second.state = State::Missing;	// An explicit request retries.
		forced = group;
		const auto start = Clock::now();
		EntryPtr result;
		while (std::chrono::duration<double, std::milli>(Clock::now() - start).count() < BLOCKING_LIMIT_MS)
		{
			PollConverter();
			PollReads();
			StartNext();
			if ((result = Get(group)) || Status(group) == State::Failed) break;
			std::this_thread::sleep_for(std::chrono::milliseconds(2));
		}
		forced = -1;
		return result;
	}
}
