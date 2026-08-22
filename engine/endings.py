"""Run endings. Doc section 01.

The MVP terminates at the cohort review. Each ending is a base passage plus
codas selected from what the run actually cost -- and the codas, not the base,
are where the thesis lands. The most important one keys off a counter the game
never displays and never rewards.
"""

from . import ui
from .data import DATA


def choose_codas(player, game, kind):
    """Which accounts are outstanding at the end of this run."""
    codas = []
    companion = next((c for c in player.companions if c.present), None)

    if companion is None:
        codas.append("companion_gone_cut" if kind == "cut" else "companion_gone_other")
    else:
        codas.append("companion_present")

    if player.foundation < 80:
        codas.append("foundation_flawed")

    if player.took_the_prize == "took":
        codas.append("took_the_prize")
    elif player.took_the_prize == "refused":
        codas.append("left_the_prize")

    # Never shown in the UI, never rewarded, never hinted at. It only exists
    # here, at the end, where the ledger is read back.
    codas.append("never_idled" if player.idle_days == 0 else "idled")
    return codas


def show(player, game, kind):
    data = DATA.endings[kind]
    ui.clear()
    ui.header(data["title"], f"day {player.day}")
    print()
    ui.say(data["body"])

    for key in choose_codas(player, game, kind):
        print()
        ui.rule()
        ui.say(DATA.endings["codas"][key])

    print()
    ui.rule()
    print()
    r = player.realm_data()
    print(ui.field("Reached", f"{r['name']}, tier {player.tier}"))
    print(ui.field("Foundation", player.foundation_label()))
    print(ui.field("Days", f"{player.day}"))
    comp = next((c for c in player.companions if c.present), None)
    print(ui.field("Shen Yaru", comp.status_line() if comp else "gone"))
    print()
