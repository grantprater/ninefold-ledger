"""Every ending reachable, every coda selectable, and the idle counter."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import endings, ui             # noqa: E402
from engine.data import DATA               # noqa: E402
from engine.world import Game              # noqa: E402

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
    ui.menu = lambda *a, **k: "x"


def run_to_review(social_every, wander=False, seed=1):
    OUT.clear()
    g = Game("Tester", {"fire": 1.0}, seed=seed)
    p = g.player
    p.set_realm(2, 1)
    g.announce_review()
    n = 0
    while g.review and not g.review.resolved and n < 400:
        n += 1
        if wander and n % 7 == 0:
            g.do_wander()
        elif social_every and n % social_every == 0 and g.companions:
            g.do_socialize()
        else:
            g.do_cultivate()
    return g, "\n".join(OUT)


def main():
    silence_ui()

    print("the review is a gate, not an ending")
    g, text = run_to_review(social_every=0)
    check("promotion continues the run", g.ending is None and g.player.promoted,
          f"ending={g.ending}, promoted={g.player.promoted}")
    check("and moves you to the inner court",
          g.player.location == "inner_court", g.player.location)
    check("the trials are not announced until realm 3", g.trials is None)

    print("\nbeing cut or kept does end it")
    for forced, want in (("cut", "cut"), ("kept", "kept")):
        g0 = Game("T", {"fire": 1.0}, seed=5)
        g0.ending = forced
        check(f"'{forced}' terminates", g0.ending == want)

    print("\nevery ending has text and is reachable")
    for kind in ("cut", "kept", "promoted", "died", "trials_won", "trials_lost"):
        d = DATA.endings.get(kind)
        check(f"'{kind}' defined", bool(d and d.get("body")),
              d["title"] if d else "missing")

    print("\nthe cut ending reads as mediocrity, not defeat")
    OUT.clear()
    g2 = Game("Tester", {"fire": 1.0}, seed=2)
    g2.player.set_realm(2, 3)
    g2.player.companions[0].present = False
    endings.show(g2.player, g2, "cut")
    cut_text = "\n".join(OUT)
    check("no villain, no betrayal", "The board was accurate." in cut_text)
    check("the genre keeps going without you",
          "You will always have seen two." in cut_text)
    check("companion coda fired", "Shen Yaru left before you did" in cut_text)

    print("\ncodas key off what the run actually cost")
    cases = [
        ("never idled, she is gone", 0, 100.0, False, "never_idled"),
        ("idled, she is gone",       4, 100.0, False, "idled"),
        ("flawed foundation",        4,  55.0, False, "foundation_flawed"),
        ("she is still here",        4, 100.0, True,  "companion_present"),
    ]
    for label, idle, foundation, companion, want in cases:
        g3 = Game("T", {"fire": 1.0}, seed=3)
        g3.player.idle_days = idle
        g3.player.foundation = foundation
        g3.player.companions[0].present = companion
        got = endings.choose_codas(g3.player, g3, "cut")
        check(label, want in got, f"{got}")

    print("\nthe idle counter is invisible until the end")
    g4, text4 = run_to_review(social_every=3, wander=True, seed=4)
    check("wandering was counted", g4.player.idle_days > 0,
          f"{g4.player.idle_days} afternoons")
    check("it never appeared in play", "idle_days" not in text4
          and "afternoons wasted" not in text4)

    OUT.clear()
    endings.show(g4.player, g4, "cut")
    idled_text = "\n".join(OUT)
    check("it appears in the ending", "did not have a column for it" in idled_text)

    OUT.clear()
    g5, _ = run_to_review(social_every=3, wander=False, seed=4)
    endings.show(g5.player, g5, "cut")
    check("and the other way round for a run with none",
          "Not once." in "\n".join(OUT), f"idle_days={g5.player.idle_days}")

    print("\nthe prize coda keys off what you did with it")
    for state, want in (("took", "on the wall, where you can see it"),
                        ("refused", "which is not the same as having it")):
        OUT.clear()
        g8 = Game("T", {"fire": 1.0}, seed=8)
        g8.player.took_the_prize = state
        endings.show(g8.player, g8, "trials_won")
        check(f"'{state}'", want in "\n".join(OUT))

    print("\nwandering costs a real action and yields nothing")
    g6 = Game("T", {"fire": 1.0}, seed=6)
    before = (g6.player.actions_left, g6.player.qi, g6.player.spirit_stones,
              g6.player.material_count())
    g6.do_wander()
    after = (g6.player.actions_left, g6.player.qi, g6.player.spirit_stones,
             g6.player.material_count())
    check("an action was spent", after[0] == before[0] - 1,
          f"{before[0]} -> {after[0]}")
    check("nothing was gained", after[1:] == before[1:])

    print("\nvignettes exist for every region the player can stand in")
    for rid in DATA.regions:
        check(f"{rid} has something to look at", rid in DATA.vignettes,
              f"{len(DATA.vignettes.get(rid, {}).get('lines', []))} lines")

    print("\nvignettes do not repeat until the pool is exhausted")
    g7 = Game("T", {"fire": 1.0}, seed=7)
    pool = len(DATA.vignettes["outer_court"]["lines"])
    for _ in range(pool // 2):
        g7.player.actions_left = 5
        g7.do_wander()
    check("seen set grew without duplicates",
          len(g7.player.seen_vignettes) == (pool // 2) * 2,
          f"{len(g7.player.seen_vignettes)} of {pool}")

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S): {failures}")
        return 1
    print("endings and vignettes clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
