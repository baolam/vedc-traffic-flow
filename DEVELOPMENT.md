# Development & Setup Guide

## Quick Start (Docker Environment)

### 1. Copy local configuration
- **Bash / Linux / macOS**:
  ```bash
  cp .env.example .env
  ```
- **Windows PowerShell**:
  ```powershell
  Copy-Item .env.example .env
  ```

### 2. Start the Simulation Stack
Run Docker Compose directly (no `make` required):
```bash
docker compose --profile simulation up --build
```
*(To run in background mode, add `-d`: `docker compose --profile simulation up -d --build`)*

### 3. Verify Service Health & View Logs
- **Check container status**:
  ```bash
  docker compose ps
  ```
- **Tail logs**:
  ```bash
  docker compose logs -f
  ```

### 4. Stop Services
```bash
docker compose down
```

### 5. Run Tests
- **Unit tests**:
  ```bash
  python -m pytest tests/unit
  ```
- **Contract tests**:
  ```bash
  python -m pytest tests/unit/test_contracts.py
  ```
- **Integration & Smoke tests**:
  ```bash
  python -m pytest tests/integration
  ```

*(Note: If you are on Linux/macOS/WSL with `make` installed, you can optionally use shortcut targets like `make up-sim`, `make test`, and `make down`)*.

---

## Local Development Requirements

- Docker & Docker Compose v2 (Docker Desktop for Windows/macOS)
- Python 3.9+
- Git
