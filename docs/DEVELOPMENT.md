# Development guide

## Requirements

- Python 3.12
- A modern browser with native JavaScript-module, WebSocket, CSS custom-property, and `crypto.randomUUID()` support

The Raspberry Pi deployment may use Python 3.11, but Python 3.12 is the reference development environment and the version against which the project was built.

## Environment setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Always prefer `python -m ...` so the command uses the currently selected interpreter and environment.

## Run locally

```bash
python -m uvicorn main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/toc/play/
```

Useful probes:

```bash
curl http://127.0.0.1:8000/toc
curl http://127.0.0.1:8000/toc/api/rule-presets
curl http://127.0.0.1:8000/toc/api/open-lobbies
```

## Automated tests

Run the complete suite:

```bash
python -m pytest -v
```

Run one file or test:

```bash
python -m pytest -v tests/test_game.py
python -m pytest -v tests/test_game.py::test_name_of_test
```

Test areas are organized by subsystem:

| File | Coverage |
|---|---|
| `test_board.py` | Move generation, board geometry, houses, blocking, special cards |
| `test_game.py` | Turn execution, dealing, exchange, kicking, hopping, winning |
| `test_game_mode.py` | Mode patterns, capacities, deck-compatible schedules |
| `test_session.py` | Lobby and session orchestration |
| `test_websocket.py` | Handshake, validation, reconnect, close codes, end-to-end message flow |
| `test_snapshot_state.py` | Snapshot invariants, JSON round trips, exact phase resume |
| `test_archive_store.py` | Atomic compressed storage and corruption handling |
| `test_audit.py` | Event schemas and finished-game history |
| `test_live_server.py` | A real Uvicorn process and WebSocket connection |
| `test_messages.py` | Translation-key registration and coverage |

The live-server test is expected to be slightly slower because it starts an actual server rather than calling application objects in process.

## Linting

Run the configured Ruff checks:

```bash
python -m ruff check .
```

Show fixes without applying them:

```bash
python -m ruff check . --diff
```

Show a summary by rule:

```bash
python -m ruff check . --statistics
```

Inspect one rule and its individual findings:

```bash
python -m ruff rule SIM118
python -m ruff check . --select SIM118
```

Apply only Ruff's safe automatic fixes after reviewing the diff:

```bash
python -m ruff check . --fix
```

## Coding conventions

The existing project intentionally uses tabs for Python indentation and camelCase for most application methods and local variables. Serialization methods retain the conventional `to_dict` and `from_dict` names. Match the surrounding file rather than mechanically introducing a second style.

Additional conventions:

- Keep function declarations on one line.
- Avoid splitting simple calls or slices across lines; multi-argument calls may be expanded when it improves readability.
- Use explicit type hints on public methods and significant local collections.
- Prefer immutable `@dataclass(frozen=True, slots=True)` records for validated configuration and persistence state.
- Use `ValueError` consistently for invalid domain or serialized input, even where a stricter type-oriented API might choose `TypeError`.
- Use `logging`, not `print`, in application code.
- Keep rules in the model, transport validation in transport modules, and lifecycle/persistence coordination in session modules.

## Working with asynchronous code

Game prompts and broadcasts are asynchronous. Tests for isolated async methods commonly use `asyncio.run(...)`; multi-step scenarios define an inner coroutine and run it once.

When mocking an async dependency, the replacement must also be async if production code awaits it. Conversely, after changing a method from async to synchronous, remove every remaining `await` at call sites. Search before committing:

```bash
rg "await .*methodName|methodName\(" .
```

Never use `asyncio.run()` from inside an already-running event loop.

## Adding a rule

1. Add the immutable field and default in `toc/model/rules.py`.
2. Add enum or allowed-choice validation as needed.
3. Ensure `to_dict`, `from_dict`, and `getRuleSchema` support it.
4. Add English and French label, description, and choice translations.
5. Implement move generation and execution behaviour.
6. Add focused rule tests for both values and relevant combinations.
7. Add snapshot round-trip coverage.
8. Decide whether `RULES_FORMAT_VERSION` must change.

## Adding a game mode

1. Add an enum member and `GameModeDefinition`.
2. Define participant and team patterns in physical seat order.
3. Choose a deal schedule satisfying `seatCount × sum(schedule) == 52 + jokerCount`.
4. Add the browser mode option and translations.
5. Test roster ordering, lobby capacity, start behaviour, gameplay, and snapshot restore.

## Changing the protocol

Maintain backward compatibility only when deliberately required. Update:

- `settings.CLIENT_MESSAGE_TYPES`;
- `isValidClientMessage` and dispatch;
- browser send/receive logic;
- protocol documentation and tests;
- `WEBSOCKET_PROTOCOL_VERSION` if existing clients would interpret the new contract incorrectly.

Every interactive response must carry the active `requestId`.

## Manual release-candidate checks

Before tagging a release:

1. Run Pytest and Ruff.
2. Start a fresh lobby in every game mode.
3. Verify adjacent and cross four-seat hand ownership.
4. Exercise Ace/King/Joker deployment, Four backward, forced Five, split Seven, seven-hop, Jack switch, house entry, blocking, and kicking.
5. Disconnect during card exchange and during a move prompt; reconnect and confirm the same prompt is restored.
6. Suspend a started game and restore it with all participants.
7. Finish a game and inspect its archive and audit sequence.
8. Check English/French live switching and mobile hand wrapping.
9. Test production through HTTPS/WSS, not only directly against Uvicorn.

## Git workflow

Use focused feature branches and commit at coherent, passing checkpoints. After rewriting already-pushed history, use:

```bash
git push --force-with-lease
```

`--force-with-lease` replaces the remote branch only if it still points where the local repository expects, protecting unrelated remote work better than `--force`.
