"""
run_demo.py - scripted run of the multi-sensor system; writes logs/sample_log.txt and logs/readings.csv.

Timeline (about 32 s): broker, aggregator, three sensors (lineA temperature with LWT + retain, lineA
vibration, lineB temperature); a late subscriber at 8 s (retained messages); a NEW sensor
plant1/lineB/humidity added at 12 s (picked up by the unchanged wildcard aggregator); hard kill of the
lineA temperature sensor at 20 s (LWT); a second late subscriber at 24 s.

    python run_demo.py --mosquitto /usr/sbin/mosquitto
"""
import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(HERE, "logs")
PY = [sys.executable, "-u"]
SENSORS = {
    "A-temp": ["--topic", "plant1/lineA/temperature", "--base", "73", "--amp", "6", "--interval", "1.0", "--lwt", "--retain", "--seed", "1"],
    "A-vib": ["--topic", "plant1/lineA/vibration", "--base", "4.5", "--amp", "1.5", "--noise", "0.3", "--spike", "3.5",
              "--interval", "0.5", "--seed", "2"],
    "B-temp": ["--topic", "plant1/lineB/temperature", "--base", "68", "--amp", "5", "--interval", "1.5", "--retain", "--seed", "3"],
    "B-hum": ["--topic", "plant1/lineB/humidity", "--base", "62", "--amp", "6", "--noise", "1", "--spike", "6",
              "--interval", "1.0", "--seed", "4"],
}


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mosquitto", default="mosquitto")
    a = ap.parse_args()
    os.makedirs(LOGS, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="plant1_")
    conf = os.path.join(tmp, "m.conf")
    open(conf, "w").write("listener 1883 127.0.0.1\nallow_anonymous true\n")
    notes, files, procs = [], [], {}

    def note(t):
        notes.append(f"[{ts()}] ===== {t}")

    def start(name, script, *args):
        path = os.path.join(tmp, f"{name}.log")
        files.append(path)
        procs[name] = subprocess.Popen(PY + [os.path.join(HERE, script), "--host", "127.0.0.1", *args],
                                       stdout=open(path, "w"), stderr=subprocess.STDOUT, cwd=HERE)
        note(f"started {name}: {script} {' '.join(args)}")

    broker = subprocess.Popen([a.mosquitto, "-c", conf], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.6)
    start("aggregator", "aggregator.py", "--csv", "logs/readings.csv", "--summary", "6")
    time.sleep(0.8)
    for s in ("A-temp", "A-vib", "B-temp"):
        start(s, "sensor.py", *SENSORS[s])
    time.sleep(8.0)
    note("retained-message demo: a late subscriber joins")
    start("late1", "late_subscriber.py")
    procs.pop("late1").wait()
    time.sleep(3.5)
    note("NEW SENSOR added while running; the aggregator code is not touched")
    start("B-hum", "sensor.py", *SENSORS["B-hum"])
    time.sleep(8.0)
    p = procs.pop("A-temp")
    p.send_signal(signal.SIGKILL)
    p.wait()
    note("LWT demo: lineA temperature sensor HARD-KILLED (SIGKILL, no DISCONNECT)")
    time.sleep(4.0)
    note("late subscriber after the crash: retained last reading + retained 'offline' status")
    start("late2", "late_subscriber.py")
    procs.pop("late2").wait()
    time.sleep(4.0)
    for n, p in procs.items():
        p.send_signal(signal.SIGTERM)
        p.wait()
    broker.send_signal(signal.SIGTERM)
    broker.wait()
    note("all stopped")

    lines = list(notes)
    for f in files:
        lines += [l.rstrip("\n") for l in open(f) if l.startswith("[")]
    lines.sort(key=lambda l: l[1:13])
    with open(os.path.join(LOGS, "sample_log.txt"), "w") as f:
        f.write("Mini Project 4.3 sample log: aggregator (plant1/+/+), alerts, retained messages, new topic, LWT.\n"
                "Sensor publish lines are not echoed; every reading is in readings.csv.\n\n" + "\n".join(lines) + "\n")
    print(f"logs/sample_log.txt: {len(lines)} lines; readings.csv: {sum(1 for _ in open(os.path.join(LOGS, 'readings.csv'))) - 1} rows")


if __name__ == "__main__":
    main()
