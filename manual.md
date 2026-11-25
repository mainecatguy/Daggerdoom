# Doomerfall player manual

What a player needs to know to play the game **as it is on `main`** (last updated for `main` at `098f262`,
2026-11-23). Only what is merged to `main` goes here: no undecided design and nothing that is only on `integration`.
Update it when the owner merges to `main` (see AGENTS.md).

## Starting the game

Run `play.bat` in the play folder. It starts Daggerfall Unity and UZDoom together; you play in Doom's window.
Choose New Game in Doom's menu. Daggerfall's own character creation and cinematics run, then a temporary difficulty
prompt and a fixed Doom class, and you start in Privateer's Hold.

## Controls

| Key | Does |
|---|---|
| Doom's movement, aim, fire, jump | As in Doom |
| E | Interact: open doors, take items, open loot piles and containers |
| I | Daggerfall's inventory |
| K | Daggerfall's fast travel map |

Rebind them in Options, Customize Controls, Doomerfall Controls.

## The world

- The world, towns, dungeons, buildings and NPCs are Daggerfall's, drawn and played in Doom.
- Walking through a door, a dungeon entrance or a town gate takes you to the next place in both games.
- Fast travel (K) uses Daggerfall's travel map: it charges gold, passes time, and moves you there.
- NPCs stand in place with their Daggerfall sprites.

## Items and loot

- Health and ammo pick up by touch. Everything else, including Doom weapons and armor and Daggerfall loot piles, is
  taken with Interact.
- Loot piles and containers open Daggerfall's loot window. House containers ask before you take private property.
  Shop shelves open the Buy window.
- What you take goes to Daggerfall's inventory.

## Combat and death

- Combat is Doom's: Doom monsters, Doom weapons, Doom movement.
- Daggerfall owns your HP. When you die, Daggerfall's death rules apply.
- Killed monsters stay dead when you leave and come back.

## Skills

No Daggerfall skill changes Doom combat or movement yet.

## Saving

Saving and loading save both games together as one save.
