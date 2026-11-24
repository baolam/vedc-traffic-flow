#!/usr/bin/env bash
# One research-loop iteration: train phase DQN on the screening panel under the loop recipe, ~45 min wall (WALL=seconds overrides the 2400 s cap).
# Usage: run.sh <iter-id> [MAP ...]   (hypothesis gates come from the caller's environment, e.g. EDGEFLOW_X=1 run.sh it03)
set -euo pipefail
REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
IT=${1:?iteration id}; shift
MAPS=${*:-cologne8_benchmark_v1 grid4x4_benchmark_v1 hcm_neighborhood_v3_benchmark_v1 jakarta_menteng_v1 hanoi_dong_da_v1 four_intersection_rl_v1}
BASE=$REPO/artifacts/benchmarks/unified-v1
ROOT=$REPO/artifacts/benchmarks/rl-loop/$IT
mkdir -p "$ROOT"
for f in prepared.json workloads.json references inputs; do ln -sfn "$BASE/$f" "$ROOT/$f"; done
# Baseline = E6 (per-node reward + tail); the loop never runs without it.
export TMPDIR=$REPO/artifacts/tmp  # user rule: nothing outside the repo (SUMO slot/coordinator locks use tempfile)
mkdir -p "$TMPDIR"
export EDGEFLOW_DQN_NODE_REWARD=${EDGEFLOW_DQN_NODE_REWARD:-1} EDGEFLOW_TAIL=${EDGEFLOW_TAIL:-0.05,60} EDGEFLOW_LIBSUMO=1
env | grep '^EDGEFLOW_' | sort > "$ROOT/gates.env"
git -C "$REPO" rev-parse HEAD > "$ROOT/commit"
git -C "$REPO" diff HEAD > "$ROOT/uncommitted.patch"
source "$REPO/.venv/bin/activate"
# LOOP_RECIPE_EXTRA (JSON) merges into the loop recipe, e.g. '{"lr": 1e-4}' (recorded in recipe.json and the run identity).
RECIPE=$(python3 -c 'import json,sys; print(json.dumps({**json.loads(sys.argv[1]), **json.loads(sys.argv[2])}))' \
  '{"version": "loop_dqn_recipe_v2", "min_episodes": 80, "min_sim_s": 0, "validate_every_episodes": 20, "patience": 8}' "${LOOP_RECIPE_EXTRA:-{\}}")
echo "$RECIPE" > "$ROOT/recipe.json"
# Loop recipe v2: validate from ep 80 every 20 (keeps the early DQN peak), stop after 8 stale checks (v1 = ep 80 / patience 4 stopped still-improving maps at ~160 eps, 7-25 min).
exec python -m src.benchmark.unified_campaign --stage train --prepared "$ROOT/prepared.json" --root "$ROOT" \
  --maps $MAPS --algorithms phase_dqn_unified --seeds ${SEED:-17} --device cpu --jobs 6 --wall-limit-s ${WALL:-2400} \
  --recipe "$RECIPE"
