# HTTP and WebSocket protocol

This is the application protocol for engine version 1.0.0. The WebSocket protocol version sent by the server is `2`.

## General conventions

- JSON is used for all request and message bodies.
- Join codes are normalized to lowercase after surrounding whitespace is removed.
- Player names are trimmed but remain case-sensitive.
- Seat IDs, participant IDs, session IDs, message IDs, and request IDs are opaque strings.
- A card is represented as `{"suit":"♥️","value":"A"}`. Ranks are `2`–`9`, `T`, `J`, `Q`, `K`, `A`, or `JOKER`; Joker suits are `red` and `black`.
- Ordinary positions use `spot-<colour>-<zero-based-number>` and houses use `house-<colour>-<zero-based-number>`.

## HTTP endpoints

### `GET /toc`

Health/status probe.

```json
{"message":"Game backend is running."}
```

### `GET /toc/api/rule-presets`

Returns the default preset name, every preset's complete rule values, a form-oriented rule schema, and registered backend translation keys.

```json
{
  "default": "montsurvent",
  "presets": {"montsurvent": {}},
  "schema": {
    "card_exchange": {"type": "boolean"},
    "rotation": {"type": "choice", "options": ["clockwise", "counterclockwise"]}
  },
  "messageKeys": []
}
```

The abbreviated empty objects above are placeholders; the real response contains all rule fields and translation keys.

### `GET /toc/api/open-lobbies`

Returns unstarted, non-full, non-expired lobbies from the current process.

```json
{
  "lobbies": [
    {
      "gameName": "nimble-horse",
      "creatorName": "Alice",
      "playerCount": 1,
      "playerCapacity": 4,
      "mode": {"name": "team_four", "layout": null}
    }
  ]
}
```

Suspended and finished games are not public lobbies.

### `POST /toc/api/create-game`

Creates an in-memory lobby.

Accepted fields:

| Field | Type | Default |
|---|---|---|
| `creatorName` | string | `""` |
| `preset` | string | `"montsurvent"` |
| `rules` | object | absent |
| `mode` | string | `"team_four"` |
| `layout` | string or null | absent |

For a named preset, omit `rules`. For a custom ruleset, send `"preset":"custom"` and a complete or valid partial `rules` object accepted by `GameRules.from_dict`.

Mode values are `duel_two`, `duel_four`, `team_four`, and `team_six`. `duel_four` requires `layout` equal to `adjacent` or `cross`; other modes reject a layout.

Example:

```http
POST /toc/api/create-game
Content-Type: application/json

{
  "creatorName": "Alice",
  "preset": "montsurvent",
  "mode": "duel_four",
  "layout": "cross"
}
```

Success:

```json
{
  "gameId": "nimble-horse",
  "creatorName": "Alice",
  "preset": "montsurvent",
  "rules": {},
  "gameMode": {"name": "duel_four", "layout": "cross"}
}
```

The real `rules` object contains every effective field.

Invalid creation data returns HTTP 422. `detail` is a translatable message object:

```json
{
  "detail": {
    "type": "http-error",
    "messageKey": "errors.invalid_game_configuration",
    "parameters": {},
    "fallback": "..."
  }
}
```

## Translatable message envelope

User-facing backend messages use:

```json
{
  "type": "log",
  "messageKey": "gameplay.deal_started",
  "parameters": {"deal": 1, "dealer": "Alice"},
  "fallback": "Deal 1 starts with Alice as dealer."
}
```

Clients should translate `messageKey` with `parameters`; if the key is absent locally, they must show `fallback`. Message-specific payload fields may be added, but `type`, `messageKey`, `parameters`, `fallback`, and legacy `msg` are reserved.

## WebSocket connection

Connect to:

```text
ws://HOST/toc/ws/{gameId}/{playerName}
wss://HOST/toc/ws/{gameId}/{playerName}
```

Use WSS when the page uses HTTPS. Both path values must be URL encoded.

### Identity handshake

The server accepts the upgrade, then waits up to five seconds for exactly one identity message:

```json
{"type":"identify","resumeToken":null}
```

For a new participant, use `null`. To reclaim an existing name, provide the previously issued token. A token supplied for a new name is not used as proof for another identity.

On success, the server sends:

```json
{
  "type": "ready",
  "protocolVersion": 2,
  "sessionId": "opaque-session-id",
  "playerId": "opaque-participant-id",
  "resumeToken": "private-token"
}
```

Store the resume token privately and key it by game plus player name. A returning participant receives the same token value supplied in the handshake; the server persists only its hash.

After `ready`, a new participant receives lobby state. A returning participant receives lobby/full UI state as appropriate, their private hands, and any pending prompt.

## Client-to-server messages

All post-handshake messages must be JSON objects with a recognized string `type`. Known malformed messages receive `errors.invalid_message_format`; unknown types receive `errors.unknown_message_type`; invalid JSON receives `errors.invalid_json_message`. The connection remains open for these protocol errors.

The browser adds a random `id` to normal messages for diagnostics. Interactive answers must include the `requestId` from the server prompt.

### Configure participant

```json
{
  "id": "client-message-id",
  "type": "configure-player",
  "team": "0",
  "colors": ["red", "green"]
}
```

`colors` must contain exactly `seatsPerParticipant` distinct, available colours. A legacy single `color` string is also accepted when only one colour is required. Configuration has no prompt `requestId`.

### Select card

Used for ordinary card choice, forced discard choice, and exchange prompts.

```json
{
  "id": "client-message-id",
  "requestId": "prompt-request-id",
  "type": "card_selection",
  "name": "Alice",
  "seatId": "seat-id",
  "value": "A",
  "suit": "♥️"
}
```

### Select origin or target position

```json
{
  "id": "client-message-id",
  "requestId": "prompt-request-id",
  "type": "spot_selection",
  "name": "Alice",
  "seatId": "seat-id",
  "result": "spot-red-7"
}
```

### Answer optional seven-hop

```json
{
  "id": "client-message-id",
  "requestId": "prompt-request-id",
  "type": "seven_hop_choice",
  "name": "Alice",
  "result": true
}
```

`result` must be a JSON boolean, not a string.

### Cancel move selection

```json
{
  "id": "client-message-id",
  "requestId": "prompt-request-id",
  "type": "cancel_move_selection"
}
```

Cancellation is honored only while an origin or target prompt explicitly has `canCancel: true`. It returns the engine to card selection.

## Request correlation and duplicate input

Interactive server prompts are `query-card`, `query-card-exchange`, `query-origin`, `query-target`, and `query-seven-hop`. Each contains a `requestId`.

The server ignores an answer when:

- no prompt is pending for that participant;
- its `requestId` differs from the current prompt;
- the same response is already queued for the same prompt.

This is intentional and prevents old browser actions from satisfying a newer prompt.

## Important server-to-client messages

All player-related gameplay messages identify the acting seat with `seatId` and also include player name, colour, and team fields. Where a different pawn owner is moved, `movedSeatId` and corresponding `movedPlayer...` fields identify it. `playerId` fields containing a name remain for browser compatibility; durable identity is represented by participant/seat IDs elsewhere.

| Type | Important fields | Purpose |
|---|---|---|
| `ready` | `protocolVersion`, `sessionId`, `playerId`, `resumeToken` | Handshake success |
| `lobby-state` | see below | Complete current lobby description |
| `lobby-error` | translation envelope | Invalid team/colour/configuration choice |
| `full-ui-state` | players, pieces, active seat, board geometry, rules, last card | Rebuild the game UI after start/reconnect |
| `draw` | seat identity, `cards` | A new private hand was dealt; client also updates hidden counts |
| `reveal` | seat identity, `cards` | Reveal an owned seat's hand |
| `dealer` | seat identity | Mark the dealer |
| `receive-card-from-friend` | seat identity, `value`, `suit` | Replace an exchanged card |
| `next-player` | seat identity plus translation | Set active seat and announce the turn |
| `forced-play` | seat/card/origin/target plus translation | Inform one participant that only one move exists |
| `fold` | seat identity plus translation | Empty an unplayable hand |
| `discard` | seat/card plus translation | Discard one unplayable card |
| `play` | acting/moved seats, card, origin, target plus translation | Apply an ordinary, deploy, entry, Five, or switch action |
| `seven-start` | seat/card plus translation | Discard the Seven and begin its sequence |
| `seven-step` | acting/moved seats, origin, target, remaining/used steps | Apply one selected split segment |
| `seven-hop` | acting/moved seats, origin, target | Apply a hop |
| `path-kicks` | `positions` | Clear pawns kicked on a King/Joker path |
| `query-card` | seat identity, `requestId` plus translation | Ask for a playable card or a specified discard |
| `query-card-exchange` | seat identity, `requestId` plus translation | Ask for exchange card |
| `query-origin` | seat identity, `requestId`, `originOptions`, `canCancel` | Ask for pawn origin |
| `query-target` | seat identity, `requestId`, `targetOptions`, `canCancel` | Ask for destination |
| `query-seven-hop` | seat identity, `requestId`, `origin`, `target` | Ask whether to hop |
| `reject-card-selection` | seat identity plus translation | Selected card currently has no legal move |
| `discard-pile-cleared` | none | New deck cycle started |
| `game-over` | `winners` plus translation | Game finished |
| `log` | translation envelope | Public activity message |
| `error` | translation envelope | Recoverable protocol/game error |

### Lobby state

`lobby-state` contains:

- `gameId`, `started`, and `creatorName`;
- `players`: one item per participant with name, team, colours, seats, connection, and configuration state;
- available colours and counts/capacity per team;
- participant and seat capacity;
- ordered seat IDs once order is known;
- game mode and optional layout;
- track region count/length and house-entry position;
- effective ruleset and seats per participant.

### Full UI state

`full-ui-state` contains one item per seat rather than participant, every occupied board position, active seat, board geometry, effective ruleset, card counts, and the last played card. Private card faces are sent separately with `reveal` messages only to the participant who controls those seats.

## WebSocket close codes

| Code | Meaning | Client action |
|---:|---|---|
| 1006 | Abnormal closure/server unreachable; browser-generated, not sent in a close frame | Show connectivity error |
| 1011 | Unexpected internal server error | Show generic closure and inspect server logs |
| 4001 | No live or restorable game for the join code | Return to game selection |
| 4002 | Player identity is already active or player context cannot be created | Choose another name or close the other connection |
| 4004 | Lobby participant capacity reached | Choose another lobby |
| 4005 | Identity timeout, malformed identity, or invalid resume token | Use the stored token for that exact game/name |
| 4006 | Lobby expired | Clear stored game credentials and return to start |
| 4007 | Game suspended | Keep credentials; reconnect to restore later |
| 4008 | Invalid player name | Choose a URL-safe name |

## Compatibility

Clients should reject or warn on an unsupported `protocolVersion`. Any incompatible message-shape change should increment `WEBSOCKET_PROTOCOL_VERSION` in `toc/infrastructure/versions.py` and update protocol tests.
