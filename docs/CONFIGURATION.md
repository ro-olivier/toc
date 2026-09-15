# Configuration reference

Configuration is split into three layers:

1. environment variables for deployment-specific paths and logging;
2. process constants in `settings.py` for lifecycle and protocol policy;
3. per-game mode and rule objects selected at lobby creation.

## Environment variables

| Name | Default | Read when | Description |
|---|---|---|---|
| `TOC_DATA_DIRECTORY` | `<repository>/game-data` | process import/startup | Root for `active`, `suspended`, and `finished` archives |
| `TOC_LOG_LEVEL` | `INFO` | logging setup | Standard logging level name; unknown values fall back to `INFO` |

Example:

```bash
TOC_DATA_DIRECTORY=/tmp/toc-data TOC_LOG_LEVEL=DEBUG python -m uvicorn main:app --reload
```

Production should use an absolute data path outside the Git checkout.

## Lifecycle settings

These constants are in `settings.py`:

| Constant | Current value | Meaning |
|---|---:|---|
| `LOBBY_LIFETIME_SECONDS` | 900 | Maximum age of an unstarted lobby |
| `GAME_INACTIVITY_SECONDS` | 900 | Started game inactivity before suspension |
| `ALL_PLAYERS_DISCONNECTED_GRACE_SECONDS` | 30 | Time with nobody connected before suspension |
| `SESSION_MONITOR_INTERVAL_SECONDS` | 5 | Background monitor polling interval |
| `MAX_PLAYER_NAME_LENGTH` | 40 | Maximum normalized name length |
| `RESUME_TOKEN_BYTES` | 32 | Entropy input to URL-safe resume-token generation |
| `PLAYER_NAME_PATTERN` | `[A-Za-z0-9._~-]+` | Allowed player-name characters |

Changing timeouts does not affect archive structure. Changing name/token policy may affect clients or identity tests and should be done deliberately.

## Available seat colours

The current lobby palette is:

```text
red, blue, green, yellow, orange, purple, pink, cyan, lime, brown, black, white
```

Colours are unique per seat within a game. They are both logical identifiers and CSS colour keys, so a new colour requires model availability plus browser presentation support.

## Game mode configuration

Mode definitions in `toc/model/game_mode.py` are immutable records. Each declares:

- mode and optional layout;
- human participant, seat, and team counts;
- participant and team indices in physical seat order;
- default per-seat deal sizes;
- number of Jokers added to the standard deck.

The constructor validates equal team distribution, equal seat ownership per participant, consistent participant/team assignment, and complete deck consumption.

| Mode | Participants | Seats | Teams | Participant pattern | Team pattern | Deal | Jokers |
|---|---:|---:|---:|---|---|---|---:|
| `duel_two` | 2 | 2 | 2 | `0,1` | `0,1` | `10,8,8` | 0 |
| `duel_four` / `adjacent` | 2 | 4 | 2 | `0,0,1,1` | `0,0,1,1` | `5,4,4` | 0 |
| `duel_four` / `cross` | 2 | 4 | 2 | `0,1,0,1` | `0,1,0,1` | `5,4,4` | 0 |
| `team_four` | 4 | 4 | 2 | `0,1,2,3` | `0,1,0,1` | `5,4,4` | 0 |
| `team_six` | 6 | 6 | 3 | `0,1,2,3,4,5` | `0,1,2,0,1,2` | `3,3,3` | 2 |

The default mode is `team_four`.

## Rulesets

`GameRules` is an immutable, slotted dataclass. The only named preset is `montsurvent`, which is also the default. A game stores both the preset label and all effective values so future preset edits cannot change an archived game retroactively.

The complete semantic reference is in [Game rules](../RULES.md).

### Programmatic construction

```python
from toc.model.rules import GameRules, Rotation, SevenHopping

rules = GameRules(
    rotation=Rotation.COUNTERCLOCKWISE,
    seven_hopping=SevenHopping.FORCED,
    track_region_length=16,
    enter_house_at_spot=16,
)
```

Because the object is frozen, create a new instance rather than changing a field after construction.

### Serialized custom rules

JSON uses enum string values and arrays for tuple fields:

```json
{
  "card_exchange": true,
  "exit_spot_is_protected_and_blocking": true,
  "house_spots_are_blocking_and_protected": true,
  "landing_on_occupied_spot_kicks_piece": true,
  "shuffle_cards": "never",
  "rotation": "clockwise",
  "deal_card_counts": [5, 4, 4],
  "track_region_length": 18,
  "enter_house_at_spot": 18,
  "cannot_play_folds_entire_hand": true,
  "four_can_move_backward": true,
  "can_enter_house_backward": false,
  "five_behaviour": "force_move_opponent",
  "seven_can_split": true,
  "seven_split_kicks_pieces_on_path": true,
  "seven_hopping": "optional",
  "five_hop_decider": "acting_player",
  "seven_hopping_on_four_backward_goes_backward": false,
  "jacks_can_switch": true,
  "jacks_can_switch_then_seven_hop": false,
  "ace_values": [1, 11],
  "king_kicks_pieces_on_path": false,
  "joker_kicks_pieces_on_path": false
}
```

Submit it with:

```json
{
  "creatorName": "Alice",
  "preset": "custom",
  "rules": {"...": "complete values as above"},
  "mode": "team_four"
}
```

Unknown fields are rejected. `track_region_length` and `enter_house_at_spot` must each be 16 or 18, and entry cannot exceed region length. The normal configurable deal list contains one 5 and two 4 values. Ace values must be `[1]`, `[11]`, or `[1,11]`.

The mode resolves the final deal schedule. It uses the custom rule schedule only if `seatCount × sum(schedule)` equals the mode's deck size; otherwise it falls back to the mode default.

## Rule schema endpoint

The browser does not hard-code the allowed values alone. `GET /toc/api/rule-presets` exposes each field as either:

```json
{"type":"boolean"}
```

or:

```json
{"type":"choice","options":[...]}
```

The UI metadata in `web/js/context.js` assigns each rule a display group and translation keys. Backend schema fields lacking UI metadata deliberately cause a browser initialization error, making partially implemented rules visible during development.

## Translation configuration

`web/translations.js` defines `en` and `fr`. Static elements use `data-i18n` or `data-i18n-placeholder`; dynamic elements and messages call the i18n helper. The language choice is stored in the browser.

When adding a backend message:

1. register its literal key in `MESSAGE_KEYS`;
2. add the key to both browser languages;
3. supply a useful English fallback and explicit interpolation parameters;
4. run translation-key parity and backend-key coverage tests.

Do not translate developer-only console or log messages unless they are presented to players.

## Version constants

`toc/infrastructure/versions.py` currently declares:

| Constant | Value | Increment when |
|---|---:|---|
| `ENGINE_VERSION` | `1.0.0` | Identifying a new engine release |
| `ARCHIVE_FORMAT_VERSION` | 4 | Persisted archive shape becomes incompatible |
| `RULES_FORMAT_VERSION` | 1 | Serialized rule meaning/shape becomes incompatible |
| `WEBSOCKET_PROTOCOL_VERSION` | 2 | Existing clients cannot safely interpret the protocol |

Engine version is descriptive; format versions are active validation gates. A format bump without a migration means older archives are rejected.
