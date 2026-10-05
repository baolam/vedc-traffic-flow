@echo off
setlocal
cd /d E:\vedc-traffic-flow\experiments\example

echo [1/2] Running SUMO...
D:\sumo\bin\sumo.exe -c "E:\vedc-traffic-flow\experiments\example\simulation.sumocfg" --tripinfo-output "E:\vedc-traffic-flow\experiments\example\tripinfo.xml" --summary-output "E:\vedc-traffic-flow\experiments\example\summary.xml" --emission-output "E:\vedc-traffic-flow\experiments\example\emission.xml"

if errorlevel 1 (
  echo SUMO FAILED.
  pause
  exit /b 1
)

echo.
echo [2/2] Calculating metrics...
python "E:\vedc-traffic-flow\experiments\example\metrics.py"

echo.
echo Done. Open metrics.csv to see the results.
pause
