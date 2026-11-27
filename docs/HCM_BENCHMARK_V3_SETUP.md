# HCM v3 junction repair

The v3 benchmark is merged into the repository root. Imported files in `networks/hcm_neighborhood_benchmark_v2/` are immutable repair inputs. Generated candidates are retained under `artifacts/hcm-qualification-v3/repair/revisions/`; the accepted engineering candidate is published separately in `networks/hcm_neighborhood_benchmark_v3/`. Publication alone does not qualify or promote the benchmark.

Run from the repository root with matching SUMO, TraCI, sumolib and netconvert versions. The recorded environment uses version 1.25.0 and Python 3.13.12. No additional dependencies were installed.

```powershell
python -m src.simulation.qualify_hcm --stage repair --resume
python scripts/render_hcm_repair_diagrams.py
python -m src.simulation.qualify_hcm --stage all --resume
python -m src.simulation.qualify_hcm --stage report
```

`--stage repair` reproduces the six v2 diagnostic cases with full FCD histories, rebuilds local connections and conflict rules in the specified hotspot order, then replays all 40 historical cases and tests red-signal bus queues in both directions between J14 and J17. These runs establish engineering regressions, not independent qualification. Failed revisions and invalidated results remain inspectable. Node boundaries, connection shapes and waiting positions are supported netconvert inputs in `configs/hcm_repair_v3.json`; generated conflict bitstrings are never edited.

The builder checks unchanged controller identities, external movement identities, lane connectivity, lane counts, permissions, road speeds, signal programs and unrelated network elements. Signal construction retains protected `G`, permissive `g`, stage order, three-second yellow and two-second all-red. Internal links and junction collision checking remain enabled. The four-intersection fixture and controller interfaces are outside this repair.

Independent evaluation requires a frozen repair with 40 passing engineering regressions and a passing adjacent-signal bus probe. Calibration uses 73001–73002, qualification uses 74001–74005, and all v2 acceptance thresholds remain unchanged. Loads and stress targets are derived from the v3 network. Do not change the repair in response to those independent seeds.

The original campaign and the merged benchmark share a 7,200-second simulation budget. `campaign.json` carries the prior run charge, a conservative charge for earlier unmetered diagnostics, and every new worker attempt, including errors and timeouts. One worker runs at a time with a maximum 300-second case timeout. The builder reserves the unspent portion of approximately 1,800 seconds for final verification. Do not delete the ledger or create a new output directory to reset the budget. Budget exhaustion leaves the result **incomplete**.

Cache identity includes the repaired network, repair inputs, construction XML, controller programs, topology, protocol, builder and simulator code, demand and matching SUMO environment. Imported v2 simulation results are never accepted as v3 results. The merge changes the implementation fingerprint and absolute runtime paths, so earlier simulation caches require revalidation. Existing results remain historical evidence and qualification remains **incomplete**. The merge does not reset the ledger or run new simulations.

The archived regression specs, their demand inputs, and six collision references are tracked under `networks/hcm_neighborhood_benchmark_v3/repair-reference/v2-qualification/` (about 5.4 MiB). Their SHA-256 manifest is checked while loading them. The reviewed build manifest is beside the published network. The full historical traces remain in the local qualification archive; historical paths there record their original workspace provenance.

The campaign ledger and budget origin are committed checkpoints. Simulation stages require that ledger and stop before changing outputs when the budget is missing or exhausted. Keep the ledger when moving the checkout; never start with a fresh output directory to reset its charge. SUMO integration checks skip before preparing results when the required matching environment or remaining budget is unavailable.

Verification commands:

```powershell
make contracts
make test
```

GNU make was unavailable in the recorded Windows environment. Its exact pytest equivalents are:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest tests/unit/test_contracts.py
python -m pytest tests/unit
python -m pytest tests/integration/test_hcm_sumo_qualification.py tests/integration/test_hcm_adjacent_signal_repair.py
```

The last command starts real simulation processes only when the ledger has enough remaining budget. Unit tests rebuild the existing four-intersection fixture; restore its exact bytes from Git afterward. Historical preservation evidence in `preservation-before.json` and `preservation-after.json` describes the pre-merge workspace layout.

Review the [repair report](../artifacts/hcm-qualification-v3/repair/report.md), [qualification report](../artifacts/hcm-qualification-v3/report.md), [repair status](../artifacts/hcm-qualification-v3/repair/status.json), and each revision's manifest before use. Geometric corrections address simulation failures. Field accuracy remains unverified; signal relocation, controller consolidation, learning and field calibration are outside scope.
