@echo off
set "NET=E:\vedc-traffic-flow\experiments\example\network.net.xml"
set "OUT=E:\vedc-traffic-flow\experiments\example\routes.rou.xml"
python "E:\vedc-traffic-flow\experiments\example\route_generator_complete.py" -n "%NET%" -o "%OUT%" -v 3000 --end 3600 --seed 42 --fixed-percent 15 --random-end-percent 15 --irregular-percent 10 --fixed-corridors 2 --fixed-min-edges 6 --fixed-max-edges 30 --min-distance 300 --alternatives 3 --max-detour 1.60 --alt-prob 0.75 --irregular-min-edges 4 --irregular-max-edges 20
pause
