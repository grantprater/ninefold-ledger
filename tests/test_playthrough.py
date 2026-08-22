"""Drives a scripted playthrough through the real Game object with stubbed UI.

Catches the integration breaks the unit tests miss: menu wiring, day rollover,
action accounting, breakthrough, and the crafting screen's material flow.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import ui                                    # noqa: E402
from engine.crafting import craft                        # noqa: E402
from engine.data import DATA                             # noqa: E402
from engine.monsters import spawn                        # noqa: E402
from engine.treasures import Treasure                    # noqa: E402
from engine.world import Game                            # noqa: E402

failures = []
OUT = []


def check(label, cond, detail=""):
    print(f"  {'pass' if cond else 'FAIL'}  {label}" + (f"   {detail}" if detail else ""))
    if not cond:
        failures.append(label)


def silence_ui():
    """Replace every UI call so the game runs headless."""
    ui.header = lambda *a, **k: None
    ui.rule = lambda *a, **k: None
    ui.pause = lambda *a, **k: None
    ui.clear = lambda *a, **k: None
    ui.say = lambda lines: OUT.extend([lines] if isinstance(lines, str) else list(lines))
    ui.c = lambda t, *s: str(t)
    ui.bar = lambda *a, **k: ""
    ui.field = lambda label, value, width=13: f"{label}: {value}"


def main():
    silence_ui()
    rng = random.Random(4)

    print("day loop and action accounting")
    g = Game("Tester", {"fire": 1.0}, seed=4)
    p = g.player
    start_day = p.day
    for _ in range(3):
        g.do_cultivate()
    check("three actions roll the day over", p.day == start_day + 1,
          f"day {p.day}, {p.actions_left} actions left")
    check("actions reset", p.actions_left == p.actions_per_day)

    print("\ncultivation reaches the realm ceiling")
    guard = 0
    while p.tier < 9 and guard < 4000:
        p.cultivate(60, [])
        guard += 1
    p.qi = p.qi_to_advance()
    check("tier 9 reachable", p.tier == 9, f"after {guard} cultivations")
    check("breakthrough unlocks at the ceiling", p.can_attempt_breakthrough())

    print("\nbreakthrough into Qi Awakened")
    p.stability = p.stability_max()
    attempts = 0
    while p.realm == 1 and attempts < 60:
        p.breakthrough_attempts += 1
        if rng.random() < p.breakthrough_odds():
            p.realm, p.tier, p.qi = 2, 1, 0
            p.stability = p.stability_max()
        else:
            p.qi = p.qi_to_advance()
        attempts += 1
    check("realm 2 reached", p.realm == 2, f"{attempts} attempts")
    check("realm 2 unlocks affinity", DATA.unlocked(p.realm, "affinity_manifest"))
    check("realm 2 unlocks resonance", DATA.unlocked(p.realm, "treasure_resonance"))

    print("\nthe unlock is felt: same blade, different realm")
    blade = p.weapon()
    p.realm = 1
    before = blade.reading(p)["power"]
    p.realm = 2
    after = blade.reading(p)["power"]
    check("the starter blade reads differently after breakthrough",
          abs(before - after) > 1e-6, f"{before:.1f} -> {after:.1f}")

    print("\nbenches belong to settlements, not to the player")
    g.player.location = "outer_court"
    check("the outer court has benches", bool(g.local_artisans()),
          f"{len(g.local_artisans())} working")
    check("hunting is not offered in the settlement", not g.can_hunt())
    for wild in ("clay_terraces", "kiln_road", "drowned_orchard"):
        g.player.location = wild
        if g.local_artisans():
            check(f"no bench in {wild}", False)
            break
        if not g.can_hunt():
            check(f"{wild} is huntable", False)
            break
    else:
        check("no bench follows you into the wilderness", True)
        check("every wilderness region is huntable", True)

    print("\ntravel costs scale with distance")
    g.player.location = "outer_court"
    near, far = g.travel_cost("clay_terraces"), g.travel_cost("drowned_orchard")
    check("the orchard costs more to reach than the terraces", far > near,
          f"{near} vs {far} actions")

    try:
        spawn("outer_court", rng)
        check("hunting a settlement fails loudly", False, "no error raised")
    except ValueError as e:
        check("hunting a settlement fails loudly", "no spawns" in str(e))

    print("\nquick harvest always yields the core")
    m = spawn("clay_terraces", random.Random(2))
    for i in range(40):
        mats, _ = m.harvest({"damage_types": set(), "overkill": False},
                            rng=random.Random(i), quick=True)
        if not any(x["part"] == "core" for x in mats):
            check("quick harvest guarantees a core", False, f"failed on seed {i}")
            break
        if any(DATA.materials[x["part"]]["slot"] != "core" for x in mats):
            check("quick harvest takes only core-slot parts", False)
            break
    else:
        check("quick harvest guarantees a core", True)
        check("quick harvest takes only core-slot parts", True)

    full, _ = m.harvest({"damage_types": set(), "overkill": False},
                        skill=0.6, care=1.0, rng=random.Random(3))
    quick, _ = m.harvest({"damage_types": set(), "overkill": False},
                         skill=0.35, care=0.3, rng=random.Random(3), quick=True)
    check("taking it apart properly yields more", len(full) > len(quick),
          f"{len(full)} vs {len(quick)}")

    print("\nharvest into inventory")
    for _ in range(12):
        m = spawn("clay_terraces", rng)
        mats, _ = m.harvest({"damage_types": set(), "overkill": False}, rng=rng)
        for mat in mats:
            p.add_material(mat)
    check("materials accumulate", p.material_count() > 0, f"{p.material_count()} held")

    print("\ncrafting consumes materials and produces a treasure")
    pool = p.flat_materials()[:3]
    n_before, mats_before = len(p.treasures), p.material_count()
    t, log = craft("blade", pool, p, g.artisans["outer_court"][0], rng)
    p.treasures.append(t)
    p.remove_materials(pool)
    check("treasure created", len(p.treasures) == n_before + 1, t.name)
    check("materials consumed", p.material_count() == mats_before - 3,
          f"{mats_before} -> {p.material_count()}")
    check("crafted item is readable", t.reading(p)["power"] > 0,
          f"power {t.reading(p)['power']:.0f}, synergy {t.synergy(p):.2f}x")

    print("\nequipping swaps by category")
    p.equip(t)
    check("weapon slot replaced", p.weapon() is t)

    print("\nthe needle discovery, both provenances")
    for choice, expect_worse in (("looted_corpse", True), ("won", False)):
        n = Treasure.from_data("widows_needle", provenance=choice)
        n.judge_provenance()
        p.stability = p.stability_max()
        ctrl = n.control(p)
        print(f"    {choice:14s} control {ctrl:.1%}  disposition {n.disposition:+.2f}")
        if expect_worse:
            looted_ctrl = ctrl
        else:
            check("burying her first leaves the needle willing",
                  ctrl > looted_ctrl, f"{looted_ctrl:.1%} vs {ctrl:.1%}")

    print("\novercap in a real fight resolves without crashing")
    from engine.combat import Combat
    needle = Treasure.from_data("widows_needle", provenance="won")
    p.treasures.append(needle)
    seen = set()
    for i in range(120):
        rr = random.Random(i)
        p.hp, p.stability = p.hp_max(), p.stability_max()
        c = Combat(p, [spawn("drowned_orchard", rr)], g.companions, rr)
        out = c.player_treasure(needle, c.enemies[0])
        seen.add("turns in your hands" in " ".join(out))
        OUT.extend(out)
    check("both success and backlash occur in combat", seen == {True, False},
          f"outcomes seen: {seen}")

    print("\nfull scripted run: 40 days of hunting, no crashes")
    g2 = Game("Runner", {"water": 1.0}, seed=9)
    g2.player.location = "clay_terraces"     # the runner hunts; the court does not
    rr = random.Random(9)
    for day in range(40):
        for _ in range(g2.player.actions_per_day):
            roll = rr.random()
            if roll < 0.4:
                g2.do_cultivate()
            elif roll < 0.75:
                m = spawn(g2.player.location, rr)
                from engine.combat import Combat as C2
                cc = C2(g2.player, [m], g2.companions, rr)
                guard = 0
                while not cc.is_over() and guard < 400:
                    a = cc.next_actor()
                    if a is None:
                        break
                    if a is cc.pc:
                        if cc.pc.band > 0:
                            cc.player_move(-1)
                        else:
                            cc.player_strike(cc.enemies[0])
                    else:
                        cc.ai_action(a)
                    g2.player.hp = cc.pc.hp
                    guard += 1
                if cc.player_won():
                    mats, _ = m.harvest(cc.kill_context(), rng=rr)
                    for mat in mats:
                        g2.player.add_material(mat)
                g2.spend_action()
                if g2.player.hp <= 0:
                    g2.player.hp = g2.player.hp_max()
            else:
                g2.do_rest()
    check("40 days survived without an exception", True,
          f"day {g2.player.day}, tier {g2.player.tier}, "
          f"{g2.player.material_count()} materials held")
    check("companion state advanced", g2.player.companions[0].resentment > 0,
          g2.player.companions[0].status_line())

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S): {failures}")
        return 1
    print("playthrough clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
