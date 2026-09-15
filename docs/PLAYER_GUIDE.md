# Player guide

## What Toc is

Toc is a race game played with cards and pawns. Each seat owns a colour, a hand, four pawns, one exit position on the shared track, and a four-position house lane. The goal is to fill every house lane belonging to your team before another team fills theirs.

In this application, a **participant** means one human connected from a browser. A **seat** means one colour, hand, and pawn set. Usually each participant controls one seat. In the four-seat duel modes, each of the two participants controls two seats and therefore two separate hands.

## Create a game

1. Open `/toc/play/` in a modern browser.
2. Enter a player name. Names are 1–40 characters and may contain ASCII letters, digits, `.`, `_`, `~`, and `-`. The names `.` and `..` are not allowed.
3. Choose a game mode.
4. Choose the Montsurvent rules preset or select **Custom** and edit individual rules.
5. Select **Create game**.
6. In the lobby, choose the required number of distinct colours and a team, then confirm.

The game is listed under **Open games** until it starts or expires. Its human-readable name, such as `nimble-horse`, is also its join code.

## Join a game

1. Enter your player name on the start screen.
2. Find the game under **Open games**.
3. Select its join action.
4. Choose a team and the required number of colours, then confirm.

The lobby prevents a team from exceeding its participant capacity and prevents two seats from claiming the same colour. A game starts automatically when every required participant has joined and confirmed a valid seat selection.

## Game modes

| Mode | Humans | Seats | Teams | Hands per human | Default deal schedule |
|---|---:|---:|---:|---:|---|
| Two-seat duel | 2 | 2 | 2 | 1 | 10, 8, 8 |
| Four-seat duel, adjacent | 2 | 4 | 2 | 2 | 5, 4, 4 |
| Four-seat duel, cross | 2 | 4 | 2 | 2 | 5, 4, 4 |
| Four-player teams | 4 | 4 | 2 | 1 | 5, 4, 4 |
| Six-player teams | 6 | 6 | 3 | 1 | 3, 3, 3 |

In an adjacent four-seat duel, each participant's colours sit next to each other. In a cross duel, the participants' colours alternate. Each hand remains independent even though one person controls both.

The six-player mode adds a red Joker and a black Joker so the 54-card deck divides evenly into three cards per seat in each deal.

## Reading the game screen

- The highlighted player block and card box identify the active seat. Their glow uses that seat's colour.
- Your hand or hands appear below the board. A coloured background identifies the seat to which each hand belongs.
- Opponents' cards are shown face down.
- The dealer marker identifies the current dealer.
- The centre discard pile shows the last played card. Played cards animate from the active seat toward it.
- The turn banner contains the current instruction.
- The activity panel shows translated public game messages.
- The rules panel shows the exact rules selected for this game; hover or focus a question-mark icon for a description.

The interface supports English and French and can change language while a game is in progress.

## Making a move

When prompted to play:

1. Select the hand associated with the active seat if you control more than one.
2. Select a card, then confirm it with a second selection.
3. If prompted, select an origin pawn.
4. If prompted, select a destination or another pawn.
5. Answer any optional seven-hop prompt.

During origin and destination selection, use **Cancel card selection** to return to card choice. Cards cannot be submitted when the server is not waiting for a card from that participant; visual card selection outside your prompt does not create a legal move.

The server is authoritative: it offers only moves that are legal under the selected rules and validates the answer against the current prompt.

## Card exchange

If card exchange is enabled and every team has exactly two seats, each pair exchanges one card after a deal and before turns begin. Both choices are made before the cards are swapped.

In a four-seat duel, the same human selects one card from each of their two hands. In four-player and six-player team games, teammates choose simultaneously. The two-seat duel has one seat per team, so no exchange takes place.

## Finished colours

When all four pawns of a seat are in its house lane, that colour is complete. Future turns for that seat control its teammate's pawns. Hands and turns still belong to their original seats; only pawn control changes.

The game ends as soon as every colour on one team has a full house lane.

## Disconnecting and resuming

The browser stores a game name, player name, and private resume token in local storage. The token is required to reclaim an existing participant name. Do not share it.

- A brief disconnection preserves the current prompt. Reconnecting with the same browser and name restores the UI, hands, and pending choice.
- If everyone disconnects for 30 seconds, or no game activity occurs for 15 minutes, the game is suspended and removed from memory.
- A suspended game is loaded from disk when a participant reconnects with the game name and correct token.
- Play resumes only after all participants have reconnected.
- When the game finishes, the browser removes its stored game name and resume token.

Private/incognito tabs in the same browser may share or isolate storage differently depending on the browser. For reliable multi-player testing on one computer, use separate browser profiles.

## Lobby expiry

An unstarted lobby remains open for 15 minutes. After that, it closes without being archived and connected participants return to the start screen.

## If something goes wrong

- If ordinary HTTP pages work but the game cannot establish a socket connection, verify that the server environment contains the `websockets` package and that the reverse proxy forwards WebSocket upgrades.
- Check the browser developer console for a WebSocket close code.
- Check the service logs with `journalctl -u toc.service`.
- Preserve the corresponding `.json.gz` archive when reporting a game-state bug; it contains the state and audit trail needed for diagnosis.

See [Game rules](./RULES.md) for all card and board behaviour.
