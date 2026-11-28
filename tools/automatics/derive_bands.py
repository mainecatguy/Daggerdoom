"""Writes each DRLA gun's base tics between shots, for the Automatics fire-rate bands (skillperks 09).

usage: python tools/automatics/derive_bands.py [--drla DIR] [--write | --check]

The owner's rule (2026-11-27): a gun's band is inherent to it, from its base time between shots: 4 or more tics slow,
3 middle, 1-2 fast. "Base" means without mods, perks or other fire-rate bonuses; a gun that spins up (the minigun)
counts at full speed; an alternate fire that shoots has its own rate. derive_rifles.trace_fire walks a DRLA gun's fire
state with the trigger held, no mods and ammo loaded, until it settles into its loop, and gives the closest two shots in
that loop: that is the spun-up rate. Here every A_WeaponReady that allows the fire also refires (ready_fires), as the
engine does with the button held. A gun that never fires while fire is held is measured pressed once per shot.

One row per way the gun can fire:
  firing modes  an item the AltFire states give (A_GiveInventory/A_SetInventory) and the Fire states check
                (A_JumpIfInventory) is a firing mode (the Grammaton Beretta's semi/burst/full auto). Each count
                0..maxamount is walked with that count; Doom reads the player's count.
  alt fire      an AltFire whose states shoot is walked as its own fire; Doom uses that row while the gun's bAltFire
                is set (the engine sets it while the alternate fire runs).
  synth fire    DRLA's dual guns (Storm Uzi) fire each hand from a button item an ACS script sets every tic
                (RLSynthFireLeft for Fire, RLSynthFireRight for AltFire); each hand is walked with its item held.

Every DRLA gun that could be an Automatic (gives the rapid-fire token, or is on DoomerfallWeaponCategory's owner list
of Automatics, or the Grammaton Cleric Beretta) must get a primary rate: --check and --write fail if one cannot be
measured. --write puts the table into mods/doomerfall/src/zscript/DoomerfallAutomaticBands.zs between the GENERATED
markers; --check also fails if it is stale.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'rifle_tag'))
import derive_rifles as d  # noqa: E402

TABLE_FILE = os.path.join(d.REPO, 'mods', 'doomerfall', 'src', 'zscript', 'DoomerfallAutomaticBands.zs')
EXTRA = {'rlgrammatonclericberetta'}  # Pistol + Automatic by the owner's dual-tag rule
SYNTH = ('rlsynthfireleft', 'rlsynthfireright')
GIVE = re.compile(r'\bA_(?:Give|Set)Inventory\s*\(\s*"(\w+)"', re.I)
CHECK = re.compile(r'\bA_JumpIfInventory\s*\(\s*"(\w+)"', re.I)
JUMPS = re.compile(r'\bA_Jump\w*\s*\((.*)\)', re.I)


def owner_automatics():
    with open(d.CATEGORY_FILE, encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'automatics\[\]\s*=\s*\{(.*?)\};', text, re.S)
    return {n.lower() for n in re.findall(r'"(\w+)"', d.strip_comments(m.group(1)))} | EXTRA


def reachable(actors, a, label):
    """The action text of every state reachable from a label, taking every branch (gotos, jumps by label or offset)."""
    owner, i = d.find_label(actors, a, label)
    todo, seen, out = ([(owner, i)] if owner else []), set(), []
    while todo:
        owner, i = todo.pop()
        if owner is None or (id(owner), i) in seen or i >= len(owner.states):
            continue
        seen.add((id(owner), i))
        st = owner.states[i]
        if st[0] == 'goto':
            o2, j = d.find_label(actors, a, st[1]) if '::' not in st[1] else d.find_label(actors, owner, st[1])
            if o2 is not None:
                todo.append((o2, d.frame_offset(o2, j, st[2]) if st[2] else j))
            continue
        if st[0] == 'goto_index':
            todo.append((owner, st[1]))
            continue
        if st[0] != 'frame':
            continue
        rest = st[2]
        out.append(rest)
        for jm in JUMPS.finditer(rest):
            for name, num in re.findall(r'"([\w.:]+)"|\b(\d+)\b', jm.group(1)):
                if name and d.find_label(actors, a, name)[0] is not None:
                    todo.append(d.find_label(actors, a, name))
                elif num:
                    todo.append((owner, d.frame_offset(owner, i, int(num))))
        todo.append((owner, i + 1))
    return out


def measure(actors, a, ammo, start='Fire', inv0=None):
    # DRLA's DRLA_SynthFire script sets RLSynthFireLeft every tic while Fire is held (RLSynthFireRight for AltFire);
    # spin-up guns (the Hurricane Cannon) keep spinning on it.
    inv0 = dict(inv0 or {})
    inv0[SYNTH[0] if start == 'Fire' else SYNTH[1]] = 1
    gap, shots, _, note = d.trace_fire(actors, a, ammo, start=start, inv0=inv0, ready_fires=True)
    if not shots:
        gap, shots, _, note = d.trace_fire(actors, a, ammo, held=False, start=start, inv0=inv0, ready_fires=True)
    return (int(round(gap)), note) if shots and gap and gap > 0 else (None, note)


def maxamount(actors, item):
    x = actors.get(item)
    v = d.prop(actors, x, 'inventory.maxamount') if x else None
    return int(v) if v and v.lstrip('-').isdigit() else 1


def a_name(actors, key):
    x = actors.get(key)
    return x.name if x else key


def press_alt(actors, a, ammo, inv):
    """Presses AltFire once with these counters, no mods and no other items: walks the states (inventory jumps by
    the counters, A_Jump(256) taken, other jumps not) until the gun is ready again. Returns (counters after, shot)."""
    owner, i = d.find_label(actors, a, 'AltFire')
    ready_owner, ready_i = d.find_label(actors, a, 'Ready')
    inv, shot, steps = dict(inv), False, 0
    while owner is not None and steps < 2000:
        steps += 1
        if (owner is ready_owner and i == ready_i) or i >= len(owner.states):
            break
        st = owner.states[i]
        if st[0] == 'goto':
            owner, i = d.find_label(actors, a, st[1]) if '::' not in st[1] else d.find_label(actors, owner, st[1])
            if owner is not None and st[2]:
                i = d.frame_offset(owner, i, st[2])
            continue
        if st[0] == 'goto_index':
            i = st[1]
            continue
        if st[0] != 'frame':
            break
        rest = st[2]
        if d.SHOT.search(rest):
            shot = True
        if re.search(r'\bA_WeaponReady\b|\bA_ReFire\b', rest, re.I):
            break
        for m in re.finditer(r'\bA_(Give|Take|Set)Inventory\s*\(\s*"(\w+)"\s*(?:,\s*(\d+))?', rest, re.I):
            item, op = m.group(2).lower(), m.group(1).lower()
            if item in ammo:
                continue
            n = int(m.group(3)) if m.group(3) else (1 if op == 'give' else 0)
            if op == 'give':
                inv[item] = min(inv.get(item, 0) + n, maxamount(actors, item))
            elif op == 'set':
                inv[item] = n
            else:
                inv[item] = 0 if n == 0 else max(inv.get(item, 0) - n, 0)
            if inv[item] == 0:
                del inv[item]
        jm = re.search(r'\bA_Jump\s*\(\s*(\d+)\s*,\s*("?[\w.:]+"?)', rest, re.I)
        im = re.search(r'\bA_JumpIfInventory\s*\(\s*"(\w+)"\s*,\s*(\d+)\s*,\s*("?[\w.:]+"?)', rest, re.I)
        target = None
        if jm and int(jm.group(1)) >= 256:
            target = jm.group(2)
        elif im:
            item, amount = im.group(1).lower(), int(im.group(2))
            have = inv.get(item, 0)
            if item in ammo or (have >= maxamount(actors, item) if amount == 0 else (have > 0 and have >= amount)):
                target = im.group(3)
        if target:
            target = target.strip('"')
            if target.isdigit():
                i = d.frame_offset(owner, i, int(target))
            else:
                owner, i = d.find_label(actors, a, target)
            continue
        i += 1
    return inv, shot


def fire_modes(actors, a, ammo):
    """The counters each AltFire press leads to, from none, until they repeat: [{}] for a gun without modes. Only
    counters the Fire states check are firing modes (a zoom cooldown or a cloak powerup the AltFire also gives is not)."""
    checked = {m.lower() for t in reachable(actors, a, 'Fire') for m in CHECK.findall(t)}
    states, inv = [{}], {}
    for _ in range(8):
        inv, _ = press_alt(actors, a, ammo, inv)
        mode = {k: v for k, v in inv.items() if k in checked}
        if mode in states:
            break
        states.append(mode)
    return states


def gun_rows(actors, a, ammo):
    """[(alt, mode item, mode count, tics)], and a note if the primary fire cannot be measured."""
    altfire = reachable(actors, a, 'AltFire')
    every = {m.lower() for t in reachable(actors, a, 'Fire') + altfire + reachable(actors, a, 'Ready') for m in CHECK.findall(t)}
    rows = []
    if SYNTH[1] in every and 'flash' in {k for x in d.ancestors(actors, a.name) if x in actors for k in actors[x].labels}:
        # Dual guns: the left hand on Fire (the main layer), the right hand on AltFire (the Flash layer).
        t, note = measure(actors, a, ammo, 'Fire')
        if t:
            rows.append((0, '', 0, t))
        t2, _ = measure(actors, a, ammo, 'Flash')
        if t2:
            rows.append((1, '', 0, t2))
        return rows, (None if t else note)
    modes = fire_modes(actors, a, ammo)
    items = sorted({k for m in modes for k in m})
    measured = []
    for m in modes:
        t, note = measure(actors, a, ammo, 'Fire', m)
        if not t and not m:
            return [], note
        if t:
            measured.append((m, t))
    if len({t for _, t in measured}) == 1:
        rows.append((0, '', 0, measured[0][1]))  # every mode fires at the same rate
    elif len(items) > 1:
        return [], 'modes fire at different rates and AltFire changes more than one counter: ' + ', '.join(items)
    else:
        rows.extend((0, a_name(actors, items[0]), m.get(items[0], 0), t) for m, t in measured)
    _, alt_shoots = press_alt(actors, a, ammo, {})
    if alt_shoots:
        t, _ = measure(actors, a, ammo, 'AltFire')
        if t:
            rows.append((1, '', 0, t))
    return rows, None


def derive(drla):
    actors = d.load_actors(drla)
    own = owner_automatics()
    rows, missing = [], []
    for key, a in sorted(actors.items()):
        anc = d.ancestors(actors, a.name)
        if ('weapon' not in anc and 'rlweapon' not in anc) or 'fire' not in a.labels:
            continue
        if 'rapidfire' not in d.tokens(a) and key not in own:
            continue
        ammo = {x.lower() for x in (d.prop(actors, a, k) for k in ('weapon.ammotype', 'weapon.ammotype1', 'weapon.ammotype2')) if x}
        r, note = gun_rows(actors, a, ammo)
        if note:
            missing.append((a.name, note))
        rows.extend((a.name,) + x for x in r)
    return rows, missing


def render(rows):
    def col(decl, fmt, idx, end):
        body = ''.join('\t\t\t' + (fmt % r[idx]) + ',\n' for r in rows)
        return '\t\tstatic const ' + decl + '[] = {\n' + body + '\t\t\t' + end + '\n\t\t};\n'
    return ('\t\t// GENERATED by tools/automatics/derive_bands.py --write. Do not edit by hand.\n'
            + col('String names', '"%s"', 0, '""') + col('int alts', '%d', 1, '0')
            + col('String modes', '"%s"', 2, '""') + col('int counts', '%d', 3, '0')
            + col('int tics', '%d', 4, '0') + '\t\t// END GENERATED\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--drla', default=d.DEFAULT_DRLA)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--write', action='store_true')
    g.add_argument('--check', action='store_true')
    args = ap.parse_args()
    rows, missing = derive(args.drla)
    for n, note in missing:
        print('NO BAND:', n, '-', note)
    block = render(rows)
    with open(TABLE_FILE, encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'\t*// GENERATED by .*?// END GENERATED\n', text, re.S)
    if not m:
        sys.exit('no GENERATED block in ' + TABLE_FILE)
    if (args.write or args.check) and missing:
        sys.exit('FAIL: %d Automatics candidates have no band' % len(missing))
    if args.write:
        with open(TABLE_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text[:m.start()] + block + text[m.end():])
        print('wrote %d rows' % len(rows))
    elif args.check:
        if m.group(0) != block:
            sys.exit('DoomerfallAutomaticBands.zs is stale: run derive_bands.py --write')
        print('ok: %d rows' % len(rows))
    else:
        for r in rows:
            print('%-34s %s %-32s %d  %d' % (r[0], 'alt' if r[1] else 'pri', r[2] or '-', r[3], r[4]))


if __name__ == '__main__':
    main()
