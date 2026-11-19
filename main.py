"""Forecast GTA VI PS5 trophy earn rates on Exophase: quantiles at the case's target.

Idea: a trophy's earn rate moves on the logit scale roughly linearly in log-time since launch
(progress slows as the launch cohort spreads out, dilution by newcomers fades). So for each
trophy we fit a recency-weighted line of logit(rate) against ln(1 + hours since launch) over
the distinct Exophase refreshes in the history, shrink its slope toward the pooled slope of all
trophies, and extrapolate to the target. The spread grows with how far we extrapolate in
log-time, plus the fit's own noise.

Reads every *.in in $MAKEFUN_INPUT_DIR (default /input), writes <id>.out to $MAKEFUN_OUTPUT_DIR
(default /output). Standard library only, no randomness, so two runs write the same bytes.
"""

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
LAUNCH = datetime(2026, 11, 19, 0, 0, tzinfo=timezone.utc)

HALF_LIFE = 0.8      # recency weight half-life, in ln-hour units
SHRINK = 1.0         # pseudo-observations pulling a trophy's slope toward the pooled slope
DAMP = 0.85          # the fitted slope is tapered when extrapolated (growth decelerates in ln-time)
BASE_SD = 0.25       # logit noise floor at the target
DRIFT_SD = 0.40      # extra logit sd per unit of ln-time extrapolated
TAIL = 1.15          # fattening of the 5% / 95% quantiles
FALLBACK_SD = 0.60   # spread when the history shows fewer than 3 refreshes
FLOOR_PCT = 0.06     # at or below this the page's 2 decimals hide the trend: the prior takes over
STUCK_FLOOR = 0.30   # chance a trophy nobody had by the checkpoint is still at the floor a week in
STUCK_NEAR = 0.10    # the same for one that has barely left it

# Where each trophy should land one week after launch among Exophase's tracked PS5 players, as a
# percent, with a logit sd saying how sure that is. A judgment from the trophy's description (story
# chapter, side strand, grind), blended with the trend the data shows; the data wins wherever the
# history actually moves. Keyed by name, with the launch list's ids as a fallback.
PRIOR = {
    "Vice Got a Price!": (0.01, 1.5),
    "Just Like Paradise": (99.9, 0.8),
    "Paradise Lost": (85, 0.8),
    "T**s Ass Drug Money": (60, 0.9),
    "Vice City, Baby!": (35, 1.0),
    "Top Of The World, Ma": (15, 1.2),
    "You Gotta Know When to Get Off": (2, 1.5),
    "Trust": (70, 1.2),
    "Break the Bank": (35, 1.5),
    "Family Matters": (35, 1.5),
    "DWNFALL": (30, 1.5),
    "Hi-Jacked": (25, 1.5),
    "Snow Storm": (15, 1.5),
    "A Long Road": (0.01, 1.5),
    "Cunning Stunts": (0.5, 1.5),
    "Master of None": (10, 1.5),
    "The Shootist": (2, 1.5),
    "Top Fun": (1, 1.5),
    "Earn Cash, Not Kudos": (3, 1.5),
    "Baited My Tackle": (45, 1.2),
    "Stick Fiddler": (15, 1.5),
    "Road to Rehabilitation": (5, 1.5),
    "This Was No Boat Accident": (5, 1.5),
    "The Lone Rider": (5, 1.5),
    "Strangers & Freaks": (1, 1.5),
    "Supply & Demand": (5, 1.5),
    "Spin On This!": (5, 1.5),
    "Positive Mental Attitude": (1, 1.5),
    "Fair Game": (10, 1.5),
    "Don't Touch My Deck": (1, 1.5),
    "You WAiNKer!": (1.5, 1.5),
    "One Last Thing": (2, 1.5),
    "Hot Together": (15, 1.5),
    "Retail Therapy": (15, 1.5),
    "Whip It Good": (25, 1.2),
    "Gunslinger": (30, 1.2),
    "Catch Me If You Can": (20, 1.5),
    "Challenging Tank": (30, 1.5),
    "Sneakthief": (10, 1.5),
    "Maximum Withdrawal": (3, 1.5),
    "A Classic Blitz Play": (20, 1.5),
    "The Goodtime State": (1, 1.5),
    "Pest Control": (3, 1.5),
    "In The Beginning…": (50, 1.5),
    "Capital Offense": (40, 1.5),
    "Let’s Go Bowling": (30, 1.5),
    "Personal Best": (30, 1.5),
    "Actions Speak Louder": (25, 1.5),
    "Bad Luck, I Guess": (25, 1.5),
    "The Truth Is Out There": (15, 1.5),
    "Ten Pin": (15, 1.5),
    "Dime on the Dollar": (3, 1.5),
    "Treat Yo Self": (5, 1.5),
    "Little Boxes": (1, 1.5),
    "On the Spot": (8, 1.5),
}
PRIOR_BY_ID = dict(enumerate(PRIOR.values(), start=1))
# an unknown trophy (a name and id the list above lacks) gets only a vague tier-level hint
TIER_PRIOR = {"platinum": (0.01, 1.5), "gold": (3, 3.0), "silver": (2, 3.0), "bronze": (10, 3.0)}


def prior_for(trophy):
    key = trophy.get("name", "")
    if key in PRIOR:
        return PRIOR[key]
    if trophy.get("id") in PRIOR_BY_ID:
        return PRIOR_BY_ID[trophy["id"]]
    return TIER_PRIOR.get(trophy.get("tier"), (10, 2.0))


def clamp(pct):
    return min(99.99, max(0.01, pct))


def logit(pct):
    p = clamp(pct) / 100.0
    return math.log(p / (1.0 - p))


def expit(y):
    if y > 40:
        return 100.0
    if y < -40:
        return 0.0
    return 100.0 / (1.0 + math.exp(-y))


def round4(x):
    scaled = x * 10000.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000.0
    return int(value) if value.is_integer() else value


def xtime(iso):
    """ln(1 + hours since launch), the time axis the trend is linear on."""
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    hours = max(0.0, (t - LAUNCH).total_seconds() / 3600.0)
    return math.log1p(hours)


def refreshes(history):
    """The reads where Exophase's counts actually changed (the page is a staircase between them)."""
    kept = []
    prev = None
    for read in history:
        key = (read.get("players_tracked"), tuple(read["rates"]))
        if key != prev:
            kept.append(read)
            prev = key
    return kept


def wls(points, x_ref):
    """Recency-weighted least squares of y on x. Returns (intercept, slope, residual sd, n_eff, slope se)."""
    w = [math.exp(-(x_ref - x) / HALF_LIFE) for x, _ in points]
    sw = sum(w)
    mx = sum(wi * x for wi, (x, _) in zip(w, points)) / sw
    my = sum(wi * y for wi, (_, y) in zip(w, points)) / sw
    sxx = sum(wi * (x - mx) ** 2 for wi, (x, _) in zip(w, points))
    sxy = sum(wi * (x - mx) * (y - my) for wi, (x, y) in zip(w, points))
    slope = sxy / sxx if sxx > 1e-9 else 0.0
    intercept = my - slope * mx
    n_eff = sw * sw / sum(wi * wi for wi in w)
    resid = sum(wi * (y - intercept - slope * x) ** 2 for wi, (x, y) in zip(w, points)) / sw
    sd = math.sqrt(resid * n_eff / max(1.0, n_eff - 2.0)) if n_eff > 2.5 else math.sqrt(resid)
    se = sd / math.sqrt(sxx) if sxx > 1e-9 else 5.0
    return intercept, slope, sd, n_eff, se


def weighted_median(values, weights):
    order = sorted(range(len(values)), key=lambda i: values[i])
    total = sum(weights)
    acc = 0.0
    for i in order:
        acc += weights[i]
        if acc >= total / 2.0:
            return values[i]
    return values[order[-1]]


def norm_ppf(p):
    """Standard normal quantile (Acklam's rational approximation, plenty for 4-decimal percents)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    if p < 0.02425:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > 1 - 0.02425:
        return -norm_ppf(1 - p)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def quantiles(center, sd_down, sd_up, stuck=0.0):
    """Five quantiles of a logit-normal belief, mixed with a chance `stuck` that the rate is still
    at the page's floor (0.01%) at the target: a level inside that mass answers the floor, the rest
    are the normal's quantiles at the level rescaled past it."""
    out = []
    for tau, z in zip(LEVELS, Z):
        if stuck > 0.0:
            if tau <= stuck:
                out.append(0.01)
                continue
            z = norm_ppf((tau - stuck) / (1.0 - stuck))
        sd = sd_down if z < 0 else sd_up
        tail = TAIL if abs(z) > 1.0 else 1.0
        out.append(expit(center + z * sd * tail))
    rows = []
    last = 0.0
    for q in out:
        q = round4(min(100.0, max(0.0, max(q, last))))
        rows.append(q)
        last = q
    return rows


def forecast_case(case):
    reads = refreshes(case["history"])
    x_target = xtime(case["target"])
    x_last = xtime(case["history"][-1]["at"])
    dx = max(0.0, x_target - x_last)
    n_trophies = len(case["trophies"])

    series = []
    for i in range(n_trophies):
        pts = [(xtime(r["at"]), logit(r["rates"][i])) for r in reads if r["rates"][i] is not None]
        series.append(pts)

    fits = []
    peaks = []
    for i, pts in enumerate(series):
        fits.append(wls(pts, x_last) if len(pts) >= 3 else None)
        peaks.append(max((r["rates"][i] or 0.0) for r in reads) if reads else 0.0)

    # the pooled slope: the typical trend among trophies whose rates are clear of the 2-decimal floor
    pooled_slope = 0.0
    clear = [f for f, pk in zip(fits, peaks) if f is not None and pk > 4 * FLOOR_PCT]
    if clear:
        pooled_slope = weighted_median([f[1] for f in clear], [f[3] for f in clear])

    rows = []
    for i, trophy in enumerate(case["trophies"]):
        pts = series[i]
        if not pts:
            y_last = logit(0.0)
        else:
            y_last = pts[-1][1]
        last_rate = case["history"][-1]["rates"][i]
        pinned = last_rate is not None and last_rate >= 99.99 and all(
            r["rates"][i] is None or r["rates"][i] >= 99.99 for r in reads)
        if pinned:
            rows.append({"id": trophy["id"], "q": [99.9, 100, 100, 100, 100]})
            continue

        # 1. what the trend says (data estimate and its sd on the logit scale)
        fit = fits[i]
        if fit is None:
            data_center = y_last + pooled_slope * dx
            data_sd = math.sqrt(FALLBACK_SD ** 2 + (DRIFT_SD * dx) ** 2)
        else:
            intercept, slope, resid_sd, n_eff, se = fit
            slope = (n_eff * slope + SHRINK * pooled_slope) / (n_eff + SHRINK)
            level = 0.5 * y_last + 0.5 * (intercept + fit[1] * x_last)
            data_center = level + DAMP * slope * dx
            data_sd = math.sqrt(BASE_SD ** 2 + (DRIFT_SD * dx) ** 2 + (se * dx) ** 2 + resid_sd ** 2)
        # near the page's 2-decimal floor the trend is quantisation noise: trust it much less, and
        # keep a chance that the trophy has still not moved off the floor at the target
        stuck = 0.0
        if peaks[i] <= FLOOR_PCT:
            data_sd = math.sqrt(data_sd ** 2 + 2.5 ** 2)
            stuck = STUCK_FLOOR
        elif (last_rate or 0.0) <= 4 * FLOOR_PCT:
            data_sd = math.sqrt(data_sd ** 2 + 1.0 ** 2)
            stuck = STUCK_NEAR

        # 2. what the trophy's description says, scaled to the case's horizon
        prior_pct, prior_sd = prior_for(trophy)
        prior_center = logit(prior_pct)
        # the prior speaks of a week after launch (dx about 1 from the deadline): over a shorter hop
        # it says less, and over the practice's 90 minutes next to nothing
        prior_sd = prior_sd / max(0.02, min(1.0, dx))

        # 3. precision-weighted blend, then a floor on the spread for what neither can know;
        #    a prior the data flatly contradicts is discounted (the data is what actually happened)
        w_d = 1.0 / data_sd ** 2
        w_p = 1.0 / prior_sd ** 2
        gap = abs(data_center - prior_center) / math.sqrt(data_sd ** 2 + prior_sd ** 2)
        if gap > 2.0:
            w_p *= (2.0 / gap) ** 2
        center = (w_d * data_center + w_p * prior_center) / (w_d + w_p)
        sd = math.sqrt(1.0 / (w_d + w_p) + BASE_SD ** 2)

        sd_up = sd
        if center < logit(2.0):
            sd_up = sd * 1.3  # a rare trophy has more room up than down
        if dx < 0.5:
            stuck = 0.0  # a short hop (the practice): the floor mass is a week-scale statement
        rows.append({"id": trophy["id"], "q": quantiles(center, sd, sd_up, stuck)})
    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
