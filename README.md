# gta6-twitch-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ariffforai/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ariffforai/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecast GTA VI's launch-day Twitch viewers hour by hour: for each of hours 2–24 of 19 November 2026 (UTC), five quantiles of the Grand Theft Auto VI category's concurrent viewers, anchored on the hour-1 print and shaped by the release-day curves of past launches that unlocked the same way — midnight local, rolling around the world, consoles only, no early access.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## Method

`main.py` (Python 3.13, standard library only, deterministic) reads the case's hour-1 print and its comparables, and for each hour takes the weighted median log-ratio to hour 1 across the rolling-midnight analogues, weighted by how close each analogue's hour-1 scale is to this case's hour-1 print, with the spread from the weighted standard deviation of those ratios. Full method and validation numbers are in the docstring at the top of `main.py`.

Validated offline on the kit's own data: mean pinball loss 0.196 on the four practice launches (house baseline 0.387) and 0.263 leave-one-out over the eleven rolling-midnight comparables (baseline 0.363).

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
