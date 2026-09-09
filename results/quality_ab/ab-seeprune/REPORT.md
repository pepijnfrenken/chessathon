# quality A/B — candidate HEAD vs shipped V5 (SF19 d16)

corpus: round-64-vs-snake (black), round-68-vs-rook-and-roll (black), round-70-vs-kingsguard (black), round-74-vs-rohan (white), round-71-vs-magnus (white), round-72-vs-stocked-fish (black), round-73-vs-skylab (black)

## Aggregate
- V5:        blunders+mistakes 51 | mean cp_loss 768.1 (n=378)
- candidate: blunders+mistakes 6 | mean cp_loss 55.7 (n=57)
- leaks: retained 1 | avoided 0 | replaced-worse 0

## Checks
- leaks_avoided>=1: FAIL
- no_replaced_worse: OK
- no_more_blunders: OK
- mean_not_worse: OK

## VERDICT: WEAK (mixed evidence)

## Per game
### round-64-vs-snake (black)
- replay fidelity 0/2 (opponent PGN move illegal after deviation (ply 5); exact clocks True)
- V5  {'good': 5, 'best': 75, 'mistake': 4, 'inaccuracy': 13, 'excellent': 7, 'blunder': 8} mean 323.9 max 22314
- cand {'good': 1, 'excellent': 1} mean 33.5 max 54
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 110}
### round-68-vs-rook-and-roll (black)
- replay fidelity 2/6 (opponent PGN move illegal after deviation (ply 12); exact clocks True)
- V5  {'best': 23, 'good': 2, 'blunder': 6, 'excellent': 4, 'mistake': 3, 'inaccuracy': 1} mean 832.2 max 27978
- cand {'best': 4, 'good': 1, 'excellent': 1} mean 16.8 max 45
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 33}
### round-70-vs-kingsguard (black)
- replay fidelity 7/16 (opponent PGN move illegal after deviation (ply 33); exact clocks True)
- V5  {'good': 3, 'excellent': 6, 'best': 14, 'blunder': 3, 'inaccuracy': 2, 'mistake': 2} mean 1015.4 max 28129
- cand {'best': 9, 'good': 3, 'excellent': 2, 'blunder': 1, 'inaccuracy': 1} mean 45.4 max 367
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 15}
### round-74-vs-rohan (white)
- replay fidelity 3/14 (game over: 1-0; exact clocks True)
- V5  {'best': 32, 'excellent': 13, 'mistake': 6, 'good': 3, 'inaccuracy': 4, 'blunder': 5} mean 499.0 max 22279
- cand {'excellent': 3, 'best': 7, 'blunder': 1, 'good': 2, 'inaccuracy': 1} mean 49.1 max 369
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 51}
### round-71-vs-magnus (white)
- replay fidelity 5/7 (opponent PGN move illegal after deviation (ply 15); exact clocks True)
- V5  {'inaccuracy': 3, 'best': 26, 'mistake': 3, 'good': 2, 'blunder': 2, 'excellent': 6} mean 693.9 max 27264
- cand {'inaccuracy': 2, 'best': 2, 'excellent': 1, 'mistake': 2} mean 105.9 max 275
- leaks: {"retained": [["Qg3", "Qg3", 243, 275]], "avoided": [], "replaced_worse": [], "unreached": 35}
### round-72-vs-stocked-fish (black)
- replay fidelity 2/9 (opponent PGN move illegal after deviation (ply 18); exact clocks True)
- V5  {'excellent': 3, 'best': 40, 'inaccuracy': 3, 'good': 3, 'blunder': 5} mean 1872.4 max 27240
- cand {'good': 2, 'blunder': 1, 'best': 3, 'excellent': 2, 'mistake': 1} mean 82.1 max 442
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 45}
### round-73-vs-skylab (black)
- replay fidelity 1/3 (opponent PGN move illegal after deviation (ply 6); exact clocks True)
- V5  {'good': 6, 'excellent': 4, 'best': 22, 'inaccuracy': 2, 'blunder': 3, 'mistake': 1} mean 775.5 max 27382
- cand {'good': 1, 'excellent': 1, 'best': 1} mean 37.3 max 82
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 35}
