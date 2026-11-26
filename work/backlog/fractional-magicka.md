# Fractional magicka

**Waiting on:** owner approval to move to todo. Owner chose the fraction carry for now (2026-11-25). Needed before damage spells or other new effects with per-target or per-tick costs (owner, 2026-11-25): with slaughter-sized packs, a cost per monster can be well under one point.

Owner asked for floating-point magicka if it is not too complicated; otherwise revisit.

Findings (2026-11-25): Daggerfall Unity stores magicka as `int` (`DaggerfallEntity.currentMagicka`), with about 54 uses across 23 files, plus save data and UI. Two routes:

1. **Float magicka:** change the entity field and every use, saves, and UI. Wide vendored change.
2. **Fraction carry (recommended to evaluate first):** keep Daggerfall's int. The Doomerfall side accumulates fractional costs and deducts a whole point from Daggerfall each time the total passes 1; the leftover fraction is saved with Doomerfall's own state. Same gameplay, small change. Shown magicka may lag by under one point.
