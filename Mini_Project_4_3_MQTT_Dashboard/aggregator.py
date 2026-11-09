"""
aggregator.py - aggregator / logger / alerter (Mini Project 4.3).

ONE wildcard subscription, plant1/+/+ (QoS 1), receives every reading and status message of every
sensor, including sensors that did not exist when it started. For each message it:
  * appends a timestamped row to a CSV log (--csv),
  * keeps the latest value, count, min and max per topic (dictionary keyed by topic),
  * checks the topic against the threshold of its measurement type (THRESHOLDS below), independently
    per topic: ALERT when a value rises above the threshold, CLEAR when it falls back,
  * reports status changes (online / offline from a Last Will).
Every --summary seconds it prints the latest value per topic.

    python aggregator.py --csv readings.csv
"""
import argparse
import csv
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt

# Per-measurement-type thresholds: a new topic of a known type is alerted with no code change.
THRESHOLDS = {"temperature": 80.0, "vibration": 7.1, "humidity": 70.0, "pressure": 6.0}


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


class Aggregator:
    def __init__(self, csv_path, summary_s):
        self.latest = {}               # topic -> dict(value, n, lo, hi, alarm)
        self.lock = threading.Lock()
        self.f = open(csv_path, "w", newline="")
        self.w = csv.writer(self.f)
        self.w.writerow(["time", "topic", "payload", "retained"])
        self.summary_s = summary_s

    def on_message(self, client, userdata, msg):
        text = msg.payload.decode(errors="replace")
        now = ts()
        with self.lock:
            self.w.writerow([now, msg.topic, text, int(msg.retain)])
            self.f.flush()
            measurement = msg.topic.split("/")[-1]
            if measurement == "status":
                print(f"[{now}] AGG STATUS {msg.topic} = {text}{'  [RETAINED]' if msg.retain else ''}", flush=True)
                return
            value = float(text)
            st = self.latest.get(msg.topic)
            if st is None:
                st = self.latest[msg.topic] = dict(value=value, n=0, lo=value, hi=value, alarm=False)
                print(f"[{now}] AGG NEW TOPIC {msg.topic} (first value {value:.2f}{', retained' if msg.retain else ''}; "
                      f"threshold {THRESHOLDS.get(measurement, 'none')})", flush=True)
            st.update(value=value, n=st["n"] + 1, lo=min(st["lo"], value), hi=max(st["hi"], value))
            thr = THRESHOLDS.get(measurement)
            if thr is not None:
                if value > thr and not st["alarm"]:
                    st["alarm"] = True
                    print(f"[{now}] AGG ALERT {msg.topic} = {value:.2f} > {thr}", flush=True)
                elif value <= thr and st["alarm"]:
                    st["alarm"] = False
                    print(f"[{now}] AGG CLEAR {msg.topic} = {value:.2f} back below {thr}", flush=True)

    def summaries(self):
        while True:
            time.sleep(self.summary_s)
            with self.lock:
                rows = [f"{t} = {s['value']:.2f} (n={s['n']}, min {s['lo']:.2f}, max {s['hi']:.2f}{', ALARM' if s['alarm'] else ''})"
                        for t, s in sorted(self.latest.items())]
            print(f"[{ts()}] AGG SUMMARY ({len(rows)} topics): " + " | ".join(rows), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--csv", default="readings.csv")
    ap.add_argument("--summary", type=float, default=5.0)
    a = ap.parse_args()
    agg = Aggregator(a.csv, a.summary)
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="plant1-aggregator")
    c.on_connect = lambda cl, u, f, rc, p: (cl.subscribe("plant1/+/+", qos=1),
                                            print(f"[{ts()}] AGG subscribed to plant1/+/+ (QoS 1)", flush=True))
    c.on_message = agg.on_message
    threading.Thread(target=agg.summaries, daemon=True).start()
    c.connect(a.host, a.port, keepalive=10)
    c.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
