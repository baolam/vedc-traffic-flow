@echo off
python "%~dp0setup_vehicle_images.py"
D:\sumo\bin\sumo-gui.exe -c "E:\vedc-traffic-flow\experiments\example\simulation.sumocfg"
