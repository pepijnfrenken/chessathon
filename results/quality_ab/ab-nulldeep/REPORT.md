# quality A/B — candidate HEAD vs shipped V5 (SF19 d16)

corpus: round-64-vs-snake (black), round-68-vs-rook-and-roll (black), round-70-vs-kingsguard (black), round-74-vs-rohan (white), round-71-vs-magnus (white), round-72-vs-stocked-fish (black), round-73-vs-skylab (black)

## Aggregate
- V5:        blunders+mistakes 51 | mean cp_loss 768.1 (n=378)
- candidate: blunders+mistakes 7 | mean cp_loss 845.0 (n=70)
- leaks: retained 2 | avoided 0 | replaced-worse 0

## Checks
- leaks_avoided>=1: FAIL
- no_replaced_worse: OK
- no_more_blunders: OK
- mean_not_worse: FAIL

## VERDICT: WEAK (mixed evidence)

## Per game
### round-64-vs-snake (black)
- replay fidelity 0/2 (opponent PGN move illegal after deviation (ply 5); exact clocks True)
- V5  {'good': 5, 'best': 75, 'mistake': 4, 'inaccuracy': 13, 'excellent': 7, 'blunder': 8} mean 323.9 max 22314
- cand {'good': 1, 'excellent': 1} mean 33.5 max 51
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 110}
### round-68-vs-rook-and-roll (black)
- replay fidelity 0/5 (opponent PGN move illegal after deviation (ply 10); exact clocks True)
- V5  {'best': 23, 'good': 2, 'blunder': 6, 'excellent': 4, 'mistake': 3, 'inaccuracy': 1} mean 832.2 max 27978
- cand {'best': 1, 'excellent': 4} mean 11.6 max 18
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 34}
### round-70-vs-kingsguard (black)
- replay fidelity 25/30 (played to end; exact clocks True)
- V5  {'good': 3, 'excellent': 6, 'best': 14, 'blunder': 3, 'inaccuracy': 2, 'mistake': 2} mean 1015.4 max 28129
- cand {'good': 6, 'excellent': 7, 'best': 11, 'blunder': 3, 'mistake': 3} mean 1924.8 max 28213
- leaks: {"retained": [["Nb4", "Nb4", 399, 394]], "avoided": [], "replaced_worse": [], "unreached": 4}
### round-74-vs-rohan (white)
- replay fidelity 1/10 (game over: 1-0; exact clocks True)
- V5  {'best': 32, 'excellent': 13, 'mistake': 6, 'good': 3, 'inaccuracy': 4, 'blunder': 5} mean 499.0 max 22279
- cand {'inaccuracy': 1, 'best': 8, 'good': 1} mean 18.9 max 125
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 54}
### round-71-vs-magnus (white)
- replay fidelity 7/11 (opponent PGN move illegal after deviation (ply 23); exact clocks True)
- V5  {'inaccuracy': 3, 'best': 26, 'mistake': 3, 'good': 2, 'blunder': 2, 'excellent': 6} mean 693.9 max 27264
- cand {'inaccuracy': 3, 'best': 5, 'mistake': 1, 'good': 2} mean 68.2 max 243
- leaks: {"retained": [["Qg3", "Qg3", 243, 243]], "avoided": [], "replaced_worse": [], "unreached": 32}
### round-72-vs-stocked-fish (black)
- replay fidelity 3/6 (opponent PGN move illegal after deviation (ply 12); exact clocks True)
- V5  {'excellent': 3, 'best': 40, 'inaccuracy': 3, 'good': 3, 'blunder': 5} mean 1872.4 max 27240
- cand {'excellent': 1, 'inaccuracy': 1, 'best': 3, 'good': 1} mean 29.7 max 92
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 48}
### round-73-vs-skylab (black)
- replay fidelity 3/6 (opponent PGN move illegal after deviation (ply 12); exact clocks True)
- V5  {'good': 6, 'excellent': 4, 'best': 22, 'inaccuracy': 2, 'blunder': 3, 'mistake': 1} mean 775.5 max 27382
- cand {'good': 2, 'best': 3, 'excellent': 1} mean 27.0 max 79
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 32}
