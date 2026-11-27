#!/bin/bash
# Test-seed benchmark: every deterministic controller plain and inside the max-red envelope, then the learned policies
# (it00b-config baseline, round-3 configuration C on learner seeds 17/29/41). Usage: run.sh det|det-plain|learned
# Finished cases are cached by identity, so a rerun only runs missing seeds (det-plain tops up the plain set).
set -u
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" && source .venv/bin/activate
export PYTHONPATH=$PWD TMPDIR=$PWD/artifacts/tmp EDGEFLOW_LIBSUMO=1 EDGEFLOW_SUMO_SLOTS=16 BENCH_WORKERS=${BENCH_WORKERS:-3}
S=docs/engineering/reports/test_benchmark_20261126/scripts/bench.py
L=artifacts/benchmarks/test-benchmark-20261126/logs; mkdir -p $L; git rev-parse HEAD > $L/commit-$1
MAPS="cologne8_benchmark_v1 grid4x4_benchmark_v1 hcm_neighborhood_v3_benchmark_v1 jakarta_menteng_v1 hanoi_dong_da_v1 four_intersection_rl_v1"
if [ "$1" != learned ]; then
  for m in $MAPS; do python $S det $m >> $L/det-$m.log 2>&1 & done; wait
  [ "$1" = det-plain ] || for m in $MAPS; do EDGEFLOW_MAX_RED=40 EDGEFLOW_MAX_RED_EXTERNAL=1 BENCH_GROUP=det-maxred python $S det $m > $L/det-maxred-$m.log 2>&1 & done; wait
else
  # One line per learned policy group: GROUP ITER:SEED [MAPS]. it00b's original policies where they exist, the
  # bench-it00b retrain where its checkpoints were deleted; bench-* = new learner seeds 1604/2026 trained for this report.
  # 4 at a time with 2 workers each: a learned-policy worker holds ~1.2 GB (torch).
  cat <<'LIST' | xargs -P 4 -L 1 bash -c 'BENCH_GROUP=$0 BENCH_WORKERS=2 python '$S' "$@" > '$L'/learned-$0.log 2>&1'
it32-17 it32:17
it37-29 it37:29
it44-41 it44:41
c-1604 bench-c-1604:1604
c-2026 bench-c-2026:2026
it00b-17 it00b:17 cologne8_benchmark_v1 grid4x4_benchmark_v1 hcm_neighborhood_v3_benchmark_v1
it00b-17 bench-it00b:17 jakarta_menteng_v1 hanoi_dong_da_v1 four_intersection_rl_v1
base-1604 bench-it00b-1604:1604
base-2026 bench-it00b-2026:2026
LIST
fi
echo "$1 done $(date)"
