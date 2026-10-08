"""Choose a fair-cycle reward weight using validation constraints only."""
import argparse
import json
from pathlib import Path

from src.rl.campaign import (Campaign, fixed_candidates, validation_summary_violation,
                             validation_violation)
from src.rl.benchmark import score
from src.simulation.runtime import file_hash


def select(config_path, pilot_root, output):
    config = json.loads(Path(config_path).read_text())
    campaign = Campaign(config, Path(output) / "baselines", max_seconds=7200)
    candidates = fixed_candidates()
    fixed_scores = {name: score(campaign.evaluate(name, spec, "train", (20000, 20001, 20002)))
                    for name, spec in candidates.items()}
    fixed_controller = candidates[min(fixed_scores, key=fixed_scores.get)]
    baselines = {"actuated": campaign.evaluate("actuated", {"type": "actuated"}, "validation"),
                 "fixed_time": campaign.evaluate("fixed-time", fixed_controller, "validation")}
    results = {}
    for label in ("lambda-0", "lambda-0_5", "lambda-2"):
        training_path = Path(pilot_root) / label / "seed-11" / "training.json"
        training = json.loads(training_path.read_text())
        checkpoints = training.get("validation", [])
        if not checkpoints or any("scenario_metrics" not in row for row in checkpoints):
            raise ValueError(f"Pilot {label} has no complete versioned validation metrics")
        checkpoint = min(checkpoints, key=lambda row: (
            validation_summary_violation(row["scenario_metrics"], baselines), row["score"]))
        model = checkpoint["model_path"]
        if file_hash(model) != checkpoint["sha256"]:
            raise ValueError(f"Pilot model changed: {model}")
        controller = {"type": "fair_cycle_rl", "model_path": model}
        rows = campaign.evaluate(label, controller, "validation")
        violation = validation_violation(rows, baselines)
        results[label] = {"model_path": model, "model_sha256": file_hash(model),
                          "validation_score": score(rows), "validation_violation": violation,
                          "selected_episode": checkpoint["episodes"]}
    selected = min(results, key=lambda name: (results[name]["validation_violation"],
                                              results[name]["validation_score"]))
    result = {"selection_split": "validation", "selected": selected,
              "selected_lambda": {"lambda-0": 0., "lambda-0_5": .5, "lambda-2": 2.}[selected],
              "fixed_controller": fixed_controller, "fixed_training_scores": fixed_scores,
              "baselines": {"actuated": baselines["actuated"], "fixed_time": baselines["fixed_time"]},
              "candidates": results}
    Path(output).mkdir(parents=True, exist_ok=True)
    (Path(output) / "selection.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--pilot-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(select(args.config, args.pilot_root, args.output), indent=2))


if __name__ == "__main__":
    main()
