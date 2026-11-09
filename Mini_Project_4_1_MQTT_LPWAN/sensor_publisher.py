"""
sensor_publisher.py - simulated factory sensor (Mini Project 4.1, Part A, steps 3-5).

Every --interval seconds it publishes a random reading between --low and --high to --topic.
Before connecting it registers a Last Will and Testament (LWT): topic factory/line3/status,
payload "offline", QoS 1, retain True. Right after connecting it publishes "online" (retain True)
to the same status topic. The first reading is published with retain=True (step 5); with
--retain-all every reading is retained, so a late subscriber always gets the latest one.

    python sensor_publisher.py                                   # step 3: temperature sensor
    python sensor_publisher.py --client-id line3-humidity-sensor \
        --topic factory/line3/humidity --low 30 --high 80 --status-topic none   # lab task 1
"""
import argparse
import os
import random
import signal
import time
from datetime import datetime

import paho.mqtt.client as mqtt


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--client-id", default="line3-temp-sensor")
    ap.add_argument("--topic", default="factory/line3/temperature")
    ap.add_argument("--status-topic", default="factory/line3/status", help="'none' disables status/LWT")
    ap.add_argument("--low", type=float, default=60.0)
    ap.add_argument("--high", type=float, default=95.0)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--qos", type=int, default=1, choices=[0, 1, 2])
    ap.add_argument("--keepalive", type=int, default=5, help="seconds; the broker fires the LWT after 1.5 x keepalive")
    ap.add_argument("--count", type=int, default=0, help="stop cleanly after N readings (0 = run until killed)")
    ap.add_argument("--retain-all", action="store_true", help="retain every reading, not only the first")
    ap.add_argument("--seq", action="store_true", help="append a sequence number to the payload (loss counting)")
    ap.add_argument("--persistent", action="store_true", help="clean_session=False (broker keeps the session)")
    ap.add_argument("--crash-after", type=int, default=0, help="SIGKILL itself right after the Nth publish (lab task 2)")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    rng = random.Random(a.seed)

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=a.client_id, clean_session=not a.persistent)
    c.max_queued_messages_set(0)                                  # queue QoS>0 messages while offline
    c.reconnect_delay_set(min_delay=1, max_delay=2)
    status = None if a.status_topic.lower() == "none" else a.status_topic
    if status:
        c.will_set(status, "offline", qos=1, retain=True)          # step 4: registered BEFORE connect

    def on_connect(client, userdata, flags, rc, props):
        print(f"[{ts()}] CONNECTED to {a.host}:{a.port} as {a.client_id} (rc={rc}, keepalive {a.keepalive} s)", flush=True)
        if status:
            client.publish(status, "online", qos=1, retain=True)
            print(f"[{ts()}] PUBLISH {status} = online (QoS 1, retained)", flush=True)

    def on_disconnect(client, userdata, flags, rc, props):
        print(f"[{ts()}] DISCONNECTED (rc={rc})", flush=True)

    c.on_connect, c.on_disconnect = on_connect, on_disconnect
    c.connect(a.host, a.port, keepalive=a.keepalive)
    c.loop_start()
    time.sleep(0.3)

    n = 0
    try:
        while a.count == 0 or n < a.count:
            n += 1
            value = round(rng.uniform(a.low, a.high), 1)
            payload = f"{value:.1f}" + (f" #{n}" if a.seq else "")
            retain = a.retain_all or n == 1
            info = c.publish(a.topic, payload, qos=a.qos, retain=retain)
            state = "" if info.rc == mqtt.MQTT_ERR_SUCCESS else ("  [queued: not connected]" if a.qos else "  [DROPPED: not connected]")
            print(f"[{ts()}] PUBLISH {a.topic} = {payload} (QoS {a.qos}{', retained' if retain else ''}){state}", flush=True)
            if a.crash_after and n == a.crash_after:
                print(f"[{ts()}] CRASH: SIGKILL right after publish #{n}", flush=True)
                os.kill(os.getpid(), signal.SIGKILL)               # ungraceful: no DISCONNECT packet is sent
            time.sleep(a.interval)
    except KeyboardInterrupt:
        pass
    print(f"[{ts()}] clean disconnect (DISCONNECT packet sent: the broker discards the LWT)", flush=True)
    c.disconnect()
    c.loop_stop()


if __name__ == "__main__":
    main()
