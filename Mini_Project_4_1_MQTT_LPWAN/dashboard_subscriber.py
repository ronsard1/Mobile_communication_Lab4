"""
dashboard_subscriber.py - live operator dashboard (Mini Project 4.1, Part A, step 6).

Subscribes to factory/line3/temperature and factory/line3/status at QoS 1 and prints one
timestamped line per message. Retained messages delivered on subscribe are marked [RETAINED].
With --persistent the session survives a broker restart (lab task 3) and readings with a
sequence number are counted, so lost readings can be reported at the end.

    python dashboard_subscriber.py
"""
import argparse
import signal
import sys
from datetime import datetime

import paho.mqtt.client as mqtt

TOPICS = ["factory/line3/temperature", "factory/line3/status"]


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--client-id", default="operator-dashboard")
    ap.add_argument("--persistent", action="store_true")
    a = ap.parse_args()
    seen = set()

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=a.client_id, clean_session=not a.persistent)
    c.reconnect_delay_set(min_delay=1, max_delay=2)

    def on_connect(client, userdata, flags, rc, props):
        resumed = getattr(flags, "session_present", False)
        print(f"[{ts()}] DASHBOARD connected (rc={rc}, session present={resumed})", flush=True)
        for t in TOPICS:
            client.subscribe(t, qos=1)
        print(f"[{ts()}] DASHBOARD subscribed to {', '.join(TOPICS)} (QoS 1)", flush=True)

    def on_message(client, userdata, msg):
        text = msg.payload.decode(errors="replace")
        if "#" in text:
            seen.add(int(text.split("#")[1]))
        tag = "  [RETAINED]" if msg.retain else ""
        print(f"[{ts()}] DASHBOARD {msg.topic:28s} {text}{tag}", flush=True)

    def stop(*_):
        if seen:
            print(f"[{ts()}] DASHBOARD summary: {len(seen)} distinct readings received, highest #{max(seen)}", flush=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    c.on_connect, c.on_message = on_connect, on_message
    c.connect(a.host, a.port, keepalive=10)
    c.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
