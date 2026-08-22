"""The rival and the cohort review. Rising action for doc section 01.

The rival is not a scripted wall. He runs the player's own progression maths on
the same clock, spending every day of it on cultivation, because he has nothing
else to spend days on. He is the branch where you optimised purely for power,
playing out beside you at full speed -- and the game never says so.

The review puts one deadline over three things at once: your standing, his, and
whether Shen Yaru keeps her place. That last one is the point. Her assessment
runs on the time you did or did not give her.
"""

import random

from .data import DATA


class Rival:
    def __init__(self, rid="gu_wenshan"):
        d = DATA.rivals[rid]
        self.id = rid
        self.data = d
        self.name = d["name"]
        self.affinity = dict(d["affinity"])
        self.realm = d["realm"]
        self.tier = d["tier"]
        self.qi = 0.0
        self.per_day = d["cultivations_per_day"]
        self.broke_through = False

    # ---------- the same maths the player uses ----------

    def realm_data(self):
        return DATA.realm(self.realm)

    def qi_to_advance(self):
        r = self.realm_data()
        return r["qi_to_advance_tier"] * (r["qi_growth_per_tier"] ** (self.tier - 1))

    def cultivation_yield(self):
        y = self.realm_data()["cultivation_yield"]
        return y + self.tier * y * 0.2

    def advance_day(self, rng=None):
        """One day of doing nothing but this. Returns a news line, or None."""
        rng = rng or random
        note = None
        self.qi += self.cultivation_yield() * self.per_day
        while self.qi >= self.qi_to_advance():
            self.qi -= self.qi_to_advance()
            if self.tier < self.realm_data()["tiers"]:
                self.tier += 1
            elif self.realm + 1 in DATA.realms:
                # He does not fail breakthroughs. He has never reached past his
                # realm for anything, so there is nothing wrong with his
                # foundation -- which is the joke, and nobody makes it.
                self.realm += 1
                self.tier = 1
                self.qi = 0.0
                self.broke_through = True
                note = self.data["breakthrough_news"]
            else:
                self.qi = self.qi_to_advance()
                break
        return note

    def standing(self):
        return score_of(self.realm, self.tier, self.qi, self.qi_to_advance())

    def status_line(self):
        return f"{self.name}  {self.realm_data()['name']} tier {self.tier}"

    def news(self, rng=None):
        return (rng or random).choice(self.data["news"])


def score_of(realm, tier, qi=0.0, need=1.0):
    """One comparable number. Realm dominates, then tier, then progress."""
    return realm * 10000 + tier * 1000 + (qi / max(1.0, need)) * 900


class CohortReview:
    """A deadline that lands on the player, the rival and the companion alike."""

    def __init__(self, start_day, rng=None):
        cfg = DATA.events["cohort_review"]
        self.cfg = cfg
        self.name = cfg["name"]
        self.start_day = start_day
        self.due_day = start_day + cfg["days"]
        self.resolved = False
        self.reminders_fired = set()
        rng = rng or random
        # Background cohort, so the board is a board and not three names.
        surnames = ["Ma", "Xu", "Peng", "Dai", "Lou", "Qin", "Shi", "Cao", "Tang"]
        given = ["Zhien", "Haoran", "Yuqi", "Suran", "Bingwen", "Lifen",
                 "Wenjing", "Zhaolu", "Meiying", "Kunpeng"]
        names = [f"{s} {g}" for s in surnames for g in given]
        rng.shuffle(names)

        c = cfg["cohort"]
        self.cohort = []
        for name in names[:cfg["cohort_size"]]:
            realm = 1 if rng.random() < c["realm_one_chance"] else 2
            lo, hi = c["realm_one_tiers"] if realm == 1 else c["realm_two_tiers"]
            self.cohort.append({"name": name,
                                "score": score_of(realm, rng.randint(lo, hi))})

    def days_left(self, today):
        return max(0, self.due_day - today)

    def due(self, today):
        return not self.resolved and today >= self.due_day

    def tick(self, today):
        """Returns a reminder line when one is newly due."""
        left = self.days_left(today)
        for r in self.cfg["reminders"]:
            if left <= r["at"] and r["at"] not in self.reminders_fired:
                self.reminders_fired.add(r["at"])
                return r["line"]
        return None

    # ---------- resolution ----------

    def companion_score(self, comp):
        """Her assessment runs on the time you gave her, and how she feels
        about the time you did not.

        This must be on the same scale as everyone else's standing -- she is
        being ranked on the same board, not against a private threshold.
        """
        base = score_of(comp.realm, comp.tier, comp.goal_progress, 100.0)
        return base - comp.resentment * 60

    def resolve(self, player, rival, companions):
        self.resolved = True
        board = list(self.cohort)
        board.append({"name": rival.name, "score": rival.standing(), "rival": True})
        board.append({
            "name": player.name,
            "score": score_of(player.realm, player.tier, player.qi,
                              player.qi_to_advance()),
            "player": True,
        })
        for c in companions:
            board.append({"name": c.name, "score": self.companion_score(c),
                          "companion": c})

        board.sort(key=lambda e: -e["score"])
        for i, e in enumerate(board, start=1):
            e["place"] = i

        cut_line = len(board) - self.cfg["cut_places"]
        for e in board:
            e["promoted"] = e["place"] <= self.cfg["promotion_places"]
            e["cut"] = e["place"] > cut_line

        outcomes = {"board": board}
        outcomes["player"] = next(e for e in board if e.get("player"))
        outcomes["rival"] = next(e for e in board if e.get("rival"))
        # She is cut by the same rule as everyone else. One board, one line.
        outcomes["companions"] = [
            (e["companion"], e["place"], not e["cut"])
            for e in board if e.get("companion")
        ]
        return outcomes
