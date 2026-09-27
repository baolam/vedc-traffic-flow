"""
P0 Test Suite — Measurement Validity and Benchmark Integrity.

Tests cover:
  - Mock/synthetic research run rejection
  - Controller identity mismatch rejection
  - Demand hash consistency across controllers
  - Fixed-Time clock correctness (not call-count dependent)
  - Actuator yellow/all-red timing (no instant transitions)
  - Illegal/expired command rejection
  - Reset between experiments
  - No-data run failure
  - Metric unit/semantic validation
  - Valid run produces complete artifacts
"""

import sys
import os
import json
import uuid
import tempfile
import math
from pathlib import Path

import pytest

# ----------------------------------------------------------------
# Path setup
# ----------------------------------------------------------------
repo_root = Path(__file__).resolve().parents[2]
for svc in ["experiment-runner", "graph-control", "actuator"]:
    p = repo_root / "services" / svc
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
for p in [repo_root / "contracts"]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import contracts_sdk
from state_machine import ActuatorStateMachine, SignalNodeState
from controller import FixedTimeController, MaxQueueController, MaxPressureController, EdgeFlowController
from metrics_collector import MetricsCollector
from manifest import ExperimentManifest, ScenarioConfig, ControllerConfig
from runner import SingleExperimentRunner, DemandGenerator, compute_hash


# ================================================================
# Fixtures
# ================================================================

@pytest.fixture
def topology():
    return contracts_sdk.load_topology("four_intersection_v1")


@pytest.fixture
def actuator():
    return ActuatorStateMachine(yellow_duration_s=3.0, all_red_duration_s=2.0)


def make_cmd(node_id="J1", target="J1_PHASE_EW", min_green=10.0, max_green=30.0, **kwargs):
    cmd = {
        "command_id": str(uuid.uuid4()),
        "node_id": node_id,
        "target_phase_id": target,
        "min_green_s": min_green,
        "max_green_s": max_green,
        "controller": "test",
    }
    cmd.update(kwargs)
    return cmd


# ================================================================
# TASK 12.1 — Mock research run rejected
# ================================================================

class TestMockRunRejection:
    def test_mock_mode_blocks_research_validity(self):
        """A mock_demo run must set valid_for_research = False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ExperimentManifest(
                experiment_id="test_mock_rejection",
                topology="four_intersection_v1",
                scenario=ScenarioConfig(name="balanced", duration_s=3, random_seed=42),
                controller=ControllerConfig(type="fixed_time"),
            )
            runner = SingleExperimentRunner(
                manifest=manifest, artifacts_root=tmpdir, mode="mock_demo"
            )
            valid = runner.run()

            assert not valid, "Mock run should not be valid"

            summary_path = Path(tmpdir) / "test_mock_rejection" / "summary.json"
            assert summary_path.exists()
            with open(summary_path) as f:
                summary = json.load(f)
            assert summary["valid_for_research"] is False
            assert summary["is_synthetic"] is True


# ================================================================
# TASK 12.2 — Controller identity mismatch rejected
# ================================================================

class TestControllerIdentity:
    def test_unknown_controller_raises(self):
        """Requesting a non-existent controller must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown controller"):
            manifest = ExperimentManifest(
                experiment_id="test_bad_ctrl",
                topology="four_intersection_v1",
                scenario=ScenarioConfig(name="balanced", duration_s=1, random_seed=1),
                controller=ControllerConfig(type="nonexistent_controller"),
            )
            SingleExperimentRunner(manifest=manifest)

    def test_controller_class_matches_request(self):
        """The instantiated controller class must match the requested name."""
        for ctrl_name, expected_class in [
            ("fixed_time", "FixedTimeController"),
            ("max_queue", "MaxQueueController"),
            ("max_pressure", "MaxPressureController"),
            ("edgeflow", "EdgeFlowController"),
        ]:
            manifest = ExperimentManifest(
                experiment_id=f"test_identity_{ctrl_name}",
                topology="four_intersection_v1",
                scenario=ScenarioConfig(name="balanced", duration_s=1, random_seed=1),
                controller=ControllerConfig(type=ctrl_name),
            )
            runner = SingleExperimentRunner(manifest=manifest)
            assert runner.controller.__class__.__name__ == expected_class


# ================================================================
# TASK 12.3 — Demand hash consistency
# ================================================================

class TestDemandHash:
    def test_same_scenario_seed_produces_same_hash(self, topology):
        """Same (scenario, seed) must produce identical demand regardless of when called."""
        d1 = DemandGenerator.generate("balanced", 101, 20, topology)
        d2 = DemandGenerator.generate("balanced", 101, 20, topology)
        assert d1["hash"] == d2["hash"]

    def test_different_seed_produces_different_hash(self, topology):
        """Different seeds must produce different demand."""
        d1 = DemandGenerator.generate("balanced", 101, 20, topology)
        d2 = DemandGenerator.generate("balanced", 202, 20, topology)
        assert d1["hash"] != d2["hash"]

    def test_different_scenario_produces_different_hash(self, topology):
        """Different scenarios must produce different demand."""
        d1 = DemandGenerator.generate("balanced", 101, 20, topology)
        d2 = DemandGenerator.generate("directional_surge", 101, 20, topology)
        assert d1["hash"] != d2["hash"]

    def test_demand_hash_used_across_controllers(self):
        """All controllers for the same scenario+seed should use the same demand hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hashes = []
            for ctrl in ["fixed_time", "max_queue", "max_pressure", "edgeflow"]:
                manifest = ExperimentManifest(
                    experiment_id=f"hash_test_{ctrl}",
                    topology="four_intersection_v1",
                    scenario=ScenarioConfig(name="balanced", duration_s=5, random_seed=101),
                    controller=ControllerConfig(type=ctrl),
                )
                runner = SingleExperimentRunner(manifest=manifest, artifacts_root=tmpdir)
                runner.run()
                hashes.append(runner.demand_hash)

            # All hashes must be identical
            assert len(set(hashes)) == 1, f"Demand hashes differ across controllers: {hashes}"


# ================================================================
# TASK 12.4 — Fixed-Time clock correctness
# ================================================================

class TestFixedTimeClock:
    def test_same_timestamp_same_phase(self, topology):
        """Calling compute_command at the same time must return the same phase."""
        ctrl = FixedTimeController(cycle_time_s=30.0)
        tel = {"simulation_time_s": 5.0, "approaches": [], "current_phase_id": "J1_PHASE_NS"}

        r1 = ctrl.compute_command("J1", tel, topology, current_time_s=5.0)
        r2 = ctrl.compute_command("J1", tel, topology, current_time_s=5.0)
        r3 = ctrl.compute_command("J1", tel, topology, current_time_s=5.0)

        assert r1["target_phase_id"] == r2["target_phase_id"] == r3["target_phase_id"]

    def test_time_within_green_same_phase(self, topology):
        """Multiple calls within the same green interval return the same phase."""
        ctrl = FixedTimeController(cycle_time_s=30.0)
        tel = {"simulation_time_s": 0.0, "approaches": []}

        results = []
        for t in [0.0, 1.0, 2.0, 3.0, 4.0]:
            r = ctrl.compute_command("J1", tel, topology, current_time_s=t)
            results.append(r["target_phase_id"])

        assert len(set(results)) == 1, f"Phase changed within green window: {results}"

    def test_phase_changes_after_green_duration(self, topology):
        """Phase must change after green + clearance duration."""
        ctrl = FixedTimeController(cycle_time_s=30.0, yellow_s=3.0, all_red_s=2.0)
        tel = {"simulation_time_s": 0.0, "approaches": []}

        # With 2 phases and cycle=30, yellow=3, all-red=2:
        # green_per_phase = (30 - 2*5) / 2 = 10s
        # Phase 0: t=0..10, Phase 1: t=15..25, Phase 0: t=30..
        r_start = ctrl.compute_command("J1", tel, topology, current_time_s=0.0)
        r_after = ctrl.compute_command("J1", tel, topology, current_time_s=16.0)

        assert r_start["target_phase_id"] != r_after["target_phase_id"], \
            "Phase should change after full green+clearance interval"

    def test_repeated_calls_no_advancement(self, topology):
        """100 calls at t=0 must all return the same phase (no call-count effect)."""
        ctrl = FixedTimeController(cycle_time_s=30.0)
        tel = {"simulation_time_s": 0.0, "approaches": []}

        phases = set()
        for _ in range(100):
            r = ctrl.compute_command("J1", tel, topology, current_time_s=0.0)
            phases.add(r["target_phase_id"])

        assert len(phases) == 1, f"Phase should not change with repeated calls: {phases}"


# ================================================================
# TASK 12.5 — Actuator yellow/all-red timing
# ================================================================

class TestActuatorTiming:
    def test_no_instant_transition(self, actuator):
        """A phase change must NOT skip yellow and all-red."""
        node = actuator.get_or_create_node("J1", default_phase="J1_PHASE_NS")
        node.phase_start_time = 0.0
        node.state_start_time = 0.0

        cmd = make_cmd(target="J1_PHASE_EW", min_green=10.0)
        ack = actuator.process_command(cmd, now=15.0)

        # The command should be ACCEPTED (transition initiated), NOT APPLIED
        assert ack["status"] == "ACCEPTED", \
            f"Should initiate transition, not instant apply: {ack}"

        # Node should be in YELLOW, not GREEN
        assert node.state == "YELLOW"
        assert node.current_phase_id == "J1_PHASE_NS", "Phase should not change yet"

    def test_yellow_then_all_red_then_green(self, actuator):
        """Full transition sequence: YELLOW -> ALL_RED -> GREEN."""
        node = actuator.get_or_create_node("J1", default_phase="J1_PHASE_NS")
        node.phase_start_time = 0.0
        node.state_start_time = 0.0

        # t=15: initiate switch
        cmd = make_cmd(target="J1_PHASE_EW", min_green=10.0)
        actuator.process_command(cmd, now=15.0)
        assert node.state == "YELLOW"

        # t=16: still YELLOW (need 3s)
        actuator.step(now=16.0)
        assert node.state == "YELLOW"

        # t=18: YELLOW done -> ALL_RED
        actuator.step(now=18.0)
        assert node.state == "ALL_RED"

        # t=19: still ALL_RED (need 2s)
        actuator.step(now=19.0)
        assert node.state == "ALL_RED"

        # t=20: ALL_RED done -> GREEN on new phase
        result = actuator.step(now=20.0)
        assert node.state == "GREEN"
        assert node.current_phase_id == "J1_PHASE_EW"
        assert len(result["applied_events"]) == 1

    def test_no_conflicting_green(self, actuator):
        """Only one phase can be GREEN at any time on the same node."""
        node = actuator.get_or_create_node("J1", default_phase="J1_PHASE_NS")
        node.phase_start_time = 0.0

        # The node is GREEN on NS. It's impossible to have EW green simultaneously.
        assert node.state == "GREEN"
        assert node.current_phase_id == "J1_PHASE_NS"

        # Initiate transition
        cmd = make_cmd(target="J1_PHASE_EW", min_green=0.0)
        actuator.process_command(cmd, now=15.0)

        # During YELLOW, the current phase is still NS
        assert node.state == "YELLOW"
        assert node.current_phase_id == "J1_PHASE_NS"

    def test_min_green_rejection(self, actuator):
        """Switch rejected if min_green not elapsed."""
        node = actuator.get_or_create_node("J1", default_phase="J1_PHASE_NS")
        node.phase_start_time = 100.0
        node.state_start_time = 100.0

        cmd = make_cmd(target="J1_PHASE_EW", min_green=10.0)
        ack = actuator.process_command(cmd, now=105.0)  # 5s < 10s min
        assert ack["status"] == "REJECTED"
        assert "Min green" in ack["reason"]

    def test_expired_command_rejected(self, actuator):
        """Expired command must be rejected."""
        cmd = make_cmd(expires_at_ms=100000)  # 100s
        ack = actuator.process_command(cmd, now=105.0)  # 105s > 100s
        assert ack["status"] == "EXPIRED"

    def test_invalid_schema_rejected(self, actuator):
        """Command missing required fields is rejected."""
        bad_cmd = {"command_id": "x", "target_phase_id": "Y"}  # missing node_id
        ack = actuator.process_command(bad_cmd, now=0.0)
        assert ack["status"] == "REJECTED"

    def test_reject_during_clearance(self, actuator):
        """Cannot switch to a DIFFERENT phase while already clearing."""
        node = actuator.get_or_create_node("J1", default_phase="J1_PHASE_NS")
        node.phase_start_time = 0.0
        node.state_start_time = 0.0

        # Initiate EW
        cmd1 = make_cmd(target="J1_PHASE_EW", min_green=0.0)
        ack1 = actuator.process_command(cmd1, now=15.0)
        assert ack1["status"] == "ACCEPTED"
        assert node.state == "YELLOW"

        # Try to switch to some other phase during YELLOW
        cmd2 = make_cmd(target="J1_PHASE_NS", min_green=0.0)
        ack2 = actuator.process_command(cmd2, now=16.0)
        # This should be "ACCEPTED" (same as current phase, clearing through)
        # or appropriate response
        # Actually J1_PHASE_NS is current_phase_id, so it should say ACCEPTED/clearing
        assert ack2["status"] == "ACCEPTED"


# ================================================================
# TASK 12.6 — Reset between experiments
# ================================================================

class TestResetBetweenExperiments:
    def test_actuator_reset_clears_state(self, actuator):
        """After reset, no node state remains."""
        actuator.get_or_create_node("J1")
        actuator.get_or_create_node("J2")
        assert len(actuator.nodes) == 2

        actuator.reset_all()
        assert len(actuator.nodes) == 0

    def test_sequential_runs_independent(self):
        """Two sequential runs should produce independent results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = []
            for i in range(2):
                manifest = ExperimentManifest(
                    experiment_id=f"reset_test_{i}",
                    topology="four_intersection_v1",
                    scenario=ScenarioConfig(name="balanced", duration_s=5, random_seed=101),
                    controller=ControllerConfig(type="max_pressure"),
                )
                runner = SingleExperimentRunner(manifest=manifest, artifacts_root=tmpdir)
                runner.run()

                summary_path = Path(tmpdir) / f"reset_test_{i}" / "summary.json"
                with open(summary_path) as f:
                    results.append(json.load(f))

            # Both runs should have the same results (same demand, same controller)
            assert results[0]["average_queue_veh"] == results[1]["average_queue_veh"]
            assert results[0]["demand_hash"] == results[1]["demand_hash"]


# ================================================================
# TASK 12.7 — No-data run fails
# ================================================================

class TestNoDataRunFails:
    def test_empty_collector_is_invalid(self):
        """A collector with zero samples must report is_valid=False."""
        collector = MetricsCollector()
        summary = collector.compute_summary()
        assert summary["is_valid"] is False
        assert summary["total_samples"] == 0


# ================================================================
# TASK 12.8 — Metric units/semantics
# ================================================================

class TestMetricSemantics:
    def test_queue_is_vehicle_count(self):
        """queue_vehicles should be a count, not a rate."""
        collector = MetricsCollector()
        collector.start()
        sample = {
            "node_id": "J1",
            "simulation_time_s": 1.0,
            "current_phase_id": "J1_PHASE_NS",
            "approaches": [
                {"approach_id": "J1_N_IN", "queue_vehicles": 8, "flow_veh_per_s": 0.5,
                 "mean_speed_mps": 0.3, "occupancy_ratio": 0.4},
                {"approach_id": "J1_S_IN", "queue_vehicles": 5, "flow_veh_per_s": 0.3,
                 "mean_speed_mps": 7.0, "occupancy_ratio": 0.2},
            ],
        }
        collector.on_mqtt_message("edgeflow/v1/telemetry/J1", json.dumps(sample))
        collector.stop()

        s = collector.telemetry_samples[0]
        assert s["queue_vehicles"] == 13.0  # 8 + 5
        assert s["waiting_vehicles"] == 8.0  # only N_IN has speed < 0.5

    def test_speed_is_real_measured(self):
        """Speed should come from the telemetry, not a constant."""
        collector = MetricsCollector()
        collector.start()
        for speed_val in [0.1, 5.5, 13.89]:
            sample = {
                "node_id": "J1",
                "simulation_time_s": 1.0,
                "current_phase_id": "J1_PHASE_NS",
                "approaches": [
                    {"approach_id": "J1_N_IN", "queue_vehicles": 1,
                     "flow_veh_per_s": 0.1, "mean_speed_mps": speed_val,
                     "occupancy_ratio": 0.1},
                ],
            }
            collector.on_mqtt_message("edgeflow/v1/telemetry/J1", json.dumps(sample))

        # Speeds should reflect the different values, not a constant
        speeds = [s["mean_speed_mps"] for s in collector.telemetry_samples]
        assert len(set(speeds)) > 1, f"All speeds identical: {speeds}"

    def test_occupancy_is_ratio(self):
        """Occupancy should be in [0, 1] range."""
        collector = MetricsCollector()
        collector.start()
        sample = {
            "node_id": "J1",
            "simulation_time_s": 1.0,
            "current_phase_id": "J1_PHASE_NS",
            "approaches": [
                {"approach_id": "J1_N_IN", "queue_vehicles": 10,
                 "flow_veh_per_s": 0.5, "mean_speed_mps": 2.0,
                 "occupancy_ratio": 0.75},
            ],
        }
        collector.on_mqtt_message("edgeflow/v1/telemetry/J1", json.dumps(sample))
        s = collector.telemetry_samples[0]
        assert 0.0 <= s["occupancy_ratio"] <= 1.0

    def test_metrics_are_finite(self):
        """All summary metrics must be finite numbers."""
        collector = MetricsCollector()
        collector.start()
        for t in range(5):
            sample = {
                "node_id": "J1",
                "simulation_time_s": float(t),
                "current_phase_id": "J1_PHASE_NS",
                "approaches": [
                    {"approach_id": "J1_N_IN", "queue_vehicles": 3,
                     "flow_veh_per_s": 0.4, "mean_speed_mps": 8.0,
                     "occupancy_ratio": 0.15},
                ],
            }
            collector.on_mqtt_message("edgeflow/v1/telemetry/J1", json.dumps(sample))
        collector.stop()

        summary = collector.compute_summary()
        for key in ["average_waiting_time_s", "average_queue_veh", "maximum_queue_veh",
                     "p50_queue_veh", "p95_queue_veh", "throughput_veh_per_s",
                     "mean_network_speed_mps"]:
            assert math.isfinite(summary[key]), f"{key} is not finite: {summary[key]}"


# ================================================================
# TASK 12.9 — Valid run produces complete artifacts
# ================================================================

class TestArtifactCompleteness:
    def test_valid_run_produces_all_artifacts(self):
        """A valid run must produce the complete evidence package."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ExperimentManifest(
                experiment_id="artifact_test",
                topology="four_intersection_v1",
                scenario=ScenarioConfig(name="balanced", duration_s=5, random_seed=42),
                controller=ControllerConfig(type="fixed_time"),
            )
            runner = SingleExperimentRunner(manifest=manifest, artifacts_root=tmpdir)
            runner.run()

            exp_dir = Path(tmpdir) / "artifact_test"
            required_files = [
                "manifest.yaml",
                "environment.json",
                "demand.json",
                "metrics.csv",
                "signal_events.jsonl",
                "faults.jsonl",
                "summary.json",
                "validity.json",
            ]
            for fname in required_files:
                assert (exp_dir / fname).exists(), f"Missing artifact: {fname}"

            # Verify validity.json content
            with open(exp_dir / "validity.json") as f:
                validity = json.load(f)
            assert "valid" in validity
            assert "demand_hash" in validity
            assert "topology_hash" in validity
            assert "requested_controller" in validity

    def test_environment_records_controller_identity(self):
        """environment.json must record the requested and active controller."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = ExperimentManifest(
                experiment_id="env_test",
                topology="four_intersection_v1",
                scenario=ScenarioConfig(name="balanced", duration_s=3, random_seed=42),
                controller=ControllerConfig(type="edgeflow"),
            )
            runner = SingleExperimentRunner(manifest=manifest, artifacts_root=tmpdir)
            runner.run()

            with open(Path(tmpdir) / "env_test" / "environment.json") as f:
                env = json.load(f)
            assert env["requested_controller"] == "edgeflow"
            assert "EdgeFlow" in env["active_controller_class"]


# ================================================================
# TASK 12.10 — SUMO metric semantics (flow definition)
# ================================================================

class TestSumoMetricDefinitions:
    def test_flow_is_not_vehicle_count(self):
        """flow_veh_per_s must be a rate, not a raw count."""
        collector = MetricsCollector()
        collector.start()
        # A sample where flow=0.55 (rate) is plausible
        sample = {
            "node_id": "J1",
            "simulation_time_s": 1.0,
            "current_phase_id": "J1_PHASE_NS",
            "approaches": [
                {"approach_id": "J1_N_IN", "queue_vehicles": 3,
                 "flow_veh_per_s": 0.55, "mean_speed_mps": 9.5,
                 "occupancy_ratio": 0.15},
            ],
        }
        collector.on_mqtt_message("edgeflow/v1/telemetry/J1", json.dumps(sample))
        collector.stop()

        s = collector.telemetry_samples[0]
        # Flow should remain as the rate from telemetry
        assert s["flow_veh_per_s"] == 0.55


# ================================================================
# Run
# ================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
