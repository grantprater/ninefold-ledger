"""Loads every content file once and hands it out.

Nothing in the engine hardcodes content. If you want a new monster family, a new
form, or a new realm, it goes in data/ and this picks it up.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(name):
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


class GameData:
    def __init__(self):
        self.affinities = _load("affinities.json")
        self.realms = {r["realm"]: r for r in _load("realms.json")}
        self.materials = {k: v for k, v in _load("materials.json").items()
                          if not k.startswith("_")}
        self.families = {k: v for k, v in _load("families.json").items()
                         if not k.startswith("_")}
        self.regions = {r["id"]: r for r in _load("regions.json")}
        self.forms = {k: v for k, v in _load("forms.json").items()
                      if not k.startswith("_")}
        self.treasures = {t["id"]: t for t in _load("treasures.json")}
        self.companions = {c["id"]: c for c in _load("companions.json")}
        self.rivals = {k: v for k, v in _load("rivals.json").items()
                       if not k.startswith("_")}
        self.events = {k: v for k, v in _load("events.json").items()
                       if not k.startswith("_")}
        self.endings = {k: v for k, v in _load("endings.json").items()
                        if not k.startswith("_")}
        self.vignettes = {k: v for k, v in _load("vignettes.json").items()
                          if not k.startswith("_")}
        self.formations = {k: v for k, v in _load("formations.json").items()
                           if not k.startswith("_")}

    @property
    def elements(self):
        return self.affinities["elements"]

    def element_name(self, key):
        return self.affinities["display"][key]["name"]

    def element_glyph(self, key):
        return self.affinities["display"][key]["glyph"]

    def element_color(self, key):
        return self.affinities["display"][key]["color"]

    def realm(self, n):
        return self.realms[min(n, max(self.realms))]

    def unlocked(self, realm_n, flag):
        return self.realm(realm_n)["unlocks"].get(flag, False)


DATA = GameData()
