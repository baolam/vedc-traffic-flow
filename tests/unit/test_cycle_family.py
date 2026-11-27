import copy
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from contracts.benchmark import CYCLE_RECIPE, OBSERVATION_SPEC, UNIFIED_DQN
from src.control.cycle_dqn import GRID, NOOP, candidate_mask
from src.control.factory import create_controller
from src.control.unified_dqn import FEATURES, MAX_PHASES
from src.rl import cycle_family as cf
from tests.unit.test_cycle_controller import run_cycles

SLOT = 0 * MAX_PHASES + 1  # donor 0 -> recipient 1


def row(slot, reward, rows, terminal=True, dt=70.0):
    greens = cf.pad_greens([30, 30])
    return dict(s_rows=rows, s_greens=greens, s_p=2, action=slot, reward=reward, terminal=terminal, dt=dt,
                s2_rows=rows, s2_greens=greens, s2_p=2)


def make_ctx(replay, recipe=None, seed=0):
    torch.manual_seed(seed)
    net = cf.build_net()
    r = {**CYCLE_RECIPE, "batch": 64, "target_every_updates": 5, **(recipe or {})}
    return SimpleNamespace(
        recipe=r, rng=np.random.default_rng(seed), replay=replay, net=net, target=copy.deepcopy(net), device="cpu",
        optimizer=torch.optim.Adam(net.parameters(), lr=1e-2), counters=dict(updates=0),
        tensor=lambda x, dtype=torch.float32: torch.as_tensor(x, dtype=dtype))


def test_replay_ring_and_roundtrip():
    replay = cf.CycleReplay(3)
    rows = np.ones((MAX_PHASES, FEATURES), np.float32)
    for i in range(5):
        replay.add(**row(NOOP, float(i), rows))
    assert replay.size == 3 and sorted(replay.a["reward"].tolist()) == [2.0, 3.0, 4.0]
    other = cf.CycleReplay(3)
    other.load(replay.state())
    assert other.size == 3 and other.ptr == replay.ptr
    assert other.sample(8, np.random.default_rng(0))["s_rows"].shape == (8, MAX_PHASES, FEATURES)


def test_update_learns_the_rewarded_transfer_and_copies_the_target():
    rng = np.random.default_rng(3)
    rows = rng.random((MAX_PHASES, FEATURES)).astype(np.float32)
    replay = cf.CycleReplay(500)
    for _ in range(100):
        for slot, reward in ((SLOT, 1.0), (1 * MAX_PHASES + 0, -1.0), (NOOP, 0.0)):
            replay.add(**row(slot, reward, rows))
    ctx = make_ctx(replay)
    for _ in range(300):
        cf.update(ctx)
    assert ctx.counters["updates"] == 300
    q = cf.q_candidates(ctx.net, rows, cf.pad_greens([30, 30]), 2, "cpu").detach().numpy()
    masked = np.where(candidate_mask(cf.pad_greens([30, 30]), 2), q, -np.inf)
    assert int(np.argmax(masked)) == SLOT and q[SLOT] == pytest.approx(1.0, abs=0.2)
    assert all(torch.equal(a, b) for a, b in zip(ctx.net.state_dict().values(), ctx.target.state_dict().values()))


def test_bootstrap_uses_physical_time_discount():
    rows = np.zeros((MAX_PHASES, FEATURES), np.float32)
    replay = cf.CycleReplay(10)
    replay.add(**{**row(NOOP, 0.0, rows, terminal=False, dt=70.0)})
    ctx = make_ctx(replay)
    with torch.no_grad():
        for p in ctx.target.parameters():
            p.zero_()
        ctx.target[2].bias.fill_(10.0)  # every next-state candidate is worth 10
    ctx.recipe["batch"] = 1
    ctx.optimizer = torch.optim.SGD(ctx.net.parameters(), lr=0.0)  # inspect the target without moving
    seen = {}
    original = cf.optimize_step
    cf.optimize_step = lambda c, loss: seen.setdefault("loss", float(loss.detach()))
    try:
        cf.update(ctx)
    finally:
        cf.optimize_step = original
    expected = 10 * 0.99 ** (70 / 5)  # gamma_5 ** (dt / 5), not a flat 0.99
    q = float(cf.q_candidates(ctx.net, rows, cf.pad_greens([30, 30]), 2, "cpu")[NOOP])
    assert seen["loss"] == pytest.approx(float(torch.nn.functional.smooth_l1_loss(torch.tensor(q), torch.tensor(expected))), rel=1e-3)


@pytest.mark.parametrize("phases", [2, 4, 8])
def test_exported_artifact_matches_torch_and_runs_as_the_deployed_controller(tmp_path, phases):
    (tmp_path / "n.net").write_text("n")
    (tmp_path / "t.json").write_text("t")
    spec = dict(id="toy", network_path=str(tmp_path / "n.net"), topology_path=str(tmp_path / "t.json"))
    torch.manual_seed(1)
    artifact = cf.export(spec, "fair_cycle_unified", cf.build_net(), 17, tmp_path / "m.json")  # parity asserted inside
    assert artifact["architecture"] == UNIFIED_DQN["algorithms"]["fair_cycle_unified"][0]
    controller = create_controller("fair_cycle_unified", model_path=str(tmp_path / "m.json"))
    greens = [g for _, g, _ in run_cycles(controller, phases)[:phases]]
    assert all(10 <= g <= 60 for g in greens) and OBSERVATION_SPEC["max_phases"] == MAX_PHASES and GRID == 65
