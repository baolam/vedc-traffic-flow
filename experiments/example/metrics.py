import xml.etree.ElementTree as ET
from pathlib import Path
import csv

ROOT = Path(r"E:\vedc-traffic-flow\experiments\example")
TRIP = ROOT / "tripinfo.xml"
SUMMARY = ROOT / "summary.xml"
EMISSION = ROOT / "emission.xml"
CSV = ROOT / "metrics.csv"

def f(x, default=0.0):
    try: return float(x)
    except: return default

# Trip metrics
n = 0
arrived = 0
sum_duration = sum_wait = sum_speed = sum_timeloss = sum_route = 0.0
if TRIP.exists():
    for e in ET.parse(TRIP).getroot().iter("tripinfo"):
        n += 1
        arrived += 1
        sum_duration += f(e.get("duration"))
        sum_wait += f(e.get("waitingTime"))
        sum_speed += f(e.get("routeLength")) / f(e.get("duration")) if f(e.get("duration")) > 0 else 0
        sum_timeloss += f(e.get("timeLoss"))
        sum_route += f(e.get("routeLength"))

avg_travel = sum_duration / n if n else 0
avg_wait = sum_wait / n if n else 0
avg_speed_ms = sum_speed / n if n else 0
avg_speed_kmh = avg_speed_ms * 3.6
avg_timeloss = sum_timeloss / n if n else 0

# Summary: last timestep with teleports if available
teleports = 0
if SUMMARY.exists():
    root = ET.parse(SUMMARY).getroot()
    for s in root.iter("step"):
        teleports = int(f(s.get("teleports")))
    # Some SUMO versions use teleports as a child/attribute in different layouts
    if teleports == 0:
        for e in root.iter():
            if "teleport" in e.tag.lower():
                teleports = max(teleports, int(f(e.get("teleports"))))

# Emissions: aggregate vehicle-step values
co2 = fuel = 0.0
emission_records = 0
if EMISSION.exists():
    for e in ET.parse(EMISSION).getroot().iter("vehicle"):
        co2 += f(e.get("CO2"))
        fuel += f(e.get("fuel"))
        emission_records += 1

# Write one-row CSV
fields = [
    "vehicles_arrived","average_travel_time_s","average_waiting_time_s",
    "average_speed_kmh","average_time_loss_s","throughput_vehicles",
    "teleports","total_co2_mg","total_fuel_ml","emission_vehicle_steps"
]
values = [
    arrived, round(avg_travel,3), round(avg_wait,3), round(avg_speed_kmh,3),
    round(avg_timeloss,3), arrived, teleports, round(co2,3), round(fuel,3),
    emission_records
]
with CSV.open("w", newline="", encoding="utf-8-sig") as fp:
    w = csv.writer(fp)
    w.writerow(fields)
    w.writerow(values)

print("\n=== SUMO METRICS ===")
for k,v in zip(fields,values):
    print(f"{k}: {v}")
print(f"\nSaved: {CSV}")
