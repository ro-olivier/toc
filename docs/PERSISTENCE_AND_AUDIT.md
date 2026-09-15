# Persistence and audit

## Purpose

Persistence serves two different goals:

1. **Resumption:** a started game can continue from its exact interactive phase after inactivity, disconnection, or server restart.
2. **Audit:** a finished game retains enough state and chronological detail to verify how cards, choices, and pawns produced the result.

Unstarted lobbies are deliberately ephemeral and are never archived.

## Storage layout

The root is selected by `TOC_DATA_DIRECTORY`, defaulting to `game-data` in the repository. The store creates:

```text
game-data/
  active/
  suspended/
  finished/
```

Each file is named with the internal 32-character hexadecimal session UUID:

```text
<session-id>.json.gz
```

The public join code is stored inside the document and is not used as a filename.

## Archive categories

### Active

An active archive is an exact checkpoint of a started, running game. Checkpoints are written at resumable phase boundaries and after decisions or movements that must survive interruption.

### Suspended

A suspended archive has the same resumable snapshot structure as an active archive, but the game is not currently executing. An active archive is moved to suspended when:

- every participant has been disconnected for at least 30 seconds;
- the game has had no recorded activity for 15 minutes; or
- the game loop fails and its last valid state can be preserved.

When a suspended join code is requested, its archive is loaded into memory. It becomes active again only after every expected participant has reconnected and been authenticated.

### Finished

A finished archive is immutable and non-resumable. It preserves the final state and complete audit trail but excludes resume-token hashes and transient prompt progress. Active and suspended copies of the same session are removed once finalization succeeds.

## File-writing guarantees

`CompressedJsonStore` uses compact, sorted UTF-8 JSON inside deterministic gzip compression at level 6. Writes are crash-conscious:

1. validate that the payload is a JSON object with no `NaN`/infinite constants;
2. write a new exclusive temporary file in the destination directory;
3. set its permissions to `0600`;
4. flush and `fsync` the file;
5. atomically replace the final path with `os.replace`;
6. `fsync` the directory where the platform supports directory descriptors.

Temporary files are removed after a failed write. Reads wrap malformed gzip, UTF-8, and JSON data as `ArchiveCorruptionError`. Document IDs are canonical UUID hex values, which prevents path traversal through archive APIs.

## Resumable snapshot structure

A snapshot has four top-level objects:

```json
{
  "metadata": {},
  "game": {},
  "events": [],
  "progress": {}
}
```

### Metadata

Metadata includes:

- archive, engine, and rules format versions;
- internal session ID and public join code;
- selected mode and duel layout;
- ruleset name and complete effective rules;
- participants and their resume-token hashes;
- seats with participant, team, and colour associations;
- creation, start, end, and last-activity timestamps.

Timestamps are timezone-aware ISO 8601 strings normalized to UTC during parsing.

### Game state

The game object contains:

- started/finished flags;
- hand-completion count;
- active seat and active index;
- dealer-rotation count;
- ordered board colours and ordered seat IDs;
- every seat's private hand and pawn count;
- every occupied ordinary/house position, its owner, and blocking/fresh-deployment flags;
- complete draw and discard piles;
- last played card.

Validation ensures the state contains exactly one complete 52- or 54-card deck with no duplicate card identities, all references are valid, and every stored pawn count equals the occupied board state.

### Progress state

`progress` identifies the exact resumable phase:

- `deal-start`
- card exchange
- turn start
- turn decision
- turn end
- seven split
- seven-hop decision
- deal end
- deck-cycle end
- finished

It also stores the current deal index. A seven split records acting seat, pawn owner, card, remaining steps, and—when allocation mode requires it—the pawns already moved. A pending seven-hop records acting seat, pawn owner, deciding seat, card, origin, and destination.

This is why recovery can resume a choice rather than merely reconstructing the board at the start of a round.

### Events

The complete audit log accumulated so far is included in active and suspended snapshots. Event sequence and elapsed-time invariants are checked during deserialization.

## Finished archive structure

A finished archive stores its version fields, session/join identity, mode, rules, participants, seats, timestamps, final `game`, and `events` directly at the top level.

Compared with resumable metadata:

- participants contain only ID and name;
- no resume-token hash is retained;
- there is no resumable `progress` object;
- `startedAt` and `endedAt` are mandatory;
- the game must be both started and finished;
- the final event must identify the actual winning team and filled houses.

## Audit event envelope

Every event has:

```json
{
  "sequence": 1,
  "elapsedSeconds": 0,
  "type": "game-started",
  "playerId": null,
  "details": {}
}
```

- `sequence` begins at 1 and is contiguous.
- `elapsedSeconds` is whole seconds since game start and never decreases. Wall-clock time is stored for game start/end, not for every event.
- `playerId` is a **seat ID** for player actions. It is null only for system-level game start and finish events.
- `details` has an exact schema per event type; unknown or missing fields are rejected.

## Audit event reference

| Type | Actor | Details |
|---|---|---|
| `game-started` | system | none |
| `cards-dealt` | receiving seat | `deckCycle`, `deal`, exact `cards` |
| `card-exchanged` | exchanging seat | `partnerId`, `givenCard`, `receivedCard` |
| `turn-started` | active seat | `handSize` |
| `card-played` | acting seat | `card`, `moveType`, `pieceOwnerId`, origin, target, `steps` |
| `card-discarded` | discarding seat | reason `no-legal-move`, exact `card` |
| `hand-folded` | folding seat | reason `no-legal-move`, exact remaining `cards` |
| `piece-moved` | acting seat | `moveType`, `pieceOwnerId`, origin, target, `steps` |
| `piece-kicked` | acting seat | kicked `pieceOwnerId`, `positionId`, reason `path` or `landing` |
| `seven-hop-decided` | deciding seat | acting/pawn-owner IDs, origin, target, accepted boolean |
| `dealer-changed` | dealer seat | `rotationCount`, `initial` boolean |
| `game-finished` | system | team, winning seat/participant IDs, winner names |

`CARD_PLAYED` records the chosen high-level action. `PIECE_MOVED` records its actual board consequence. A Jack switch therefore produces movement records for both pawns. Split-seven segments and hops likewise create explicit movement events. Kicks are separate events so path and landing effects remain auditable.

## Finished-archive integrity checks

Loading a finished archive verifies, among other invariants:

- supported archive and rules format versions;
- canonical session, participant, and seat IDs;
- unique participants, names, seats, and colours where required;
- mode capacities and participant-to-seat relationships;
- exact game/seat order agreement;
- one `game-started` event first and one `game-finished` event last;
- contiguous event sequence and nondecreasing elapsed seconds;
- valid player, card, position, and partner references;
- winning event names/participants/seats agree with each other;
- every winning seat's four house positions are occupied by that seat in the final state.

The event stream is intended for verification, not as the source from which the final state is rebuilt. The archive stores both the history and the validated final state.

## Startup recovery

During the FastAPI lifespan startup, `ConnectionManager.recoverInterruptedGames()` scans `active/`:

- a valid unfinished active checkpoint is moved to `suspended/`;
- a valid checkpoint already marked finished is converted to a finished archive;
- if active and suspended copies coexist, the newer `lastActivityAt` wins, with active preferred on an exact tie;
- invalid/corrupt archives are logged and left for operator investigation rather than silently discarded.

The suspended join-code index is then rebuilt. This avoids decompressing every suspended archive on each reconnect attempt.

## Suspension and reconnection sequence

1. The monitor detects inactivity or all participants disconnected beyond the grace period.
2. The game task is cancelled at a checkpoint-safe boundary.
3. The latest state is written to `suspended/` and the active file is deleted.
4. Connections close with code 4007 and routing state is released or prepared for restore.
5. A later WebSocket request finds the join code in the suspended index and reconstructs participants, seats, board, deck, hands, events, and progress.
6. Each participant proves the resume token associated with their name.
7. When everyone is connected, the suspended archive transitions back to `active/` and the recorded phase continues.

If persisting a suspension fails, the session does not deliberately discard the only live copy; the failure is logged and the engine attempts to preserve/restart the running state.

## Resume-token handling

- A raw token is generated with `secrets.token_urlsafe(32)` and sent only to that participant.
- The browser stores it in local storage under a game/name-specific key.
- The server stores only `SHA-256(token)` in active/suspended metadata.
- Verification uses `secrets.compare_digest`.
- Finished archives omit both raw tokens and hashes.
- The browser clears game ID and token after `game-over` or lobby expiry, but keeps credentials when a game is suspended.

These tokens prevent casual name hijacking; they are not a substitute for user accounts or end-to-end authentication.

## Inspect an archive

Read an archive without modifying it:

```bash
python - <<'PY'
import gzip
import json
from pathlib import Path

path = Path("/var/lib/toc/finished/SESSION_ID.json.gz")
with gzip.open(path, "rt", encoding="utf-8") as file:
    payload = json.load(file)

print(json.dumps(payload, indent=2, ensure_ascii=False))
PY
```

Do not edit archives in place. Their cross-field invariants are intentionally strict, and a hand-edited document may no longer restore or validate.

## Backup and retention

Back up the complete data root so category transitions remain consistent. A simple local archive can be created with:

```bash
sudo tar -C /var/lib -czf toc-game-data-$(date +%F).tar.gz toc
```

Finished archives are not automatically expired. For a private server their compressed size should be modest, but operators should monitor disk usage and define a retention policy before public deployment. Never remove active or suspended files while the service is running unless you deliberately accept losing resumability.
