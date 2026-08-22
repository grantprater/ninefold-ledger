"""The player, and the shared combatant shape everything in a fight uses."""

import random
from dataclasses import dataclass, field

from .affinity import TABLE, describe
from .data import DATA

# Injuries are drawn from here on bad backlash. Each is persistent until healed.
INJURIES = [
    {"id": "cracked_meridian", "name": "Cracked Meridian",
     "note": "-20% qi from cultivation", "qi_mult": 0.8},
    {"id": "torn_sinew", "name": "Torn Sinew",
     "note": "-15% strike power", "power_mult": 0.85},
    {"id": "scattered_breath", "name": "Scattered Breath",
     "note": "-10% speed", "speed_mult": 0.9},
    {"id": "clouded_sea", "name": "Clouded Qi Sea",
     "note": "stability recovers slower", "stability_regen_mult": 0.6},
]


@dataclass
class Combatant:
    """Anything that can take a turn. Player, companion, and monster all use this."""
    name: str
    hp: float
    hp_max: float
    speed: float
    power: float
    affinity: dict = field(default_factory=dict)
    ward: float = 0.0
    band: int = 1
    preferred_band: int = 1
    ai: str = "aggressive"
    physical_resist: float = 0.0
    next_at: float = 0.0
    side: str = "enemy"
    ref: object = None          # back-reference to Player / Monster / Companion
    statuses: dict = field(default_factory=dict)

    @property
    def alive(self):
        return self.hp > 0

    def delay(self, cost):
        """Tick cost of an action. Higher speed means you come round sooner."""
        return cost * (100.0 / max(1.0, self.speed))

    def take(self, amount):
        amount = max(0.0, amount)
        self.hp = max(0.0, self.hp - amount)
        return amount


class Player:
    def __init__(self, name, affinity):
        self.name = name
        self.affinity = affinity          # {} means Void
        self.realm = 1
        self.tier = 1
        self.qi = 0.0
        self.day = 1
        self.actions_left = 3
        self.actions_per_day = 3

        r = DATA.realm(1)
        self.stability = float(r["stability_max"])
        self.foundation = 100.0
        self.hp = float(self.hp_max())

        self.treasures = []               # owned
        self.equipped = {}                # form-category -> Treasure
        self.materials = {}               # key -> list of material dicts
        self.injuries = []
        self.insights = []
        self.spirit_stones = 40
        self.location = "clay_terraces"
        self.log = []
        self.companions = []
        self.breakthrough_attempts = 0
        self.found_needle = False
        # Counted, never displayed, never rewarded. Read back only in endings.
        self.idle_days = 0
        self.seen_vignettes = set()
        self.promoted = False
        self.took_the_prize = None      # None / "took" / "refused"

    # ---------- derived stats ----------

    def realm_data(self):
        return DATA.realm(self.realm)

    def hp_max(self):
        r = self.realm_data()
        return r["hp_base"] + r["hp_per_tier"] * (self.tier - 1)

    def qi_max(self):
        r = self.realm_data()
        return r["qi_base"] + r["qi_per_tier"] * (self.tier - 1)

    def stability_max(self):
        return self.realm_data()["stability_max"]

    def qi_to_advance(self):
        r = self.realm_data()
        return r["qi_to_advance_tier"] * (r["qi_growth_per_tier"] ** (self.tier - 1))

    def set_realm(self, realm, tier=1):
        """Move to a realm/tier and refresh the pools that scale with it.

        Setting realm and tier directly without this leaves hp at the old
        realm's value against the new realm's maximum, which is a silent way to
        build a character who dies in two hits.
        """
        self.realm = realm
        self.tier = tier
        self.hp = float(self.hp_max())
        self.stability = float(self.stability_max())
        self.qi = 0.0

    def cultivation_yield(self):
        """Qi from one day of circulating. Scales with realm, or realm 2 is a
        wall -- its costs are 4x realm 1's and a flat yield never catches up."""
        y = self.realm_data()["cultivation_yield"]
        return y + self.tier * y * 0.2

    def base_speed(self):
        s = self.realm_data()["speed"]
        return s * self._injury_mult("speed_mult")

    def base_power(self):
        p = 5 + self.realm_data()["hp_per_tier"] * 0.4 * self.tier
        return p * self._injury_mult("power_mult")

    def _injury_mult(self, key):
        m = 1.0
        for inj in self.injuries:
            m *= inj.get(key, 1.0)
        return m

    def stability_factor(self):
        return max(0.25, self.stability / self.stability_max())

    def insight_bonus(self):
        return 0.0 if not self.insights else 0.05 * len(self.insights)

    # ---------- equipment ----------

    def weapon(self):
        return self.equipped.get("weapon")

    def total_ward(self):
        return sum(t.current_ward() for t in self.equipped.values())

    def equip(self, treasure):
        cat = DATA.forms[treasure.form]["category"]
        self.equipped[cat] = treasure

    def is_void(self):
        return TABLE.is_void(self.affinity)

    def affinity_label(self):
        return describe(self.affinity)

    # ---------- costs and harm ----------

    def take_backlash(self, recoil, gap, log, rng=None):
        """Stability, then injury, then the one that does not show up until later."""
        rng = rng or random
        if self.is_void():
            log.append("Void takes it. There is nothing in you for it to catch on.")
            return
        self.hp = max(1.0, self.hp - recoil)
        log.append(f"It costs you {recoil:.0f} health.")

        injury_chance = min(0.8, 0.25 * gap)
        if rng.random() < injury_chance:
            pool = [i for i in INJURIES if i["id"] not in {x["id"] for x in self.injuries}]
            if pool:
                inj = dict(rng.choice(pool))
                self.injuries.append(inj)
                log.append(f"Injury: {inj['name']} ({inj['note']}).")

        if gap >= 2 and rng.random() < 0.5:
            dmg = 2.0 + gap
            self.foundation = max(0.0, self.foundation - dmg)
            # Deliberately understated. It does not move a stat the player is
            # watching, and it will not matter until the Realm 5 tribulation.
            log.append("Something deeper than the injury does not settle back.")

    def foundation_label(self):
        f = self.foundation
        if f >= 95:
            return "Sound"
        if f >= 80:
            return "Marked"
        if f >= 60:
            return "Flawed"
        if f >= 35:
            return "Badly Flawed"
        return "Ruined"

    # ---------- progression ----------

    def cultivate(self, amount, log):
        amount *= self._injury_mult("qi_mult")
        self.qi += amount
        log.append(f"You circulate for a day. +{amount:.0f} qi.")
        while self.qi >= self.qi_to_advance() and self.tier < self.realm_data()["tiers"]:
            self.qi -= self.qi_to_advance()
            self.tier += 1
            self.hp = self.hp_max()
            log.append(f"Tier {self.tier} of {self.realm_data()['name']}.")
        if self.tier >= self.realm_data()["tiers"] and self.qi >= self.qi_to_advance():
            self.qi = self.qi_to_advance()
            log.append("You are as full as this realm can hold. "
                       "The next step is not a step.")

    def can_attempt_breakthrough(self):
        return (self.tier >= self.realm_data()["tiers"]
                and self.qi >= self.qi_to_advance()
                and self.realm + 1 in DATA.realms)

    def breakthrough_odds(self):
        """Foundation biases this. In the MVP the bias is small and survivable --
        it is the Realm 5 tribulation where it becomes a wall."""
        base = 0.62
        base += 0.03 * self.breakthrough_attempts        # you learn from failing
        base -= (100.0 - self.foundation) * 0.004
        base *= self.stability_factor()
        return max(0.05, min(0.95, base))

    def rest(self, log):
        regen = 22 * self._injury_mult("stability_regen_mult")
        self.stability = min(self.stability_max(), self.stability + regen)
        self.hp = min(self.hp_max(), self.hp + self.hp_max() * 0.35)
        log.append(f"You rest. Stability {self.stability:.0f}/{self.stability_max()}.")

    # ---------- materials ----------

    def add_material(self, mat):
        self.materials.setdefault(mat["part"], []).append(mat)

    def material_count(self):
        return sum(len(v) for v in self.materials.values())

    def flat_materials(self):
        out = []
        for part, items in sorted(self.materials.items()):
            for m in items:
                out.append(m)
        return out

    def remove_materials(self, chosen):
        for m in chosen:
            bucket = self.materials.get(m["part"], [])
            if m in bucket:
                bucket.remove(m)
            if not bucket:
                self.materials.pop(m["part"], None)

    def to_combatant(self):
        weapon = self.weapon()
        wp = 0.0
        if weapon:
            wp = weapon.reading(self)["power"] if weapon.gap(self) <= 0 else 0.0
        return Combatant(
            name=self.name, hp=self.hp, hp_max=self.hp_max(),
            speed=self.base_speed(), power=self.base_power() + wp,
            affinity=self.affinity, ward=self.total_ward(),
            band=1, preferred_band=0, side="player", ref=self,
        )
