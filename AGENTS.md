# AGENTS.md - Coding Agent Guardrails & Architectural Rules

This document defines non-negotiable architectural invariants and guardrails for coding agents working on **EdgeFlow AI**.

---

## Core Invariants

1. **Schema Authority**:
   - Never redefine canonical schemas inside an individual service.
   - All message schemas, enums, and topology IDs MUST originate from `contracts/`.

2. **Microservice Isolation**:
   - Do NOT directly import implementation code from another microservice.
   - All inter-service communication MUST occur via documented MQTT topics or HTTP/WebSocket endpoints.

3. **Canonical Topology & Telemetry**:
   - Use stable human-readable topology IDs (`J1`, `J1_N_IN`, `J1_N_TO_E`, `J1_PHASE_NS`, `four_intersection_v1`).
   - `Graph-Control` must remain completely agnostic to whether telemetry comes from SUMO simulation, video processing, or physical sensors.

4. **Controller Abstraction**:
   - All controllers (Fixed-Time, Max-Pressure, future RL) MUST implement the same unified controller interface.

5. **Actuator Abstraction**:
   - All actuator implementations (SimulationActuator, VirtualActuator, PhysicalActuator) MUST consume the exact same abstract `ControlCommand`.

6. **Scoped Tasks**:
   - Limit changes strictly to the target module/service paths specified in task definitions.
   - Do not edit unrelated services or shared contracts without prior authorization.

7. **Verification**:
   - Always run contract tests (`make contracts`) and unit tests (`make test`) before proposing changes.
