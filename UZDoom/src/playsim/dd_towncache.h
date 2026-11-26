// [Doomerfall] Disk cache and background converter for generated Daggerfall locations.
// Inactive unless the game is started with -ddtowncache <dir> and -ddconverter <exe>.
#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

namespace DDTownCache
{
	enum class State { Missing, Converting, Reading, Ready, Failed };

	// One decompressed cache file: MAPWAD, DFMESH, DFFLATS, DFGATES, and DDTOWN.
	struct Entry
	{
		std::unordered_map<std::string, std::vector<uint8_t>> lumps;
		const std::vector<uint8_t> *Find(const char *name) const
		{
			auto it = lumps.find(name);
			return it == lumps.end() ? nullptr : &it->second;
		}
	};
	using EntryPtr = std::shared_ptr<const Entry>;

	bool Init();
	State Status(int group);
	bool Converting();

	// Requests are rebuilt on every scan, so a location the player walked away from drops out of the queue.
	void BeginScan();
	void Request(int group, double distance);

	// Advances the converter and file reads. Never blocks.
	void Poll();
	void Pin(int group);	// This group is never evicted from memory. -1 clears it.
	void SetWinter(bool on);	// Daggerfall's season: places loaded afterwards use its winter textures.

	EntryPtr Get(int group);			// The data if it is ready now.
	EntryPtr GetBlocking(int group);	// Reads or converts now. For loading a save, or a future fast-travel transition.
}
