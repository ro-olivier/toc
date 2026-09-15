# Toc

Toc is a private, browser-based implementation of the Toc board game. The server is written in Python with FastAPI, communication during a game uses WebSockets, and the browser client is plain HTML, CSS, and JavaScript.

This release supports two, four, and six-seat boards; human participants may control one or two seats depending on the selected game mode. Games can be resumed after interruption, and completed games are archived with a detailed audit trail.

## Documentation

- [Player guide](docs/PLAYER_GUIDE.md) — creating, joining, playing, reconnecting, and the supported modes.
- [Game rules](RULES.md) — the complete implemented rules and every configurable option.
- [Architecture](docs/ARCHITECTURE.md) — source layout, responsibilities, runtime flow, and domain model.
- [Configuration reference](docs/CONFIGURATION.md) — environment, lifecycle constants, modes, rulesets, translations, and versions.
- [HTTP and WebSocket protocol](docs/PROTOCOL.md) — public endpoints, message contracts, and close codes.
- [Persistence and audit](docs/PERSISTENCE_AND_AUDIT.md) — snapshots, suspension, recovery, finished archives, and audit events.
- [Development guide](docs/DEVELOPMENT.md) — local setup, test and lint commands, and contribution conventions.
- [Deployment and operations](docs/DEPLOYMENT.md) — Raspberry Pi deployment, systemd, Apache, storage, logs, and backups.

## Quick start

Python 3.12 is the reference development version.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m uvicorn main:app --reload
```

Open <http://127.0.0.1:8000/toc/play/> and create a game. Run the checks with:

```bash
python -m pytest
python -m ruff check .
```

The production dependency set includes a WebSocket implementation explicitly. Do not omit `websockets`; without it Uvicorn accepts ordinary HTTP requests but cannot upgrade WebSocket connections.

## Technology and versions

- Python 3.12
- FastAPI 0.141.1
- Uvicorn 0.52.4
- websockets 17.1
- Browser client using native ES modules
- Archive format 4
- Rules format 1
- WebSocket protocol 2

## Configuration

The application uses two environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `TOC_DATA_DIRECTORY` | `game-data` below the repository root | Active, suspended, and finished game archives |
| `TOC_LOG_LEVEL` | `INFO` | Python logging level, such as `DEBUG`, `INFO`, or `WARNING` |

Operational timeouts and protocol constants live in `settings.py`. Game-rule values live in `toc/model/rules.py`; game-mode definitions live in `toc/model/game_mode.py`.

## Source layout

| File/Directory | Description |
| --- | --- |
| `main.py` | ASGI compatibility entry point |
| `settings.py` | deployment and protocol settings |
| `toc/application.py` | FastAPI application and lifespan |
| `toc/runtime.py` | process-wide manager, router, and store |
| `toc/model/` | cards, board, moves, rules, modes, and game engine |
| `toc/session/` | lobby, participants, connections, and orchestration |
| `toc/transport/` | HTTP and WebSocket endpoints |
| `toc/persistence/` | compressed snapshots and finished archives |
| `toc/infrastructure/` | logging, identity, clocks, messages, and versions |
| `web/` | browser application |
| `tests/` | automated test suite |


## Security scope

Toc is designed for a small, trusted group rather than an untrusted public service. Reconnection is protected by high-entropy resume tokens, only their SHA-256 hashes are persisted, player names are restricted to URL-safe ASCII characters, and inbound WebSocket messages are validated. It does not currently provide user accounts, passwords, authorization roles, rate limiting, or hostile-internet hardening.

## License

No license file is currently included.
