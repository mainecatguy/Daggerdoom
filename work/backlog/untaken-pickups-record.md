# Untaken pickups should not be stored in the place record (low priority)

Waiting on: the owner; low priority because the size is small (owner, 2026-11-27, sheet item 57: "Untaken pickups should
be deterministic and procedural, they shouldn't need a record right, backlog as low priority due to small size of it").
Today untaken ammo pickups grow the place record (49 rows / 4,288 bytes instead of 21 / 2,240 in Privateer's Hold).
Store only taken ones (see `takenpickups` 01).
