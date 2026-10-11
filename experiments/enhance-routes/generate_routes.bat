@echo off
python "E:\vedc-traffic-flow\experiments\example\route_generator.py" -n "E:\vedc-traffic-flow\experiments\example\network.net.xml" -o "E:\vedc-traffic-flow\experiments\example\routes.rou.xml" -v 1000 --end 3600 --seed 42 --min-distance 300 --alternatives 3 --max-detour 1.60 --alt-prob 0.75
pause
