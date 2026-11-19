# gta6-trophy-rarity-forecast-01-entry

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/yuzansama/gta6-trophy-rarity-forecast-01-entry/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/yuzansama/gta6-trophy-rarity-forecast-01-entry/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecasts the week-one earn rate of every Grand Theft Auto VI PlayStation 5 trophy on Exophase as five quantiles per trophy. For each trophy it fits a recency-weighted line of logit(rate) against log-time since launch over the distinct Exophase refreshes in the case's history, tapers and extrapolates that trend to the target, blends it with a per-trophy prior drawn from the trophy's description (story chapter, side strand, grind), and widens the band with the extrapolation distance, keeping a point mass at the page's 0.01% floor for trophies nobody had yet. Python 3.13, standard library only, deterministic.

Entry for the [make.fun bounty](https://make.fun/bounty/gta6-trophy-rarity-forecast-01).

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

`python3 selftest.py` runs a shape and monotonicity check on a synthetic case.

---

<sub>Entered on [make.fun](https://make.fun/?ref=brg435wz&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
