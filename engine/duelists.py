"""Cultivator opponents for the Inner Trials.

A duelist is not a beast. They hold a band by choice, they have an element that
answers them, and unlike a monster they will disengage and reposition rather
than run at you. Gu Wenshan enters as himself, using whatever realm and tier he
has actually reached on the clock -- he is not scaled to the player.
"""

import random

from .data import DATA
from .entities import Combatant


class Duelist:
    def __init__(self, name, realm, tier, affinity, line="", rng=None):
        rng = rng or random
        r = DATA.realm(realm)
        self.name = name
        self.realm = realm
        self.tier = tier
        self.affinity = dict(affinity)
        self.line = line

        # Inner court, and everyone entering has been preparing for months.
        # Tuned so a same-realm bout is decided by matchup and tactics rather
        # than by tier alone -- an unfavourable element should be losable.
        self.hp_max = (r["hp_base"] + r["hp_per_tier"] * tier) * 1.15
        self.speed = r["speed"] * rng.uniform(0.95, 1.08)
        self.power = (8 + r["hp_per_tier"] * 0.42 * tier) * 1.15

    @classmethod
    def from_data(cls, d, rng=None):
        return cls(d["name"], d["realm"], d["tier"], d["affinity"],
                   d.get("line", ""), rng)

    @classmethod
    def from_rival(cls, rival, rng=None):
        d = cls(rival.name, rival.realm, rival.tier, rival.affinity,
                "He has not asked you a question in three years.", rng)
        # He does nothing but this, and it shows in the only place it can.
        d.power *= 1.12
        return d

    def display(self):
        return f"{self.name} ({DATA.realm(self.realm)['name']} tier {self.tier})"

    def to_combatant(self):
        return Combatant(
            name=self.name, hp=self.hp_max, hp_max=self.hp_max,
            speed=self.speed, power=self.power, affinity=self.affinity,
            ward=0.0, band=2, preferred_band=1, ai="skirmish",
            side="enemy", ref=self,
        )
