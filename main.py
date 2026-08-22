"""The Ninefold Ledger -- MVP, realms 1 and 2.

    py main.py            play
    py main.py --seed 7   play with a fixed seed
"""

import argparse
import sys

from engine import ui
from engine.affinity import TABLE
from engine.data import DATA
from engine.world import Game


def choose_affinity():
    ui.header("what you are made of",
              "Your affinity decides which treasures answer you and which fight you.")
    print()
    print(ui.c("  The five relate in cycles. Each element feeds two others and "
               "is opposed by\n  two more, so there is no safe pick -- only a "
               "different set of enemies.", "grey"))

    opts = []
    for i, el in enumerate(DATA.elements, start=1):
        feeds = [DATA.element_name(b) for a, b in TABLE.generates if a == el]
        opposes = [DATA.element_name(b) for a, b in TABLE.destroys if a == el]
        opts.append((str(i), DATA.element_name(el), True,
                     f"overcomes {', '.join(opposes)}  /  feeds {', '.join(feeds)}"))
    opts.append(("v", ui.c("Void", "magenta"), True,
                 "no affinity at all -- flat 0.60x with everything, and nothing "
                 "can ever backlash you"))

    choice = ui.menu(opts, "affinity > ")
    if choice == "v":
        print()
        print(ui.c("  Everyone will tell you this is the supreme protagonist "
                   "affinity.\n  The arithmetic disagrees, for now.", "magenta"))
        ui.pause()
        return {}
    return {DATA.elements[int(choice) - 1]: 1.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    ui.init()
    ui.clear()
    ui.header("the ninefold ledger", "realms one and two")

    name = args.name
    if not name:
        try:
            name = input(ui.c("\n  your name > ", "bcyan"))
        except (EOFError, KeyboardInterrupt):
            return 0
    # Strip a BOM as well as whitespace -- piped stdin on Windows carries one.
    name = (name or "").lstrip("﻿").strip() or "Ren Xiaobai"

    affinity = choose_affinity()
    Game(name, affinity, seed=args.seed).run()
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
