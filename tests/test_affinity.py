"""Checks the synergy formula against the worked examples in design doc 06."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.affinity import TABLE, normalize  # noqa: E402

CASES = [
    ("Pure Fire", {"fire": 1.0},  "Fire blade",  {"fire": 1.0},  1.5,  "identity"),
    ("Wood",      {"wood": 1.0},  "Fire blade",  {"fire": 1.0},  0.85, "generating"),
    ("Fire",      {"fire": 1.0},  "Earth charm", {"earth": 1.0}, 0.85, "generating"),
    ("Water",     {"water": 1.0}, "Fire blade",  {"fire": 1.0},  0.0,  "destroying"),
    ("Fire",      {"fire": 1.0},  "Water charm", {"water": 1.0}, 0.0,  "destroying"),
    ("Void",      {},             "Fire blade",  {"fire": 1.0},  0.6,  "void"),
]


def main():
    failures = 0

    print("synergy formula")
    for cname, avec, tname, tvec, want, want_rel in CASES:
        got = TABLE.synergy(avec, tvec)
        rel = TABLE.relation_label(avec, tvec)
        ok = abs(got - want) < 0.011 and rel == want_rel
        failures += not ok
        print(f"  {'pass' if ok else 'FAIL'}  {cname:10s} + {tname:12s} "
              f"= {got:.3f}x  (want {want})  [{rel}]")

    print("\ndilution -- same fire blade, every split build costs something")
    pure = TABLE.synergy({"fire": 1.0}, {"fire": 1.0})
    print(f"  {'pure fire':18s} -> {pure:.3f}x")
    for label, vec in [("fire/wood 50/50",  {"fire": 0.5, "wood": 0.5}),
                       ("fire/wood 70/30",  {"fire": 0.7, "wood": 0.3}),
                       ("fire/metal 70/30", {"fire": 0.7, "metal": 0.3}),
                       ("fire/metal 50/50", {"fire": 0.5, "metal": 0.5})]:
        got = TABLE.synergy(vec, {"fire": 1.0})
        ok = got <= pure + 1e-9
        failures += not ok
        print(f"  {'pass' if ok else 'FAIL'}  {label:16s} -> {got:.3f}x  "
              f"(costs {pure - got:.3f})")
    # The point of L1: diluting toward a generating element is a mild cost,
    # diluting toward a destroying one is severe. That is the decision space.
    mild = pure - TABLE.synergy({"fire": 0.7, "wood": 0.3}, {"fire": 1.0})
    harsh = pure - TABLE.synergy({"fire": 0.7, "metal": 0.3}, {"fire": 1.0})
    ok = harsh > mild
    failures += not ok
    print(f"  {'pass' if ok else 'FAIL'}  diluting toward a destroying element "
          f"costs {harsh / mild:.1f}x more than toward a generating one")

    print("\nvoid -- the edge is the floor, not the average")
    # With only the five wuxing elements there are no unrelated pairs, so the
    # 0.2 floor never fires and a specialist's *average* beats void's flat 0.6.
    # Void's actual advantage is that it has no dead items and no backlash,
    # which is what matters for uniques you cannot choose the element of.
    pool = [{e: 1.0} for e in ("fire", "water", "wood", "metal", "earth")]
    spec = [TABLE.synergy({"fire": 1.0}, t) for t in pool]
    void = [TABLE.synergy({}, t) for t in pool]
    print(f"  fire specialist  avg {sum(spec)/len(spec):.3f}x   "
          f"floor {min(spec):.3f}x   dead items {sum(s == 0 for s in spec)}/5")
    print(f"  void             avg {sum(void)/len(void):.3f}x   "
          f"floor {min(void):.3f}x   dead items {sum(s == 0 for s in void)}/5")
    if min(void) <= min(spec) or any(s == 0 for s in void):
        print("    FAIL: void should never hold a dead item")
        failures += 1

    print("\n  overcap reach on an unchooseable rank+2 unique (control x mult)")
    for label, vec in [("fire specialist, matched", {"fire": 1.0}),
                       ("fire specialist, opposed", {"fire": 1.0}),
                       ("void, anything", {})]:
        tvec = {"fire": 1.0} if "matched" in label else {"water": 1.0}
        if not vec:
            tvec = {"water": 1.0}
        mult = 0.5 + TABLE.synergy(vec, tvec)
        print(f"    {label:26s} -> {mult:.2f}x control")

    print("\nnormalize")
    n = normalize({"fire": 3.0, "metal": 1.0})
    ok = abs(sum(n.values()) - 1.0) < 1e-9
    failures += not ok
    print(f"  {'pass' if ok else 'FAIL'}  {n}")

    print(f"\n{'all checks passed' if not failures else f'{failures} FAILURE(S)'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
