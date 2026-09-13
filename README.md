# EdgeFlow AI - Adaptive Traffic Control System

EdgeFlow AI is a graph-based, real-time adaptive traffic signal control system for microservice environments. 

## Key Features
- **Network-Level Graph State**: Models road networks as $G=(V,E)$ and uses queue, flow, speed, and occupancy features.
- **Max-Pressure Control Policy**: Implements Max-Pressure adaptive control for dynamic signal optimization.
- **Contract-First Microservices**: Standardized JSON schema contracts and MQTT event backbone.
- **Software Digital Twin**: Integrated SUMO traffic simulation for reproducible benchmarking.

## Repository Layout
- `contracts/`: JSON Schemas and topology definitions.
- `infra/`: Infrastructure configs (Mosquitto broker).
- `services/`: Microservices (`api`, `graph-control`, `simulator`, `vision`, `actuator`, `dashboard`).
- `experiments/`: Experiment definitions and manifests.
- `tests/`: Fixtures, unit, contract, and integration tests.

## Getting Started
See [DEVELOPMENT.md](DEVELOPMENT.md) for environment setup and commands.
See [ARCHITECTURE.md](ARCHITECTURE.md) for details on microservice interaction.
See [AGENTS.md](AGENTS.md) for coding guidelines.
