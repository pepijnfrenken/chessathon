# quality A/B — candidate HEAD vs shipped V5 (SF19 d16)

corpus: round-64-vs-snake (black), round-68-vs-rook-and-roll (black), round-70-vs-kingsguard (black), round-74-vs-rohan (white), round-71-vs-magnus (white), round-72-vs-stocked-fish (black), round-73-vs-skylab (black)

## Aggregate
- V5:        blunders+mistakes 51 | mean cp_loss 768.1 (n=378)
- candidate: blunders+mistakes 8 | mean cp_loss 77.7 (n=81)
- leaks: retained 5 | avoided 0 | replaced-worse 0

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
- cand {'good': 1, 'excellent': 1} mean 44.0 max 48
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 110}
### round-68-vs-rook-and-roll (black)
- replay fidelity 16/21 (opponent PGN move illegal after deviation (ply 42); exact clocks True)
- V5  {'best': 23, 'good': 2, 'blunder': 6, 'excellent': 4, 'mistake': 3, 'inaccuracy': 1} mean 832.2 max 27978
- cand {'best': 11, 'good': 4, 'blunder': 3, 'excellent': 3} mean 128.0 max 1460
- leaks: {"retained": [["Bxc2", "Bxc2", 314, 412], ["Qa1+", "Qa1+", 491, 432], ["Kd6", "Kd6", 1804, 1460]], "avoided": [], "replaced_worse": [], "unreached": 22}
### round-70-vs-kingsguard (black)
- replay fidelity 16/25 (opponent PGN move illegal after deviation (ply 51); exact clocks True)
- V5  {'good': 3, 'excellent': 6, 'best': 14, 'blunder': 3, 'inaccuracy': 2, 'mistake': 2} mean 1015.4 max 28129
- cand {'good': 2, 'excellent': 9, 'best': 8, 'blunder': 3, 'inaccuracy': 2, 'mistake': 1} mean 93.6 max 770
- leaks: {"retained": [["Nb4", "Nb4", 399, 389]], "avoided": [], "replaced_worse": [], "unreached": 9}
### round-74-vs-rohan (white)
- replay fidelity 2/10 (opponent PGN move illegal after deviation (ply 21); exact clocks True)
- V5  {'best': 32, 'excellent': 13, 'mistake': 6, 'good': 3, 'inaccuracy': 4, 'blunder': 5} mean 499.0 max 22279
- cand {'inaccuracy': 1, 'best': 7, 'excellent': 2} mean 19.3 max 122
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 54}
### round-71-vs-magnus (white)
- replay fidelity 7/11 (opponent PGN move illegal after deviation (ply 23); exact clocks True)
- V5  {'inaccuracy': 3, 'best': 26, 'mistake': 3, 'good': 2, 'blunder': 2, 'excellent': 6} mean 693.9 max 27264
- cand {'inaccuracy': 3, 'best': 6, 'mistake': 1, 'good': 1} mean 62.2 max 247
- leaks: {"retained": [["Qg3", "Qg3", 243, 247]], "avoided": [], "replaced_worse": [], "unreached": 32}
### round-72-vs-stocked-fish (black)
- replay fidelity 3/6 (opponent PGN move illegal after deviation (ply 12); exact clocks True)
- V5  {'excellent': 3, 'best': 40, 'inaccuracy': 3, 'good': 3, 'blunder': 5} mean 1872.4 max 27240
- cand {'excellent': 1, 'inaccuracy': 1, 'best': 3, 'good': 1} mean 32.8 max 104
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 48}
### round-73-vs-skylab (black)
- replay fidelity 3/6 (opponent PGN move illegal after deviation (ply 12); exact clocks True)
- V5  {'good': 6, 'excellent': 4, 'best': 22, 'inaccuracy': 2, 'blunder': 3, 'mistake': 1} mean 775.5 max 27382
- cand {'good': 1, 'excellent': 1, 'best': 4} mean 16.8 max 70
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 32}
