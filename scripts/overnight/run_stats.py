"""Print token and tool-output stats for an overnight run's agent sessions as JSON.

Usage: run_stats.py --since <ISO time> <session-id> [<session-id> ...]

Transcripts repeat an API response once per content block, so usage is counted per message id.
Entries before --since are skipped, so a session forked from a planning chat counts only this run.
"""
import argparse
import glob
import json
import os
from datetime import datetime, timezone


def parse_time(text):
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def tool_chars(content):
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(b.get("text", "")) for b in content if isinstance(b, dict))
    return 0


def read_transcript(path, since, usage, tools):
    """Adds this file's entries to usage and tools. Returns the file's peak context."""
    peak = 0
    with open(path, encoding="utf-8", errors="replace") as lines:
        for line in lines:
            try:
                entry = json.loads(line)
                if parse_time(entry["timestamp"]) < since:
                    continue
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            if entry.get("type") == "assistant" and message.get("id") and message.get("usage"):
                if message.get("model") == "<synthetic>":
                    continue
                u = message["usage"]
                usage[message["id"]] = u
                context = sum(u.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
                peak = max(peak, context)
            elif entry.get("type") == "user" and isinstance(message.get("content"), list):
                for block in message["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tools[block.get("tool_use_id")] = tool_chars(block.get("content"))
    return peak


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", required=True)
    parser.add_argument("sessions", nargs="+")
    args = parser.parse_args()

    since = parse_time(args.since)
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    usage, tools = {}, {}
    peak = 0
    for session in dict.fromkeys(args.sessions):
        for path in glob.glob(os.path.join(glob.escape(home), "projects", "*", session + ".jsonl")):
            # Peak context describes the main agent. Subagents have their own smaller contexts.
            peak = max(peak, read_transcript(path, since, usage, tools))
            pattern = os.path.join(glob.escape(path[:-len(".jsonl")]), "subagents", "**", "*.jsonl")
            for subagent in glob.glob(pattern, recursive=True):
                read_transcript(subagent, since, usage, tools)

    print(json.dumps({
        "PeakContext": peak,
        "CacheReadTokens": sum(u.get("cache_read_input_tokens") or 0 for u in usage.values()),
        "OutputTokens": sum(u.get("output_tokens") or 0 for u in usage.values()),
        "Messages": len(usage),
        "ToolOutputChars": sum(tools.values()),
    }))


if __name__ == "__main__":
    main()
