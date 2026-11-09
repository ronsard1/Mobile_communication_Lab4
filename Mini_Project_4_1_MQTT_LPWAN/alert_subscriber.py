"""
alert_subscriber.py - threshold alerting (Mini Project 4.1, Part A, step 7).

Subscribes to the wildcard factory/+/temperature at QoS 1 and prints an ALERT line only when a
temperature exceeds --threshold (default 90.0). It also watches factory/+/status so that a sensor
going offline (the LWT) is reported. For lab task 1 run it with --topic factory/line3/+ : it then
receives temperature, humidity and status without any change to the temperature threshold logic.

    python alert_subscriber.py
    python alert_subscriber.py --topic factory/line3/+          # lab task 1
"""
import argparse
from datetime import datetime

import paho.mqtt.client as mqtt


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--topic", action="append", help="subscription(s); default factory/+/temperature and factory/+/status")
    ap.add_argument("--threshold", type=float, default=90.0)
    ap.add_argument("--verbose", action="store_true", help="also log readings that do not raise an alert")
    a = ap.parse_args()
    topics = a.topic or ["factory/+/temperature", "factory/+/status"]

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="alert-service")

    def on_connect(client, userdata, flags, rc, props):
        for t in topics:
            client.subscribe(t, qos=1)
        print(f"[{ts()}] ALERTER subscribed to {', '.join(topics)} (QoS 1), threshold {a.threshold}", flush=True)

    def on_message(client, userdata, msg):
        text = msg.payload.decode(errors="replace")
        if msg.topic.endswith("/status"):
            if text == "offline":
                print(f"[{ts()}] ALERTER ALERT: {msg.topic} reports OFFLINE{'  [RETAINED]' if msg.retain else ''}", flush=True)
            elif a.verbose:
                print(f"[{ts()}] ALERTER received {msg.topic} = {text}", flush=True)
            return
        if msg.topic.endswith("/temperature"):                       # unchanged temperature threshold logic
            value = float(text.split()[0])
            if value > a.threshold:
                print(f"[{ts()}] ALERTER ALERT: {msg.topic} = {value:.1f} exceeds {a.threshold:.1f}", flush=True)
            elif a.verbose:
                print(f"[{ts()}] ALERTER received {msg.topic} = {value:.1f} (below threshold)", flush=True)
            return
        print(f"[{ts()}] ALERTER received {msg.topic} = {text} (no threshold for this measurement)", flush=True)

    c.on_connect, c.on_message = on_connect, on_message
    c.connect(a.host, a.port, keepalive=10)
    c.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
