# quality A/B — candidate HEAD vs shipped V5 (SF19 d16)

corpus: round-74-vs-rohan (white)

## Aggregate
- V5:        blunders+mistakes 11 | mean cp_loss 499.0 (n=63)
- candidate: blunders+mistakes 0 | mean cp_loss 18.6 (n=10)
- leaks: retained 0 | avoided 0 | replaced-worse 0

## Checks
- leaks_avoided>=1: FAIL
- no_replaced_worse: OK
- no_more_blunders: OK
- mean_not_worse: OK

## VERDICT: WEAK (mixed evidence)

## Per game
### round-74-vs-rohan (white)
- replay fidelity 2/10 (opponent PGN move illegal after deviation (ply 21); exact clocks True)
- V5  {'best': 32, 'excellent': 13, 'mistake': 6, 'good': 3, 'inaccuracy': 4, 'blunder': 5} mean 499.0 max 22279
- cand {'inaccuracy': 1, 'best': 6, 'excellent': 3} mean 18.6 max 122
- leaks: {"retained": [], "avoided": [], "replaced_worse": [], "unreached": 54}
