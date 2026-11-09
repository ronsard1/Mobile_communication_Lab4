"""
link_budget_compare.py - LPWAN coverage margin and battery life (Mini Project 4.1, Part B, steps 11-14
and lab tasks 4-6).

Scenario (step 11): 200 soil sensors on a 25 km2 farm, 12-byte reading every 30 min, max 8 km to the
gateway, 5-year target on a 3.6 V 19 000 mAh lithium cell, no cellular coverage nearby, no per-device fees
wanted at 200 units.

    MCL      = Tx power - receiver sensitivity                         (dB)
    PL(d)    = PL(d0) + 10 n log10(d / d0),  PL(1 km) = 91.5 dB, n = 3.5
    margin   = MCL - PL(8 km)
    battery  = 19 000 mAh / (cycles per year x mAh per cycle + sleep mA x 8760 h)

    python link_budget_compare.py          -> results_partB.txt, figures/fig_partB.png
"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = []

# ------------------------------------------------------------------ scenario and assumptions
SCENARIO = dict(devices=200, area_km2=25, payload_bytes=12, interval_min=30, distance_km=8.0,
                target_years=5, battery_mAh=19000, battery_V=3.6)
PL_D0, D0, N_RURAL = 91.5, 1.0, 3.5

# Tx power / sensitivity from the handout (RedCap: representative values, lab task 5).
# Energy per cycle (step 13, our assumptions): effective transmit current and on-air time per report,
# including NB-IoT / LTE-M repetitions for coverage enhancement; sleep current in PSM / LoRa class A.
TECH = {
    "NB-IoT":            dict(tx_dBm=23, sens_dBm=-129, tx_mA=220, tx_s=2.0,  sleep_uA=5,  network="operator (cellular)"),
    "LTE-M (CE Mode B)": dict(tx_dBm=23, sens_dBm=-125, tx_mA=450, tx_s=2.0,  sleep_uA=8,  network="operator (cellular)"),
    "LoRaWAN SF12":      dict(tx_dBm=14, sens_dBm=-137, tx_mA=44,  tx_s=None, sleep_uA=2,  network="self-owned gateway"),
    "5G RedCap":         dict(tx_dBm=23, sens_dBm=-110, tx_mA=600, tx_s=1.0,  sleep_uA=15, network="operator (5G SA)"),
}
CORE = ["NB-IoT", "LTE-M (CE Mode B)", "LoRaWAN SF12"]


def lora_time_on_air(payload, sf=12, bw=125e3, cr=1, preamble=8, header=True, crc=True, overhead=13):
    """Semtech SX127x time-on-air; 13 bytes of LoRaWAN MAC overhead are added to the application payload."""
    pl = payload + overhead
    t_sym = (2 ** sf) / bw
    de = 1 if t_sym > 0.016 else 0                       # low-data-rate optimisation at SF11/12, 125 kHz
    h = 0 if header else 1
    n = 8 + max(math.ceil((8 * pl - 4 * sf + 28 + 16 * crc - 20 * h) / (4 * (sf - 2 * de))) * (cr + 4), 0)
    return (preamble + 4.25) * t_sym + n * t_sym


def path_loss(d_km, n=N_RURAL):
    return PL_D0 + 10 * n * math.log10(d_km / D0)


def battery_years(t):
    cycles = 365 * 24 * 60 / SCENARIO["interval_min"]
    tx_s = t["tx_s"] if t["tx_s"] else lora_time_on_air(SCENARIO["payload_bytes"])
    per_cycle_mAh = t["tx_mA"] * tx_s / 3600
    year_mAh = cycles * per_cycle_mAh + t["sleep_uA"] / 1000 * 8760
    return SCENARIO["battery_mAh"] / year_mAh, per_cycle_mAh, year_mAh, tx_s


def say(s=""):
    print(s)
    OUT.append(s)


def main():
    pl8 = path_loss(SCENARIO["distance_km"])
    say(f"Scenario: {SCENARIO}")
    say(f"Path loss at {SCENARIO['distance_km']:.0f} km: {PL_D0} + 10 x {N_RURAL} x log10(8) = {pl8:.1f} dB")
    say(f"LoRaWAN SF12 time on air for {SCENARIO['payload_bytes']} + 13 bytes: {lora_time_on_air(12) * 1000:.0f} ms")
    say("=" * 108)
    say(f"{'technology':20s}{'Tx dBm':>7s}{'sens dBm':>9s}{'MCL dB':>8s}{'margin dB':>10s}{'mAh/cycle':>11s}"
        f"{'mAh/year':>10s}{'years':>8s}{'5 y?':>6s}  network")
    rows = {}
    for name, t in TECH.items():
        mcl = t["tx_dBm"] - t["sens_dBm"]
        yrs, per, yr, tx_s = battery_years(t)
        rows[name] = dict(mcl=mcl, margin=mcl - pl8, years=yrs)
        tag = "  (lab task 5)" if name == "5G RedCap" else ""
        say(f"{name:20s}{t['tx_dBm']:>7d}{t['sens_dBm']:>9d}{mcl:>8.0f}{mcl - pl8:>10.1f}{per:>11.4f}{yr:>10.0f}"
            f"{yrs:>8.1f}{('yes' if yrs >= SCENARIO['target_years'] else 'NO'):>6s}  {t['network']}{tag}")
    say("  assumptions per report: NB-IoT 220 mA x 2.0 s, LTE-M 450 mA x 2.0 s (CE repetitions), LoRaWAN 44 mA x time on air,")
    say("  RedCap 600 mA x 1.0 s; sleep 5 / 8 / 2 / 15 uA. Lithium self-discharge (~1%/year) caps any real life near 15-20 years.")
    say(f"  LoRaWAN airtime per device per day: {48 * lora_time_on_air(12):.0f} s (1% duty cycle allows 864 s; public TTN fair use 30 s)")

    # ------------------------------------------------------------------ lab task 6: path-loss exponent
    say("=" * 108)
    say("Lab task 6: sensitivity to the path-loss exponent n (margin at 8 km in dB; maximum range in km for margin = 0)")
    ns = [2.5, 3.0, 3.5, 4.0]
    say(f"{'technology':20s}" + "".join(f"{'n=' + str(n):>16s}" for n in ns))
    sweep = {}
    for name, t in TECH.items():
        mcl = t["tx_dBm"] - t["sens_dBm"]
        cells = []
        for n in ns:
            m = mcl - path_loss(8, n)
            rmax = 10 ** ((mcl - PL_D0) / (10 * n))
            sweep[(name, n)] = m
            cells.append(f"{m:6.1f} / {rmax:5.0f} km")
        say(f"{name:20s}" + "".join(f"{c:>16s}" for c in cells))
    say("  Ranges beyond ~30-40 km exceed the radio horizon of ground-level sensors and a gateway mast, so they are not reachable.")

    # ------------------------------------------------------------------ lab task 4: shipping container
    say("=" * 108)
    say("Lab task 4: container on an ocean crossing - margin (dB) if the nearest terrestrial site were d km away (n = 3.5;")
    say("            over open sea n ~ 2.5 is kinder, shown in brackets)")
    dists = [10, 50, 200, 1000, 5000]
    say(f"{'technology':20s}" + "".join(f"{str(d) + ' km':>16s}" for d in dists))
    for name in CORE + ["5G RedCap"]:
        t = TECH[name]
        mcl = t["tx_dBm"] - t["sens_dBm"]
        say(f"{name:20s}" + "".join(f"{mcl - path_loss(d):>8.0f} ({mcl - path_loss(d, 2.5):>4.0f})" for d in dists))
    say("  Beyond ~30-50 km offshore every terrestrial link fails; mid-ocean the distance to a base station is undefined.")

    # ------------------------------------------------------------------ figure
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    names = list(TECH)
    cols = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd"]
    w = 0.2
    for i, n in enumerate(ns):
        axes[0].bar(np.arange(len(names)) + (i - 1.5) * w, [sweep[(nm, n)] for nm in names], w,
                    label=f"n = {n}", color=plt.cm.Blues(0.35 + 0.18 * i), edgecolor="black", lw=0.3)
    axes[0].axhline(0, color="black", lw=0.8)
    axes[0].set_xticks(range(len(names)))
    axes[0].set_xticklabels(names, fontsize=8)
    axes[0].set_ylabel("coverage margin at 8 km (dB)")
    axes[0].set_title("Coverage margin vs path-loss exponent (n = 3.5 is the scenario)", fontsize=9)
    axes[0].legend(fontsize=7)
    axes[0].grid(axis="y", alpha=0.3)
    yrs = [rows[nm]["years"] for nm in names]
    axes[1].bar(names, yrs, color=cols, edgecolor="black", lw=0.3)
    axes[1].axhline(SCENARIO["target_years"], color="#d62728", ls="--", lw=1)
    axes[1].text(3.4, SCENARIO["target_years"] + 1, "5-year target", color="#d62728", fontsize=8, ha="right")
    for i, y in enumerate(yrs):
        axes[1].text(i, min(y, 38) + 0.8, f"{y:.1f} y", ha="center", fontsize=8)
    axes[1].set_ylim(0, 42)
    axes[1].set_ylabel("estimated battery life (years)")
    axes[1].set_title("Battery life, 19 000 mAh, one 12-byte report per 30 min", fontsize=9)
    axes[1].tick_params(axis="x", labelsize=8)
    axes[1].grid(axis="y", alpha=0.3)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, "figures"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "figures", "fig_partB.png"), dpi=150)
    with open(os.path.join(HERE, "results_partB.txt"), "w") as f:
        f.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
