"""Preregistered plateau rule: checkpoints may improve slightly without resetting patience."""


class Plateau:
    def __init__(self, patience, rel=0.01, floor=1e-6):
        self.patience, self.rel, self.floor = patience, rel, floor
        self.best = self.anchor = None
        self.stale = 0

    def update(self, score, feasible=True):
        improved = feasible and (self.best is None or score < self.best)
        if improved:
            self.best = score
        if not feasible:
            self.stale += 1
        elif self.anchor is None or score <= self.anchor - self.rel * max(abs(self.anchor), self.floor):
            self.anchor, self.stale = score, 0
        else:
            self.stale += 1
        return dict(improved_best=bool(improved), stop=self.stale >= self.patience)

    def state(self):
        return dict(best=self.best, anchor=self.anchor, stale=self.stale)

    def load(self, state):
        self.best, self.anchor, self.stale = state["best"], state["anchor"], state["stale"]
