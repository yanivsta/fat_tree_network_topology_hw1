"""Run reproducible fat-tree robustness experiments and create result plots."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from pathlib import Path
import statistics
from typing import Sequence

from analysis import calculate_host_pair_metrics
from fat_tree import (
    FAILURE_SCOPES,
    build_fat_tree,
    inject_link_failures,
    validate_failure_rate,
    validate_failure_scope,
    validate_fat_tree,
    validate_k,
)


DEFAULT_K_VALUES = (4, 6, 8)
DEFAULT_FAILURE_RATES = tuple(range(0, 51, 5))
DEFAULT_TRIALS = 30
DEFAULT_SEED_START = 0
DEFAULT_FAILURE_SCOPE = "fabric"
CSV_FILENAME = "robustness_metrics.csv"
REACHABILITY_PLOT_FILENAME = "reachability_vs_failure_rate.png"
EFFICIENCY_PLOT_FILENAME = "efficiency_vs_failure_rate.png"


@dataclass(frozen=True)
class ExperimentRow:
    """One deterministic trial in the robustness experiment."""

    k: int
    requested_failure_rate: float
    realized_failure_rate: float
    failure_scope: str
    trial: int
    seed: int
    eligible_links: int
    removed_links: int
    total_host_pairs: int
    reachable_host_pairs: int
    reachability_percentage: float
    average_reachable_path_length: float | None
    host_pair_efficiency: float
    normalized_efficiency_percentage: float


def validate_experiment_inputs(
    k_values: Sequence[int],
    failure_rates: Sequence[float],
    trials: int,
    failure_scope: str,
) -> None:
    """Raise ``ValueError`` when experiment settings are invalid."""
    if not k_values:
        raise ValueError("at least one k value is required")
    if not failure_rates:
        raise ValueError("at least one failure rate is required")
    for k in k_values:
        validate_k(k)
    for failure_rate in failure_rates:
        validate_failure_rate(failure_rate)
    if isinstance(trials, bool) or not isinstance(trials, int) or trials < 1:
        raise ValueError("trials must be an integer greater than or equal to 1")
    validate_failure_scope(failure_scope)


def run_experiment(
    k_values: Sequence[int] = DEFAULT_K_VALUES,
    failure_rates: Sequence[float] = DEFAULT_FAILURE_RATES,
    trials: int = DEFAULT_TRIALS,
    seed_start: int = DEFAULT_SEED_START,
    failure_scope: str = DEFAULT_FAILURE_SCOPE,
    output_dir: Path | str = Path("results"),
) -> list[ExperimentRow]:
    """Run all trials, write CSV and plots, and return deterministic rows."""
    validate_experiment_inputs(k_values, failure_rates, trials, failure_scope)
    if isinstance(seed_start, bool) or not isinstance(seed_start, int):
        raise ValueError("seed start must be an integer")

    rows: list[ExperimentRow] = []
    for k in k_values:
        intact_graph = build_fat_tree(k)
        validate_fat_tree(intact_graph, k)
        baseline = calculate_host_pair_metrics(intact_graph).host_pair_efficiency

        for failure_rate in failure_rates:
            for trial_index in range(trials):
                seed = seed_start + trial_index
                failure_result = inject_link_failures(
                    intact_graph,
                    failure_rate=failure_rate,
                    scope=failure_scope,
                    seed=seed,
                )
                metrics = calculate_host_pair_metrics(
                    failure_result.graph,
                    baseline_efficiency=baseline,
                )
                if metrics.normalized_efficiency_percentage is None:
                    raise RuntimeError("normalized efficiency was not calculated")
                rows.append(
                    ExperimentRow(
                        k=k,
                        requested_failure_rate=float(failure_rate),
                        realized_failure_rate=failure_result.realized_rate,
                        failure_scope=failure_scope,
                        trial=trial_index + 1,
                        seed=seed,
                        eligible_links=len(failure_result.eligible_links),
                        removed_links=len(failure_result.removed_links),
                        total_host_pairs=metrics.total_host_pairs,
                        reachable_host_pairs=metrics.reachable_host_pairs,
                        reachability_percentage=metrics.reachability_percentage,
                        average_reachable_path_length=metrics.average_reachable_path_length,
                        host_pair_efficiency=metrics.host_pair_efficiency,
                        normalized_efficiency_percentage=metrics.normalized_efficiency_percentage,
                    )
                )

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    write_results_csv(rows, destination / CSV_FILENAME)
    plot_experiment_results(rows, destination)
    return rows


def write_results_csv(rows: Sequence[ExperimentRow], path: Path) -> None:
    """Write trial-level results with a stable schema and ordering."""
    if not rows:
        raise ValueError("cannot write an empty experiment")
    fieldnames = list(asdict(rows[0]))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _series_summary(
    rows: Sequence[ExperimentRow],
    k: int,
    failure_rates: Sequence[float],
    metric_name: str,
) -> tuple[list[float], list[float]]:
    means: list[float] = []
    deviations: list[float] = []
    for failure_rate in failure_rates:
        values = [
            float(getattr(row, metric_name))
            for row in rows
            if row.k == k and row.requested_failure_rate == failure_rate
        ]
        if not values:
            raise ValueError(f"missing results for k={k}, failure rate={failure_rate:g}")
        means.append(statistics.mean(values))
        deviations.append(statistics.stdev(values) if len(values) > 1 else 0.0)
    return means, deviations


def _plot_metric(
    rows: Sequence[ExperimentRow],
    output_path: Path,
    metric_name: str,
    title: str,
    y_label: str,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    k_values = tuple(dict.fromkeys(row.k for row in rows))
    failure_rates = tuple(dict.fromkeys(row.requested_failure_rate for row in rows))
    figure, axis = plt.subplots(figsize=(8.5, 5.5))

    for k in k_values:
        means, deviations = _series_summary(rows, k, failure_rates, metric_name)
        lower = [max(0.0, mean - deviation) for mean, deviation in zip(means, deviations)]
        upper = [min(100.0, mean + deviation) for mean, deviation in zip(means, deviations)]
        (line,) = axis.plot(failure_rates, means, marker="o", linewidth=2, label=f"k = {k}")
        axis.fill_between(failure_rates, lower, upper, color=line.get_color(), alpha=0.16)

    axis.set_title(title)
    axis.set_xlabel("Failed fabric links (%)")
    axis.set_ylabel(y_label)
    minimum_rate = min(failure_rates)
    maximum_rate = max(failure_rates)
    if minimum_rate == maximum_rate:
        axis.set_xlim(minimum_rate - 1, maximum_rate + 1)
    else:
        axis.set_xlim(minimum_rate, maximum_rate)
    axis.set_ylim(0, 102)
    axis.grid(True, alpha=0.3)
    axis.legend(title="Switch ports")
    figure.tight_layout()
    figure.savefig(output_path, dpi=200)
    plt.close(figure)


def plot_experiment_results(rows: Sequence[ExperimentRow], output_dir: Path) -> None:
    """Create reachability and normalized-efficiency plots."""
    _plot_metric(
        rows,
        output_dir / REACHABILITY_PLOT_FILENAME,
        metric_name="reachability_percentage",
        title="Fat-Tree Reachability Under Random Fabric-Link Failures",
        y_label="Reachable host pairs (%)",
    )
    _plot_metric(
        rows,
        output_dir / EFFICIENCY_PLOT_FILENAME,
        metric_name="normalized_efficiency_percentage",
        title="Fat-Tree Communication Efficiency Under Random Fabric-Link Failures",
        y_label="Normalized host-pair efficiency (%)",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the experiment command-line parser."""
    parser = argparse.ArgumentParser(
        description="Measure fat-tree robustness under random link failures."
    )
    parser.add_argument("--k-values", nargs="+", type=int, default=list(DEFAULT_K_VALUES))
    parser.add_argument(
        "--failure-rates",
        nargs="+",
        type=float,
        default=list(DEFAULT_FAILURE_RATES),
        metavar="PERCENT",
    )
    parser.add_argument("--trials", type=int, default=DEFAULT_TRIALS)
    parser.add_argument("--seed-start", type=int, default=DEFAULT_SEED_START)
    parser.add_argument(
        "--failure-scope",
        choices=sorted(FAILURE_SCOPES),
        default=DEFAULT_FAILURE_SCOPE,
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        rows = run_experiment(
            k_values=args.k_values,
            failure_rates=args.failure_rates,
            trials=args.trials,
            seed_start=args.seed_start,
            failure_scope=args.failure_scope,
            output_dir=args.output_dir,
        )
    except ValueError as error:
        parser.error(str(error))

    print(f"Completed {len(rows)} trials.")
    print(f"CSV: {args.output_dir / CSV_FILENAME}")
    print(f"Reachability plot: {args.output_dir / REACHABILITY_PLOT_FILENAME}")
    print(f"Efficiency plot: {args.output_dir / EFFICIENCY_PLOT_FILENAME}")


if __name__ == "__main__":
    main()
