# Weapon material damage bonus

**Waiting on:** owner approval to move to todo, and *Doom weapons have a Daggerfall material*.

Owner rule (2026-11-24): a Doom weapon's material gives a damage modifier taken from Daggerfall's own material system,
not from the ammo material rules. Daggerfall's hit chance bonus becomes a percent damage modifier. It multiplies with
the ammo modifier and any other bonus.

Daggerfall's hit chance bonus is the material modifier times 10 (`FormulaHelper.CalculateWeaponToHit`, `:1146`;
`DaggerfallUnityItem.GetWeaponMaterialModifier`, `:1001`). As damage modifiers:

| Iron | Steel | Silver | Elven | Dwarven | Mithril | Adamantium | Ebony | Orcish | Daedric |
|---|---|---|---|---|---|---|---|---|---|
| -10% | 0% | 0% | +10% | +20% | +30% | +30% | +40% | +50% | +60% |

## How it reaches Doom (the existing path)

This needs no new damage tracking. Daggerfall already publishes one total damage multiplier every frame
(`DoomerfallDamageBonus.cs`, `dfb_df_state.damage_bonus_bp`), and Doom applies it in `P_DamageMobj` to all damage
whose source is the player (`DD_BridgeDamageBonus`, `dd_bridge.cpp:994`). In Doom the player is the source of hitscan
hits, projectiles, rocket and grenade splash, and anything those spawn with the player as their owner. A barrel the
player sets off also counts the player as its source. The only element today is the loaded ammo's material.

So this item adds one element: the equipped weapon's material, `1 + 0.10 x material modifier`, multiplied with the
ammo element. The bonus follows the gun Daggerfall has equipped. Skill bonuses later use the same path.

## Known gap, accepted for now

A projectile already in flight when the player switches guns uses the new gun's bonus. If play-testing shows that
matters, stamp the bonus on the projectile when it is fired and prefer the stamp. The owner made that a future item
(`work/future-ideas.md`, 2026-11-24).
