# Default ruleset

Cards are dealt one-by-one, in clockwise order. In the first round, 5 cards are dealt, then in the two subsequent rounds, 4 cards are dealt.
Before each round, after cards are dealt, the players exchange one card of their choice with their partner.

Once all cards have been dealt, the player directly clockwise to the dealer becomes the new dealer. The discard pile is then dealt in the same fashion as above, without shuffling.

Player play one card in turn, rotating clockwise. After applying the effect(s) of the card that has been played, the card is placed on the discard pile. If a player cannot play, he must fold all his remaining cards to the discard pile.

The goal of the game is to place all the piece of both player in a team into the "house" spots. To do that, player must first place a piece on the board by playing an Ace or a King. The piece are places on the "exit" spot on the track. The piece must then move from this spot (either forward or backward) and then enter the "house" spots by passing again on the exit spot and then moving on to the house spots.

Once a player has filled his house, he keeps playing using his partner's pieces. The game ends when a team manages to fill both the team-member's houses.

## Track and house entrance

The colour order is:

1. Red
2. Blue
3. Green
4. Yellow

A player's starting position is also the entrance to that player's house lane.

For example, red's starting position can be described as either:

- `yellow-18`, because it is the final position of yellow territory; or
- `red-0`, because it is red's starting and house-entry position.

The current implementation uses `red-0`.

A newly deployed piece on its starting position is protected and cannot immediately enter its houses.

After moving forward around the board, a red piece may enter the red house lane when it reaches or passes `red-0`.

Entering the house lane is optional. The player may instead continue around the ordinary track.

House entry can only be performed while moving forward. A backward move with a four cannot enter a house lane.

## House movement

The four house positions are internally numbered 0–3, corresponding to physical house positions 1–4.

From the house-entry position:

- 1 step reaches house 1 (`house-red-0`).
- 2 steps reaches house 2 (`house-red-1`).
- 3 steps reaches house 3 (`house-red-2`).
- 4 steps reaches house 4 (`house-red-3`).

The move must use an exact count. A piece cannot overshoot the final house position.

Pieces inside a house lane:

- Can move forward using ordinary cards.
- Can move forward as part of a seven split.
- Cannot move backward with a four.
- Cannot be switched with a Jack.
- Cannot be kicked.
- Cannot jump over another piece.
- Cannot land on an occupied house position.
- Cannot share a house position.

## Four

A four allows a player to move a piece by four either forward or backward.

## Five

A five allows the acting player to choose one opposing team's piece
and move it exactly five positions forward.

- The acting player's own pieces cannot be selected.
- The acting player's partner's pieces cannot be selected.
- Only pieces on the ordinary circular track can be selected.
- Pieces inside houses cannot be selected.
- The piece remains on the ordinary track and cannot enter its houses.
- Protected starting positions block its movement normally.
- Landing on an occupied non-protected position kicks the occupying piece.
- The moved piece retains its original owner.
- If no opposing piece can legally move five positions, the five cannot be played.

## Seven split

A seven moves the player's pieces a total of exactly seven forward
positions.

- The steps may be distributed between any number of the player's pieces.
- The same piece may be moved multiple times.
- Pieces may be moved in any order.
- Pieces on the ordinary track and inside houses may be moved.
- All seven steps must be legally completed.
- If no complete seven-step sequence exists, the seven cannot be played.
- Kicking occurs immediately after each individual step.
- Every individual step must obey ordinary blocking and house rules.

## Jack

A Jack can be used to switch the player's piece with any other player's piece. It cannot be used by a player to switch his own piece with another of hiw own piece.

## King

A King can be used either to place a piece on the board, on the "exit" spot of the player's color, or move a piece forward by thirtheen.

## Ace

An Ace can be used either to place a piece on the board, on the "exit" spot of the player's color, or move a piece forward by eleven or by one.

## Seven-hopping

After a movement finishes on a track position numbered 7, the player who played the card may move that piece to the next position numbered 7.

- Seven-hopping is optional.
- Only one hop may occur.
- Intermediate positions are ignored.
- Landing on an occupied destination kicks its occupant, including one's own or one's partner's piece.
- The initial movement is resolved before the hop, including any kick on the first position numbered 7.
- Forward movement, a backward four, and a five may trigger seven-hopping.
- With a five, the player who played the card decides whether the opposing piece hops.
- A seven-split may trigger a hop only after all seven steps have been completed, and only when its final step lands on a position numbered 7.
- A Jack switch never triggers seven-hopping.

## Landing on occupied track positions

A piece may land on any non-protected occupied track position.

The occupying piece is kicked, including when it belongs to:

- An opponent.
- The moving player's partner.
- The moving player themselves.

The moving piece replaces the occupying piece. Pieces cannot stack.

This rule also applies to every individual step of a seven split.