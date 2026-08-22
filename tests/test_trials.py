"""Realm 3, formations, and the Inner Trials.

The questions here: is the trials window a tighter squeeze than the review was
(escalation), can formations actually answer a realm gap, and does the prize
land as a temptation rather than an upgrade.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import ui                              # noqa: E402
from engine.combat import COST_STRIKE, Combat      # noqa: E402
from engine.data import DATA                       # noqa: E402
from engine.duelists import Duelist                # noqa: E402
from engine.entities import Player                 # noqa: E402
from engine.rivals import Rival                    # noqa: E402
from engine.tournament import InnerTrials          # noqa: E402
from engine.treasures import Treasure              # noqa: E402

failures = []


def check(label, cond, detail=""):
    print(f"  {'pass' if cond else 'FAIL'}  {label}" + (f"   {detail}" if detail else ""))
    if not cond:
        failures.append(label)


def days_to_max(realm):
    r = DATA.realms[realm]
    cost = sum(r["qi_to_advance_tier"] * r["qi_growth_per_tier"] ** (t - 1)
               for t in range(1, 9))
    y = r["cultivation_yield"]
    return cost / (y + 4.5 * y * 0.2) / 3


def main():
    print("the squeeze tightens, realm to realm")
    r2 = days_to_max(2) / DATA.events["cohort_review"]["days"]
    r3 = days_to_max(3) / DATA.events["inner_trials"]["days"]
    print(f"    realm 2: {days_to_max(2):.0f} days to max in a "
          f"{DATA.events['cohort_review']['days']}-day window ({r2:.0%} of it)")
    print(f"    realm 3: {days_to_max(3):.0f} days to max in a "
          f"{DATA.events['inner_trials']['days']}-day window ({r3:.0%} of it)")
    check("realm 3 leaves proportionally less slack", r3 > r2,
          f"{r2:.0%} -> {r3:.0%}")

    print("\nrealm 3 keeps the 3x action-frequency gap")
    p = Player("T", {"fire": 1.0})
    p.realm = 3
    pc = p.to_combatant()
    r2c = Duelist("x", 2, 5, {"metal": 1.0}, rng=random.Random(1)).to_combatant()
    ratio = r2c.delay(COST_STRIKE) / pc.delay(COST_STRIKE)
    check("a realm 3 player acts ~3x per realm 2 opponent", 2.4 <= ratio <= 3.6,
          f"ratio {ratio:.2f}")

    print("\nformations are locked until realm 3")
    for realm, want in ((2, False), (3, True)):
        check(f"realm {realm} world energy = {want}",
              DATA.unlocked(realm, "world_energy") == want)

    print("\na binding mesh answers a realm gap")
    rng = random.Random(4)
    p2 = Player("T", {"fire": 1.0})
    p2.set_realm(3, 4)
    p2.qi = p2.qi_max()
    over = Duelist("Above", 4, 5, {"metal": 1.0}, rng=rng) \
        if 4 in DATA.realms else Duelist("Above", 3, 9, {"metal": 1.0}, rng=rng)

    def enemy_turns_in(combat, span=4000):
        sim = [(a, a.next_at) for a in combat.actors if a.alive]
        n = 0
        clock = 0.0
        while clock < span:
            a, t = min(sim, key=lambda x: x[1])
            clock = t
            if a.side == "enemy":
                n += 1
            cost = COST_STRIKE * (1.0 + combat.field_value("slow")
                                  if a.side == "enemy" else COST_STRIKE / COST_STRIKE)
            cost = COST_STRIKE * (1.0 + combat.field_value("slow")) \
                if a.side == "enemy" else COST_STRIKE
            sim = [(x, t + x.delay(cost) if x is a else y) for x, y in sim]
        return n

    c_plain = Combat(p2, [over], [], random.Random(4))
    before = enemy_turns_in(c_plain)
    c_mesh = Combat(p2, [over], [], random.Random(4))
    p2.qi = p2.qi_max()
    c_mesh.player_formation("binding_mesh")
    after = enemy_turns_in(c_mesh)
    check("the mesh removes enemy actions", after < before,
          f"{before} -> {after} enemy turns over the same span")

    print("\nthe drawing array returns qi as you act")
    p3 = Player("T", {"fire": 1.0})
    p3.set_realm(3, 3)
    p3.qi = p3.qi_max()
    c = Combat(p3, [Duelist("x", 3, 3, {"wood": 1.0}, rng=rng)], [], rng)
    c.player_formation("drawing_array")
    low = p3.qi = 40.0
    c.player_steady()
    check("qi came back from the room", p3.qi > low, f"{low:.0f} -> {p3.qi:.0f}")

    print("\nthe sundering line strips ward")
    p4 = Player("T", {"fire": 1.0})
    p4.set_realm(3, 3)
    p4.qi = p4.qi_max()
    d = Duelist("Warded", 3, 3, {"wood": 1.0}, rng=rng)
    c2 = Combat(p4, [d], [], rng)
    c2.enemies[0].ward = 60.0
    plain, _ = c2._damage(c2.pc, c2.enemies[0], 100.0)
    c2.player_formation("sundering_line")
    broken, _ = c2._damage(c2.pc, c2.enemies[0], 100.0)
    check("ward break increases damage through", broken > plain,
          f"{plain:.0f} -> {broken:.0f}")

    print("\nthe bracket escalates and ends with him")
    t = InnerTrials(1, random.Random(2))
    rival = Rival()
    rival.realm, rival.tier = 3, 5      # Rival has no hp pools to refresh
    bracket = t.bracket(rival)
    check("three rounds", len(bracket) == DATA.events["inner_trials"]["rounds"],
          f"{len(bracket)}")
    check("the final is the rival", bracket[-1].name == rival.name,
          " -> ".join(d.display() for d in bracket))
    early = bracket[:-1]
    check("earlier rounds are ordered by strength",
          all(early[i].tier <= early[i + 1].tier for i in range(len(early) - 1)))

    print("\nthe rival is not scaled to the player")
    r_low, r_high = Rival(), Rival()
    r_low.realm, r_low.tier = 2, 4
    r_high.realm, r_high.tier = 3, 8
    a = Duelist.from_rival(r_low, random.Random(1))
    b = Duelist.from_rival(r_high, random.Random(1))
    check("he arrives at whatever the clock gave him", b.power > a.power,
          f"{a.display()} vs {b.display()}")

    print("\nthe prize is a temptation, not an upgrade")
    # It is water/metal. What it is worth depends entirely on your build, which
    # is the affinity system doing its job -- so the trap is not "nobody can
    # swing it". The trap is that the builds who CAN swing it will, and will
    # arrive at the realm 5 tribulation having paid for every swing.
    prize = Treasure.from_data("first_frost", provenance="won")
    prize.judge_provenance()

    matched = Player("Water", {"water": 1.0})
    mismatched = Player("Fire", {"fire": 1.0})
    for pl in (matched, mismatched):
        pl.set_realm(3, 9)
        pl.stability = pl.stability_max()

    rd = prize.reading(matched)
    check("it is two realms above a realm 3 winner", rd["gap"] == 2, f"gap +{rd['gap']}")
    check("its raw power is enormous", rd["raw_power"] > 5000, f"{rd['raw_power']:.0f}")

    cm = prize.control(matched)
    cx = prize.control(mismatched)
    print(f"    water build  control {cm:.0%}")
    print(f"    fire build   control {cx:.0%}")
    # A mismatched build gets almost nothing from affinity -- what control it
    # has comes from the blade being well disposed toward whoever won it
    # fairly. The will compensating for a bad match is the system working.
    check("a mismatched build holds it far worse", cx < cm * 0.6 and cx < 0.3,
          f"{cx:.0%} vs {cm:.0%} -- {cx / cm:.0%} of a matched build")
    check("a matched build can, at odds", 0.3 < cm < 0.65, f"{cm:.0%}")

    outcomes = {"success": 0, "wild": 0, "backlash": 0}
    for i in range(300):
        matched.stability = matched.stability_max()
        matched.hp = matched.hp_max()
        o, _d, _l = prize.activate(matched, random.Random(i))
        outcomes[o] += 1
    check("even matched, half of it goes wrong",
          outcomes["success"] < 200, str(outcomes))
    check("and every swing is charged to the foundation",
          matched.foundation < 40.0,
          f"{matched.foundation:.0f} ({matched.foundation_label()}) after 300 swings")

    print("\nstability, not luck, is what stops you spamming it")
    fresh = Player("Water", {"water": 1.0})
    fresh.set_realm(3, 9)
    fresh.stability = fresh.stability_max()
    first = prize.control(fresh)
    uses = 0
    while prize.control(fresh) > first * 0.5 and uses < 40:
        prize.activate(fresh, random.Random(uses))
        uses += 1
    check("control halves within a handful of swings", uses <= 12,
          f"{uses} swings to halve control ({first:.0%} -> "
          f"{prize.control(fresh):.0%})")

    print("\nnew regions gate on realm and have vignettes")
    for rid in ("inner_court", "ash_shelf"):
        reg = DATA.regions[rid]
        check(f"{rid} requires realm 3", reg.get("requires_realm") == 3)
        check(f"{rid} has vignettes", rid in DATA.vignettes)

    print("\nboth trial endings exist")
    for kind in ("trials_won", "trials_lost"):
        check(f"'{kind}' defined", bool(DATA.endings.get(kind, {}).get("body")),
              DATA.endings.get(kind, {}).get("title", "missing"))
    for coda in ("took_the_prize", "left_the_prize"):
        check(f"coda '{coda}' defined", coda in DATA.endings["codas"])

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S): {failures}")
        return 1
    print("realm 3 and the trials check out")
    return 0


if __name__ == "__main__":
    sys.exit(main())
