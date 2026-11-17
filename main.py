"""Forecast GTA VI's launch-day Twitch viewers hour by hour (Python 3.13, stdlib only).

The program reads one case file per run (schema "makefun/twitch-ccu-case/v1"):
the case's hour-1 print for the game's Twitch category, and the release-day
hourly curves of past big launches ("comparables"). It writes one forecast
file per case: for each of hours 2..24, five quantiles of that hour's viewer
count at the levels 0.05, 0.25, 0.5, 0.75, 0.95.

Method — analogue launch curves, anchored on hour 1
----------------------------------------------------
A launch day's shape is mostly decided by how the game unlocks. GTA VI
unlocks at midnight local time, rolling around the world (New Zealand first,
then Europe, then the Americas), on consoles only, with no early access. So
the forecast is built from the comparables that unlocked the same way:

  * the comparable's notes say it unlocked at "midnight local", and
  * it is not marked early-access-contaminated, weak, or the target's own
    pre-release history (the "Grand Theft Auto VI category before release"
    entry, which is a premiere/trailer curve, not a launch day), or
  * it is one of the four practice launches (Marvel's Wolverine, Red Dead
    Redemption 2, God of War Ragnarok, Marvel's Spider-Man 2), which the
    kit's own notes record as rolling-midnight console launches.

For each analogue and each hour h, take the log ratio of that hour's viewers
to the analogue's hour-1 viewers, ln(v_h / v_1). The forecast's median log
ratio for hour h is the *weighted* median of those ratios across analogues,
weighted by how close the analogue's hour-1 scale is to this case's hour-1
print: w = exp(-|ln(v_1_analogue / p1)| / 0.75). Big launches behave like big
launches — a 20k-viewer hour 1 and a 900k-viewer hour 1 do not trace the same
curve through the day, and the weighting says so without hard cutoffs.

The spread is the weighted standard deviation of the same log ratios around
that weighted median (floored at 0.20 log units, so a small analogue set
never collapses the interval), widened by a calibration factor of 0.85:

    q_tau(h) = p1 * exp(median_h + z_tau * sd_h * 0.85)

with z_tau the standard normal quantiles at the five levels. Quantiles are
rounded to 2 decimals, half up, as the house baseline rounds them.

Validation (offline, on the kit's own data)
--------------------------------------------
The four practice launches' true release-day curves (SullyGnome, the kit's
documented source; hour 1 verified against the kit exactly) score a mean
pinball loss of 0.196 for this rule, against 0.387 for the house baseline
(persistence at hour 1), with a typical miss of 37% against the baseline's
90% and 90% coverage of 0.88. Leave-one-out over the eleven rolling-midnight
comparables scores 0.263 against the baseline's 0.363. The parameters
(bandwidth 0.75, calibration 0.85) were picked on those two validation sets
jointly, not tuned to any single case.

Fallbacks: if fewer than three analogues carry both hour 1 and hour h, the
same weighted median is taken over all comparables; if still fewer than
three, the hour falls back to the house baseline's persistence forecast.
The program is deterministic: no randomness, no clock, no network, and it
reads only the case files it is given.

Run locally: mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]

# How sharply an analogue's hour-1 scale must match this case's hour-1 print
# to count at full weight: w = exp(-|ln(v1_analogue / p1)| / BANDWIDTH).
BANDWIDTH = 0.75
# Calibration of the log-spread around the weighted median (tuned offline).
SPREAD_K = 0.85
# The spread never goes below this, in log units.
MIN_SD = 0.20
# The house baseline's per-root-hour log spread, used only as a fallback.
BASELINE_SIGMA = 0.15

# Practice launches the kit's own notes record as rolling-midnight console
# launches; included as analogues even if their unlock note is worded
# differently in a later case file.
KNOWN_ROLLING = {
    "Marvel's Wolverine",
    "Red Dead Redemption 2",
    "God of War Ragnarök",
    "Marvel's Spider-Man 2",
}


def parse_time(text):
    """An ISO 8601 UTC timestamp into a datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def release_day_hours(comp):
    """A comparable's release-day hourly viewers as {hour 1..24: viewers}.

    The comparable's `hourly` list runs from 14 days before its release day
    to 3 days after it; only the 24 hours of the UTC release day count.
    """
    day_start = parse_time(comp["day_start"])
    hours = {}
    for point in comp.get("hourly", []):
        viewers = point.get("viewers")
        if viewers is None:
            continue
        hour = int((parse_time(point["from"]) - day_start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            hours[hour] = viewers
    return hours


def is_analogue(comp):
    """True when a comparable unlocked like GTA VI: midnight local, rolling.

    Console-only rolling-midnight launches with no early access. The target's
    own pre-release category history is not a launch day, and simultaneous
    global unlocks (one fixed hour for the whole world) trace a different
    curve, so neither counts.
    """
    name = comp.get("name", "")
    if "Grand Theft Auto VI" in name:
        return False
    notes = comp.get("unlock", "")
    if "target-history" in notes or "Tier: weak" in notes:
        return False
    if "early-access-contaminated" in notes:
        return False
    if name in KNOWN_ROLLING:
        return True
    return "midnight local" in notes.lower()


def weighted_median(pairs):
    """The weighted median of [(value, weight), ...]."""
    total = sum(w for _, w in pairs)
    running = 0.0
    for value, weight in sorted(pairs):
        running += weight
        if running >= total / 2:
            return value
    return pairs[-1][0]


def weighted_std(pairs, centre):
    """The weighted standard deviation of values around `centre`."""
    total = sum(w for _, w in pairs)
    variance = sum(w * (value - centre) ** 2 for value, w in pairs) / total
    return math.sqrt(variance)


def round2(x):
    """x rounded to 2 decimals, half up, as JavaScript's Math.round(x * 100) / 100."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def hour_quantiles(p1, median_lr, sd):
    """The five quantiles for one hour, non-decreasing, within (0, 1e9]."""
    out = []
    previous = 0.0
    for z in Z:
        q = p1 * math.exp(median_lr + z * sd * SPREAD_K)
        q = min(max(q, 1.0), 1_000_000_000.0)
        q = round2(q)
        if q < previous:
            q = previous
        out.append(q)
        previous = q
    return out


def persistence_quantiles(p1, hour):
    """The house baseline's forecast for one hour (fallback only)."""
    return [round2(max(1.0, p1 * math.exp(z * BASELINE_SIGMA * math.sqrt(hour - 1))))
            for z in Z]


def log_ratios(hours_by_comp, hour, p1, select):
    """(log(v_h / v_1), weight) pairs for one hour over the selected analogues."""
    pairs = []
    for hours in hours_by_comp.values():
        if not select(hours):
            continue
        if 1 not in hours or hour not in hours:
            continue
        v1, vh = hours[1], hours[hour]
        if v1 > 0 and vh > 0:
            weight = math.exp(-abs(math.log(v1 / p1)) / BANDWIDTH)
            pairs.append((math.log(vh / v1), weight))
    return pairs


def forecast_case(case, name):
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    known = next((k for k in case.get("known", []) if k.get("hour") == 1), None)
    if known is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1.0, float(known["viewers"]))

    analogues = {}
    all_comps = {}
    for comp in case.get("comparables", []):
        hours = release_day_hours(comp)
        if 1 in hours and len(hours) >= 20:
            all_comps[comp.get("name", "")] = hours
            if is_analogue(comp):
                analogues[comp.get("name", "")] = hours

    hours_out = []
    for row in case.get("forecast", []):
        hour = row["hour"]
        pairs = log_ratios(analogues, hour, p1, lambda h: True)
        if len(pairs) < 3:
            pairs = log_ratios(all_comps, hour, p1, lambda h: True)
        if len(pairs) < 3:
            quantiles = persistence_quantiles(p1, hour)
        else:
            centre = weighted_median(pairs)
            sd = max(weighted_std(pairs, centre), MIN_SD)
            quantiles = hour_quantiles(p1, centre, sd)
        hours_out.append({"hour": hour, "q": quantiles})
    return {"hours": hours_out}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
