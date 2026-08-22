"""Balance probe for the cohort review.

Plays out the 30 days under different action splits and reports where each
strategy lands, and what happens to Shen Yaru. The question this has to answer
is whether the deadline is a real squeeze rather than either a formality or an
impossibility -- and whether saving her costs you something real.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.companions import Companion    # noqa: E402
from engine.data import DATA               # noqa: E402
from engine.entities import Player         # noqa: E402
from engine.rivals import CohortReview, Rival, score_of  # noqa: E402

failures = []


def check(label, cond, detail=""):
    print(f"  {'pass' if cond else 'FAIL'}  {label}" + (f"   {detail}" if detail else ""))
    if not cond:
        failures.append(label)


def simulate(cultivate_share, social_share, seed=0):
    """Run the review window with a fixed daily action split."""
    rng = random.Random(seed)
    p = Player("Sim", {"fire": 1.0})
    p.realm, p.tier, p.qi = 2, 1, 0.0
    yaru = Companion("shen_yaru")
    rival = Rival()
    review = CohortReview(p.day, rng)

    days = DATA.events["cohort_review"]["days"]
    per_day = p.actions_per_day
    for _ in range(days):
        socialised = False
        for slot in range(per_day):
            r = (slot + 1) / per_day
            if r <= cultivate_share:
                p.cultivate(p.cultivation_yield() + rng.uniform(-2, 4), [])
            elif r <= cultivate_share + social_share:
                yaru.socialize([], rng)
                socialised = True
            # remaining slots are hunting/crafting/resting -- no qi, no bond
        p.day += 1
        if not socialised:
            yaru.idle_day([])
        rival.advance_day(rng)

    out = review.resolve(p, rival, [yaru] if yaru.present else [])
    return p, yaru, rival, out


def main():
    print("realm 2 cultivation is no longer a wall")
    p = Player("x", {"fire": 1.0})
    p.realm = 2
    for tier, want in ((1, 8.0), (9, 22.0)):
        p.tier = tier
        actions = p.qi_to_advance() / p.cultivation_yield()
        check(f"realm 2 tier {tier} pacing", actions <= want,
              f"{actions:.1f} actions per tier (want <= {want})")

    p.tier = 1
    total = sum(DATA.realms[2]["qi_to_advance_tier"]
                * DATA.realms[2]["qi_growth_per_tier"] ** (t - 1)
                for t in range(1, 9))
    avg = p.cultivation_yield() + 4.5 * 56 * 0.2
    days_to_max = total / avg / p.actions_per_day
    check("maxing realm 2 takes most of the review window",
          20 <= days_to_max <= 32, f"{days_to_max:.0f} days at 3 actions/day")

    print("\nstrategies over the 30-day window")
    rows = []
    for label, cult, soc in (
        ("all cultivation", 1.0, 0.0),
        ("2 cult / 1 social", 0.67, 0.33),
        ("1 cult / 1 social", 0.34, 0.33),
        ("no cultivation", 0.0, 0.34),
    ):
        places, tiers, saved = [], [], 0
        for seed in range(12):
            p, yaru, rival, out = simulate(cult, soc, seed)
            places.append(out["player"]["place"])
            tiers.append(p.tier)
            if out["companions"] and out["companions"][0][2]:
                saved += 1
        rows.append((label, sum(places) / len(places), sum(tiers) / len(tiers),
                     saved / 12))
        print(f"  {label:20s} avg place {rows[-1][1]:4.1f}   "
              f"avg tier {rows[-1][2]:4.1f}   she keeps her place "
              f"{rows[-1][3]:.0%} of runs")

    by_label = {r[0]: r for r in rows}
    check("pure cultivation places better than splitting",
          by_label["all cultivation"][1] < by_label["1 cult / 1 social"][1],
          f"{by_label['all cultivation'][1]:.1f} vs "
          f"{by_label['1 cult / 1 social'][1]:.1f}")
    check("pure cultivation loses her",
          by_label["all cultivation"][3] < 0.5,
          f"saved {by_label['all cultivation'][3]:.0%} of runs")
    check("splitting saves her",
          by_label["2 cult / 1 social"][3] > 0.9,
          f"saved {by_label['2 cult / 1 social'][3]:.0%} of runs")
    # The thesis, as balance: going all-in delivers exactly what the genre
    # promises -- first place, reliably. What it takes is never on the board.
    check("saving her costs real standing",
          by_label["2 cult / 1 social"][1] > by_label["all cultivation"][1],
          f"place {by_label['all cultivation'][1]:.1f} -> "
          f"{by_label['2 cult / 1 social'][1]:.1f}")

    print("\nthe rival is beatable but not free")
    beat = 0
    for seed in range(12):
        p, yaru, rival, out = simulate(1.0, 0.0, seed)
        if out["player"]["place"] < out["rival"]["place"]:
            beat += 1
    check("all-in beats the rival most of the time", beat >= 7, f"{beat}/12")
    beat_split = 0
    for seed in range(12):
        p, yaru, rival, out = simulate(0.67, 0.33, seed)
        if out["player"]["place"] < out["rival"]["place"]:
            beat_split += 1
    check("splitting usually does not", beat_split <= 5, f"{beat_split}/12")

    print("\nthe rival breaks through on his own")
    rng = random.Random(1)
    r = Rival()
    notes = [n for _ in range(30) if (n := r.advance_day(rng))]
    check("he reaches Qi Awakened inside the window", r.realm == 2,
          f"realm {r.realm} tier {r.tier}, {len(notes)} announcement(s)")

    print("\nreminders fire once each, in order")
    rv = CohortReview(1, random.Random(0))
    fired = [ln for d in range(1, 32) if (ln := rv.tick(d))]
    check("four reminders, no repeats", len(fired) == 4, f"{len(fired)} fired")

    print()
    failed = [f for f in failures if f]
    if failed:
        print(f"{len(failed)} FAILURE(S): {failed}")
        return 1
    print("review balance holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
