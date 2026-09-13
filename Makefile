.PHONY: help contracts test integration smoke up-sim down experiment

help:
	@echo "EdgeFlow AI - Standard Developer Commands:"
	@echo "  make contracts       Validate shared contracts and generate types"
	@echo "  make test            Run unit and contract tests"
	@echo "  make integration     Run service integration tests"
	@echo "  make smoke           Run docker compose smoke test"
	@echo "  make up-sim          Start simulation stack with Docker Compose"
	@echo "  make down            Stop all Docker Compose services"
	@echo "  make experiment EXP=<name> Run experiment manifest"

contracts:
	python -m pytest tests/unit/test_contracts.py

test:
	python -m pytest tests/unit

integration:
	python -m pytest tests/integration

smoke:
	docker compose --profile simulation up -d --build
	python -m pytest tests/integration/test_smoke.py

up-sim:
	docker compose --profile simulation up --build

down:
	docker compose down

experiment:
	@if [ -z "$(EXP)" ]; then echo "Usage: make experiment EXP=<manifest_name>"; exit 1; fi
	python -m experiment_runner.runner --manifest experiments/$(EXP).yaml
