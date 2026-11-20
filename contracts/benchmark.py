"""Canonical benchmark protocol; independent of services and training frameworks."""

TIMING = dict(step_s=1, decision_s=5, min_green_s=10, max_green_s=60, yellow_s=3, all_red_s=2)
SEEDS = dict(
    train=list(range(60000, 61000)),
    validation=list(range(70001, 70006)),
    test=list(range(80001, 80011)),
    development=list(range(90001, 90004)),
)
LEARNER_SEEDS = [17, 29, 43]
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
    features=[
        "served_queue", "served_occupancy",
        "down1_queue", "down1_occupancy", "down2_queue", "down2_occupancy",
        "up1_queue", "up1_occupancy", "up2_queue", "up2_occupancy",
        "nonserved_queue", "service_age", "elapsed_green", "is_current",
        "green", "yellow", "all_red", "confidence",
    ],
    normalization=dict(queue_vehicles=20, service_age_s=60, elapsed_green_s=60),
)
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
