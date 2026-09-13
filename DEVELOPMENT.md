# Development & Setup Guide

## Quick Start (Docker Environment)

1. Copy local configuration:
   ```bash
   cp .env.example .env
   ```

2. Start the simulation stack:
   ```bash
   make up-sim
   # or: docker compose --profile simulation up --build
   ```

3. Verify service health:
   ```bash
   docker compose ps
   ```

4. Run tests:
   ```bash
   make test
   ```

## Local Development Requirements

- Docker & Docker Compose v2
- Python 3.11+
- Git
