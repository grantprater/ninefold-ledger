"""Companions. Doc sections 12 and 13.

A companion is action economy first and a relationship second, which is the
whole argument -- the player who treats them as a trophy still has a body in
the initiative order, but a body that is not really trying.

Neglect is tracked on two separate numbers. Relationship decays because you are
not there. Resentment accrues because she has her own realm to reach and is not
reaching it.
"""

import random

from .data import DATA
from .entities import Combatant


class Companion:
    def __init__(self, cid):
        d = DATA.companions[cid]
        self.id = cid
        self.data = d
        self.name = d["name"]
        self.affinity = dict(d["affinity"])
        self.realm = d["realm"]
        self.tier = d["tier"]
        self.relationship = float(d["relationship"])
        self.resentment = float(d["resentment"])
        self.goal_progress = float(d["goal"]["progress"])
        self.present = True
        self.days_since_seen = 0
        self.beats_fired = set()

    # ---------- combat ----------

    def effectiveness(self):
        """How hard she actually fights for you."""
        e = 0.5 + self.relationship / 200.0 - self.resentment / 110.0
        return max(0.28, min(1.15, e))

    def to_combatant(self):
        d = self.data
        hp = d["hp_base"] + 8 * self.tier
        return Combatant(
            name=self.name, hp=hp, hp_max=hp,
            speed=d["speed"], power=d["power"] + 1.5 * self.tier,
            affinity=self.affinity, band=1,
            preferred_band=d["preferred_band"],
            side="player", ref=self,
        )

    # ---------- daily upkeep ----------

    def idle_day(self, log):
        """Called on any day you did not spend time with her."""
        d = self.data
        self.days_since_seen += 1
        self.relationship = max(0.0, self.relationship - d["decay_per_idle_day"])
        self.resentment = min(100.0, self.resentment + d["resent_per_idle_day"])
        self._maybe_beat(log)

    def socialize(self, log, rng=None):
        rng = rng or random
        d = self.data
        self.days_since_seen = 0
        self.relationship = min(100.0, self.relationship + d["socialize_gain"])
        self.resentment = max(0.0, self.resentment - d["socialize_resent_relief"])
        self.goal_progress = min(d["goal"]["target"],
                                 self.goal_progress + d["goal"]["progress_per_help"])

        band = self._band()
        log.append(rng.choice(d["bands"][band]["lines"]))
        if self.goal_progress >= d["goal"]["target"]:
            self._advance_goal(log)

    def _band(self):
        for key in ("warm", "neutral", "cool"):
            if self.relationship >= self.data["bands"][key]["min_relationship"]:
                return key
        return "cool"

    def _advance_goal(self, log):
        if self.tier < 9:
            self.tier += 1
            self.goal_progress = 0.0
            log.append(f"[{self.name}] Tier {self.tier}. She does not make anything "
                       f"of it, which is how you know it mattered.")

    def _maybe_beat(self, log):
        """Resentment surfaces as dialogue before it surfaces as departure."""
        for beat in self.data["resentment_beats"]:
            if self.resentment >= beat["at"] and beat["at"] not in self.beats_fired:
                self.beats_fired.add(beat["at"])
                log.append(f"[{self.name}] {beat['line']}")

    def should_leave(self):
        return self.resentment >= self.data["leave_threshold"]

    def depart(self, log):
        self.present = False
        log.append("")
        log.append(self.data["departure"])

    # ---------- display ----------

    def status_line(self):
        d = self.data
        goal_pct = self.goal_progress / d["goal"]["target"] * 100
        return (f"{self.name}  bond {self.relationship:.0f}  "
                f"resentment {self.resentment:.0f}  "
                f"tier {self.tier}  her goal {goal_pct:.0f}%  "
                f"fighting at {self.effectiveness():.0%}")
