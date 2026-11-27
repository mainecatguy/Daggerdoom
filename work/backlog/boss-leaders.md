# Strong boss leaders, and titans below area level 20 as rare surprises

Waiting on: the owner moving it to todo (owner, 2026-11-26: "Boss card let's put it in the backlog"). The card is ready below.


Lane: `bossleader` (new). Model: Opus. Depends on the finished `encounters` lane.

In the encounter planner test, a level 30 Human Stronghold's strong boss was a Brown Cacodemon leading 247 escorts
(202 Elite Human Handcannons, 40 zombies, 5 cacodemons): the leader is limited to the army's kinds and 3/4 of the boss
points, so in a cheap army the leftover buys a huge escort. First measure how typical this is across many plans
(leader strength against the boss budget, escort sizes). Then review the original design and change the boss and titan
rules to something faithful to it.

Owner's words (2026-11-26): "it does sound like something went wrong here. I would say a new rule is that the boss gets
to violate more of the monster selection rules if it's necessary for the boss to get a lot of points. Usually bosses
should be strong but surprising exceptions are permitted if they're rare. We want this system to be high in bayesian
surprise. We want to make sure the agent doing this reviews the original design and comes up with something faithful
to it. ... if this was an extreme one time fluke that's very funny and could be left in the game, we want the system
to generate surprises, however if this is a typical result I would want to change it."
And: "let's allow the rule against generating titans below area level 20 to be broken, it's not absolute, as long as
it's a surprise and a rarity, I do want you to tell me if this results in titans appearing all the time and too much,
we really want to have a huge amount of variety in the systems and generally I want to maximize variety and surprise
again"

Done when: the notes report how often a weak leader with a huge escort happened before and after; bosses are usually
strong, with rare surprising exceptions; titans can appear below area level 20 as a rare surprise (which also allows
the "lone titan" surprise room); the notes give titan frequency by area level so the owner can judge "too much".
Context: design `work/notes/20261123-205402-fractal-encounter-variety.md` (sections 1, 6.3, 6.4, 7.1, 8.3); planner
results `work/notes/20261124-102050.md`; decision `gamedesign/decisions/20261126-boss-leaders-and-titans-owner.md`.
