import xml.etree.ElementTree as ET
import random
from pathlib import Path

base = Path(r"E:\vedc-traffic-flow\experiments\example")
route_file = base / "routes.rou.xml"

tree = ET.parse(route_file)
root = tree.getroot()

# Remove old vType definitions with these IDs, if present.
ids = {"motorcycle", "car", "taxi", "bus", "truck"}
for e in list(root):
    if e.tag == "vType" and e.get("id") in ids:
        root.remove(e)

types = [
    ("motorcycle", "motorcycle", "motorcycle.png", "2.2", "0.9", "3.0", "5.0", "50"),
    ("car", "passenger", "car.png", "4.5", "1.8", "2.6", "4.5", "50"),
    ("taxi", "taxi", "taxi.png", "4.5", "1.8", "2.6", "4.5", "50"),
    ("bus", "bus", "bus.png", "12", "2.5", "1.2", "4.0", "40"),
    ("truck", "truck", "truck.png", "8", "2.4", "1.5", "4.0", "40"),
]

for vid, vclass, image, length, width, accel, decel, maxspeed in reversed(types):
    ET.SubElement(root, "vType", {
        "id": vid,
        "vClass": vclass,
        "guiShape": "passenger" if vid in {"car", "taxi"} else vid,
        "imgFile": f"vehicles/{image}",
        "length": length,
        "width": width,
        "minGap": "1.5" if vid == "motorcycle" else "2.5",
        "accel": accel,
        "decel": decel,
        "maxSpeed": maxspeed,
        "color": "1,1,1",
    })

random.seed(42)
weights = ["motorcycle"] * 65 + ["car"] * 25 + ["taxi"] * 4 + ["bus"] * 3 + ["truck"] * 3

count = 0
for tag in ("vehicle", "flow"):
    for v in root.findall(tag):
        v.set("type", random.choice(weights))
        count += 1

ET.indent(tree, space="    ")
tree.write(route_file, encoding="UTF-8", xml_declaration=True)
print(f"OK: configured raster vehicle images for {count} vehicles/flows.")
print("Next: open SUMO-GUI, press F9, Vehicles -> Shape -> raster images.")
