SUMO METRICS PACKAGE

Copy these files into:
E:\vedc-traffic-flow\experiments\example\

Then double-click:
run_simulation.bat

It runs SUMO and produces:
- tripinfo.xml
- summary.xml
- emission.xml
- metrics.csv

metrics.csv includes:
- vehicles_arrived
- average_travel_time_s
- average_waiting_time_s
- average_speed_kmh
- average_time_loss_s
- throughput_vehicles
- teleports
- total_co2_mg
- total_fuel_ml

Note: queue length is not inferred from tripinfo because accurate queue measurement
requires lane/edge detectors or a dedicated queue output. It can be added next.
