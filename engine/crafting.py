"""Composition crafting. Doc section 10.

There are no recipes. You pick a form and feed materials into it:

    affinity_tags = normalize(sum mat.affinity * mat.quality * qty)
    rank          = f(highest_rank_input, total_quality)
    effects       = union of material hooks
    growth        = if any input is growth-bearing
    will          = only from intact soul-bearing material

The crafter does not change the average result. The crafter changes the spread.
"""

import json
import random
from pathlib import Path

from .affinity import TABLE, normalize, dominant
from .data import DATA, DATA_DIR
from .treasures import Treasure

with open(Path(DATA_DIR) / "artisans.json", encoding="utf-8") as fh:
    ARTISAN_POOL = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}


class Artisan:
    """A generated village craftsman. Fungible, and meant to be."""

    def __init__(self, rng=None):
        rng = rng or random
        self.name = (f"{rng.choice(ARTISAN_POOL['surnames'])} "
                     f"{rng.choice(ARTISAN_POOL['given'])}")
        if rng.random() < 0.4:
            self.name += f", {rng.choice(ARTISAN_POOL['titles'])}"
        self.skill = rng.uniform(0.25, 0.6)
        self.specialty = rng.choice(list(DATA.forms))
        self.element = rng.choice(DATA.elements)
        self.trait = rng.choice(ARTISAN_POOL["traits"])
        self.want = rng.choice(ARTISAN_POOL["wants"])
        self.fee = int(12 + 40 * self.skill)
        self.master = False
        self.disposition = 0.0

    def describe(self):
        return (f"{self.name} -- {self.trait['name']}, best with "
                f"{DATA.forms[self.specialty]['name'].lower()}s and "
                f"{DATA.element_name(self.element)}. "
                f"Skill {self.skill:.0%}. Fee {self.fee} stones.")

    def spread_for(self, form):
        """Low skill means a wide, low-ceilinged distribution."""
        s = 0.34 * (1.0 - self.skill) + 0.05 + self.trait["spread"]
        if form == self.specialty:
            s -= 0.05
        return max(0.03, s)

    def ceiling_for(self, form, element):
        c = 0.68 + 0.55 * self.skill + self.trait["ceiling"]
        if form == self.specialty:
            c += 0.08
        if element == self.element:
            c += 0.08
        if self.master and self.disposition > 0.5:
            c += 0.25          # inspired work: masters can exceed the normal ceiling
        return c


def preview(form_key, materials, character):
    """What this combination would produce, before committing to it."""
    form = DATA.forms[form_key]
    if not materials:
        return None

    vec, power, ward, effects = {}, 0.0, 0.0, []
    growth_bearing = will_bearing = False
    max_rank, total_q = 1, 0.0

    for m in materials:
        part = DATA.materials[m["part"]]
        q = m["quality"]
        total_q += q
        max_rank = max(max_rank, m["rank"])
        for el, w in m["affinity"].items():
            vec[el] = vec.get(el, 0.0) + w * q
        power += part["power"] * q
        ward += part["power"] * q * 0.5
        effects.extend(part.get("effects", []))
        growth_bearing |= part.get("growth_bearing", False)
        will_bearing |= part.get("will_bearing", False)

    tags = normalize(vec)
    avg_q = total_q / len(materials)
    rank = max_rank if avg_q >= 0.75 else max(1, max_rank - (0 if avg_q >= 0.5 else 1))

    return {
        "form": form_key,
        "affinity": tags,
        "rank": rank,
        "power": power * form["power_scale"],
        "ward": ward * form["ward_scale"],
        "effects": _merge_effects(effects),
        "growth": growth_bearing,
        "will": will_bearing,
        "avg_quality": avg_q,
        "synergy": TABLE.synergy(character.affinity, tags),
        "relation": TABLE.relation_label(character.affinity, tags),
    }


def _merge_effects(effects):
    merged = {}
    for e in effects:
        key = (e["hook"], e["type"])
        merged[key] = merged.get(key, 0) + e["magnitude"]
    return [{"hook": h, "type": t, "magnitude": m} for (h, t), m in merged.items()]


def craft(form_key, materials, character, artisan, rng=None):
    """Resolve a craft. Returns (Treasure, log lines)."""
    rng = rng or random
    p = preview(form_key, materials, character)
    form = DATA.forms[form_key]
    log = []

    element = dominant(p["affinity"])
    spread = artisan.spread_for(form_key)
    ceiling = artisan.ceiling_for(form_key, element)
    centre = 0.45 + 0.4 * artisan.skill

    roll = rng.gauss(centre, spread)
    roll = max(0.12, min(ceiling, roll))
    quality_mult = 0.55 + roll

    name = _name_for(form_key, element, roll, rng)
    t = Treasure(
        id=f"crafted_{rng.randrange(10**6)}",
        name=name,
        rank=p["rank"],
        form=form_key,
        affinity=p["affinity"],
        power=p["power"] * quality_mult,
        ward=p["ward"] * quality_mult,
        effects=p["effects"],
        growth=_growth_for(p, rng) if p["growth"] else None,
        will=_will_for(rng) if p["will"] else None,
        description=f"Made at {artisan.name}'s bench on day {character.day}.",
        provenance="crafted",
    )

    log.append(f"{artisan.name} works for the better part of two days.")
    if roll >= ceiling - 0.02:
        log.append("It is the best thing they have made in a season, and they know it.")
    elif roll <= 0.2:
        log.append("It holds together. That is the kindest thing to be said for it.")

    if t.growth:
        log.append("There is slack in it -- it will take more, later, if you feed it.")
    if t.will:
        log.append("Something came through with the soul remnant. It is not inert.")
    return t, log


def _growth_for(p, rng):
    base = p["power"]
    return {"xp": 0, "stages": [
        {"at": 45,  "name": "Settled",  "power": base * 1.35,
         "note": "It has stopped fighting your grip."},
        {"at": 150, "name": "Answering", "power": base * 1.9, "ward": p["ward"] * 1.4,
         "note": "It moves before you have quite decided to move it."},
    ]}


def _will_for(rng):
    return {
        "disposition": rng.uniform(-0.1, 0.15),
        "name": "unnamed",
        "demands": ["kill_cleanly"],
        "voice": ["It shifts, fractionally, toward the thing you are looking at.",
                  "There is a pause before it answers. There did not used to be."],
    }


ADJECTIVES = {
    "fire":  ["Kiln", "Ember", "Scorch"], "water": ["Ford", "Tide", "Rain"],
    "wood":  ["Bramble", "Green", "Root"], "metal": ["Filed", "Wire", "Grey"],
    "earth": ["Clay", "Cairn", "Dust"],
}
QUALITY_WORDS = [(0.85, "Fine"), (0.55, ""), (0.3, "Plain"), (0.0, "Poor")]


def _name_for(form_key, element, roll, rng):
    form = DATA.forms[form_key]["name"]
    adj = rng.choice(ADJECTIVES.get(element, ["Nameless"]))
    qual = next(w for threshold, w in QUALITY_WORDS if roll >= threshold)
    return " ".join(x for x in (qual, adj, form) if x)
