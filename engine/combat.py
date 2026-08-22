"""Tick-based combat. Doc section 12.

Every action has a time cost; whoever has the lowest accumulated time acts next.
The realm gap is therefore felt as action frequency rather than damage -- a
realm 2 monster (speed 300) simply acts three times per action of a realm 1
player (speed 100). Companions are literally action economy.
"""

import random

from .affinity import TABLE, dominant
from .data import DATA

CLOSE, MID, FAR = 0, 1, 2
BAND_NAMES = {CLOSE: "Close", MID: "Mid", FAR: "Far"}

COST_STRIKE = 100
COST_TECHNIQUE = 110
COST_TREASURE = 130
COST_MOVE = 55
COST_STEADY = 90
COST_FLEE = 100

# A strike loses force at range; a technique does not care as much.
BAND_PENALTY = {0: 1.0, 1: 0.55, 2: 0.0}


class Combat:
    def __init__(self, player, monsters, companions=(), rng=None):
        self.rng = rng or random
        self.player = player
        self.clock = 0.0
        self.log = []
        self.round_actions = 0

        self.actors = []
        pc = player.to_combatant()
        pc.band = MID
        self.actors.append(pc)
        self.pc = pc

        for comp in companions:
            c = comp.to_combatant()
            c.band = MID
            self.actors.append(c)

        for m in monsters:
            mc = m.to_combatant()
            mc.band = FAR
            self.actors.append(mc)

        for a in self.actors:
            a.next_at = a.delay(50)   # small stagger so speed matters immediately

        # Harvest bookkeeping -- what the kill did to the corpse.
        self.damage_types = set()
        self.overkill = False
        self.rounds = 0

        # Realm 3 formations. These sit on the field, not on a combatant.
        self.field = []

    # ---------- state ----------

    @property
    def enemies(self):
        return [a for a in self.actors if a.side == "enemy" and a.alive]

    @property
    def allies(self):
        return [a for a in self.actors if a.side == "player" and a.alive]

    def is_over(self):
        return not self.enemies or not self.pc.alive

    def player_won(self):
        return not self.enemies and self.pc.alive

    def next_actor(self):
        """Advance the clock to whoever comes round next."""
        live = [a for a in self.actors if a.alive]
        if not live:
            return None
        nxt = min(live, key=lambda a: a.next_at)
        self.clock = nxt.next_at
        return nxt

    def spend(self, actor, cost):
        # A binding mesh makes everything the enemy does cost more time. This
        # is the only lever in the game that answers a realm gap directly,
        # because the realm gap *is* action frequency.
        if actor.side == "enemy":
            cost *= 1.0 + self.field_value("slow")
        actor.next_at = self.clock + actor.delay(cost)
        self.rounds += 1
        if actor.side == "player":
            regen = self.field_value("qi_regen")
            if regen and actor is self.pc:
                self.player.qi = min(self.player.qi_max(), self.player.qi + regen)

    # ---------- formations ----------

    def field_value(self, kind):
        """Total magnitude of live formations of a given kind."""
        return sum(f["magnitude"] for f in self.field
                   if f["type"] == kind and f["expires_at"] > self.clock)

    def active_formations(self):
        return [f for f in self.field if f["expires_at"] > self.clock]

    def player_formation(self, key):
        out = []
        if not DATA.unlocked(self.player.realm, "world_energy"):
            out.append("You cannot feel the room yet. Only what is inside you.")
            return out
        f = DATA.formations[key]
        if self.player.qi < f["qi"]:
            out.append(f"Not enough qi -- {f['name']} needs {f['qi']}.")
            return out
        self.player.qi -= f["qi"]
        eff = f["effect"]
        self.field.append({
            "name": f["name"],
            "type": eff["type"],
            "magnitude": eff["magnitude"],
            "expires_at": self.clock + f["duration"],
        })
        out.append(f["line"])
        self.spend(self.pc, f["setup_ticks"])
        return out

    def initiative_preview(self, limit=6):
        """Who acts next, and how often. This is where the realm gap is visible."""
        sim = [(a, a.next_at) for a in self.actors if a.alive]
        out = []
        for _ in range(limit):
            a, t = min(sim, key=lambda x: x[1])
            out.append(a)
            sim = [(x, t + x.delay(COST_STRIKE) if x is a else y) for x, y in sim]
        return out

    # ---------- resolution ----------

    def _damage(self, attacker, target, power, element=None, physical=True):
        mult = 1.0
        if element:
            mult = TABLE.combat_multiplier(element, dominant(target.affinity))
        raw = power * mult * self.rng.uniform(0.88, 1.12)
        if physical:
            raw *= 1.0 - target.physical_resist
        ward = target.ward
        if target.side == "enemy":
            ward *= max(0.0, 1.0 - self.field_value("ward_break"))
        dealt = target.take(max(1.0, raw - ward))
        return dealt, mult

    def _record_kill_context(self, target, dealt, element):
        if element:
            self.damage_types.add(element)
        if not target.alive and dealt > target.hp_max * 0.4:
            self.overkill = True

    def _relation_note(self, mult):
        if mult >= 1.5:
            return " It overcomes them."
        if mult <= 0.6:
            return " Their element eats most of it."
        if mult <= 0.9:
            return " They barely mind."
        return ""

    # ---------- player actions ----------

    def player_strike(self, target):
        out = []
        pen = BAND_PENALTY[self.pc.band]
        if pen == 0.0:
            out.append("Too far to reach. You need to close first.")
            return out
        weapon = self.player.weapon()
        element = dominant(weapon.affinity) if (
            weapon and DATA.unlocked(self.player.realm, "treasure_resonance")) else None
        dealt, mult = self._damage(self.pc, target, self.pc.power * pen, element)
        self._record_kill_context(target, dealt, element)
        if weapon:
            weapon.gain_growth(dealt * 0.12, out)
        out.append(f"You strike {target.name} for {dealt:.0f}."
                   + self._relation_note(mult)
                   + ("" if pen == 1.0 else " (reaching, at mid range)"))
        self.spend(self.pc, COST_STRIKE)
        self._check_death(target, out)
        return out

    def player_technique(self, target):
        out = []
        if not DATA.unlocked(self.player.realm, "elemental_technique"):
            out.append("Your affinity is still latent. There is nothing to send.")
            return out
        cost = 12
        if self.player.qi < cost:
            out.append("Not enough qi.")
            return out
        if self.pc.band == FAR:
            out.append("Too far. The technique disperses before it arrives.")
            return out
        self.player.qi -= cost
        element = dominant(self.player.affinity)
        power = self.pc.power * 1.15
        dealt, mult = self._damage(self.pc, target, power, element, physical=False)
        self._record_kill_context(target, dealt, element)
        el_name = DATA.element_name(element) if element else "Void"
        out.append(f"{el_name} answers you. {target.name} takes {dealt:.0f}."
                   + self._relation_note(mult))
        self.spend(self.pc, COST_TECHNIQUE)
        self._check_death(target, out)
        return out

    def player_treasure(self, treasure, target):
        out = []
        outcome, power, log = treasure.activate(self.player, self.rng)
        out.extend(log)
        if outcome is None:
            return out
        if outcome != "backlash" and power > 0:
            element = dominant(treasure.affinity)
            dealt, mult = self._damage(self.pc, target, power, element, physical=False)
            self._record_kill_context(target, dealt, element)
            out.append(f"{target.name} takes {dealt:.0f}." + self._relation_note(mult))
            self._check_death(target, out)
        self.pc.hp = self.player.hp = min(self.player.hp, self.pc.hp)
        self.spend(self.pc, COST_TREASURE)
        return out

    def player_move(self, delta):
        new = max(CLOSE, min(FAR, self.pc.band + delta))
        if new == self.pc.band:
            return ["There is nowhere further to go that way."]
        self.pc.band = new
        self.spend(self.pc, COST_MOVE)
        return [f"You shift to {BAND_NAMES[new].lower()} range."]

    def player_steady(self):
        gain = 14
        self.player.stability = min(self.player.stability_max(),
                                    self.player.stability + gain)
        self.spend(self.pc, COST_STEADY)
        return [f"You settle your breathing. Stability "
                f"{self.player.stability:.0f}/{self.player.stability_max()}."]

    def player_flee(self):
        fastest = max((e.speed for e in self.enemies), default=1)
        odds = min(0.9, 0.35 + 0.5 * (self.pc.speed / max(1.0, fastest))
                   + 0.15 * self.pc.band)
        self.spend(self.pc, COST_FLEE)
        if self.rng.random() < odds:
            self.fled = True
            return ["You break away and do not look back.", "__FLED__"]
        return ["You turn to run and it is faster than you."]

    # ---------- ai ----------

    def ai_action(self, actor):
        out = []
        if actor.side == "player":
            return self._companion_action(actor, out)

        targets = self.allies
        if not targets:
            return out
        # Companions draw fire, which is part of why they matter.
        target = self.rng.choice(targets) if len(targets) > 1 and self.rng.random() < 0.4 \
            else min(targets, key=lambda a: a.hp)

        want = actor.preferred_band
        if actor.band != want and self.rng.random() < 0.55:
            actor.band += 1 if want > actor.band else -1
            self.spend(actor, COST_MOVE)
            return [f"{actor.name} shifts to {BAND_NAMES[actor.band].lower()} range."]

        reach = BAND_PENALTY[abs(actor.band - target.band)] if actor.band != target.band else 1.0
        if reach == 0.0:
            actor.band += 1 if target.band > actor.band else -1
            self.spend(actor, COST_MOVE)
            return [f"{actor.name} closes."]

        element = dominant(actor.affinity)
        dealt, mult = self._damage(actor, target, actor.power * reach, element)
        out.append(f"{actor.name} hits {target.name} for {dealt:.0f}."
                   + self._relation_note(mult))
        if target is self.pc:
            self.player.hp = self.pc.hp
        self.spend(actor, COST_STRIKE)
        self._check_death(target, out)
        return out

    def _companion_action(self, actor, out):
        comp = actor.ref
        enemies = self.enemies
        if not enemies:
            return out
        target = min(enemies, key=lambda e: e.hp)
        effectiveness = comp.effectiveness() if comp else 1.0
        element = dominant(actor.affinity)
        dealt, mult = self._damage(actor, target, actor.power * effectiveness, element)
        line = f"{actor.name} hits {target.name} for {dealt:.0f}."
        if effectiveness < 0.7:
            line += " She is not really trying."
        out.append(line + self._relation_note(mult))
        self.spend(actor, COST_STRIKE)
        self._check_death(target, out)
        return out

    def _check_death(self, target, out):
        if target.alive:
            return
        if target.side == "enemy":
            out.append(f"{target.name} goes down.")
        else:
            out.append(f"{target.name} is down.")
            if target is self.pc:
                self.player.hp = 0.0

    def kill_context(self):
        return {"damage_types": set(self.damage_types),
                "overkill": self.overkill,
                "rounds": self.rounds}
