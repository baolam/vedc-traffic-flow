"""Evaluate one frozen MAPPO actor on the versioned validation or holdout split."""

import argparse
import json
from pathlib import Path

from contracts.research import GRAPH_MAPPO_SEED_SPLITS
from src.rl.benchmark import evaluate_policy, score
from src.simulation.runtime import file_hash


def is_frozen_model(selection, model_path, artifact):
    digest = file_hash(model_path)
    return any(spec.get("type") == artifact.get("algorithm")
               and spec.get("sha256") == digest
               for spec in selection.get("selected_models", {}).values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--split", choices=("validation", "holdout"), default="validation")
    parser.add_argument("--selection-manifest")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    model_path = Path(args.model).resolve()
    artifact = json.loads(model_path.read_text(encoding="utf-8"))
    if args.split == "holdout":
        if not args.selection_manifest:
            parser.error("holdout evaluation requires a frozen validation selection manifest")
        selection = json.loads(Path(args.selection_manifest).read_text(encoding="utf-8"))
        if (selection.get("selection_split") != "validation"
                or not is_frozen_model(selection, model_path, artifact)):
            raise ValueError("Holdout model does not match the frozen validation selection")
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=False)
    controller = {"type": artifact["algorithm"], "model_path": str(model_path)}
    rows = evaluate_policy(config, controller, GRAPH_MAPPO_SEED_SPLITS[args.split], root / "cases")
    result = {"split": args.split, "algorithm": artifact["algorithm"],
              "model_path": str(model_path), "model_sha256": file_hash(model_path),
              "score": score(rows), "runs": rows,
              "selection_manifest": args.selection_manifest if args.split == "holdout" else None}
    (root / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"split": args.split, "algorithm": artifact["algorithm"],
                      "score": result["score"], "runs": len(rows), "model_sha256": result["model_sha256"]}))


if __name__ == "__main__":
    main()
