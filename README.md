# Mobile Communications – Lab 4 (Unit 4 Mini Projects)

University of Rwanda, College of Science and Technology, School of ICT, Department of Computer Engineering
Group 3: Ronsard RUGIRANGOGA (223026673), Ivan MULISA (223026695), Dieudonne BYIRINGIRO (223026513)

The written report summarises the results; this repository holds the complete code, the console logs and the result files.

## Structure

```
Mini_Project_4_1_MQTT_LPWAN/
    sensor_publisher.py      Part A: line3-temp-sensor, QoS 1, LWT "offline" (retained), "online" on connect, first reading retained
    dashboard_subscriber.py  Part A: factory/line3/temperature + factory/line3/status, timestamped lines
    alert_subscriber.py      Part A: factory/+/temperature (threshold 90) + factory/+/status; --topic factory/line3/+ for lab task 1
    run_part_a.py            starts a Mosquitto broker and runs steps 8-10 and lab tasks 1-3, logs -> logs/
    link_budget_compare.py   Part B: MCL, path loss, coverage margin, battery life; lab tasks 4-6 -> results_partB.txt, figures/
Mini_Project_4_2_Tech_Selector/
    selector.py              scoring matrix, weights, constraint rules, 4 Section 4.3 scenarios + 1 new -> results_4_2.txt
Mini_Project_4_3_MQTT_Dashboard/
    sensor.py                one simulated sensor per process (plant1/<line>/<measurement>, QoS 1, optional LWT / retain)
    aggregator.py            ONE wildcard subscription plant1/+/+, CSV log, per-topic thresholds, periodic summary
    late_subscriber.py       prints the retained messages a late subscriber receives
    run_demo.py              scripted run: 3 sensors, late joiner, new topic at run time, LWT -> logs/
```

## Run

Python 3.9 or later and a Mosquitto broker (`apt install mosquitto` or https://mosquitto.org/download/).

```
pip install -r requirements.txt
cd Mini_Project_4_1_MQTT_LPWAN
python run_part_a.py --mosquitto mosquitto          (~3 min; or run the three scripts by hand in three terminals)
python link_budget_compare.py
cd ../Mini_Project_4_2_Tech_Selector
python selector.py                                  (python selector.py --interactive for a new scenario)
cd ../Mini_Project_4_3_MQTT_Dashboard
python run_demo.py --mosquitto mosquitto            (~35 s)
```

The scripts default to a broker on localhost:1883; pass `--host test.mosquitto.org` to use a public test broker for the
manual three-terminal run.
