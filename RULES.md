# Default ruleset

## Track and house entrance

The colour order is:

1. Red
2. Blue
3. Green
4. Yellow

A player's starting position is also the entrance to that player's
house lane.

For example, red's starting position can be described as either:

- `yellow-18`, because it is the final position of yellow territory; or
- `red-0`, because it is red's starting and house-entry position.

The current implementation uses `red-0`.

A newly deployed piece on its starting position is protected and cannot
immediately enter its houses.

After moving forward around the board, a red piece may enter the red
house lane when it reaches or passes `red-0`.

Entering the house lane is optional. The player may instead continue
around the ordinary track.

House entry can only be performed while moving forward. A backward move
with a four cannot enter a house lane.

## House movement

The four house positions are internally numbered 0–3, corresponding to
physical house positions 1–4.

From the house-entry position:

- 1 step reaches house 1 (`house-red-0`).
- 2 steps reaches house 2 (`house-red-1`).
- 3 steps reaches house 3 (`house-red-2`).
- 4 steps reaches house 4 (`house-red-3`).

The move must use an exact count. A piece cannot overshoot the final
house position.

Pieces inside a house lane:

- Can move forward using ordinary cards.
- Can move forward as part of a seven split.
- Cannot move backward with a four.
- Cannot be switched with a Jack.
- Cannot be kicked.
- Cannot jump over another piece.
- Cannot land on an occupied house position.
- Cannot share a house position.
