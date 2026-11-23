"""Lists where DRLA's scripts touch player health, to decide which Doom paths the HP sync must cover."""
import zipfile, re, collections
base = "D:/dev/DoomDaggerfall/GameMods/"
pat = re.compile(r'GiveBody|A_Heal|SetHealth|\.health\s*[-+*]?=|\bhealth\s*[-+]=|A_DamageSelf|DamageMobj\(\s*(self|owner)|"Health"|MaxHealth')
for f in ["DoomRL_Arsenal_1.1.5.pk3", "drlax_1.2b.pk3"]:
    z = zipfile.ZipFile(base + f)
    c = collections.Counter()
    ex = []
    for n in z.namelist():
        if 'monster' in n.lower():
            continue
        try:
            t = z.read(n).decode('latin1')
        except Exception:
            continue
        if len(t) > 5_000_000:
            continue
        for i, l in enumerate(t.split('\n')):
            if pat.search(l):
                c[n] += 1
                if len(ex) < 40:
                    ex.append((n, i + 1, l.strip()[:130]))
    print(f, sum(c.values()), c.most_common(8))
    for e in ex:
        print(e)
