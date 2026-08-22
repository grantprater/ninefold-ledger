"""Monsters compose rather than being written. Doc section 11.

    monster = Family x Affinity x Rank x Region

Family sets anatomy, combat role and stat shape; affinity sets damage type and
what the parts are made of; rank sets scale; region picks from a spawn table.
Nothing here is per-creature -- adding a family is a data edit.
"""

import random

from .data import DATA
from .entities import Combatant


class Monster:
    def __init__(self, family_key, affinity_key, rank, rng=None):
        rng = rng or random
        fam = DATA.families[family_key]
        realm = DATA.realm(rank)

        self.family_key = family_key
        self.family = fam
        self.affinity_key = affinity_key
        self.affinity = {affinity_key: 1.0}
        self.rank = rank
        self.name = rng.choice(fam["names"][affinity_key])
        self.trait = None

        tier = rng.randint(2, 7)
        self.hp_max = (realm["hp_base"] + realm["hp_per_tier"] * tier) * fam["hp_mult"] * 0.7
        self.speed = realm["speed"] * fam["speed_mult"]
        self.power = (6 + realm["hp_per_tier"] * 0.45 * tier) * fam["power_mult"] * 0.8
        self.physical_resist = fam.get("physical_resist", 0.0)

        self._maybe_trait(rng)

    def _maybe_trait(self, rng):
        """Traits change behaviour and loot together, not just numbers."""
        if rng.random() > 0.18:
            return
        trait = rng.choice([
            {"id": "ancient", "name": "Ancient", "hp": 1.5, "power": 1.2,
             "quality": 0.25, "note": "Older than it has any right to be."},
            {"id": "starving", "name": "Starving", "hp": 0.7, "power": 1.35,
             "quality": -0.15, "note": "Ribs showing. It will not disengage."},
            {"id": "twin_cored", "name": "Twin-Cored", "hp": 1.2, "power": 1.1,
             "quality": 0.15, "extra_core": True,
             "note": "Two hearts of qi, beating out of step."},
        ])
        self.trait = trait
        self.hp_max *= trait.get("hp", 1.0)
        self.power *= trait.get("power", 1.0)
        self.name = f"{trait['name']} {self.name}"

    def display(self):
        el = DATA.element_name(self.affinity_key)
        return f"{self.name} ({el} {self.family['name']}, rank {self.rank})"

    def to_combatant(self):
        return Combatant(
            name=self.name, hp=self.hp_max, hp_max=self.hp_max,
            speed=self.speed, power=self.power, affinity=self.affinity,
            ward=0.0, band=2, preferred_band=self.family["preferred_band"],
            ai=self.family["ai"], physical_resist=self.physical_resist,
            side="enemy", ref=self,
        )

    # ---------- harvesting ----------

    def harvest(self, kill_context, skill=0.5, care=1.0, rng=None, quick=False):
        """Anatomy is the loot table. How you killed it decides what survives.

        kill_context carries the damage types used and whether the killing blow
        was overkill -- see doc section 11, killing well vs looting well.

        quick=True is the free "cut the core out and go" option: it only reaches
        for core-slot parts, but it always gets them.
        """
        rng = rng or random
        out, notes = [], []
        ruined = set(kill_context.get("damage_types", set()))
        if kill_context.get("overkill"):
            ruined.add("overkill")

        for entry in self.family["anatomy"]:
            part_key = entry["part"]
            part = DATA.materials[part_key]
            if quick and part["slot"] != "core":
                continue
            if part_key == "core" and self.trait and self.trait.get("extra_core"):
                entry = dict(entry, qty=entry["qty"] + 1)

            chance = 1.0 if quick else entry["chance"] * (0.6 + 0.8 * skill) * care
            spoiled = ruined.intersection(part.get("ruined_by", []))
            if spoiled:
                chance *= 0.35

            for _ in range(entry["qty"]):
                if rng.random() > min(0.98, chance):
                    continue
                quality = (0.45 + 0.1 * self.rank
                           + rng.uniform(-0.12, 0.18)
                           + 0.3 * skill
                           + (self.trait or {}).get("quality", 0.0))
                if spoiled:
                    quality -= 0.3
                quality = max(0.1, min(1.6, quality))
                out.append({
                    "part": part_key,
                    "name": part["name"],
                    "affinity": dict(self.affinity),
                    "quality": quality,
                    "rank": self.rank,
                    "source": self.name,
                })

            if spoiled and entry["chance"] >= 0.4:
                why = "the burning" if "fire" in spoiled else "the way it came apart"
                notes.append(f"The {part['name'].lower()} did not survive {why}.")

        return out, notes


def spawn(region_id, rng=None):
    """Roll an encounter from a region's weighted spawn table."""
    rng = rng or random
    region = DATA.regions[region_id]
    table = region.get("spawns") or []
    if not table:
        # Settlements have no spawn table. The day menu gates on this, but a
        # new region added to data could miss the gate -- say so clearly.
        raise ValueError(
            f"region '{region_id}' ({region['name']}) has no spawns; "
            f"nothing to hunt here")
    pick = rng.choices(table, weights=[e["weight"] for e in table])[0]
    lo, hi = region["rank_range"]
    return Monster(pick["family"], pick["affinity"], rng.randint(lo, hi), rng)
