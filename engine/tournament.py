"""The Inner Trials. Doc section 01, rising action, realm 3.

The second rung of the ladder. Where the review was a comparison against a
board, this is a contest against a person -- zero-sum, public, and named. And
where the review's stake was failing to gain, the stake here is losing in front
of everyone to somebody who then has nothing to say about it.

The prize is the point. It is rank five, presented on a stand, for being
excellent, and it will maim anyone at the third realm who reaches for it. Act
one ends when the player accepts it.
"""

import random

from .data import DATA
from .duelists import Duelist


class InnerTrials:
    def __init__(self, start_day, rng=None):
        cfg = DATA.events["inner_trials"]
        self.cfg = cfg
        self.name = cfg["name"]
        self.start_day = start_day
        self.due_day = start_day + cfg["days"]
        self.resolved = False
        self.reminders_fired = set()
        self.round = 0
        self.eliminated = False
        self.won = False
        self.rng = rng or random

    def days_left(self, today):
        return max(0, self.due_day - today)

    def due(self, today):
        return not self.resolved and today >= self.due_day

    def tick(self, today):
        left = self.days_left(today)
        for r in self.cfg["reminders"]:
            if left <= r["at"] and r["at"] not in self.reminders_fired:
                self.reminders_fired.add(r["at"])
                return r["line"]
        return None

    def bracket(self, rival):
        """Earlier rounds are drawn from the pool; the final is him, if he is
        still standing. He is not scaled to the player -- he arrives at
        whatever realm and tier the clock actually gave him."""
        pool = list(self.cfg["opponents"])
        self.rng.shuffle(pool)
        rounds = [Duelist.from_data(d, self.rng)
                  for d in pool[:self.cfg["rounds"] - 1]]
        rounds.sort(key=lambda d: (d.realm, d.tier))
        if rival:
            rounds.append(Duelist.from_rival(rival, self.rng))
        else:
            rounds.append(Duelist.from_data(pool[-1], self.rng))
        return rounds
