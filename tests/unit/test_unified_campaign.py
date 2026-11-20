import json

import pytest

from src.benchmark.unified_campaign import aggregate, main, with_models

TEST_SEEDS = [1, 2]


def row(map_id, case, kind, seed, delay, learner=None, valid=True):
    controller = dict(type=kind, **({"learner_seed": learner} if learner is not None else {}))
    return dict(topology_id=map_id, scenario=case, controller=controller, seed=seed, valid=valid,
                delay_per_scheduled_s=delay)


def learned_rows(map_id, case, kind, by_learner):
    return [row(map_id, case, kind, s, d + s, learner) for learner, d in by_learner.items() for s in TEST_SEEDS]


def test_aggregate_two_level_mean_and_reference_ratio():
    rows = [row("m", "c", "fixed_time", s, 100) for s in TEST_SEEDS]
    rows += learned_rows("m", "c", "phase_dqn_unified", {17: 40.0, 29: 50.0, 43: 60.0})
    out = aggregate(rows, TEST_SEEDS)
    e = next(x for x in out["entries"] if x["controller"] == "phase_dqn_unified")
    assert e["learned"] and e["n_complete"] == 3
    assert e["per_seed"]["17"]["mean_delay_s"] == pytest.approx(41.5)  # mean over the two test seeds
    assert e["mean_delay_s"] == pytest.approx(51.5)
    assert e["std_across_training_seeds"] == pytest.approx(10.0)
    lo, hi = e["ci95_t_over_training_seeds"]
    assert lo < 51.5 < hi
    assert e["relative_to_fixed_time"] == pytest.approx(0.515)
    ft = next(x for x in out["entries"] if x["controller"] == "fixed_time")
    assert not ft["learned"] and ft["std_across_training_seeds"] is None and ft["ci95_t_over_training_seeds"] is None


def test_incomplete_or_invalid_training_seed_is_kept_but_not_averaged_in():
    rows = learned_rows("m", "c", "shared_dqn_unified", {17: 40.0, 29: 50.0})
    rows[-1]["valid"] = False  # seed 29 has an invalid test run
    rows.pop(0)  # seed 17 has only one of two test seeds
    e = aggregate(rows, TEST_SEEDS)["entries"][0]
    assert e["n_complete"] == 0 and e["mean_delay_s"] is None
    assert e["per_seed"]["17"]["n_runs"] == 1 and e["per_seed"]["29"]["n_valid"] == 1


def test_equal_map_aggregate_requires_every_map():
    rows = []
    for m, base in (("m1", 100), ("m2", 200)):
        rows += [row(m, "c", "fixed_time", s, base) for s in TEST_SEEDS]
    rows += learned_rows("m1", "c", "phase_dqn_unified", {17: 48.5})  # mean 50 -> ratio .5
    rows += learned_rows("m1", "c", "presslight_unified", {17: 48.5})
    rows += learned_rows("m2", "c", "presslight_unified", {17: 98.5})  # mean 100 -> ratio .5
    out = aggregate(rows, TEST_SEEDS)["equal_map_relative_delay"]
    assert "phase_dqn_unified" not in out  # missing m2
    assert out["presslight_unified"] == pytest.approx(0.5)


def test_freeze_refuses_incomplete_training(tmp_path):
    suite = dict(workers=1, maps=[dict(id="m", cases=["c"])])
    with pytest.raises(ValueError, match="Training incomplete"):
        with_models(suite, tmp_path, ["phase_dqn_unified"], [17])


def test_with_models_keeps_unselected_runs_visible(tmp_path):
    suite = dict(workers=1, maps=[dict(id="m", cases=["c"], extra_controllers=[dict(type="fair_cycle")])])
    for seed, selected in ((17, dict(episode=4, score=1.0, path="/p.json")), (29, None)):
        d = tmp_path / "training" / "m" / "phase_dqn_unified" / str(seed)
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps(dict(status="selected" if selected else "no_feasible_checkpoint",
                                                       stop_reason="plateau", converged=bool(selected),
                                                       counters={}, selected=selected)))
    out, runs = with_models(suite, tmp_path, ["phase_dqn_unified"], [17, 29])
    extras = out["maps"][0]["extra_controllers"]
    assert [c["type"] for c in extras] == ["fair_cycle", "phase_dqn_unified"] and extras[1]["learner_seed"] == 17
    assert runs["m/phase_dqn_unified/29"]["status"] == "no_feasible_checkpoint"  # reported, not dropped
    assert "learner_seed" not in suite["maps"][0]["extra_controllers"][0]  # input suite untouched


def test_test_split_only_for_evaluate_and_report(tmp_path):
    prepared = tmp_path / "p.json"
    prepared.write_text(json.dumps(dict(workers=1, maps=[])))
    with pytest.raises(ValueError, match="test split"):
        main(["--prepared", str(prepared), "--root", str(tmp_path / "r"), "--stage", "train", "--split", "test"])


def test_unevaluated_training_seed_is_listed_with_its_status():
    rows = learned_rows("m", "c", "phase_dqn_unified", {17: 40.0})
    training = {"m/phase_dqn_unified/17": dict(status="selected"),
                "m/phase_dqn_unified/29": dict(status="no_feasible_checkpoint")}
    e = aggregate(rows, TEST_SEEDS, training=training)["entries"][0]
    assert set(e["per_seed"]) == {"17", "29"} and e["n_complete"] == 1
    assert e["per_seed"]["29"]["status"] == "no_feasible_checkpoint" and e["per_seed"]["29"]["mean_delay_s"] is None


def test_test_split_rejects_protocol_overrides(tmp_path):
    prepared = tmp_path / "p.json"
    prepared.write_text(json.dumps(dict(workers=1, maps=[])))
    with pytest.raises(ValueError, match="frozen protocol"):
        main(["--prepared", str(prepared), "--root", str(tmp_path / "r"), "--stage", "evaluate",
              "--split", "test", "--demand-s", "60"])


def fake_scheduler(monkeypatch, behaviour):
    import src.benchmark.scheduling as scheduling
    monkeypatch.setattr(scheduling, "run_tasks", lambda tasks, workers=4, continue_on_error=False: behaviour(tasks))


def mapping(tmp_path):
    topology = tmp_path / "t.json"
    topology.write_text(json.dumps(dict(nodes=[dict(node_id="J1", phases=[{}, {}])])))
    return dict(id="m", topology_path=str(topology), network_path="n", cases=["balanced"])


def test_calibration_treats_invalid_runs_under_load_as_unstable(tmp_path, monkeypatch):
    from src.benchmark.calibration import calibrate

    def behaviour(tasks):
        load = tasks[0][1]["intensity"]
        return [None if load > 1 else dict(scheduled=10, completed=10, delay_per_scheduled_s=1.0) for _ in tasks]

    fake_scheduler(monkeypatch, behaviour)
    m = calibrate(mapping(tmp_path), tmp_path, dict(type="fixed_time"))
    assert 0 < m["intensity_by_case"]["balanced"] <= 1


def test_tuning_keeps_valid_candidates_and_falls_back_when_none(tmp_path, monkeypatch):
    from src.benchmark.unified_campaign import calibrate_then_tune

    def run(delay_by_green, fail_all=False):
        def behaviour(tasks):
            splits = tasks[0][0]["controller"].get("parameters", {}).get("phase_splits")
            if splits is None:  # calibration probe: stable up to load 1, invalid beyond
                ok = tasks[0][1]["intensity"] <= 1
                return [dict(scheduled=10, completed=10, delay_per_scheduled_s=1.0) if ok else None for _ in tasks]
            green = splits["J1"][0]
            if fail_all or green == 10:
                return [None for _ in tasks]
            return [dict(scheduled=10, completed=10, delay_per_scheduled_s=delay_by_green[green]) for _ in tasks]
        return behaviour

    fake_scheduler(monkeypatch, run({20: 50.0, 30: 40.0}))
    m = calibrate_then_tune(mapping(tmp_path), tmp_path, 1)
    assert m["controller_overrides"]["fixed_time"]["parameters"]["phase_splits"]["J1"] == [30, 30]
    assert [t["green_s"] for t in m["fixed_time_tuning"]] == [20, 30]  # green 10 was invalid, dropped
    fake_scheduler(monkeypatch, run({}, fail_all=True))
    assert calibrate_then_tune(mapping(tmp_path), tmp_path, 1)["controller_overrides"] == {}
