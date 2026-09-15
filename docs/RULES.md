# Toc game rules

This document describes the rules implemented by the application. The default preset is **Montsurvent**. A custom game may change most items described under [Configurable rules](#configurable-rules).

## Terminology

- A **participant** is a human using one browser identity.
- A **seat** is one colour, one hand, one set of four pawns, one exit position, and one house lane.
- A **team** is the set of seats whose house lanes must all be filled for a shared victory.
- The **ordinary track** is the circular sequence of coloured regions.
- A **house lane** is a colour's four finishing positions.
- To **kick** a pawn is to remove it from the board and return it to its owner's reserve.
- To **deploy** a pawn is to move it from reserve to its colour's exit position.

## Objective

Each seat begins with four pawns in reserve. A pawn is deployed onto its exit position, travels around the ordinary track, and then enters its own four-position house lane. A team wins immediately when all four house positions belonging to every seat on that team are filled.

If a seat fills its house before the rest of its team, future turns belonging to that completed seat move a teammate's pawns. The completed seat's hand and place in turn order do not disappear.

## Board geometry and position names

The board contains one ordinary-track region and one house lane per seat. A region contains 18 positions by default, or 16 under an alternative rule. A house lane always contains four positions.

Internally, ordinary-track positions are numbered from `0`. The zero position of a colour is physically the final numbered position of the previous colour. On a four-region board ordered red, blue, green, yellow:

- `spot-red-0` is red's exit and house-entry position;
- the same physical position can be described by players as yellow-18 on an 18-position track;
- red then moves through the red, blue, green, and yellow regions before returning to its entry.

House positions are internally numbered `0`–`3`, corresponding to the physical house positions 1–4. Their protocol identifiers are such as `house-red-0`.

Colours are chosen in the lobby, so the actual region order is the valid seat order derived for that game mode rather than a permanently fixed red-blue-green-yellow order.

## Starting, dealing, and turn order

The first ordered seat begins as dealer. Cards are dealt one at a time, beginning with the next seat in the configured rotation. The next seat after the dealer also takes the first turn.

The normal four-seat cycle consists of three deals: five cards per seat, then four, then four. The complete 52-card deck is consumed. Mode-specific schedules are used when necessary:

- two-seat duel: 10, 8, 8 cards per seat;
- six-seat teams: 3, 3, 3 cards per seat from a 54-card deck;
- four-seat modes: 5, 4, 4 cards per seat.

After all three deals, the discard pile becomes the next draw pile. By default its existing order is preserved. The dealer then rotates one seat and a new three-deal cycle begins.

## Card exchange

With the default rule, each two-seat team exchanges one card after every deal and before the first turn. Both selections are completed before either selected card is transferred.

Exchange is performed only when the rule is enabled **and every team has exactly two seats**. Consequently:

- it is available in both four-seat duel layouts;
- it is available in four-player 2v2 and six-player 2v2v2;
- it is not performed in a two-seat duel because each team contains one seat.

## Ordinary movement

A pawn moves forward by the value of the played card. Ordinary forward values are:

| Card | Forward movement |
|---|---:|
| 2 | 2 |
| 3 | 3 |
| 6 | 6 |
| 8 | 8 |
| 9 | 9 |
| 10 | 10 |
| Queen | 12 |

Ace, Four, Five, Seven, Jack, King, and Joker have the behaviour described below. Several of them can become ordinary movement cards through custom rules.

## Deployment

An Ace or King may deploy a pawn onto the acting colour's exit. A Joker may also deploy a pawn in six-seat mode.

Deployment is impossible if:

- the exit is blocked by a freshly deployed pawn under the protected-exit rule; or
- all four pawns of that colour are already on the board or in its houses.

A pawn newly deployed onto its exit is marked as fresh. It cannot immediately turn into its house lane; it must first leave the exit and travel before entering.

## House entry and movement

House entry is optional. Whenever a forward move could enter a legal house position, the player may instead continue along the ordinary track.

Entry requires an exact count. A pawn cannot overshoot the fourth house position. A pawn already inside its house may continue forward with an ordinary card or as part of a seven split, but it cannot move backward.

With the default entry position 18, a pawn enters after completing its full region. If entry is configured at position 16, it may turn into its house early: one step from the entry reaches house 1, two steps reach house 2, and so on. The player may still decline entry and continue to positions 17, 18, and the following region.

Backward house entry is disabled by default. When enabled, a backward Four may turn into the house from the configured entry position. It must still obey exit blocking and house protection.

## Occupied positions and kicking

Under the default landing rule, a pawn landing on an occupied, unprotected ordinary-track position kicks the occupant and takes its place. This applies regardless of ownership: the kicked pawn may belong to an opponent, a teammate, or the moving seat itself. Pawns never stack.

When landing kicks are disabled, landing on any occupied target is illegal instead.

An exit occupied by a freshly deployed pawn is protected and blocking under the default rule. It cannot be landed on, crossed, kicked, or used in a Jack switch. A Five may nevertheless select and force-move the pawn away from its protected exit; the resulting path and target must still be legal.

With protected houses enabled, house pawns cannot be crossed, landed on, or kicked. With protection disabled, a move may pass through an occupied house and the ordinary landing rule determines whether an occupied destination is kicked or makes the move illegal.

## Ace

An Ace always offers deployment. Its forward values are configurable:

- 1 only;
- 11 only; or
- either 1 or 11, which is the default.

## Four

A Four always allows an ordinary forward move of four. With the default rule it may instead move a pawn on the ordinary track four positions backward. A backward Four cannot move a pawn already inside a house.

Backward house entry and the direction of a resulting seven-hop are separate configurable rules.

## Five

By default, a Five lets the acting player select a pawn belonging to an opposing team and force it exactly five positions forward.

- The acting seat's pawns and its teammates' pawns cannot be selected.
- Only a pawn on the ordinary track can be selected.
- The forced pawn retains its owner.
- It cannot enter its owner's house; it remains on the ordinary track.
- Protected exits block its path and destination normally, although a pawn sitting on its own protected exit may be selected as the origin.
- Its landing follows the ordinary occupied-position rule.
- If it lands on a position numbered 7, seven-hopping may apply.

Custom rules can instead make Five an ordinary forward-five card, or allow both ordinary movement and forced-opponent movement.

## Seven

By default, a Seven is split into forward movement totalling exactly seven. The entire total must be legally completed; otherwise the Seven cannot be played.

With **path kicking enabled**, movement is selected and executed one step at a time:

- any number of the controlled colour's pawns may be used;
- a pawn may be selected repeatedly;
- ordinary-track and house pawns are eligible;
- every step must leave at least one legal continuation for the remaining total;
- each step resolves its landing immediately, including a kick.

With **path kicking disabled**, the seven is allocated in multi-step chunks:

- each chosen pawn receives one allocation during that split;
- only that pawn's final position resolves a landing and possible kick;
- intermediate occupied positions are not kicked;
- all allocations together must still total seven.

If splitting is disabled, Seven is an ordinary forward move of seven by one pawn.

A split can trigger seven-hopping only after the complete seven has been used and only when the final moved pawn ends on a numbered-7 track position.

## Seven-hopping

A qualifying move that finishes on an ordinary-track position numbered 7 may hop that pawn to the next region's position 7. Only one hop occurs; intermediate track positions are ignored. The hop destination obeys the ordinary landing rule.

Seven-hopping may be disabled, optional, or forced. It can be triggered by:

- an ordinary forward move, including a Joker's 18;
- a backward Four;
- a forced Five;
- the final movement of a complete seven split;
- a Jack switch only when the dedicated switch-then-hop rule is enabled.

For an optional hop caused by a Five, the acting player decides by default. A custom rule may give the decision to the forced pawn's owner.

A backward Four normally hops to the next position 7 in forward order. A custom rule makes it hop toward the previous region instead.

## Jack

By default, a Jack switches one controlled pawn on the ordinary track with another player's pawn on the ordinary track.

- The second pawn may belong to an opponent or a teammate.
- It cannot be another pawn belonging to the controlled colour.
- House pawns cannot participate.
- A protected exit at either end makes the switch illegal.

If Jack switching is disabled, Jack becomes an ordinary forward move of 11.

By default a switch does not trigger seven-hopping. If switch-then-hop is enabled, it is the acting player's moved pawn—not the displaced pawn—that may hop if its new position is numbered 7.

## King

A King may deploy a pawn or move a pawn 13 positions forward.

By default only the final landing can kick. If King path kicking is enabled, every occupied position crossed on the ordinary track is kicked. A King entering or moving inside a house may kick crossed house pawns only when house protection is disabled. A protected exit still blocks the route.

## Joker

The red and black Jokers exist only in the six-seat 54-card deck. A Joker may deploy a pawn or move one pawn 18 positions forward.

- It may enter a house or remain on the ordinary track.
- It cannot split its movement.
- Its final landing follows the ordinary occupied-position rule.
- Landing on a numbered-7 position may trigger seven-hopping.
- Joker path kicking is controlled by its own rule and is disabled by default; the King path rule does not affect it.

## Unable to play

By default, if a seat has no legal move for any card, its entire remaining hand is folded into the discard pile and that seat is skipped until the next deal.

With the alternative rule, the participant chooses one card to discard. On that seat's next turn, it must play if the changed board now provides a legal move; otherwise it discards one more card.

## Game modes and victory

| Mode | Seat order by participant | Team order | Victory requirement |
|---|---|---|---|
| Two-seat duel | A, B | 0, 1 | Fill the participant's single house lane |
| Four-seat duel, adjacent | A, A, B, B | 0, 0, 1, 1 | Fill both house lanes controlled by one participant |
| Four-seat duel, cross | A, B, A, B | 0, 1, 0, 1 | Fill both house lanes controlled by one participant |
| Four-player teams | A, B, C, D | 0, 1, 0, 1 | Both partners fill their houses |
| Six-player teams | A, B, C, D, E, F | 0, 1, 2, 0, 1, 2 | Both partners on one of three teams fill their houses |

## Configurable rules

The Montsurvent preset uses the bold/default value in each row.

| Rule field | Values | Effect |
|---|---|---|
| `card_exchange` | **true**, false | Exchange one card between paired seats before play |
| `exit_spot_is_protected_and_blocking` | **true**, false | Fresh exit pawn cannot be kicked, crossed, landed on, or switched |
| `house_spots_are_blocking_and_protected` | **true**, false | House pawns block movement and cannot be kicked |
| `landing_on_occupied_spot_kicks_piece` | **true**, false | Occupied landing kicks; when false, the landing is illegal |
| `shuffle_cards` | **`never`**, `on_dealer_change`, `on_dealer_cycle` | When a recycled discard pile is shuffled |
| `rotation` | **`clockwise`**, `counterclockwise` | Dealing, play, and dealer rotation direction |
| `deal_card_counts` | **`[5,4,4]`**, `[4,5,4]`, `[4,4,5]` | Order of deal sizes when compatible with the mode |
| `track_region_length` | **18**, 16 | Ordinary positions per region |
| `enter_house_at_spot` | **18**, 16 | Forward and backward house-entry position; cannot exceed region length |
| `cannot_play_folds_entire_hand` | **true**, false | Fold the hand or discard one card when no move exists |
| `four_can_move_backward` | **true**, false | Permit backward-four movement |
| `can_enter_house_backward` | true, **false** | Permit backward Four to enter a house |
| `five_behaviour` | **`force_move_opponent`**, `normal_move_by_five`, `both` | Available Five actions |
| `seven_can_split` | **true**, false | Split seven or move one pawn seven |
| `seven_split_kicks_pieces_on_path` | **true**, false | Resolve every single step, or only each allocated pawn's final landing |
| `seven_hopping` | `disabled`, **`optional`**, `forced` | Availability and choice of seven-hop |
| `five_hop_decider` | **`acting_player`**, `piece_owner` | Who decides an optional hop caused by Five |
| `seven_hopping_on_four_backward_goes_backward` | true, **false** | Backward Four hops to previous rather than next region's 7 |
| `jacks_can_switch` | **true**, false | Switch pawns or move forward 11 |
| `jacks_can_switch_then_seven_hop` | true, **false** | Allow acting pawn to hop after switching onto 7 |
| `ace_values` | **`[1,11]`**, `[1]`, `[11]` | Permitted forward Ace values; deployment is always allowed |
| `king_kicks_pieces_on_path` | true, **false** | Kick pawns crossed by a forward King |
| `joker_kicks_pieces_on_path` | true, **false** | Kick pawns crossed by a forward Joker |

The mode may override an incompatible `deal_card_counts` value so that one deck cycle always consumes the complete deck. In particular, two-seat and six-seat modes use their schedules shown above.
