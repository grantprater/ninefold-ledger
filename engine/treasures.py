"""Treasures, and what happens when you reach past your realm. Doc sections 07, 08.

    gap     = treasure.rank - character.realm
    power   = base * 5^gap          full power, always
    control = 0.45^gap              but your grip collapses

Control is then modified by affinity match, the treasure's own disposition
toward you, and your current meridian integrity.
"""

import random
from dataclasses import dataclass, field

from .affinity import TABLE
from .data import DATA

SUCCESS, WILD, BACKLASH = "success", "wild", "backlash"

POWER_PER_GAP = 5.0
CONTROL_PER_GAP = 0.45
HARD_CAP_GAP = 5
STABILITY_COST_PER_GAP = 8.0


@dataclass
class Treasure:
    id: str
    name: str
    rank: int
    form: str
    affinity: dict
    power: float
    ward: float = 0.0
    effects: list = field(default_factory=list)
    growth: dict | None = None
    will: dict | None = None
    description: str = ""
    unique: bool = False
    provenance: str = "found"
    growth_stage: int = 0
    growth_xp: float = 0.0

    # ---------- construction ----------

    @classmethod
    def from_data(cls, tid, provenance="issued"):
        d = DATA.treasures[tid]
        return cls(
            id=d["id"], name=d["name"], rank=d["rank"], form=d["form"],
            affinity=dict(d["affinity"]), power=float(d["power"]),
            ward=float(d.get("ward", 0)), effects=list(d.get("effects", [])),
            growth=dict(d["growth"]) if d.get("growth") else None,
            will=dict(d["will"]) if d.get("will") else None,
            description=d.get("description", ""), unique=d.get("unique", False),
            provenance=provenance,
        )

    # ---------- disposition ----------

    @property
    def disposition(self):
        """How willing the treasure is. Non-sentient items are simply neutral."""
        if not self.will:
            return 0.0
        return self.will.get("disposition", 0.0)

    def adjust_disposition(self, delta):
        if self.will:
            self.will["disposition"] = max(-0.4, min(0.4, self.disposition + delta))

    def judge_provenance(self):
        """A sentient treasure has opinions about how it came to you.

        This is the hook doc section 09 relies on: gear taken off a corpse is
        exactly the gear that will not cooperate when you are desperate.
        """
        if not self.will:
            return None
        demands = self.will.get("demands", [])
        if "never_looted_from_corpse" in demands and self.provenance == "looted_corpse":
            # Deliberately short of lethal. -0.30 stacked with a bad affinity
            # match drove control to a flat 0%, which teaches "never loot"
            # instead of "looting costs you". It should hurt, not brick.
            self.adjust_disposition(-0.18)
            return ("It came off a body, and it knows it. Whatever is in the "
                    "hilt has decided about you already.")
        if self.provenance in ("gifted", "won", "crafted"):
            self.adjust_disposition(0.1)
            return None
        return None

    # ---------- power ----------

    def base_power(self):
        """Current power including any growth stages already reached."""
        p = self.power
        if self.growth:
            for stage in self.growth["stages"][:self.growth_stage]:
                p = stage.get("power", p)
        return p

    def current_ward(self):
        w = self.ward
        if self.growth:
            for stage in self.growth["stages"][:self.growth_stage]:
                w = stage.get("ward", w)
        return w

    def gap(self, character):
        return self.rank - character.realm

    def synergy(self, character):
        """Affinity match. Latent until Qi Awakened, so realm 1 is flat."""
        if not DATA.unlocked(character.realm, "treasure_resonance"):
            return 1.0
        return TABLE.synergy(character.affinity, self.affinity)

    def reading(self, character):
        """Everything the UI needs to explain this treasure to the player."""
        gap = self.gap(character)
        syn = self.synergy(character)
        power = self.base_power() * (POWER_PER_GAP ** gap if gap > 0 else 1.0)
        return {
            "gap": gap,
            "synergy": syn,
            "relation": (TABLE.relation_label(character.affinity, self.affinity)
                         if DATA.unlocked(character.realm, "treasure_resonance")
                         else "latent"),
            "power": power * (syn if gap <= 0 else 1.0),
            "raw_power": power,
            "control": self.control(character),
            "usable": gap < HARD_CAP_GAP,
            "overcap": gap > 0,
        }

    def control(self, character):
        """Odds of the activation going the way you intended."""
        gap = self.gap(character)
        if gap <= 0:
            return 1.0
        if gap >= HARD_CAP_GAP:
            return 0.0
        base = CONTROL_PER_GAP ** gap
        base *= 0.5 + self.synergy(character)
        base += self.disposition
        base *= character.stability_factor()
        base += character.insight_bonus()
        return max(0.0, min(0.99, base))

    # ---------- activation ----------

    def activate(self, character, rng=None):
        """Resolve an overcap use. Returns (outcome, damage, log lines)."""
        rng = rng or random
        gap = self.gap(character)
        r = self.reading(character)

        if gap >= HARD_CAP_GAP:
            return (None, 0.0, ["It does not answer. It is simply too far above you."])

        if gap <= 0:
            return (SUCCESS, r["power"], [])

        control = r["control"]
        roll = rng.random()
        log = []
        # Stability drains on every overcap use, success included.
        drain = STABILITY_COST_PER_GAP * gap
        character.stability = max(0.0, character.stability - drain)

        if roll <= control:
            if self.will:
                log.append(rng.choice(self.will.get("voice", ["It allows it."])))
            log.append(f"The {self.name} answers. Fully.")
            return (SUCCESS, r["raw_power"], log)

        # Half the remaining space is a wild activation; the rest is backlash.
        if roll <= control + (1.0 - control) * 0.5:
            log.append(f"The {self.name} goes off crooked -- most of it lands "
                       f"somewhere other than where you aimed.")
            character.stability = max(0.0, character.stability - drain * 0.5)
            return (WILD, r["raw_power"] * 0.35, log)

        recoil = r["raw_power"] * 0.25
        log.append(f"The {self.name} turns in your hands.")
        character.stability = max(0.0, character.stability - drain)
        character.take_backlash(recoil, gap, log, rng)
        return (BACKLASH, 0.0, log)

    # ---------- growth ----------

    def gain_growth(self, amount, log=None):
        if not self.growth:
            return
        self.growth_xp += amount
        stages = self.growth["stages"]
        while (self.growth_stage < len(stages)
               and self.growth_xp >= stages[self.growth_stage]["at"]):
            stage = stages[self.growth_stage]
            self.growth_stage += 1
            if log is not None:
                log.append(f"[{self.name}] {stage['name']}. {stage.get('note', '')}")

    def growth_label(self):
        if not self.growth:
            return None
        stages = self.growth["stages"]
        if self.growth_stage >= len(stages):
            return "fully realised"
        nxt = stages[self.growth_stage]
        return (f"{stages[self.growth_stage - 1]['name'] if self.growth_stage else 'unawakened'}"
                f" -- {self.growth_xp:.0f}/{nxt['at']} to {nxt['name']}")
