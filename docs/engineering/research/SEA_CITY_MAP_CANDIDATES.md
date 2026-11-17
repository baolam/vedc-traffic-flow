# Southeast Asian city candidates for SUMO signal-control experiments (Research Note)

> Hanoi and Jakarta are now prepared benchmark maps. See [benchmarking.md](../benchmarking.md) for the frozen suite and generated-map limitations.

Verified: 2026-11-17. Scope: primary-source research and small text/metadata inspection only; no scenario archive download, SUMO execution, or training.

## Recommendation

Add **Hanoi** and **Jakarta** alongside the HCMC district scenario if motorcycle-heavy traffic is the priority. Both have current downloadable OSM geometry, but this investigation did **not** verify a public, openly licensed, ready-to-run, calibrated SUMO package for either city. Treat them as scenario construction projects. Keep **Bangkok/Sathorn** as the strongest verified ready-made SEA SUMO alternative, subject to license clarification and modernization; its published route files currently model cars rather than an explicit motorcycle fleet.

These are selection judgments, not claims of completed validation. A real map, a runnable simulation, calibrated demand, and validated motorcycle behavior are separate deliverables.

## Accepted scope and resource limits

The user selected Hanoi and Jakarta, limited to one small/medium district or corridor per city. Bangkok remains optional. Start with controlled synthetic motorcycle-heavy demand and label any later field-calibrated results separately.

Accepted crop ceiling: 32 signalized junctions including boundary-buffer signals, using one connected small/medium district or corridor per city. Preserve feeder roads and downstream storage; audit the actual boundary before selecting a district. The ceiling is not a verified count for any named district. The initial city track has three representative workloads per city, a timed/memory pilot before full evaluation, and up to four concurrent SUMO processes globally across training and evaluation. Use the GPU for learning and suitable batched inference; SUMO traffic simulation remains on CPU. The inspected machine exposes 20 logical CPUs, 15 GiB RAM and an RTX 4070 Laptop GPU with approximately 8 GiB VRAM; CUDA computation has not been tested. Full-city maps, multiple districts per city and broad fleet-share sweeps are outside the first version. See the [suite proposal](RL_BENCHMARK_SUITE_PROPOSAL.md) for case counts and resource admission rules.

## Candidate comparison

| City / area | Geometry and artifact status | Demand evidence | Motorcycle evidence and limitation | License / access |
| --- | --- | --- | --- | --- |
| Hanoi, Vietnam | Current Vietnam OSM PBF verified; clip a connected signalized urban district/corridor. No reusable SUMO package verified here. [Geofabrik Vietnam](https://download.geofabrik.de/asia/vietnam.html) | Published Hanoi studies exist, including a 2026 HaUI–Hanoi National University corridor study reporting field/camera observations and SUMO calibration; the publisher exposes a paper, not a verified simulation-file bundle. [Publisher record](https://www.vjol.info.vn/tckhcndaihoccongnghiep-vie/en/article/view/224782/) | A primary Hanoi SUMO incident study explicitly studies motorcycle-dominated mixed traffic. This establishes relevance, not transferable current calibration. [2020 study](https://iaeme.com/MasterAdmin/Journal_uploads/IJARET/VOLUME_11_ISSUE_11/IJARET_11_11_054.pdf) | OSM data: ODbL with attribution and applicable share-alike obligations. Paper access does not establish rights to unpublished scenario files. [OSM license](https://www.openstreetmap.org/copyright) |
| Jakarta, Indonesia; Menteng/Senen as research reference | Current Java OSM PBF verified; crop central Jakarta. A primary study describes a 31-intersection SUMO model, but no downloadable scenario is linked by its data-availability statement. [Geofabrik Java](https://download.geofabrik.de/asia/indonesia/java.html), [2022 study](https://www.mdpi.com/2071-1050/14/21/14590) | The study uses incoming traffic, turning ratios, and signal phases from TomTom/SCATS on 2020-01-17. These observations are not included as a verified open artifact. [Study §5](https://www.mdpi.com/2071-1050/14/21/14590) | Its **simulated fleet** includes 69.2% motorcycles. This is a study-specific input, not a present citywide trip share; lateral-behavior calibration is not verified. [Study §5](https://www.mdpi.com/2071-1050/14/21/14590) | OSM geometry has ODbL terms. The paper says data availability is not applicable; do not assume its TomTom/SCATS inputs or model are redistributable. [Study data statement](https://www.mdpi.com/2071-1050/14/21/14590) |
| Bangkok, Thailand; Sathorn | Public Chula-SSS repository verified with AM/PM network, routes, signal additions, configuration and launch scripts. File presence verified; current SUMO execution untested. [Author repository](https://github.com/SathornModel/Chula-SSS), [recursive inventory](https://api.github.com/repos/SathornModel/Chula-SSS/git/trees/master?recursive=1) | Authors report calibrated morning/evening scenarios, 2,375 nodes, 4,517 edges and 10 main signalized intersections. The calibration is historical, and the dataset README describes ongoing improvements. [2018 paper](https://easychair.org/publications/paper/jDp8/download), [dataset README](https://raw.githubusercontent.com/SathornModel/Chula-SSS/master/models/sathorn-morning-caswakul_sumoconf2018/readme.txt) | Both inspected route files define only one `vType`, `Car`, length 4.62 m. No explicit motorcycle type or motorcycle calibration is supplied by those files. [AM routes](https://raw.githubusercontent.com/SathornModel/Chula-SSS/master/models/sathorn-morning-caswakul_sumoconf2018/sathorn_w_20160422.rou.xml), [PM routes](https://raw.githubusercontent.com/SathornModel/Chula-SSS/master/models/sathorn-evening-caswakul_sumoconf2018/sathorn_w_20160422.rou.xml) | Public download is verified; reusable license is **unresolved**: repository metadata reports `license: null`, and `Chula-SSS/LICENSE.txt` is empty. [Metadata](https://api.github.com/repos/SathornModel/Chula-SSS), [license file](https://raw.githubusercontent.com/SathornModel/Chula-SSS/master/Chula-SSS/LICENSE.txt) |

## Exact source and extraction paths

The following are upstream download URLs, not files downloaded into this repository:

| Target | Regional PBF URL | Proposed extraction path |
| --- | --- | --- |
| Hanoi | [vietnam-latest.osm.pbf](https://download.geofabrik.de/asia/vietnam-latest.osm.pbf) | Vietnam PBF → explicit Hanoi district/corridor boundary with connecting approaches → city clip → SUMO network import → geometry/turn/signal audit → demand and fleet construction. |
| Jakarta | [java-latest.osm.pbf](https://download.geofabrik.de/asia/indonesia/java-latest.osm.pbf) | Java PBF → central Jakarta boundary, preferably a bounded connected Menteng/Senen subnetwork → city clip → import configured for local driving side → audit → demand/fleet construction. |
| Bangkok fallback | [thailand-latest.osm.pbf](https://download.geofabrik.de/asia/thailand-latest.osm.pbf) | Thailand PBF → Sathorn corridor boundary → city clip → import configured for local driving side → audit → demand/fleet construction. |

Geofabrik lists regional extracts, not calibrated demand or SUMO-ready signals. Its pages checked above contained OSM data through 2026-11-16; `latest` is mutable, so archive a dated input and checksum when implementation begins. Boundary choice, lane counts, turn permissions and signal programs remain to be surveyed. OSM licensing is documented by the [OSM Foundation](https://www.openstreetmap.org/copyright).

The extraction sequence is a proposed workflow, not a claim that these city clips already exist. Use the official [SUMO OSM import documentation](https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html) when implementing import, and the [SUMO sublane model documentation](https://sumo.dlr.de/docs/Simulation/SublaneModel.html) for the separate lateral-behavior configuration work. No numeric motorcycle share should be inferred from OSM, vehicle registrations, or the name of a city.

## Bangkok artifact details and acceptance gates

Verified model directories:

- [Morning scenario](https://github.com/SathornModel/Chula-SSS/tree/master/models/sathorn-morning-caswakul_sumoconf2018)
- [Evening scenario](https://github.com/SathornModel/Chula-SSS/tree/master/models/sathorn-evening-caswakul_sumoconf2018)

Each contains `sathorn_w_fixed_20160404.net.xml`, `sathorn_w_20160422.rou.xml`, `sathorn_w.sumo.cfg`, `sathon_wide_tls_20160418_edited.add.xml`, and `sathorn_wide_run.bat`. The configuration references the network/routes, while the batch launcher separately supplies the signal additions. Preserve that distinction when importing. [AM configuration](https://raw.githubusercontent.com/SathornModel/Chula-SSS/master/models/sathorn-morning-caswakul_sumoconf2018/sathorn_w.sumo.cfg), [AM launcher](https://raw.githubusercontent.com/SathornModel/Chula-SSS/master/models/sathorn-morning-caswakul_sumoconf2018/sathorn_wide_run.bat)

The AM config spans 21,600–32,400 seconds; the PM config spans 53,100–69,300 seconds. Use the actual config boundaries rather than assuming the paper's rounded rush-hour descriptions. [PM configuration](https://raw.githubusercontent.com/SathornModel/Chula-SSS/master/models/sathorn-evening-caswakul_sumoconf2018/sathorn_w.sumo.cfg)

Before adoption: clarify redistribution rights; pin the upstream revision; check legacy flags against the installed SUMO version; run deterministic baseline smoke checks and inspect warnings, collisions, teleports, insertion delay, signal conflicts and blocked junctions; then independently add and validate motorcycle demand/behavior. The historical launcher includes permissive junction settings and randomization, so copying it verbatim is not evidence of a safe or reproducible RL benchmark. [Launch settings](https://raw.githubusercontent.com/SathornModel/Chula-SSS/master/models/sathorn-morning-caswakul_sumoconf2018/sathorn_wide_run.bat)

## Motorcycle evidence and modeling requirements

A [World Bank Hanoi project evaluation](https://documents.worldbank.org/curated/en/917761525040838911/pdf/Vietnam-VN-HANOI-URBAN-TRANSPORT.pdf) reports that motorcycles made up 50–75% of weekday traffic counted along RR2 in October 2017. This is historical corridor evidence, not a current citywide demand estimate. [BPS Jakarta's 2024 registration table](https://jakarta.bps.go.id/en/statistics-table/2/Nzg2IzI%3D/jumlah-kendaraan-) lists 9,167,512 motorcycles among 12,057,335 registered vehicles. Those are fleet registrations, not junction flow or trip shares. Both support candidate relevance; neither supplies complete current turning demand for the proposed benchmark.

Current official documentation was checked using Context7 (`/eclipse-sumo/sumo`) and the upstream SUMO pages. [OSM import](https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html) supports building networks from map extracts, with local driving-side configuration and subsequent audits of inferred connections and signals. The [OSM Web Wizard](https://sumo.dlr.de/docs/Tutorials/OSMWebWizard.html) can generate randomized multimodal demand; that does not establish field calibration. SUMO's [sublane model](https://sumo.dlr.de/docs/Simulation/SublaneModel.html) supports two-wheelers riding side by side and lateral movement. Dimensions, lateral gaps, lane permissions and fleet mix need explicit settings and validation; fine lateral resolution raises simulation cost.

For this repo, first distinguish a controlled synthetic motorcycle-heavy workload on real geometry from a field-calibrated city workload. Keep per-class delay, tail wait and completed/unfinished counts. The current corrected runtime generates only one car type; using one of these maps requires demand/model changes as well as the already identified topology adaptation.

## Search limits

The [official SUMO scenario catalog](https://sumo.dlr.de/docs/Data/Scenarios.html), checked with its 2026-10-25 edit date, does not list Hanoi, Jakarta or Bangkok. That is a catalog observation, not proof no scenario exists. Research papers and public repositories were searched; file bundles behind author contact, private institutional systems, or unindexed repositories remain possible. No simulation, calibration, artifact hash validation, training, or code tests were performed for this research-only note.
