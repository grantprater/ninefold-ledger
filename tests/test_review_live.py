"""Drives the review through the real Game object, both endings."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import ui                      # noqa: E402
from engine.data import DATA               # noqa: E402
from engine.world import Game              # noqa: E402

OUT = []


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


def play(social_every, seed=1):
    """Run to the review, socialising every Nth action (0 = never)."""
    OUT.clear()
    g = Game("Tester", {"fire": 1.0}, seed=seed)
    p = g.player
    p.set_realm(2, 1)
    g.announce_review()

    n = 0
    while g.review and not g.review.resolved:
        n += 1
        if social_every and n % social_every == 0 and g.companions:
            g.do_socialize()
        else:
            g.do_cultivate()
        if n > 400:
            break
    return g, list(OUT)


def main():
    silence_ui()
    failures = []

    def check(label, cond, detail=""):
        print(f"  {'pass' if cond else 'FAIL'}  {label}" + (f"   {detail}" if detail else ""))
        if not cond:
            failures.append(label)

    print("the review announces itself and resolves on time")
    g, log = play(social_every=0)
    text = "\n".join(log)
    check("announced", "cohort review is in thirty days" in text.lower())
    check("rival introduced", "Gu Wenshan" in text)
    check("resolved", g.review.resolved)
    check("resolved on the due day", g.player.day >= g.review.due_day,
          f"day {g.player.day}, due {g.review.due_day}")
    check("reminders appeared", "Ten days." in text)

    print("\nnever making time for her: she is cut")
    check("she leaves the board", "does not" in text and "ink is still wet" in text)
    check("she is gone afterwards", not g.companions)
    check("you still placed", "You are going up." in text or "keep your place" in text)

    print("\nmaking time for her: she keeps her place")
    g2, log2 = play(social_every=3)
    text2 = "\n".join(log2)
    check("she keeps her place", "keeps her place" in text2)
    check("she is still with you", bool(g2.companions),
          g2.companions[0].status_line() if g2.companions else "gone")
    check("she noticed", "I wanted to see if you did" in text2)

    print("\nthe rival advanced under his own steam")
    check("rival progressed past his start",
          g.rival.realm > 1 or g.rival.tier > DATA.rivals["gu_wenshan"]["tier"],
          g.rival.status_line())

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S): {failures}")
        return 1
    print("review plays through clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
