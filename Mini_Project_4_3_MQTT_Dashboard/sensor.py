"""
sensor.py - one simulated plant sensor (Mini Project 4.3). Run one process per sensor.

Each sensor publishes to plant1/<line>/<measurement> at its own interval, QoS 1. The signal is a
slow sine around --base with noise and occasional spikes (so thresholds are crossed now and then).
--lwt registers a Last Will "offline" (QoS 1, retained) on plant1/<line>/status and publishes "online"
after connecting. --retain retains every reading so a late subscriber gets the latest value at once.

    python sensor.py --topic plant1/lineA/temperature --base 72 --amp 6 --interval 1 --lwt --retain
"""
import argparse
import math
import random
import time
from datetime import datetime

import paho.mqtt.client as mqtt


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--base", type=float, default=70.0)
    ap.add_argument("--amp", type=float, default=5.0, help="amplitude of the slow sine")
    ap.add_argument("--period", type=float, default=20.0, help="period of the slow sine (s)")
    ap.add_argument("--noise", type=float, default=0.5)
    ap.add_argument("--spike-prob", type=float, default=0.08)
    ap.add_argument("--spike", type=float, default=8.0)
    ap.add_argument("--qos", type=int, default=1)
    ap.add_argument("--lwt", action="store_true")
    ap.add_argument("--retain", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    line = a.topic.split("/")[1]
    cid = a.topic.replace("/", "-")
    status = f"plant1/{line}/status"

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid)
    if a.lwt:
        c.will_set(status, "offline", qos=1, retain=True)
    c.connect(a.host, a.port, keepalive=5)
    c.loop_start()
    if a.lwt:
        c.publish(status, "online", qos=1, retain=True)
    print(f"[{ts()}] SENSOR {a.topic} up (every {a.interval} s, QoS {a.qos}{', LWT' if a.lwt else ''}"
          f"{', retained' if a.retain else ''})", flush=True)
    t0 = time.time()
    while True:
        t = time.time() - t0
        v = a.base + a.amp * math.sin(2 * math.pi * t / a.period) + rng.gauss(0, a.noise)
        if rng.random() < a.spike_prob:
            v += a.spike
        c.publish(a.topic, f"{v:.2f}", qos=a.qos, retain=a.retain)
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
