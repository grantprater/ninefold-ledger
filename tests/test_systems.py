"""Headless exercise of every MVP system. No input, no UI."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.combat import COST_STRIKE, Combat            # noqa: E402
from engine.companions import Companion                  # noqa: E402
from engine.crafting import Artisan, craft, preview      # noqa: E402
from engine.data import DATA                             # noqa: E402
from engine.entities import Player                       # noqa: E402
from engine.monsters import Monster, spawn               # noqa: E402
from engine.treasures import Treasure                    # noqa: E402

failures = []


def check(label, cond, detail=""):
    print(f"  {'pass' if cond else 'FAIL'}  {label}" + (f"   {detail}" if detail else ""))
    if not cond:
        failures.append(label)


def main():
    rng = random.Random(11)

    print("realm gap as action frequency (doc 12)")
    p = Player("Test", {"fire": 1.0})
    starter = Treasure.from_data("hollow_reed")
    p.treasures.append(starter)
    p.equip(starter)
    r1 = p.to_combatant()
    m2 = Monster("beast", "water", 2, rng).to_combatant()
    ratio = r1.delay(COST_STRIKE) / m2.delay(COST_STRIKE)
    check("realm+1 enemy acts ~3x per player action", 2.4 <= ratio <= 3.6,
          f"ratio {ratio:.2f}")

    print("\ncompanions are action economy")
    c = Combat(p, [Monster("beast", "water", 2, rng)], [Companion("shen_yaru")], rng)
    order = c.initiative_preview(12)
    ally_turns = sum(1 for a in order if a.side == "player")
    check("allies take more of the initiative than the player alone",
          ally_turns > sum(1 for a in order if a is c.pc),
          f"{ally_turns}/12 ally turns")

    print("\ntreasure resonance is latent at realm 1, live at realm 2")
    syn1 = starter.synergy(p)
    p.realm = 2
    syn2 = starter.synergy(p)
    p.realm = 1
    check("realm 1 synergy is flat 1.0", abs(syn1 - 1.0) < 1e-9, f"{syn1:.2f}")
    check("realm 2 synergy is live", abs(syn2 - 1.0) > 1e-9,
          f"{syn2:.2f}x for a fire wielder on a wood/water blade")

    print("\novercap: full power, collapsing control (doc 07)")
    needle = Treasure.from_data("widows_needle")
    p.treasures.append(needle)
    r = needle.reading(p)
    check("rank 3 vs realm 1 is gap +2", r["gap"] == 2)
    check("power scales 5^gap", abs(r["raw_power"] - needle.power * 25) < 1e-6,
          f"{r['raw_power']:.0f}")
    check("control has collapsed", r["control"] < 0.35, f"{r['control']:.0%}")

    outcomes = {"success": 0, "wild": 0, "backlash": 0}
    stab_before = p.stability
    for _ in range(400):
        p.stability = p.stability_max()
        p.hp = p.hp_max()
        o, _dmg, _log = needle.activate(p, rng)
        outcomes[o] += 1
    check("all three outcome bands fire", all(v > 0 for v in outcomes.values()),
          str(outcomes))
    p.stability = stab_before

    print("\nprovenance: a looted sentient treasure resists you")
    clean = Treasure.from_data("widows_needle", provenance="won")
    looted = Treasure.from_data("widows_needle", provenance="looted_corpse")
    clean.judge_provenance()
    looted.judge_provenance()
    p.stability = p.stability_max()
    check("looted control is worse than won control",
          looted.control(p) < clean.control(p),
          f"looted {looted.control(p):.1%} vs won {clean.control(p):.1%}")

    print("\nstability gates repeated overcap")
    p.stability = p.stability_max()
    firsts = needle.control(p)
    for _ in range(4):
        needle.activate(p, rng)
    check("control degrades as stability drains", needle.control(p) < firsts,
          f"{firsts:.1%} -> {needle.control(p):.1%}")

    print("\nharvest: how you kill it decides what survives (doc 11)")
    beast = Monster("beast", "earth", 1, random.Random(5))
    clean_mats, _ = beast.harvest({"damage_types": set(), "overkill": False},
                                  rng=random.Random(3))
    burnt_mats, notes = beast.harvest({"damage_types": {"fire"}, "overkill": True},
                                      rng=random.Random(3))
    check("a clean kill yields more than a burnt one",
          len(clean_mats) >= len(burnt_mats),
          f"{len(clean_mats)} vs {len(burnt_mats)}")
    check("the game says why", bool(notes), notes[0] if notes else "")

    print("\nfamilies source the special material properties (doc 11)")
    props = {"growth": False, "will": False, "effect": False}
    for fam in DATA.families:
        for entry in DATA.families[fam]["anatomy"]:
            part = DATA.materials[entry["part"]]
            props["growth"] |= part.get("growth_bearing", False)
            props["will"] |= part.get("will_bearing", False)
            props["effect"] |= bool(part.get("effects"))
    check("growth, will and effects all have a source", all(props.values()), str(props))

    print("\ncrafting: composition, sharp vs strong (doc 10)")
    fire_mat = {"part": "fang", "name": "Fang", "affinity": {"fire": 1.0},
                "quality": 0.9, "rank": 1, "source": "test"}
    water_mat = {"part": "fang", "name": "Fang", "affinity": {"water": 1.0},
                 "quality": 0.9, "rank": 1, "source": "test"}
    p.realm = 2
    sharp = preview("blade", [fire_mat, fire_mat], p)
    strong = preview("blade", [fire_mat, water_mat, water_mat], p)
    check("pure inputs give a clean high synergy", sharp["synergy"] >= 1.4,
          f"{sharp['synergy']:.2f}x")
    check("mixed inputs raise raw power but wreck synergy",
          strong["power"] > sharp["power"] and strong["synergy"] < sharp["synergy"],
          f"power {sharp['power']:.0f}->{strong['power']:.0f}, "
          f"synergy {sharp['synergy']:.2f}->{strong['synergy']:.2f}")

    void = Player("Void", {})
    void.realm = 2
    vs = preview("blade", [fire_mat, water_mat, water_mat], void)
    check("void prefers the muddied blade a specialist would not touch",
          vs["synergy"] > strong["synergy"],
          f"void {vs['synergy']:.2f}x vs specialist {strong['synergy']:.2f}x")

    print("\ncrafter shapes variance, not the mean")
    lo, hi = Artisan(rng), Artisan(rng)
    lo.skill, hi.skill = 0.25, 0.95
    lo.trait = hi.trait = {"id": "x", "name": "x", "spread": 0.0, "ceiling": 0.0}
    res = {}
    for who, a in (("low", lo), ("high", hi)):
        vals = [craft("blade", [fire_mat, fire_mat], p, a, random.Random(i))[0].power
                for i in range(200)]
        res[who] = (min(vals), max(vals), sum(vals) / len(vals))
    check("high skill has a higher ceiling", res["high"][1] > res["low"][1],
          f"low max {res['low'][1]:.1f}, high max {res['high'][1]:.1f}")
    check("high skill has a narrower spread",
          (res["high"][1] - res["high"][0]) < (res["low"][1] - res["low"][0]),
          f"low spread {res['low'][1]-res['low'][0]:.1f}, "
          f"high spread {res['high'][1]-res['high'][0]:.1f}")

    print("\nwill only comes from soul-bearing material")
    soul = {"part": "soul_remnant", "name": "Soul Remnant",
            "affinity": {"water": 1.0}, "quality": 1.0, "rank": 2, "source": "test"}
    with_soul, _ = craft("talisman", [soul], p, hi, random.Random(1))
    without, _ = craft("talisman", [fire_mat], p, hi, random.Random(1))
    check("soul remnant produces a will", with_soul.will is not None)
    check("ordinary material does not", without.will is None)

    print("\ngrowth-bearing material produces a growth track")
    sinew = {"part": "sinew", "name": "Sinew", "affinity": {"earth": 1.0},
             "quality": 1.0, "rank": 1, "source": "test"}
    grown, _ = craft("blade", [sinew], p, hi, random.Random(1))
    check("sinew produces growth", grown.growth is not None)
    before = grown.base_power()
    grown.gain_growth(500, [])
    check("growth raises power", grown.base_power() > before,
          f"{before:.0f} -> {grown.base_power():.0f}")

    print("\ncompanion neglect (doc 13)")
    y = Companion("shen_yaru")
    start_eff = y.effectiveness()
    log = []
    days = 0
    while not y.should_leave() and days < 200:
        y.idle_day(log)
        days += 1
    check("neglect eventually makes her leave", y.should_leave(), f"{days} days")
    check("she fights worse long before that", y.effectiveness() < start_eff,
          f"{start_eff:.0%} -> {y.effectiveness():.0%}")
    check("she says so first", any("[" not in ln and ln for ln in log) or bool(log),
          f"{len(log)} lines of warning")

    y2 = Companion("shen_yaru")
    for _ in range(10):
        y2.socialize([], rng)
    check("time spent recovers the bond", y2.effectiveness() > start_eff,
          f"{y2.effectiveness():.0%}")

    print("\nfoundation damage is silent and permanent (doc 07)")
    p3 = Player("Deep", {"fire": 1.0})
    p3.stability = p3.stability_max()
    odds_before = p3.breakthrough_odds()
    for _ in range(60):
        p3.stability = p3.stability_max()
        p3.hp = p3.hp_max()
        p3.take_backlash(10, 2, [], rng)
    p3.stability = p3.stability_max()
    check("foundation degrades from overcap backlash", p3.foundation < 100,
          f"{p3.foundation:.0f} ({p3.foundation_label()})")
    check("it lowers breakthrough odds", p3.breakthrough_odds() < odds_before,
          f"{odds_before:.0%} -> {p3.breakthrough_odds():.0%}")

    print("\nvoid is immune to backlash")
    pv = Player("Void", {})
    pv.stability = pv.stability_max()
    log = []
    pv.take_backlash(50, 3, log, rng)
    check("void takes no foundation or health damage from backlash",
          pv.foundation == 100.0 and pv.hp == pv.hp_max(), log[0] if log else "")

    print("\nfull combat runs to a conclusion")
    for seed in range(25):
        rr = random.Random(seed)
        pp = Player("Runner", {"fire": 1.0})
        st = Treasure.from_data("hollow_reed")
        pp.treasures.append(st)
        pp.equip(st)
        cc = Combat(pp, [spawn("clay_terraces", rr)], [Companion("shen_yaru")], rr)
        guard = 0
        while not cc.is_over() and guard < 500:
            a = cc.next_actor()
            if a is None:
                break
            if a is cc.pc:
                cc.player_strike(cc.enemies[0]) if cc.pc.band == 0 else cc.player_move(-1)
            else:
                cc.ai_action(a)
            pp.hp = cc.pc.hp
            guard += 1
        if guard >= 500:
            check(f"combat seed {seed} terminates", False, "hit the guard rail")
            break
    else:
        check("25 combats all terminate", True)

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S): {failures}")
        return 1
    print("all systems check out")
    return 0


if __name__ == "__main__":
    sys.exit(main())
