"""Layer-one affinity math. Design doc sections 05 and 06.

    match   = sum_ij  (A_i / |A|_1) * R_ij * (T_j / |T|_1)     in [-1, 1]
    synergy = clamp(0.2 + 1.3 * match, 0, 1.5)

R carries the wuxing cycles, so generation and destruction fall out of one
expression instead of needing special cases.

Note on normalization: this is an L1-weighted average, not L2 cosine. Cosine is
the intuitive reach here but it is wrong for this matrix -- because R has
positive off-diagonal entries, cosine lets match exceed 1.0 and a fire/wood
split build scores *higher* with a fire blade than a pure fire build does. That
deletes the dilution tradeoff entirely and makes fire+wood a free lunch.

Under L1, match is the weighted average relation of your affinity mix to the
treasure, so dilution always costs something -- but diluting toward a
generating element costs less than diluting toward a destroying one, which is a
better decision space than cosine gave us.
"""

from .data import DATA


class AffinityTable:
    def __init__(self, cfg):
        self.elements = cfg["elements"]
        vals = cfg["relation_values"]
        self.curve = cfg["synergy_curve"]
        self.void = cfg["void"]

        # R is symmetric -- synergy does not care which way a cycle points.
        # Combat does, so keep the directed pairs too.
        self.destroys = {tuple(p) for p in cfg["destroying"]}
        self.generates = {tuple(p) for p in cfg["generating"]}

        self.R = {a: {b: vals["unrelated"] for b in self.elements}
                  for a in self.elements}
        for e in self.elements:
            self.R[e][e] = vals["identity"]
        # Generation runs both ways: wood feeds fire, and fire is fed by wood.
        for a, b in cfg["generating"]:
            self.R[a][b] = vals["generating"]
            self.R[b][a] = vals["generating"]
        # Destruction poisons the pairing regardless of which way it points.
        for a, b in cfg["destroying"]:
            self.R[a][b] = vals["destroying"]
            self.R[b][a] = vals["destroying"]

    @staticmethod
    def magnitude(vec):
        """L1 weight. Zero means Void."""
        return sum(abs(w) for w in vec.values())

    def match(self, a_vec, t_vec):
        """Weighted average relation between two affinity mixes, in [-1, 1]."""
        ma, mt = self.magnitude(a_vec), self.magnitude(t_vec)
        if ma == 0 or mt == 0:
            return None  # a zero vector is Void, handled by synergy()
        total = 0.0
        for a_el, a_w in a_vec.items():
            row = self.R.get(a_el)
            if not row:
                continue
            for t_el, t_w in t_vec.items():
                total += (a_w / ma) * row.get(t_el, 0.0) * (t_w / mt)
        return total

    def synergy(self, a_vec, t_vec):
        """The multiplier applied to a treasure's base power."""
        m = self.match(a_vec, t_vec)
        if m is None:
            # Void: no match with anything, no opposition to anything.
            return self.void["flat_synergy"]
        c = self.curve
        return max(c["floor"], min(c["ceiling"], c["base"] + c["scale"] * m))

    def relation_label(self, a_vec, t_vec):
        m = self.match(a_vec, t_vec)
        if m is None:
            return "void"
        if m >= 0.95:
            return "identity"
        if m >= 0.25:
            return "generating"
        if m <= -0.25:
            return "destroying"
        return "unrelated"

    def is_void(self, vec):
        return self.magnitude(vec) == 0

    def directed(self, attacker_el, defender_el):
        """Which way a wuxing cycle points, for combat. Doc section 12."""
        if attacker_el is None or defender_el is None:
            return "neutral"
        if attacker_el == defender_el:
            return "same"
        if (attacker_el, defender_el) in self.destroys:
            return "overcomes"
        if (defender_el, attacker_el) in self.destroys:
            return "overcome_by"
        if ((attacker_el, defender_el) in self.generates
                or (defender_el, attacker_el) in self.generates):
            return "feeds"
        return "neutral"

    # How much damage a directed relation is worth. Using the element that
    # overcomes theirs is the single biggest tactical lever a low realm has.
    #
    # These were 1.6 / 0.55 -- a 2.9x swing, which is fine against monsters you
    # chose to hunt and wrong for a duel you were drawn into. At that spread a
    # hard-countered bout is decided before it starts and no amount of tactics
    # moves it. 2.07x still makes the matrix the biggest lever on the board
    # without making the draw the whole story.
    COMBAT_MULT = {
        "overcomes": 1.45,     # fire against metal
        "overcome_by": 0.7,    # fire against water
        "feeds": 0.9,          # fire against earth -- you are nourishing it
        "same": 0.75,          # it lives in this element
        "neutral": 1.0,
    }

    def combat_multiplier(self, attacker_el, defender_el):
        return self.COMBAT_MULT[self.directed(attacker_el, defender_el)]


def normalize(vec):
    """Scale a vector to unit weight-sum, dropping anything negligible."""
    vec = {k: v for k, v in vec.items() if v > 1e-9}
    total = sum(vec.values())
    if total == 0:
        return {}
    return {k: v / total for k, v in vec.items()}


def dominant(vec):
    if not vec:
        return None
    return max(vec.items(), key=lambda kv: kv[1])[0]


def describe(vec):
    if not vec:
        return "Void"
    parts = sorted(vec.items(), key=lambda kv: -kv[1])
    return "  ".join(f"{DATA.element_name(k)} {v * 100:.0f}%" for k, v in parts)


TABLE = AffinityTable(DATA.affinities)
