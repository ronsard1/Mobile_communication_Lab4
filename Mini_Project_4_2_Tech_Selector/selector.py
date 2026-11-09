"""
selector.py - rule-based IoT connectivity technology selector (Mini Project 4.2).

Six requirement axes (Section 4.3): data rate, coverage category, battery-life target, mobility,
infrastructure ownership and cost sensitivity. Every technology has a 0-5 capability per axis
(the CAPABILITY tables below, transcribed from the Section 4.2 / 4.3 comparisons). Requirements are
mapped onto the same 0-5 scale, each axis gives a 0-5 fit, and the overall score is the weighted mean
of the fits scaled to 0-100. Constraint rules then handle what a weighted sum handles poorly.

    python selector.py                 # the four Section 4.3 scenarios + the new scenario -> results_4_2.txt
    python selector.py --interactive   # enter a new scenario and print the ranked recommendation
"""
import argparse
import math
import os

TECHS = ["NB-IoT", "LTE-M", "LoRaWAN", "5G RedCap", "BLE", "Zigbee"]

# ------------------------------------------------------------------ capability tables (0 = unsuitable, 5 = excellent)
# Ordinal axes: capability level compared with the required level.
DATA_RATE = {"NB-IoT": 3, "LTE-M": 4, "LoRaWAN": 2, "5G RedCap": 5, "BLE": 4, "Zigbee": 3}
#   level 1 <= 1 kbit/s, 2 <= 10 kbit/s, 3 <= 100 kbit/s, 4 <= 1 Mbit/s, 5 > 1 Mbit/s (sustained application rate)
BATTERY = {"NB-IoT": 5, "LTE-M": 4, "LoRaWAN": 5, "5G RedCap": 3, "BLE": 3, "Zigbee": 3}
#   level 1 < 0.5 y, 2 <= 2 y, 3 <= 5 y, 4 <= 10 y, 5 > 10 y on a primary cell
LOW_COST = {"NB-IoT": 4, "LTE-M": 3, "LoRaWAN": 5, "5G RedCap": 1, "BLE": 5, "Zigbee": 5}
#   module price plus recurring fees per device; 5 = cheapest

# Categorical axes: the table entry IS the fit for that requirement category.
COVERAGE = {   # deep indoor, wide-area cellular, long-range rural, short-range only
    "NB-IoT":    {"deep_indoor": 5, "wide_area": 5, "rural_long_range": 3, "short_range": 2},
    "LTE-M":     {"deep_indoor": 4, "wide_area": 5, "rural_long_range": 3, "short_range": 2},
    "LoRaWAN":   {"deep_indoor": 3, "wide_area": 3, "rural_long_range": 5, "short_range": 2},
    "5G RedCap": {"deep_indoor": 2, "wide_area": 4, "rural_long_range": 2, "short_range": 2},
    "BLE":       {"deep_indoor": 1, "wide_area": 0, "rural_long_range": 0, "short_range": 5},
    "Zigbee":    {"deep_indoor": 2, "wide_area": 0, "rural_long_range": 0, "short_range": 5},
}
MOBILITY = {   # stationary, local (site / body), wide-area (handover), global roaming
    "NB-IoT":    {"stationary": 5, "local": 4, "wide_area": 2, "global": 2},
    "LTE-M":     {"stationary": 5, "local": 5, "wide_area": 5, "global": 4},
    "LoRaWAN":   {"stationary": 5, "local": 4, "wide_area": 1, "global": 0},
    "5G RedCap": {"stationary": 5, "local": 5, "wide_area": 5, "global": 3},
    "BLE":       {"stationary": 5, "local": 4, "wide_area": 0, "global": 0},
    "Zigbee":    {"stationary": 5, "local": 2, "wide_area": 0, "global": 0},
}
OWNERSHIP = {  # operator-managed preferred, no preference, self-owned preferred
    "NB-IoT":    {"operator": 5, "any": 4, "self": 1},
    "LTE-M":     {"operator": 5, "any": 4, "self": 1},
    "LoRaWAN":   {"operator": 3, "any": 4, "self": 5},
    "5G RedCap": {"operator": 5, "any": 4, "self": 2},
    "BLE":       {"operator": 0, "any": 4, "self": 5},
    "Zigbee":    {"operator": 0, "any": 4, "self": 5},
}

WEIGHTS = {"data_rate": 1.0, "coverage": 1.5, "battery": 1.0, "mobility": 1.5, "ownership": 1.0, "cost": 1.0}
AXIS_NAME = {"data_rate": "data rate", "coverage": "coverage", "battery": "battery life", "mobility": "mobility",
             "ownership": "infrastructure ownership", "cost": "cost per device"}


# ------------------------------------------------------------------ requirement mapping (inputs -> 0-5)
def rate_level(kbps):
    for lvl, lim in ((1, 1), (2, 10), (3, 100), (4, 1000)):
        if kbps <= lim:
            return lvl
    return 5


def battery_level(years):
    if years < 0.5:
        return 1
    for lvl, lim in ((2, 2), (3, 5), (4, 10)):
        if years <= lim:
            return lvl
    return 5


def cost_level(devices, budget):
    """Cost sensitivity 1-5: grows with fleet size, shifted by budget tier (high -1, medium 0, low +1)."""
    lvl = 1 + sum(devices > lim for lim in (50, 500, 5000, 50000))
    return max(1, min(5, lvl + {"high": -1, "medium": 0, "low": 1}[budget]))


def ordinal_fit(capability, required):
    """5 when capability >= requirement; 1.5 points lost per level of shortfall."""
    return max(0.0, 5.0 - 1.5 * max(0, required - capability))


# ------------------------------------------------------------------ scoring
def score(req, weights=WEIGHTS):
    kbps = req.get("kbps") or req["message_bytes"] * 8 / req["interval_s"] / 1000
    need = {"data_rate": rate_level(kbps), "battery": battery_level(req["battery_years"]),
            "cost": cost_level(req["devices"], req["budget"])}
    results = []
    for t in TECHS:
        fit = {
            "data_rate": ordinal_fit(DATA_RATE[t], need["data_rate"]),
            "coverage": COVERAGE[t][req["coverage"]],
            "battery": ordinal_fit(BATTERY[t], need["battery"]),
            "mobility": MOBILITY[t][req["mobility"]],
            "ownership": OWNERSHIP[t][req["ownership"]],
            "cost": ordinal_fit(LOW_COST[t], need["cost"]),
        }
        s = 20 * sum(weights[a] * fit[a] for a in fit) / sum(weights.values())
        rules = []
        # R1: hard capacity limit - a link that cannot carry the traffic is not a candidate
        if DATA_RATE[t] < need["data_rate"]:
            s *= 0.4
            rules.append("R1 data rate below requirement (x0.4)")
        # R2: no cellular-style handover - LoRaWAN / short-range cannot serve wide-area or global mobility
        if req["mobility"] in ("wide_area", "global") and t in ("LoRaWAN", "BLE", "Zigbee"):
            s *= 0.5
            rules.append("R2 no handover for wide-area mobility (x0.5)")
        # R3: short-range technologies need the devices to be within ~100 m of a gateway or hub
        if req["coverage"] != "short_range" and t in ("BLE", "Zigbee"):
            s *= 0.5
            rules.append("R3 short range only (x0.5)")
        # R4: large, cost-sensitive fleets favour self-owned networks without per-device fees
        if req["devices"] >= 1000 and need["cost"] >= 4 and req["ownership"] != "operator":
            if t in ("LoRaWAN", "BLE", "Zigbee"):
                s *= 1.1
                rules.append("R4 no per-device fees at scale (x1.1)")
            else:
                s *= 0.9
                rules.append("R4 subscription per device at scale (x0.9)")
        # R5: a battery shortfall of two or more levels means the target cannot be met
        if need["battery"] - BATTERY[t] >= 2:
            s *= 0.5
            rules.append("R5 battery target out of reach (x0.5)")
        results.append({"tech": t, "score": round(min(s, 100.0), 1), "fit": fit, "rules": rules})
    results.sort(key=lambda r: -r["score"])
    for r in results:                                # how each axis compares with the field average
        r["rel"] = {a: r["fit"][a] - sum(x["fit"][a] for x in results) / len(results) for a in r["fit"]}
    return results, need, kbps


def justify(r):
    """Name the axes that most separate this technology from the others (weighted fit above / below average)."""
    w = WEIGHTS
    order = sorted(r["rel"], key=lambda a: -w[a] * r["rel"][a])
    strong = [AXIS_NAME[a] for a in order if w[a] * r["rel"][a] >= 0.75][:2]
    weak = [AXIS_NAME[a] for a in reversed(order) if w[a] * r["rel"][a] <= -0.75 or r["fit"][a] <= 2][:2]
    text = f"Above the field on {', '.join(strong) if strong else 'no axis'}"
    text += f"; below on {', '.join(weak)}." if weak else "; no weak axis."
    if r["rules"]:
        text += " Rules: " + "; ".join(x.split(" (")[0] for x in r["rules"]) + "."
    return text


# ------------------------------------------------------------------ scenarios
SCENARIOS = {
    "Smart water meter (4.3)": dict(message_bytes=50, interval_s=3600, coverage="deep_indoor", battery_years=12,
                                    mobility="stationary", ownership="operator", devices=100000, budget="low",
                                    expected="NB-IoT"),
    "Fleet-tracked shipping container (4.3)": dict(message_bytes=100, interval_s=900, coverage="wide_area",
                                                   battery_years=5, mobility="global", ownership="operator",
                                                   devices=10000, budget="medium", expected="LTE-M"),
    "Factory-floor sensor network (4.3)": dict(kbps=20, coverage="short_range", battery_years=2, mobility="stationary",
                                               ownership="self", devices=300, budget="medium", expected="Zigbee / BLE"),
    "Wearable health monitor (4.3)": dict(kbps=16, coverage="short_range", battery_years=0.1, mobility="local",
                                          ownership="any", devices=20000, budget="medium", expected="BLE"),
    "NEW: Akagera wildlife collars": dict(message_bytes=20, interval_s=3600, coverage="rural_long_range",
                                          battery_years=3, mobility="local", ownership="self", devices=40,
                                          budget="low", expected="LoRaWAN"),
}


def report(name, req, out):
    res, need, kbps = score(req)
    out.append(f"{name}  (expected from the unit's reasoning: {req.get('expected', '-')})")
    out.append(f"  inputs: {kbps:.3g} kbit/s -> rate level {need['data_rate']}, coverage {req['coverage']}, "
               f"battery {req['battery_years']} y -> level {need['battery']}, mobility {req['mobility']}, "
               f"ownership {req['ownership']}, {req['devices']} devices / {req['budget']} budget -> cost level {need['cost']}")
    for i, r in enumerate(res, 1):
        out.append(f"  {i}. {r['tech']:10s} {r['score']:5.1f}  {justify(r)}")
    out.append("")
    return res


def ask(prompt, choices=None, cast=str):
    while True:
        v = input(prompt + (f" {choices}" if choices else "") + ": ").strip()
        try:
            v = cast(v)
        except ValueError:
            continue
        if not choices or v in choices:
            return v


def interactive():
    req = dict(
        kbps=ask("required application data rate in kbit/s", cast=float),
        coverage=ask("coverage category", ["deep_indoor", "wide_area", "rural_long_range", "short_range"]),
        battery_years=ask("battery-life target in years", cast=float),
        mobility=ask("mobility", ["stationary", "local", "wide_area", "global"]),
        ownership=ask("infrastructure ownership preference", ["operator", "any", "self"]),
        devices=ask("number of devices", cast=int),
        budget=ask("budget tier", ["high", "medium", "low"]),
    )
    out = []
    report("Your scenario", req, out)
    print("\n".join(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interactive", action="store_true")
    a = ap.parse_args()
    if a.interactive:
        return interactive()
    out = ["Weights: " + ", ".join(f"{AXIS_NAME[k]} {v}" for k, v in WEIGHTS.items()), ""]
    table = []
    for name, req in SCENARIOS.items():
        res = report(name, req, out)
        table.append((name, req["expected"], res[0]["tech"], res[0]["score"], res[1]["tech"], res[1]["score"]))
    out.append(f"{'scenario':42s}{'expected':>14s}{'1st':>12s}{'score':>7s}{'2nd':>12s}{'score':>7s}")
    for row in table:
        out.append(f"{row[0]:42s}{row[1]:>14s}{row[2]:>12s}{row[3]:>7.1f}{row[4]:>12s}{row[5]:>7.1f}")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results_4_2.txt"), "w") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
