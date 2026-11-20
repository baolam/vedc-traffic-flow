"""Pieces shared by the DQN families (phase selection, cycle residual)."""
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
