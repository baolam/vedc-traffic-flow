"""Canonical benchmark protocol; independent of services and training frameworks."""

TIMING = dict(step_s=1, decision_s=5, min_green_s=10, max_green_s=60, yellow_s=3, all_red_s=2)
SEEDS = dict(
    train=list(range(60000, 61000)),
    validation=list(range(70001, 70006)),
    test=list(range(80001, 80011)),
    development=list(range(90001, 90004)),
)
LEARNER_SEEDS = [17, 29, 43]
# Five independent whole-system training runs per map and algorithm; LEARNER_SEEDS stays frozen for old protocols.
UNIFIED_CAMPAIGN = dict(version="unified_campaign_v1", learner_seeds=[17, 29, 43, 59, 71])
# Native-phase fair cycle: length max(base, per_phase * P) s incl. clearance_s per phase; greens quantized.
CYCLE_RULE = dict(version="multiphase_cycle_v1", base_s=70, per_phase_s=25, clearance_s=5,
                  min_green_s=10, max_green_s=60, quantum_s=5)
FLEET = dict(motorcycle=65, car=25, taxi=4, bus=3, truck=3)
CORE_CASES = [
    "balanced",
    "directional_surge",
    "directional_surge_ew",
    "downstream_bottleneck",
    "sparse",
    "near_capacity",
    "oversaturated",
    "directional_reversal",
]
CITY_CASES = ["balanced", "directional_reversal", "downstream_bottleneck"]
PHASE_FEATURES = [
    "served_queue",
    "served_occupancy",
    "downstream_queue",
    "downstream_occupancy",
    "nonserved_queue",
    "service_age",
    "elapsed_green",
    "is_current",
    "green",
    "yellow",
    "all_red",
    "confidence",
]
OBSERVATION_SPEC = dict(
    version="raw_two_hop_v1",
    radius_hops=2,
    max_phases=8,
    features=[
        "served_queue", "served_occupancy",
        "down1_queue", "down1_occupancy", "down2_queue", "down2_occupancy",
        "up1_queue", "up1_occupancy", "up2_queue", "up2_occupancy",
        "nonserved_queue", "service_age", "elapsed_green", "is_current",
        "green", "yellow", "all_red", "confidence",
    ],
    normalization=dict(queue_vehicles=20, service_age_s=60, elapsed_green_s=60),
)
UNIFIED_DQN = dict(
    schema="unified_dqn_v1",
    # algorithm -> (architecture, reward); generalized project variants, not exact paper reproductions
    algorithms=dict(
        phase_dqn_unified=("scalar_phase_scorer", "wait_tail_v1"),
        shared_dqn_unified=("padded_vector_head", "wait_tail_v1"),
        presslight_unified=("scalar_phase_scorer", "node_pressure_v1"),
        fair_cycle_unified=("candidate_pair_scorer", "wait_tail_v1"),
    ),
    hidden=64,
)
# Cycle-residual action: a 5 s green transfer donor->recipient among native phases, or no-op (slot GRID-1).
# Candidate input = donor row + recipient row (OBSERVATION_SPEC features each) + these extras.
CYCLE_DQN = dict(schema="cycle_candidates_v1", extras=["is_noop", "donor_green", "recipient_green", "cycle_length"])
# Frozen first recipe (unverified starting point, see docs/engineering/research/INITIAL_RL_HYPERPARAMETERS.md).
DQN_RECIPE = dict(
    version="unified_dqn_recipe_v1", gamma_5=0.99, reference_s=5, lr=3e-4, replay=200000, batch=256,
    learning_starts=5000, update_every_decisions=4, target_every_updates=1000, grad_clip=10,
    epsilon_end=0.05, epsilon_decay_sim_s=125000, validate_every_episodes=20,
    min_sim_s=250000, min_episodes=100, min_case_visits=10, patience=10, rel_improvement=0.01,
    cap_sim_s=2500000, demand_s=1800, drain_s=600,
)
# Cycle-residual DQN recipe: phase recipe with its own cadence (one optimizer step per joint cycle decision).
CYCLE_RECIPE = dict(DQN_RECIPE, version="unified_cycle_recipe_v1", learning_starts=1024, target_every_updates=200,
                    replay=50000, wait_penalty_lambda=0.5)
PHASE_NORMALIZATION = dict(
    queue_vehicles=20,
    service_age_s=60,
    elapsed_green_s=60,
    occupancy_ratio="fraction_0_to_1",
    confidence="fraction_0_to_1",
)
VEHICLES = dict(
    motorcycle=("motorcycle", 2.2, 0.9, 3.0, 5.0, 13.89),
    car=("passenger", 4.5, 1.8, 2.6, 4.5, 13.89),
    taxi=("taxi", 4.5, 1.8, 2.6, 4.5, 13.89),
    bus=("bus", 12.0, 2.5, 1.2, 4.0, 11.11),
    truck=("truck", 8.0, 2.4, 1.5, 4.0, 11.11),
)
