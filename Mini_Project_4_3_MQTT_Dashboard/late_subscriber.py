"""
late_subscriber.py - joins late, prints what the broker delivers at once (retained messages), exits.

    python late_subscriber.py --seconds 0.5
"""
import argparse
import time
from datetime import datetime

import paho.mqtt.client as mqtt


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


ap = argparse.ArgumentParser()
ap.add_argument("--host", default="localhost")
ap.add_argument("--port", type=int, default=1883)
ap.add_argument("--seconds", type=float, default=0.5)
a = ap.parse_args()
c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="late-joiner")
c.on_connect = lambda cl, u, f, rc, p: cl.subscribe("plant1/#", qos=1)
c.on_message = lambda cl, u, m: m.retain and print(
    f"[{ts()}] LATE received at subscribe: {m.topic} = {m.payload.decode()}  [RETAINED]", flush=True)
c.connect(a.host, a.port)
c.loop_start()
print(f"[{ts()}] LATE joiner subscribed to plant1/# (only retained messages are printed)", flush=True)
time.sleep(a.seconds)
c.disconnect()
c.loop_stop()
