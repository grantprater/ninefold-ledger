"""The day loop and every screen hanging off it. Doc sections 12, 13, 14.

Three actions a day. Cultivating, hunting, harvesting, crafting and spending
time with someone all draw from the same pool, which is what makes a companion
an opportunity cost rather than a free reward.
"""

import random

from . import endings, ui
from .affinity import TABLE, describe, dominant
from .combat import BAND_NAMES, Combat
from .companions import Companion
from .crafting import Artisan, craft, preview
from .data import DATA
from .entities import Player
from .monsters import spawn
from .rivals import CohortReview, Rival
from .tournament import InnerTrials
from .treasures import Treasure


class Game:
    def __init__(self, name, affinity, seed=None):
        self.rng = random.Random(seed)
        self.player = Player(name, affinity)
        self.running = True

        # Artisans belong to settlements, not to the player. A bench does not
        # follow you into the Drowned Orchard.
        self.artisans = {}
        for rid, reg in DATA.regions.items():
            if reg.get("settlement"):
                self.artisans[rid] = [Artisan(self.rng)
                                      for _ in range(reg.get("artisans", 1))]
        self.player.location = "outer_court"

        starter = Treasure.from_data("hollow_reed", provenance="issued")
        self.player.treasures.append(starter)
        self.player.equip(starter)

        yaru = Companion("shen_yaru")
        self.player.companions.append(yaru)

        # He is already ahead, and already cultivating. The clock over both of
        # you does not start until you break through -- see end_day.
        self.rival = Rival()
        self.review = None
        self.trials = None
        self.rival_met = False
        self.ending = None

    # ---------- helpers ----------

    @property
    def companions(self):
        return [c for c in self.player.companions if c.present]

    @property
    def here(self):
        return DATA.regions[self.player.location]

    def local_artisans(self):
        return self.artisans.get(self.player.location, [])

    def can_hunt(self):
        return bool(self.here.get("spawns"))

    def spend_action(self, socialized=False):
        p = self.player
        p.actions_left -= 1
        if p.actions_left <= 0:
            self.end_day(socialized)

    def end_day(self, socialized):
        p = self.player
        log = []
        p.day += 1
        p.actions_left = p.actions_per_day
        p.stability = min(p.stability_max(), p.stability + 6)

        for comp in list(self.companions):
            if not socialized:
                comp.idle_day(log)
            if comp.should_leave():
                comp.depart(log)

        # The rival only starts mattering once there is a clock on both of you.
        clock = self.active_event()
        if clock:
            note = self.rival.advance_day(self.rng)
            if note:
                log.append("")
                log.append(note)
            elif self.rng.random() < 0.18 and self.here.get("settlement"):
                log.append(self.rival.news(self.rng))

            reminder = clock.tick(p.day)
            if reminder:
                log.append("")
                log.append(ui.c(reminder, "byellow"))

        if log:
            ui.header(f"day {p.day - 1} ends")
            ui.say(log)
            ui.pause()

        if self.review and self.review.due(p.day):
            self.do_review()
        elif self.trials and self.trials.due(p.day):
            self.do_trials()

    def active_event(self):
        """Whichever deadline is currently running, if any."""
        for e in (self.review, self.trials):
            if e and not e.resolved:
                return e
        return None

    # ---------- top level ----------

    def run(self):
        self.intro()
        while self.running and self.ending is None and self.player.hp > 0:
            self.day_menu()
        if self.player.hp <= 0 and self.ending is None:
            self.ending = "died"
        if self.ending:
            endings.show(self.player, self, self.ending)

    def intro(self):
        p = self.player
        ui.clear()
        ui.header("the ninefold ledger", "an outer disciple, and everything it costs")
        print()
        ui.say([
            f"You are {p.name}, {ui.ordinal(p.tier)} tier of Body Tempering, "
            f"which is where you were this time last year.",
            "",
            f"Your affinity reads: {ui.c(p.affinity_label(), 'bcyan')}.",
            "",
            DATA.realm(1)["flavor"],
        ])
        print()
        ui.say(DATA.companions["shen_yaru"]["intro"])
        ui.pause()

    # ---------- status ----------

    def status_block(self):
        p = self.player
        r = p.realm_data()
        print()
        print(ui.field("Day", f"{p.day}   actions left {p.actions_left}/{p.actions_per_day}"))
        print(ui.field("Realm", f"{r['name']}  tier {p.tier}/{r['tiers']}"))
        print(ui.field("Health", f"{ui.bar(p.hp, p.hp_max())} {p.hp:.0f}/{p.hp_max():.0f}"))
        print(ui.field("Qi", f"{ui.bar(p.qi, p.qi_to_advance(), style='blue')} "
                             f"{p.qi:.0f}/{p.qi_to_advance():.0f}"))
        print(ui.field("Stability", f"{ui.bar(p.stability, p.stability_max(), style='cyan')} "
                                    f"{p.stability:.0f}/{p.stability_max()}"))

        # Shown from day one, long before it does anything. That is the point.
        fl = p.foundation_label()
        style = "green" if fl == "Sound" else ("byellow" if fl == "Marked" else "bred")
        print(ui.field("Foundation", ui.c(fl, style)))

        if p.injuries:
            print(ui.field("Injuries", ui.c(", ".join(i["name"] for i in p.injuries), "bred")))
        print(ui.field("Location", DATA.regions[p.location]["name"]))
        print(ui.field("Stones", f"{p.spirit_stones}"))

        clock = self.active_event()
        if clock:
            left = clock.days_left(p.day)
            style = "bred" if left <= 5 else ("byellow" if left <= 12 else "white")
            print(ui.field(clock.name.replace("The ", ""),
                           ui.c(f"{left} days", style)
                           + ui.c(f"   {self.rival.status_line()}", "grey")))

        for comp in self.companions:
            print(ui.field("Companion", comp.status_line()))

    def day_menu(self):
        p = self.player
        ui.clear()
        ui.header(f"{DATA.regions[p.location]['name']}", DATA.regions[p.location]["flavor"])
        self.status_block()

        benches = self.local_artisans()
        opts = [
            ("1", "Cultivate", True, "circulate qi for the day"),
            ("2", "Hunt", self.can_hunt(),
             "find something and fight it" if self.can_hunt()
             else "nothing here worth hunting"),
            ("4", "Visit a bench", bool(benches),
             f"{len(benches)} working" if benches
             else "no benches out here"),
            ("5", "Spend the day with Shen Yaru",
             bool(self.companions), "" if self.companions else "she is gone"),
            ("6", "Rest", True, "recover stability and health"),
            ("7", "Travel", True, "move to another region"),
            ("8", DATA.vignettes[p.location]["verb"]
             if p.location in DATA.vignettes else "Wander",
             p.location in DATA.vignettes, ""),
            ("i", "Inventory", True, ""),
            ("b", "Attempt breakthrough", p.can_attempt_breakthrough(),
             f"{p.breakthrough_odds():.0%} odds" if p.can_attempt_breakthrough()
             else "not yet full"),
            ("q", "Quit", True, ""),
        ]
        choice = ui.menu(opts)

        if choice == "1":
            self.do_cultivate()
        elif choice == "2":
            self.do_hunt()
        elif choice == "4":
            self.do_bench()
        elif choice == "5":
            self.do_socialize()
        elif choice == "6":
            self.do_rest()
        elif choice == "7":
            self.do_travel()
        elif choice == "8":
            self.do_wander()
        elif choice == "i":
            self.do_inventory()
        elif choice == "b":
            self.do_breakthrough()
        elif choice == "q":
            self.running = False

    # ---------- actions ----------

    def do_cultivate(self):
        log = []
        gain = self.player.cultivation_yield() + self.rng.uniform(-2, 4)
        self.player.cultivate(gain, log)
        ui.header("you sit")
        ui.say(log)
        ui.pause()
        self.spend_action()

    def do_rest(self):
        log = []
        self.player.rest(log)
        ui.header("you rest")
        ui.say(log)
        ui.pause()
        self.spend_action()

    def do_socialize(self):
        if not self.companions:
            return
        log = []
        self.companions[0].socialize(log, self.rng)
        ui.header("the well")
        ui.say(log)
        ui.pause()
        self.spend_action(socialized=True)

    def do_wander(self):
        """Costs an action. Returns nothing. Is counted.

        The counter is never surfaced in the UI and never feeds a stat -- it
        exists only for the ending codas. An optimising player will never spend
        an action here, and the game will have noticed that too.
        """
        p = self.player
        pool = DATA.vignettes.get(p.location)
        if not pool:
            return

        unseen = [ln for ln in pool["lines"] if ln not in p.seen_vignettes]
        if not unseen:
            unseen = list(pool["lines"])
            p.seen_vignettes -= set(pool["lines"])

        picks = self.rng.sample(unseen, min(2, len(unseen)))
        p.seen_vignettes.update(picks)
        p.idle_days += 1

        ui.header(pool["verb"], "nothing comes of it")
        for line in picks:
            print()
            ui.say(line)
        print()
        ui.say(ui.c("The day goes. You have nothing to show for it.", "grey"))
        ui.pause()
        self.spend_action()

    def travel_cost(self, dest_id):
        """Actions to get there. Distance is measured from the Outer Court."""
        a = self.here.get("travel_days", 0)
        b = DATA.regions[dest_id].get("travel_days", 0)
        return max(1, abs(a - b))

    def do_travel(self):
        opts = []
        for i, (rid, reg) in enumerate(DATA.regions.items(), start=1):
            here = rid == self.player.location
            locked = self.player.realm < reg.get("requires_realm", 1)
            if locked:
                opts.append((str(i), reg["name"], False,
                             f"needs {DATA.realm(reg['requires_realm'])['name']}"))
                continue
            if here:
                note = "you are here"
            else:
                cost = self.travel_cost(rid)
                bits = [f"{cost} action{'s' if cost > 1 else ''}"]
                if reg.get("settlement"):
                    bits.append("benches")
                if reg.get("spawns"):
                    bits.append(f"rank {reg['rank_range'][0]}-{reg['rank_range'][1]}")
                note = "  ".join(bits)
            opts.append((str(i), reg["name"], not here, note))
        opts.append(("x", "Stay", True, ""))
        choice = ui.menu(opts, "travel to > ")
        if choice == "x":
            return
        rid = list(DATA.regions)[int(choice) - 1]
        cost = self.travel_cost(rid)
        self.player.location = rid
        ui.header("you travel")
        ui.say(DATA.regions[rid]["flavor"])
        ui.pause()
        for _ in range(cost):
            self.spend_action()

    # ---------- hunting ----------

    def do_hunt(self):
        if self.maybe_discovery():
            return
        monster = spawn(self.player.location, self.rng)
        combat = Combat(self.player, [monster], self.companions, self.rng)
        ui.header("you find something", monster.display())
        result = self.combat_loop(combat, monster)
        self.spend_action()
        if result == "won":
            self.do_harvest(monster, combat.kill_context())

    def maybe_discovery(self):
        """The one rank-3 unique in the MVP, and how you take it.

        This exists to teach provenance in a single decision: the impatient
        answer is free and permanently worse, and the game does not say so.
        """
        p = self.player
        if p.found_needle or p.location != "drowned_orchard":
            return False
        if self.rng.random() > 0.45:
            return False

        p.found_needle = True
        ui.header("someone got here first",
                  "a woman face-down in the silt, a long way from anywhere")
        ui.say([
            "She has been here a season at least. Outer court robes, no sect "
            "token, both hands still closed around the grip of something.",
            "",
            "It is a needle. An embroidery needle, if embroidery were done on "
            "something the size of a door -- long enough to be a sword, and "
            "clearly used as one.",
            "",
            "It is rank three. You are not.",
        ])

        choice = ui.menu([
            ("1", "Take it", True, "she is past minding"),
            ("2", "Bury her first, then take it", True,
             ui.c("costs your remaining actions today", "grey")),
            ("3", "Leave it where it is", True, ""),
        ], "> ")

        if choice == "3":
            p.found_needle = False
            ui.say("\n  You leave her holding it.")
            ui.pause()
            self.spend_action()
            return True

        provenance = "looted_corpse" if choice == "1" else "won"
        needle = Treasure.from_data("widows_needle", provenance=provenance)
        note = needle.judge_provenance()
        p.treasures.append(needle)

        print()
        if choice == "2":
            ui.say([
                "It takes most of the afternoon. The silt does not want to hold "
                "a shape and you have nothing to dig with but your hands.",
                "",
                "When you finally lift the needle it comes away easily, which "
                "you had not expected.",
            ])
            p.actions_left = 1        # consumed below
        else:
            ui.say("You work her fingers open. It takes a while. "
                   "They have set around the grip.")
        if note:
            print()
            ui.say(ui.c(note, "magenta"))
        print()
        self.show_treasure(needle)
        ui.pause()
        self.spend_action()
        return True

    def combat_loop(self, combat, monster):
        p = self.player
        while not combat.is_over():
            actor = combat.next_actor()
            if actor is None:
                break
            if actor is combat.pc:
                out = self.player_turn(combat, monster)
                if out == "fled":
                    return "fled"
            else:
                ui.say(combat.ai_action(actor))
            p.hp = combat.pc.hp

        if combat.player_won():
            ui.say(["", ui.c("It is over.", "bgreen")])
            weapon = p.weapon()
            if weapon:
                weapon.gain_growth(12, [])
            ui.pause()
            return "won"
        ui.pause()
        return "lost"

    def player_turn(self, combat, monster):
        p = self.player
        enemies = combat.enemies
        if not enemies:
            return None
        target = enemies[0]

        print()
        ui.rule()
        print(ui.field("You", f"{ui.bar(combat.pc.hp, combat.pc.hp_max)} "
                              f"{combat.pc.hp:.0f}/{combat.pc.hp_max:.0f}   "
                              f"{BAND_NAMES[combat.pc.band]} range"))
        for e in enemies:
            print(ui.field(e.name[:12], f"{ui.bar(e.hp, e.hp_max, style='red')} "
                                        f"{e.hp:.0f}/{e.hp_max:.0f}   "
                                        f"{BAND_NAMES[e.band]}"))
        for a in combat.allies:
            if a is not combat.pc:
                print(ui.field(a.name[:12], f"{ui.bar(a.hp, a.hp_max)} "
                                            f"{a.hp:.0f}/{a.hp_max:.0f}"))
        order = " -> ".join(x.name.split()[0][:8] for x in combat.initiative_preview(5))
        print(ui.field("Next", ui.c(order, "grey")))

        live = combat.active_formations()
        if live:
            print(ui.field("Field", ui.c(
                "  ".join(f["name"] for f in live), "bgreen")))

        overcap = [t for t in p.treasures if t.gap(p) > 0]
        arrays = DATA.unlocked(p.realm, "world_energy")
        opts = [
            ("1", "Strike", combat.pc.band < 2, f"{BAND_NAMES[combat.pc.band]} range"),
            ("2", "Technique", DATA.unlocked(p.realm, "elemental_technique"),
             "12 qi" if DATA.unlocked(p.realm, "elemental_technique") else "affinity still latent"),
            ("3", "Activate a treasure", bool(overcap), "reach past your realm"),
            ("4", "Close", combat.pc.band > 0, ""),
            ("5", "Back off", combat.pc.band < 2, ""),
            ("6", "Steady", True, "recover stability"),
            ("7", "Lay a formation", arrays,
             "costs time, buys more of it" if arrays else "you cannot feel the room yet"),
            ("f", "Flee", True, ""),
        ]
        choice = ui.menu(opts, "action > ")

        if choice == "1":
            ui.say(combat.player_strike(target))
        elif choice == "2":
            ui.say(combat.player_technique(target))
        elif choice == "3":
            t = self.pick_treasure(overcap)
            if t:
                ui.say(combat.player_treasure(t, target))
        elif choice == "4":
            ui.say(combat.player_move(-1))
        elif choice == "5":
            ui.say(combat.player_move(1))
        elif choice == "6":
            ui.say(combat.player_steady())
        elif choice == "7":
            key = self.pick_formation(combat)
            if key:
                ui.say(combat.player_formation(key))
        elif choice == "f":
            out = combat.player_flee()
            ui.say(out)
            if "__FLED__" in out:
                return "fled"
        return None

    def pick_formation(self, combat):
        p = self.player
        opts = []
        for i, (key, f) in enumerate(DATA.formations.items(), start=1):
            afford = p.qi >= f["qi"]
            note = f"{f['qi']} qi -- {f['description']}"
            opts.append((str(i), f["name"], afford,
                         note if afford else ui.c(f"{f['qi']} qi, you have "
                                                  f"{p.qi:.0f}", "grey")))
        opts.append(("x", "Never mind", True, ""))
        choice = ui.menu(opts, "lay > ")
        if choice == "x":
            return None
        return list(DATA.formations)[int(choice) - 1]

    def pick_treasure(self, treasures):
        p = self.player
        opts = []
        for i, t in enumerate(treasures, start=1):
            r = t.reading(p)
            if not r["usable"]:
                note = ui.c("beyond you entirely", "grey")
            else:
                control = ui.c(f"control {r['control']:.0%}", "byellow")
                note = f"gap +{r['gap']}  power x{5 ** r['gap']}  {control}"
            opts.append((str(i), t.name, r["usable"], note))
        opts.append(("x", "Never mind", True, ""))
        choice = ui.menu(opts, "activate > ")
        if choice == "x":
            return None
        return treasures[int(choice) - 1]

    # ---------- harvesting ----------

    def do_harvest(self, monster, ctx):
        """Offered at the kill, not filed away on the day menu.

        The action cost is the design (doc 09 and 11 -- harvesting competes with
        cultivating for the day), but the *decision* belongs here, while the
        player can still see how the fight went and what it cost the corpse.
        """
        p = self.player
        ui.header("the body", monster.display())

        # Preview what the fight already ruined, so the choice is informed.
        spoiled = set(ctx.get("damage_types", set()))
        if ctx.get("overkill"):
            spoiled.add("overkill")
        at_risk = sorted({
            DATA.materials[e["part"]]["name"]
            for e in monster.family["anatomy"]
            if spoiled.intersection(DATA.materials[e["part"]].get("ruined_by", []))
        })
        if at_risk:
            ui.say(ui.c(f"The way it died was hard on the "
                        f"{', '.join(n.lower() for n in at_risk)}.", "grey"))

        choice = ui.menu([
            ("1", "Strip the core and move on", True,
             ui.c("free", "grey")),
            ("2", "Take it apart properly", True,
             ui.c("costs an action", "byellow")),
            ("3", "Leave it", True, ""),
        ], "> ")

        if choice == "3":
            ui.say("\n  You leave it for whatever comes along next.")
            ui.pause()
            return

        quick = choice == "1"
        if quick:
            care, skill, label = 0.3, 0.35, "You cut the core out and go."
        else:
            care, skill, label = 1.0, 0.6, "It takes most of what is left of the day."

        mats, notes = monster.harvest(ctx, skill=skill, care=care,
                                      rng=self.rng, quick=quick)
        print()
        ui.say(label)
        for n in notes:
            print(ui.c(f"    {n}", "grey"))
        if not mats:
            print(ui.c("    Nothing usable comes off it.", "grey"))
        for m in mats:
            p.add_material(m)
            print(f"    {m['name']:<14} quality {m['quality']:.2f}  "
                  f"{DATA.element_name(dominant(m['affinity']))}")
        print()
        ui.say(f"{len(mats)} material{'s' if len(mats) != 1 else ''} taken.")
        ui.pause()
        if choice == "2":
            self.spend_action()

    # ---------- crafting ----------

    def do_bench(self):
        p = self.player
        benches = self.local_artisans()
        if not benches:
            return

        if len(benches) == 1:
            artisan = benches[0]
        else:
            opts = [(str(i), a.name, True, a.describe().split(" -- ", 1)[-1])
                    for i, a in enumerate(benches, start=1)]
            opts.append(("x", "Leave", True, ""))
            pick = ui.menu(opts, "whose bench > ")
            if pick == "x":
                return
            artisan = benches[int(pick) - 1]

        ui.header("the bench", artisan.describe())
        ui.say(f"They want {artisan.want}.")
        if not p.materials:
            ui.say("You have nothing to work with.")
            ui.pause()
            return

        opts = [(str(i), f"{DATA.forms[f]['name']}", True, DATA.forms[f]["description"])
                for i, f in enumerate(DATA.forms, start=1)]
        opts.append(("x", "Leave", True, ""))
        choice = ui.menu(opts, "form > ")
        if choice == "x":
            return
        form_key = list(DATA.forms)[int(choice) - 1]
        slots = DATA.forms[form_key]["slots"]

        chosen = []
        pool = p.flat_materials()
        while len(chosen) < slots and pool:
            opts = []
            for i, m in enumerate(pool, start=1):
                el = DATA.element_name(dominant(m["affinity"]))
                part = DATA.materials[m["part"]]
                tags = []
                if part.get("growth_bearing"):
                    tags.append("growth")
                if part.get("will_bearing"):
                    tags.append("will")
                if part.get("effects"):
                    tags.append(part["effects"][0]["type"])
                opts.append((str(i), f"{m['name']} ({el})",
                             True, f"q{m['quality']:.2f}  {' '.join(tags)}"))
            opts.append(("x", "Done" if chosen else "Cancel", True,
                         f"{len(chosen)}/{slots} slots used"))
            pick = ui.menu(opts, "material > ")
            if pick == "x":
                break
            m = pool.pop(int(pick) - 1)
            chosen.append(m)

            pv = preview(form_key, chosen, p)
            print()
            print(ui.c("  would produce:", "grey"))
            print(f"    affinity  {describe(pv['affinity'])}")
            print(f"    rank {pv['rank']}   power {pv['power']:.0f}   ward {pv['ward']:.0f}")
            syn_style = ("bgreen" if pv["synergy"] >= 1.2
                         else "byellow" if pv["synergy"] >= 0.6 else "bred")
            syn = ui.c(f"{pv['synergy']:.2f}x", syn_style)
            print(f"    for you   {syn}  ({pv['relation']})")

        if not chosen:
            return
        if p.spirit_stones < artisan.fee:
            ui.say("You cannot cover the fee.")
            ui.pause()
            return

        p.spirit_stones -= artisan.fee
        p.remove_materials(chosen)
        treasure, log = craft(form_key, chosen, p, artisan, self.rng)
        p.treasures.append(treasure)
        print()
        ui.say(log)
        print()
        self.show_treasure(treasure)
        if ui.menu([("y", "Equip it", True, ""), ("n", "Put it away", True, "")],
                   "> ") == "y":
            p.equip(treasure)
        self.spend_action()

    # ---------- inventory ----------

    def show_treasure(self, t):
        p = self.player
        r = t.reading(p)
        print(ui.c(f"  {t.name}", "bold"), ui.c(f"rank {t.rank} {t.form}", "grey"))
        print(f"    affinity  {describe(t.affinity)}")
        if r["gap"] > 0:
            control = ui.c(f"{r['control']:.0%}", "byellow")
            print(f"    {ui.c('OVERCAP', 'bred')}  gap +{r['gap']}  "
                  f"raw power {r['raw_power']:.0f}  control {control}")
        else:
            print(f"    power {r['power']:.0f}   ward {t.current_ward():.0f}   "
                  f"synergy {r['synergy']:.2f}x ({r['relation']})")
        if t.growth:
            print(ui.c(f"    growth: {t.growth_label()}", "grey"))
        if t.will:
            print(ui.c("    it is not inert", "magenta"))
        if t.description:
            print(ui.c(f"    {t.description}", "grey"))

    def do_inventory(self):
        p = self.player
        ui.header("what you carry")
        for t in p.treasures:
            eq = " (equipped)" if t in p.equipped.values() else ""
            print()
            self.show_treasure(t)
            if eq:
                print(ui.c("    equipped", "bgreen"))
        print()
        print(ui.c(f"  materials: {p.material_count()}", "grey"))
        for part, items in sorted(p.materials.items()):
            avg = sum(m["quality"] for m in items) / len(items)
            print(ui.c(f"    {DATA.materials[part]['name']:<14} x{len(items)}  "
                       f"avg quality {avg:.2f}", "grey"))
        ui.pause()

    # ---------- the review ----------

    def announce_review(self):
        """Fires once, on the breakthrough into Qi Awakened. Until now nothing
        has been urgent, which is deliberate -- the first realm is where you
        learn the systems without a clock on you."""
        if self.review:
            return
        cfg = DATA.events["cohort_review"]
        self.review = CohortReview(self.player.day, self.rng)
        ui.header("the board", cfg["name"].lower())
        ui.say(cfg["announcement"])
        if not self.rival_met:
            self.rival_met = True
            print()
            ui.say(self.rival.data["intro"])
        print()
        ui.say(ui.c(f"{cfg['days']} days. Top {cfg['promotion_places']} go up. "
                    f"Bottom {cfg['cut_places']} go home.", "byellow"))
        ui.pause()

    def do_review(self):
        p = self.player
        cfg = self.review.cfg
        out = self.review.resolve(p, self.rival, self.companions)

        ui.header(cfg["name"].lower(), "the board goes up at dawn")
        print()
        for e in out["board"]:
            mark = "  "
            style = None
            if e.get("player"):
                mark, style = "->", "bcyan"
            elif e.get("rival"):
                style = "white"
            elif e.get("companion"):
                style = "cyan"
            tag = ""
            if e["promoted"]:
                tag = ui.c("  inner court", "bgreen")
            elif e["cut"]:
                tag = ui.c("  sent home", "bred")
            name = ui.c(e["name"], style) if style else e["name"]
            print(f"  {mark} {e['place']:>2}. {name}{tag}")

        print()
        me = out["player"]
        rival_entry = out["rival"]
        if me["place"] < rival_entry["place"]:
            ui.say(self.rival.data["review_line_behind"])
        else:
            ui.say(self.rival.data["review_line_ahead"])

        print()
        if me["promoted"]:
            # Promotion is a gate, not an ending. The run continues upward.
            ui.say(ui.c("You are going up.", "bgreen"))
            p.spirit_stones += 250
            p.promoted = True
            p.location = "inner_court"
        elif me["cut"]:
            ui.say(ui.c("You are going home.", "bred"))
            self.ending = "cut"
        else:
            ui.say("You keep your place. That is all keeping your place is.")
            p.spirit_stones += 60
            self.ending = "kept"

        # Her result is the one the whole design has been pointing at.
        for comp, place, passed in out["companions"]:
            print()
            if passed:
                ui.say([
                    f"{comp.name} keeps her place.",
                    "",
                    "\"I know what tier I'm at,\" she says, when you find her "
                    "afterwards. \"I've known for weeks. I wanted to see if you did.\"",
                ])
            else:
                ui.say([
                    ui.c(f"{comp.name} does not.", "bred"),
                    "",
                    "She is not on the board long enough for anyone to read her "
                    "name properly. Six years, and the ink is still wet when they "
                    "take it down.",
                    "",
                    f"You were at the {ui.ordinal(p.tier)} tier of "
                    f"{p.realm_data()['name']} on the morning of the review. "
                    f"She was at the {ui.ordinal(comp.tier)} of Body Tempering, "
                    f"which is where she was in spring, and the spring before.",
                ])
                comp.depart([])
        ui.pause()

    # ---------- the trials ----------

    def announce_trials(self):
        if self.trials:
            return
        cfg = DATA.events["inner_trials"]
        self.trials = InnerTrials(self.player.day, self.rng)
        ui.header("the inner trials", "posted in the covered walk")
        ui.say(cfg["announcement"])
        ui.pause()

    def do_trials(self):
        p = self.player
        t = self.trials
        t.resolved = True
        bracket = t.bracket(self.rival if self.rival.realm >= 2 else None)

        ui.header("the inner trials", "three rounds, drawn on the morning")
        for i, duelist in enumerate(bracket, start=1):
            print()
            ui.rule()
            final = i == len(bracket)
            ui.say(ui.c(f"Round {i}{' -- the final' if final else ''}: "
                        f"{duelist.display()}", "bold"))
            if duelist.line:
                ui.say(ui.c(duelist.line, "grey"))

            # They patch you up between rounds. They cannot do anything about
            # your meridians -- so anything you reached for in round one is
            # still costing you in round three.
            p.hp = p.hp_max()
            p.qi = p.qi_max()
            if i > 1:
                ui.say(ui.c(f"An hour between bouts. Stability "
                            f"{p.stability:.0f}/{p.stability_max()}.", "grey"))
            ui.pause()

            combat = Combat(p, [duelist], self.companions, self.rng)
            result = self.combat_loop(combat, duelist)
            p.hp = max(1.0, p.hp)          # trials are not to the death

            if result != "won":
                t.eliminated = True
                print()
                ui.say([
                    f"{duelist.name} takes it.",
                    "",
                    "You are helped off the sand by two people whose names you "
                    "do not know, and the next bout starts before you are "
                    "properly out of the ring.",
                ])
                ui.pause()
                self.after_trials()
                return

        t.won = True
        self.offer_prize()
        self.after_trials()

    def offer_prize(self):
        """Act one ends here. It is a reward, and it is a trap, and the game
        does not distinguish between those two things out loud."""
        p = self.player
        prize = Treasure.from_data(DATA.events["inner_trials"]["prize"],
                                   provenance="won")
        ui.header("first frost", "presented on a stand, in front of everybody")
        ui.say([
            "You win the trials.",
            "",
            "They bring it out on a lacquered stand and an elder you have never "
            "spoken to says several true things about your discipline. The "
            "applause is genuine. Somebody you beat in the second round is "
            "clapping hardest.",
            "",
            "It is the most beautiful object you have ever been within reach of.",
        ])
        print()
        self.show_treasure(prize)
        print()
        ui.say(ui.c("You are at the third realm. It is at the fifth.", "grey"))

        choice = ui.menu([
            ("1", "Take it", True, "it is yours, you won it"),
            ("2", "Take it and leave it in the vault", True,
             ui.c("you will not carry it", "grey")),
        ], "> ")

        p.treasures.append(prize)
        prize.judge_provenance()
        if choice == "1":
            p.took_the_prize = "took"
            print()
            ui.say("You carry it out yourself. It is lighter than it looks, "
                   "which is the first lie it tells you.")
        else:
            p.took_the_prize = "refused"
            print()
            ui.say([
                "You sign for it and have it put back.",
                "",
                "Nobody says anything. Two people notice.",
            ])
        ui.pause()

    def after_trials(self):
        """Realm 3 is the end of the current build."""
        self.ending = "trials_won" if self.trials.won else "trials_lost"

    # ---------- breakthrough ----------

    def do_breakthrough(self):
        p = self.player
        odds = p.breakthrough_odds()
        ui.header("the step that is not a step",
                  f"{odds:.0%} by your own reckoning")
        ui.say([
            "You have been at the ninth tier for a while now. The qi has nowhere "
            "left to go inside you.",
            "",
            f"Foundation: {p.foundation_label()}.  Stability: "
            f"{p.stability:.0f}/{p.stability_max()}.",
        ])
        if ui.menu([("y", "Attempt it", True, ""),
                    ("n", "Not today", True, "")], "> ") != "y":
            return

        p.breakthrough_attempts += 1
        if self.rng.random() < odds:
            p.realm += 1
            p.tier = 1
            p.qi = 0
            p.stability = p.stability_max()
            p.hp = p.hp_max()
            ui.header(DATA.realm(p.realm)["name"].lower())
            ui.say(DATA.realm(p.realm)["flavor"])
            print()
            if p.realm == 2:
                ui.say(ui.c("Your affinity is no longer latent. Treasures "
                            "resonate now -- check what you are carrying. Not "
                            "all of it will still suit you.", "bgreen"))
                ui.pause()
                self.announce_review()
            elif p.realm == 3:
                ui.say(ui.c("You can draw on the room now. Formations are yours "
                            "-- they do not care how strong anything is, only "
                            "how much time it has.", "bgreen"))
                ui.pause()
                self.announce_trials()
        else:
            p.qi *= 0.55
            p.stability = max(0.0, p.stability - 30)
            ui.header("it does not take")
            ui.say([
                "The qi turns over once, finds the shape of you insufficient, "
                "and settles back.",
                "You lose a good deal of what you had gathered.",
            ])
        ui.pause()
        self.spend_action()
