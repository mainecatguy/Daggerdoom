"""Heading-by-heading comparison of two paired_walk.py summaries (old map first).
usage: paired_walk_compare.py <old summary.txt> <new summary.txt>
Columns: net distance / jitter tics / snags / floor steps, and the end point. Flags more jitter, more snags, and reach
more than 10 units shorter.
"""
import re, sys
pat = re.compile(r"spot (\d) heading +([\d.]+): net +(\d+) to (\S+), jitter tics +(\d+), path +(\d+), tic +[\d.]+, snags (\d+), floor steps (\d+)")
def load(p):
    return {(m[1], m[2]): m for m in (pat.match(l) for l in open(p)) if m}
old, new = load(sys.argv[1]), load(sys.argv[2])
print("spot heading | old net/jit/snag/step end | new net/jit/snag/step end | flag")
for k in sorted(old, key=lambda k: (int(k[0]), float(k[1]))):
    o, n = old[k], new[k]
    flags = []
    if int(n[5]) > int(o[5]): flags.append("MORE JITTER")
    if int(n[7]) > int(o[7]): flags.append("MORE SNAGS")
    if int(n[3]) < int(o[3]) - 10: flags.append("LESS REACH")
    if int(n[5]) < int(o[5]): flags.append("less jitter")
    if int(n[7]) < int(o[7]): flags.append("fewer snags")
    print(f"{k[0]} {k[1]:>5} | {o[3]:>4}/{o[5]:>3}/{o[7]}/{o[8]} {o[4]:<16} | {n[3]:>4}/{n[5]:>3}/{n[7]}/{n[8]} {n[4]:<16} | {', '.join(flags)}")
