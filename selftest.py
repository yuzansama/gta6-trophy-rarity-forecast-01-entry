"""Smallest check that fails if the forecast logic breaks: a synthetic case with a rising trophy, a
pinned-at-100 trophy and a floor trophy, run through forecast_case twice."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import main  # noqa: E402


def synthetic():
    history = []
    for h in range(5, 60, 3):
        at = f"2026-11-{19 + h // 24:02d}T{h % 24:02d}:00:00.000Z"
        rising = 100 / (1 + 2.718 ** (-(0.9 * (h / 10) - 4)))
        history.append({"slot": at, "at": at, "players_tracked": 3000 + 800 * h, "trophies_earned": 0,
                        "rates": [100.0, round(rising, 2), 0.0, 0.63]})
    trophies = [
        {"id": 1, "name": "Just Like Paradise", "description": "", "tier": "bronze", "points": 15, "secret": True},
        {"id": 2, "name": "Paradise Lost", "description": "", "tier": "bronze", "points": 15, "secret": True},
        {"id": 3, "name": "You Gotta Know When to Get Off", "description": "", "tier": "gold", "points": 90, "secret": True},
        {"id": 4, "name": "Unknown Trophy", "description": "", "tier": "silver", "points": 30, "secret": False},
    ]
    return {"id": "t00", "at": "2026-11-21T11:30:00Z", "horizon_minutes": 6510, "target": "2026-11-26T00:00:00Z",
            "levels": main.LEVELS, "game": {}, "trophies": trophies, "history": history, "notes": ""}


case = synthetic()
out = main.forecast_case(case)
again = main.forecast_case(case)
assert json.dumps(out) == json.dumps(again), "not deterministic"
rows = {r["id"]: r["q"] for r in out["trophies"]}
assert sorted(rows) == [1, 2, 3, 4]
for q in rows.values():
    assert len(q) == 5 and all(0 <= v <= 100 for v in q) and all(q[i] <= q[i + 1] for i in range(4)), q
assert rows[1][2] == 100, rows[1]                       # pinned at 100 stays there
last = case["history"][-1]["rates"][1]
assert rows[2][2] > last, (rows[2], last)                 # a rising trophy keeps rising
assert rows[3][0] == 0.01 and rows[3][4] > 0.5, rows[3]  # floor trophy: floor mass below, room above
assert len(json.dumps(out, separators=(",", ":"))) < 65536
print("selftest ok", rows)
