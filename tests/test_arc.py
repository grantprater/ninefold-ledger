"""The whole arc, realm 1 through the Inner Trials, through the real Game."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import ui                       # noqa: E402
from engine.data import DATA                # noqa: E402

CHOICES = []
OUT = []
failures = []


def check(label, cond, detail=""):
    print(f"  {'pass' if cond else 'FAIL'}  {label}" + (f"   {detail}" if detail else ""))
    if not cond:
        failures.append(label)


def silence_ui():
    ui.header = lambda *a, **k: OUT.append(f"== {a[0] if a else ''}")
    ui.rule = lambda *a, **k: None
    ui.pause = lambda *a, **k: None
    ui.clear = lambda *a, **k: None
    ui.say = lambda lines: OUT.extend([lines] if isinstance(lines, str) else list(lines))
    ui.c = lambda t, *s: str(t)
    ui.bar = lambda *a, **k: ""
    ui.field = lambda label, value, width=13: f"{label}: {value}"
    # Menus answer from a script, falling back to the first enabled option.
    def menu(options, prompt="> "):
        if CHOICES:
            return CHOICES.pop(0)
        for key, _label, enabled, _note in options:
            if enabled:
                return key
        return "x"
    ui.menu = menu


def main():
    silence_ui()
    from engine.world import Game

    rng = random.Random(3)
    g = Game("Arc", {"water": 1.0}, seed=3)
    p = g.player
    milestones = {}

    guard = 0
    while g.ending is None and guard < 3000:
        guard += 1
        if p.realm == 1 and p.can_attempt_breakthrough():
            CHOICES.append("y")
            g.do_breakthrough()
            milestones.setdefault("realm2", p.day)
            continue
        if p.realm == 2 and p.can_attempt_breakthrough() and g.review \
                and g.review.resolved:
            CHOICES.append("y")
            g.do_breakthrough()
            milestones.setdefault("realm3", p.day)
            continue
        # Split the days: mostly cultivate, make time for her every third.
        if guard % 3 == 0 and g.companions:
            g.do_socialize()
        else:
            g.do_cultivate()

    text = "\n".join(str(x) for x in OUT)
    check("the arc terminated", g.ending is not None, f"{g.ending} on day {p.day}")
    check("realm 2 reached", "realm2" in milestones, f"day {milestones.get('realm2')}")
    check("the review happened", g.review is not None and g.review.resolved)
    check("promotion moved you up", p.promoted, f"location {p.location}")
    check("realm 3 reached", p.realm >= 3, f"realm {p.realm} tier {p.tier}")
    check("the trials were announced", g.trials is not None)
    check("the trials resolved", g.trials and g.trials.resolved)
    check("an ending fired", g.ending in ("trials_won", "trials_lost"), g.ending)

    print("\n  timeline")
    for k in ("realm2", "realm3"):
        print(f"    {k:8s} day {milestones.get(k, '-')}")
    print(f"    ending   day {p.day}, {g.ending}")
    print(f"    rival    {g.rival.status_line()}")
    comp = next((c for c in p.companions if c.present), None)
    print(f"    yaru     {comp.status_line() if comp else 'gone'}")

    print("\n  key beats present")
    for beat, needle in (
        ("review board", "cohort review is in thirty days"),
        ("realm 3 unlock", "Formations are yours"),
        ("trials announced", "rank-five blade out of the sect vault"),
    ):
        check(beat, needle.lower() in text.lower())

    print("\nyou are patched up between rounds, but not repaired")
    from engine.entities import Player as P2
    from engine.tournament import InnerTrials
    pt = P2("T", {"water": 1.0})
    pt.set_realm(3, 6)
    pt.hp, pt.qi = 10.0, 0.0
    pt.stability = 40.0
    g2 = Game("T", {"water": 1.0}, seed=11)
    g2.player = pt
    g2.trials = InnerTrials(pt.day, rng)
    CHOICES.clear()
    OUT.clear()
    g2.do_trials()
    trial_text = "\n".join(str(x) for x in OUT)
    # Entering on 10 hp, surviving to round 2 is only possible if the between
    # -round restore ran before round 1.
    check("hp and qi came back", "Round 2" in trial_text,
          "reached round 2 from 10 hp")
    check("stability did not", pt.stability <= 40.0,
          f"{pt.stability:.0f}/{pt.stability_max()}")

    print("\nformations change trial outcomes, not just flavour")
    from engine.combat import Combat as C3
    from engine.duelists import Duelist as D3
    from engine.entities import Player as P3

    from engine.treasures import Treasure as T3

    def run_bout(use_formation, seed):
        pl = P3("T", {"water": 1.0})
        pl.set_realm(3, 7)
        blade = T3.from_data("hollow_reed")
        pl.treasures.append(blade)
        pl.equip(blade)
        pl.qi = pl.qi_max()
        pl.stability = pl.stability_max()
        rr = random.Random(seed)
        # Earth overcomes water: the player is on the wrong side of the matrix
        # here, which is exactly the situation formations exist for.
        foe = D3("Kong Deshan", 3, 5, {"earth": 1.0}, rng=random.Random(seed))
        c = C3(pl, [foe], [], rr)
        if use_formation:
            c.player_formation("binding_mesh")
        guard = 0
        while not c.is_over() and guard < 600:
            a = c.next_actor()
            if a is None:
                break
            if a is c.pc:
                # Do not chase a skirmisher who wants mid range -- striking at
                # a penalty beats spending every action closing.
                if c.pc.band == 2:
                    c.player_move(-1)
                else:
                    c.player_technique(c.enemies[0]) if pl.qi >= 12 \
                        else c.player_strike(c.enemies[0])
            else:
                c.ai_action(a)
            pl.hp = c.pc.hp
            guard += 1
        return c.player_won()

    plain = sum(run_bout(False, s) for s in range(40))
    meshed = sum(run_bout(True, s) for s in range(40))
    print(f"    striking only      {plain}/40 wins")
    print(f"    mesh then strike   {meshed}/40 wins")
    check("laying a mesh wins bouts striking alone loses", meshed > plain,
          f"{plain} -> {meshed}")

    print("\nformations are offered only from realm 3")
    from engine.combat import Combat
    from engine.duelists import Duelist
    from engine.entities import Player
    for realm, want in ((2, False), (3, True)):
        pp = Player("T", {"fire": 1.0})
        pp.realm = realm
        pp.qi = pp.qi_max()
        c = Combat(pp, [Duelist("x", realm, 3, {"wood": 1.0}, rng=rng)], [], rng)
        out = c.player_formation("binding_mesh")
        laid = bool(c.active_formations())
        check(f"realm {realm} can lay one = {want}", laid == want,
              out[0] if out else "")

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S): {failures}")
        return 1
    print("the arc runs clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
