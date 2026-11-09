"""
run_part_a.py - runs the Part A demonstrations end to end and saves the console logs in logs/.

  main   steps 8-10: two subscribers + publisher, restart of the dashboard (retained messages),
         hard kill of the publisher (LWT), then a clean disconnect for comparison
  task1  second sensor on factory/line3/humidity, alert subscriber on factory/line3/+
  task2  ungraceful disconnect at QoS 0, 1 and 2: is the last reading before the crash received?
  task3  broker killed and restarted while the publisher runs at QoS 0 and at QoS 1: readings lost

It starts its own Mosquitto broker on 127.0.0.1:1883 (path given by --mosquitto, default "mosquitto").

    python run_part_a.py --mosquitto /usr/sbin/mosquitto            # everything (~2.5 minutes)
    python run_part_a.py --only main
"""
import argparse
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime

import paho.mqtt.client as mqtt

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, "logs")
PY = [sys.executable, "-u"]
HOST, PORT = "127.0.0.1", 1883


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


class Lab:
    def __init__(self, mosquitto):
        self.mosquitto = mosquitto
        self.procs, self.files, self.notes = {}, [], []
        self.broker = None
        self.tmp = tempfile.mkdtemp(prefix="mqtt_lab_")

    # ------------------------------------------------------------------ broker
    def start_broker(self, persistent=False):
        conf = os.path.join(self.tmp, "mosquitto.conf")
        with open(conf, "w") as f:
            f.write(f"listener {PORT} {HOST}\nallow_anonymous true\n")
            if persistent:
                f.write(f"persistence true\npersistence_location {self.tmp}/\nautosave_interval 1\n")
        self.broker = subprocess.Popen([self.mosquitto, "-c", conf], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.6)
        self.note(f"broker started (pid {self.broker.pid}{', persistence on' if persistent else ''})")

    def stop_broker(self, how="TERM"):
        if self.broker:
            self.broker.send_signal(signal.SIGTERM if how == "TERM" else signal.SIGKILL)
            self.broker.wait()
            self.note(f"broker stopped (SIG{how})")
            self.broker = None

    # ------------------------------------------------------------------ processes
    def start(self, name, script, *args):
        path = os.path.join(self.tmp, f"{name}_{len(self.files)}.log")
        f = open(path, "w")
        self.files.append(path)
        self.procs[name] = subprocess.Popen(PY + [os.path.join(HERE, script), "--host", HOST, *args],
                                            stdout=f, stderr=subprocess.STDOUT, cwd=HERE)
        self.note(f"started {script} {' '.join(args)}".rstrip())
        return self.procs[name]

    def stop(self, name, sig=signal.SIGTERM, label="stopped"):
        p = self.procs.pop(name)
        p.send_signal(sig)
        p.wait()
        self.note(f"{label} {name} (pid {p.pid})")

    def stop_all(self):
        for n in list(self.procs):
            self.stop(n)
        self.stop_broker()

    def note(self, text):
        self.notes.append(f"[{ts()}] ===== {text}")

    def merged(self):
        lines = list(self.notes)
        for p in self.files:
            lines += [l.rstrip("\n") for l in open(p) if l.startswith("[")]
        return sorted(lines, key=lambda l: l[1:13])


def save(name, lines, header):
    os.makedirs(LOGS, exist_ok=True)
    with open(os.path.join(LOGS, name), "w") as f:
        f.write(header.rstrip() + "\n\n" + "\n".join(lines) + "\n")
    print(f"--- {name}: {len(lines)} lines")


# ====================================================================== scenarios
def run_main(mosq):
    lab = Lab(mosq)
    lab.start_broker()
    lab.start("dashboard", "dashboard_subscriber.py")
    lab.start("alerter", "alert_subscriber.py")
    time.sleep(1.0)
    lab.start("publisher", "sensor_publisher.py", "--seed", "11")
    time.sleep(17.5)                                   # readings at ~0, 5, 10, 15 s
    lab.stop("dashboard", label="step 9: stopped")
    time.sleep(1.5)
    lab.note("step 9: restarting the dashboard between two publish cycles")
    lab.start("dashboard", "dashboard_subscriber.py")
    time.sleep(10.0)
    lab.stop("publisher", signal.SIGKILL, label="step 10: HARD KILL (SIGKILL, no DISCONNECT sent) of")
    lab.note("the OS closes the dead process's TCP socket, so the broker sees an unclean close at once")
    time.sleep(5.0)
    lab.note("step 10b: silent link loss - publisher frozen with SIGSTOP (socket stays open, no PINGREQ)")
    lab.start("publisher3", "sensor_publisher.py", "--seed", "9", "--interval", "5")
    time.sleep(2.0)
    p3 = lab.procs["publisher3"]
    p3.send_signal(signal.SIGSTOP)
    lab.note(f"publisher frozen (pid {p3.pid}); only the broker's keep-alive timer can detect it "
             "(1.5 x 5 s = 7.5 s after the last packet, checked by Mosquitto every 5 s)")
    time.sleep(15.0)
    lab.stop("publisher3", signal.SIGKILL, label="removed frozen")
    time.sleep(1.0)
    lab.note("comparison: publisher run with a clean disconnect after 2 readings")
    lab.start("publisher2", "sensor_publisher.py", "--seed", "8", "--count", "2", "--interval", "2")
    lab.procs["publisher2"].wait()
    lab.procs.pop("publisher2")
    time.sleep(9.0)
    lab.note("no 'offline' arrived after the clean disconnect: the broker discarded the LWT")
    lab.stop_all()
    save("part_a_main.log", lab.merged(),
         "Part A, steps 8-10: normal operation, retained messages on a late subscriber, LWT on an ungraceful\n"
         "disconnect, and a clean disconnect for comparison. Publisher keep-alive 5 s, interval 5 s, QoS 1.")


def run_task1(mosq):
    lab = Lab(mosq)
    lab.start_broker()
    lab.start("alerter", "alert_subscriber.py", "--topic", "factory/line3/+", "--verbose")
    time.sleep(1.0)
    lab.start("temp", "sensor_publisher.py", "--seed", "3", "--interval", "2", "--count", "4")
    lab.start("hum", "sensor_publisher.py", "--client-id", "line3-humidity-sensor", "--topic", "factory/line3/humidity",
              "--low", "30", "--high", "80", "--status-topic", "none", "--seed", "4", "--interval", "2", "--count", "4")
    lab.procs["temp"].wait()
    lab.procs["hum"].wait()
    lab.procs.pop("temp"), lab.procs.pop("hum")
    time.sleep(1.0)
    lab.stop_all()
    save("task1_humidity.log", lab.merged(),
         "Lab task 1: second sensor on factory/line3/humidity; the alert subscriber now subscribes to factory/line3/+\n"
         "and receives temperature, humidity and status with its temperature threshold logic unchanged.")


class Counter:
    """In-process subscriber that records the sequence numbers it receives."""

    def __init__(self, client_id, persistent=False):
        self.seen = []
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, clean_session=not persistent)
        self.c.reconnect_delay_set(1, 1)
        self.c.on_connect = lambda c, u, f, rc, p: c.subscribe("factory/line3/temperature", qos=2)
        self.c.on_message = self._msg
        self.c.connect(HOST, PORT, keepalive=10)
        self.c.loop_start()
        time.sleep(0.4)

    def _msg(self, c, u, m):
        t = m.payload.decode()
        if "#" in t and not m.retain:
            self.seen.append(int(t.split("#")[1]))

    def close(self):
        self.c.disconnect()
        self.c.loop_stop()


def run_task2(mosq, trials=10):
    lab = Lab(mosq)
    lab.start_broker()
    out = []
    for qos in (0, 1, 2):
        got = 0
        for k in range(trials):
            sub = Counter(f"task2-q{qos}-{k}")
            p = lab.start("pub", "sensor_publisher.py", "--qos", str(qos), "--seq", "--interval", "0.2",
                          "--crash-after", "3", "--status-topic", "none", "--seed", str(k))
            p.wait()
            lab.procs.pop("pub")
            time.sleep(0.5)
            ok = 3 in sub.seen
            got += ok
            sub.close()
            out.append(f"QoS {qos} trial {k + 1:2d}: received {sorted(set(sub.seen))} -> last reading (#3) {'received' if ok else 'LOST'}")
        out.append(f"QoS {qos}: last reading before the crash received in {got}/{trials} trials")
    lab.stop_all()
    summary = [l for l in out if "trials" in l]
    save("task2_qos_crash.log", out + [""] + summary,
         "Lab task 2: publisher SIGKILLs itself immediately after its 3rd publish call, 10 trials per QoS level.")
    return summary


def run_task3(mosq, n=40, interval=0.5):
    results = []
    lab = Lab(mosq)
    for qos in (0, 1):
        lab.start_broker(persistent=True)
        sub = Counter(f"task3-dashboard-q{qos}", persistent=True)
        lab.start("pub", "sensor_publisher.py", "--client-id", f"task3-pub-q{qos}", "--qos", str(qos), "--seq",
                  "--persistent", "--interval", str(interval), "--count", str(n), "--status-topic", "none", "--seed", "1")
        time.sleep(6.0)
        lab.stop_broker("TERM")
        lab.note(f"QoS {qos}: broker DOWN for 5 s (unreliable network)")
        time.sleep(5.0)
        lab.start_broker(persistent=True)
        lab.procs["pub"].wait()
        lab.procs.pop("pub")
        time.sleep(2.0)
        seen = sorted(set(sub.seen))
        lost = [i for i in range(1, n + 1) if i not in seen]
        results.append(f"QoS {qos}: {n} readings sent, {len(seen)} received, {len(lost)} lost {lost if lost else ''}")
        lab.note(results[-1])
        sub.close()
        lab.stop_broker()
    save("task3_unreliable.log", lab.merged() + [""] + results,
         f"Lab task 3: broker stopped for 5 s and restarted while the publisher sends {n} readings every {interval} s.\n"
         "Publisher and subscriber use persistent sessions (clean_session=False); the broker keeps sessions on disk.")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mosquitto", default="mosquitto")
    ap.add_argument("--only", choices=["main", "task1", "task2", "task3"])
    a = ap.parse_args()
    todo = [a.only] if a.only else ["main", "task1", "task2", "task3"]
    summary = []
    for t in todo:
        print(f"running {t} ...", flush=True)
        r = {"main": run_main, "task1": run_task1, "task2": run_task2, "task3": run_task3}[t](a.mosquitto)
        summary += r or []
    if summary:
        with open(os.path.join(LOGS, "summary_tasks_2_3.txt"), "w") as f:
            f.write("\n".join(summary) + "\n")
        print("\n".join(summary))
