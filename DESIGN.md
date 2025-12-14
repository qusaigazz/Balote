# Balote Engine – Design Notes

## Core Philosophy
- GameState is an immutable snapshot of the game
- Moves do not mutate state; they return a new GameState
- Design is solver- and simulation-friendly

Immutability makes the game state solver-friendly because each move produces a new, independent snapshot of the game. This allows the solver to explore many possible future branches from the same state without accidental interference, enables safe backtracking and replay, and allows states to be cached or compared reliably.

## Game Representation
- Cards are immutable (`Card`)
- Hands are tuples of cards
- Hokm vs Sun is represented by `trump: Suit | None`

## Modules
- cards.py: Card, Suit, Rank definitions
- gamestate.py: Complete snapshot of the game at a moment
- rules.py: Legal moves and state transitions
