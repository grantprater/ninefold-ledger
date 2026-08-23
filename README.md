# The Ninefold Ledger — MVP

A xianxia deconstruction. Realms 1 through 3, built against [the design doc](DESIGN.html)
([published version](https://claude.ai/code/artifact/2627c50a-934e-4c69-82ad-b0a45e65c916)).

```
py main.py              play
py main.py --seed 7     fixed seed
py tests\test_affinity.py       the synergy math
py tests\test_systems.py        every system, headless
py tests\test_playthrough.py    scripted integration run
py tests\test_review.py         review balance across strategies
py tests\test_review_live.py    both review endings, real Game object
py tests\test_endings.py        endings, codas, and the idle counter
py tests\test_trials.py         realm 3, formations, the prize
py tests\test_arc.py            the whole arc, realm 1 to the trials
```

Python 3.14, no dependencies. Note that `python` on this machine hits the
Microsoft Store stub — use `py`.

## Layout

```
data/       all content. Adding a monster family, form, region, realm or
            treasure is a JSON edit, not a code change.
engine/     rules only, no printing except in ui.py and world.py
tests/      three suites, all runnable directly
```

| File | What it owns |
|---|---|
| `engine/affinity.py` | the relation matrix, synergy, wuxing combat multipliers |
| `engine/treasures.py` | treasures, growth, will, overcap resolution |
| `engine/entities.py` | player, combatant shape, injuries, foundation |
| `engine/monsters.py` | `Family × Affinity × Rank × Region`, harvesting |
| `engine/crafting.py` | composition crafting, procedural artisans |
| `engine/combat.py` | the tick scheduler and range bands |
| `engine/companions.py` | relationship, resentment, departure |
| `engine/world.py` | the day loop and every screen |

## What's implemented

- **Affinity synergy** — five wuxing elements, generation and destruction
  cycles, Void as the zero vector.
- **Realms 1→2** — realm 1 has affinity *latent*, so treasures read flat.
  Breaking through turns resonance on and your gear suddenly means something.
- **Overcap** — full power, collapsing control, three outcome bands, and the
  cost ladder: stability, then injuries, then foundation.
- **Foundation** — displayed from day one, moves no stat, quietly biases
  breakthrough odds. It is meant to matter at realm 5, which does not exist yet.
- **Tick combat** — the realm gap is action frequency. A realm-2 monster acts
  three times per action of a realm-1 player.
- **Companions as action economy** — Shen Yaru is initiative, and neglect
  makes her fight at 28% before she leaves entirely.
- **Composition crafting** — no recipes. Materials compose into the affinity
  vector; the artisan shapes variance, not the mean.
- **Harvesting** — anatomy is the loot table, kill method decides what
  survives, and the choice is offered at the kill: strip the core (free),
  take it apart properly (costs an action), or leave it.
- **Places** — the Outer Court is a settlement with benches and nothing to
  hunt; the three wilderness regions are the reverse. Travel costs actions by
  distance, so returning to craft is a real decision.
- **Provenance** — how you took the Widow's Needle changes whether it
  cooperates when you are desperate.
- **The cohort review** — announced on your breakthrough into realm 2, thirty
  days out. Realm 1 has no clock on it deliberately; that is where you learn
  the systems. See below.

## The rising action

Gu Wenshan is not a scripted wall. He runs the player's own progression maths
on the same clock at 3.0 cultivations a day — you get three actions for
*everything*, he spends three on this. The number is the characterisation.

The review puts one deadline over three things at once: your standing, his, and
whether Shen Yaru keeps her place. Measured over 12 seeded runs per strategy:

| Daily split | Your place | Your tier | She keeps her place |
|---|---|---|---|
| All cultivation | 1st | 9 | **0%** |
| 2 cultivate / 1 with her | 2nd | 8 | 100% |
| 1 cultivate / 1 with her | 2nd | 5 | 100% |

Going all-in delivers exactly what the genre promises — first place, reliably,
beating the rival 12 out of 12. What it costs is never on the board. Saving her
means handing Gu Wenshan the top slot, and he takes it the way you would accept
a delivery.

Her assessment is scored on the same board as everyone else, so she is cut by
the same rule — no private threshold. The background cohort is tuned (in
`data/events.json`) so that investment reliably clears the cut and neglect
reliably does not; her fate should read as consequence, not a dice roll.

## Endings

The review terminates the run. Four endings — `cut`, `kept`, `promoted`,
`died` — each a base passage plus **codas** selected from what the run actually
cost: whether Shen Yaru is still there, whether your foundation is marked, and
one more (below).

The `cut` ending is the important one. Nobody wronged you, there is no rival
gloating, and the board was accurate. You reached the second realm, which is
genuinely impressive in a market town and insufficient here, and the realms
keep going upward without you. The genre never looks at this outcome and it is
the median one.

## Realm 3 and the Inner Trials

The review is now a **gate, not an ending**. Promotion moves you to the inner
court and the run continues; being cut or kept ends it.

Realm 3 unlocks **formations** — the one verb in the game that attacks the tick
economy rather than hit points, which is the only thing that has ever answered
a realm gap. A binding mesh nearly doubles what every enemy action costs them.

Measured over 40 seeded bouts, tier 7 against a tier 5 who counters your
element:

```
striking only       0/40 wins
mesh then strike   26/40 wins
```

Irrelevant when you already counter them, decisive when you don't, and unable
to save a badly outclassed player. That is what a new verb should look like.

The **Inner Trials** are three rounds, 45 days out, ending with Gu Wenshan at
whatever realm and tier the clock actually gave him — he is never scaled to
you. You are patched up between rounds but your *stability* is not, so anything
you reached for in round one is still costing you in round three.

**The prize is the point.** First Frost is rank five, presented on a stand, in
front of everybody, for being excellent. You are at the third realm. A matched
build can swing it at about even odds and will; 300 swings takes a pristine
foundation to Ruined. Act one ends when you accept it, and nothing says so.

## The idle counter

`Waste an afternoon` costs an action, yields nothing mechanical, and is
counted in `player.idle_days`.

That counter is **never displayed, never rewarded, and never hinted at.** It
exists only to select between two ending codas: one for a run where every
single day went somewhere, and one for a run where some of it didn't. An
optimising player will never spend an action on it, and the ending will have
noticed that too.

This is the action economy pointed at the player rather than at their build.
Vignettes are per-region in `data/vignettes.json` and don't repeat until the
local pool is exhausted.

## Two corrections found while building

**Synergy uses L1, not cosine.** Cosine lets `match` exceed 1.0 because `R` has
positive off-diagonal entries — a fire/wood split build scored *higher* with a
fire blade than pure fire did, deleting the dilution tradeoff. L1 weighting
makes every dilution cost something, and diluting toward a generating element
costs about 4x less than toward a destroying one.

**Void's edge is its floor, not its average.** With only five wuxing elements
there are no unrelated pairs, so the `0.2` floor never fires and a specialist
averages `0.64` on random loot — beating Void's flat `0.6`. Void's real
advantage is that it never holds a dead item (specialists hold 2 in 5) and
never suffers backlash, which is what matters for uniques you cannot choose
and for overcap reach.

**The combat matrix was too decisive.** `1.6x / 0.55x` is a 2.9x swing, which
is fine against monsters you chose to hunt and wrong for a duel you were drawn
into — at that spread a hard-countered bout is over before it starts and no
tactic moves it. Now `1.45 / 0.7`, a 2.07x swing: still the biggest lever on
the board, no longer the whole story.

## Tuning knobs

- `data/realms.json` — `speed` is what produces the 3x action-frequency gap.
- `data/affinities.json` — `synergy_curve` and `void.flat_synergy`.
- `engine/treasures.py` — `POWER_PER_GAP`, `CONTROL_PER_GAP`, `HARD_CAP_GAP`.
- Realm 1 currently caps in about 13 cultivations, which is fast. Raise
  `qi_to_advance_tier` in `realms.json` for a longer first realm.
