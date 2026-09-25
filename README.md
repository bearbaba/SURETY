# SURETY

Performance bonds for machine work.
GenLayer judges the file. We hold the money.

v1 underwrites one peril: a pinned spec versus a delivered artifact.
This is a surety book, not an insurance company.

Settled on GenLayer. Underwritten here.

## Term sheet (frozen 30 days)

| Parameter | Value |
|---|---|
| Surety fee | 8% of notional, paid at `post` |
| Performance bond | 15% of notional, paid at `post` |
| Contest bond | 10% of notional, paid at `contest` |
| Max per risk | 5% of book |
| Halt new bonds | utilization ≥ 80% |
| Standing to contest | recorded `client` or book `owner` |
| Impairment | book pays client notional; contest bond returned |
| Hold | principal receives performance bond; contest bond stays in book |
| Out of scope | flights, elections, hacks, lending, tokens |

## Repo

- `contracts/surety.py` — Intelligent Contract
- `web/index.html` — public book
- `marks/` — expected vs on-chain verdicts

## Studio

1. https://studio.genlayer.com
2. Paste `contracts/surety.py` and deploy
3. `fund("junior")` then `fund("senior")`
4. `post(...)` with value = 23% notional
5. `contest(...)` from the client with value = 10% notional
6. Write the mark into `marks/`
