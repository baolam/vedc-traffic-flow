"""Pieces shared by the DQN families (phase selection, cycle residual)."""
import os

import torch
from torch import nn


def optimize_step(ctx, loss):
    """One clipped Adam step on `loss`, with the hard target copy every target_every_updates steps."""
    if not torch.isfinite(loss):
        raise RuntimeError("Nonfinite training loss")
    ctx.optimizer.zero_grad()
    loss.backward()
    nn.utils.clip_grad_norm_(ctx.net.parameters(), ctx.recipe["grad_clip"])
    ctx.optimizer.step()
    ctx.counters["updates"] += 1
    if ctx.counters["updates"] % ctx.recipe["target_every_updates"] == 0:
        ctx.target.load_state_dict(ctx.net.state_dict())


def invalid_episode(ctx, error):
    """Record an invalid (collision/teleport) training episode; the episode is abandoned."""
    import json

    ctx.counters["invalid_episodes"] += 1
    with (ctx.output / "invalid-episodes.jsonl").open("a") as handle:
        handle.write(json.dumps(dict(episode=ctx.counters["episode"], reason=str(error))) + "\n")


_TAIL = tuple(float(x) for x in os.environ["EDGEFLOW_TAIL"].split(",")) if os.environ.get("EDGEFLOW_TAIL") else None


def tail_penalty(items):
    """Experiment: lambda * sum over approaches of the oldest wait beyond T seconds (per 60 s); 0 when disabled."""
    if _TAIL is None:
        return 0.0
    lam, limit = _TAIL
    return lam * sum(max(0.0, max(a["oldest_stopped_wait_s"], a["oldest_external_wait_s"]) - limit) / 60.0
                     for a in items)
