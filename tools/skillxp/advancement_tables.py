"""Daggerfall skill advancement tables and their Doom Skill XP translation (work/notes/20261126-010200.md).

usage: python tools/skillxp/advancement_tables.py
uses() copies FormulaHelper.CalculateSkillUsesForAdvancement. Class multipliers are read from CLASS*.CFG (offset 54).
"""
import math
HITS = 6.5          # owner anchor: uses from one Daggerfall fight
KILLS = 30          # Doom kills per Daggerfall fight
K = 250             # proposed Skill XP (HP) per use-equivalent

def uses(s, L, c, m=2):
    return math.floor(s * m * c * (1.04 ** L) * 2 / 5) + 1  # FormulaHelper.CalculateSkillUsesForAdvancement

def span(a, b, c, L0, L1=None, m=2):
    t = 0
    for s in range(a, b):
        L = L0 if L1 is None else round(L0 + (L1 - L0) * (s - a) / (b - a))
        t += uses(s, L, c, m)
    return t

classes = [('Barbarian', 0.64), ('Warrior', 0.75), ('Healer/avg', 1.00), ('Mage', 1.04)]
print('## Uses to raise a weapon skill (multiplier 2), fixed character level')
for name, c in classes:
    for L in (1, 10, 20, 30):
        r = [span(a, a + 25, c, L) for a in (25, 50, 75)]
        print('%-11s c=%.2f L%-2d 25-50 %5d  50-75 %5d  75-100 %5d' % (name, c, L, *r))
print()
print('## Balanced path: level 1->10 during 25-50, 10->20 during 50-75, 20->30 during 75-100')
for name, c in classes:
    r = [span(25, 50, c, 1, 10), span(50, 75, c, 10, 20), span(75, 100, c, 20, 30)]
    f = [x / HITS for x in r]
    k = [x / HITS * KILLS for x in r]
    print('%-11s uses %5d %5d %5d | DF fights %4.0f %4.0f %4.0f | Doom kills %6.0f %6.0f %6.0f | Skill XP %8d %8d %8d' %
          (name, *r, *f, *k, *[x * K for x in r]))
print()
print('## Focused path: only melee rises (level 1->3, 3->5, 5->6)')
for name, c in classes:
    r = [span(25, 50, c, 1, 3), span(50, 75, c, 3, 5), span(75, 100, c, 5, 6)]
    print('%-11s uses %5d %5d %5d | DF fights %4.0f %4.0f %4.0f | Doom kills %6.0f %6.0f %6.0f' %
          (name, *r, *[x / HITS for x in r], *[x / HITS * KILLS for x in r]))
print()
print('## Per-point cost in Skill XP (K=%d), Warrior c=0.75' % K)
for L in (1, 10, 20, 30):
    print('L%-2d' % L, ' '.join('%d:%d' % (s, uses(s, L, 0.75) * K) for s in (5, 25, 50, 75, 95, 99)))
print()
print('## 6-hour gate: max one point per skill per 6 game hours (PlayerEntity.RaiseSkills, 360 classic minutes)')
print('25 points take at least 150 game hours = 6.25 game days of use-based gain.')
