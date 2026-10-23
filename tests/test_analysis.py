"""Tests for host-pair metrics and the robustness experiment."""

import csv
from pathlib import Path
import tempfile
import unittest

from analysis import calculate_host_pair_metrics
from experiment import (
    CSV_FILENAME,
    EFFICIENCY_PLOT_FILENAME,
    REACHABILITY_PLOT_FILENAME,
    _failure_scope_plot_text,
    run_experiment,
    validate_experiment_inputs,
)
from fat_tree import build_fat_tree, inject_link_failures


class HostPairMetricTests(unittest.TestCase):
    def test_intact_k4_metrics(self) -> None:
        graph = build_fat_tree(4)
        baseline = calculate_host_pair_metrics(graph)
        metrics = calculate_host_pair_metrics(
            graph,
            baseline_efficiency=baseline.host_pair_efficiency,
        )

        self.assertEqual(metrics.total_host_pairs, 120)
        self.assertEqual(metrics.reachable_host_pairs, 120)
        self.assertEqual(metrics.reachability_percentage, 100)
        self.assertAlmostEqual(metrics.average_reachable_path_length, 656 / 120)
        self.assertAlmostEqual(metrics.host_pair_efficiency, 0.2)
        self.assertAlmostEqual(metrics.normalized_efficiency_percentage, 100)

    def test_disconnected_pairs_contribute_zero_efficiency(self) -> None:
        graph = build_fat_tree(4)
        baseline = calculate_host_pair_metrics(graph).host_pair_efficiency
        damaged = inject_link_failures(graph, 100, scope="fabric", seed=0).graph
        metrics = calculate_host_pair_metrics(damaged, baseline_efficiency=baseline)

        self.assertEqual(metrics.total_host_pairs, 120)
        self.assertEqual(metrics.reachable_host_pairs, 8)
        self.assertAlmostEqual(metrics.reachability_percentage, 100 * 8 / 120)
        self.assertEqual(metrics.average_reachable_path_length, 2)
        self.assertAlmostEqual(metrics.host_pair_efficiency, 1 / 30)
        self.assertAlmostEqual(metrics.normalized_efficiency_percentage, 100 / 6)

    def test_baseline_efficiency_must_be_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "baseline efficiency"):
            calculate_host_pair_metrics(build_fat_tree(4), baseline_efficiency=0)


class ExperimentTests(unittest.TestCase):
    def test_plot_text_matches_failure_scope(self) -> None:
        self.assertEqual(
            _failure_scope_plot_text("fabric"),
            ("Random Fabric-Link Failures", "Requested failed fabric links (%)"),
        )
        self.assertEqual(
            _failure_scope_plot_text("all"),
            ("Random Failures Across All Links", "Requested failed links (%)"),
        )

    def test_small_run_is_reproducible_and_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as first_directory, tempfile.TemporaryDirectory() as second_directory:
            first_path = Path(first_directory)
            second_path = Path(second_directory)
            arguments = {
                "k_values": (4,),
                "failure_rates": (0, 50),
                "trials": 2,
                "seed_start": 3,
                "failure_scope": "fabric",
            }

            first_rows = run_experiment(output_dir=first_path, **arguments)
            second_rows = run_experiment(output_dir=second_path, **arguments)

            self.assertEqual(first_rows, second_rows)
            self.assertEqual(len(first_rows), 4)
            self.assertEqual(
                (first_path / CSV_FILENAME).read_bytes(),
                (second_path / CSV_FILENAME).read_bytes(),
            )
            with (first_path / CSV_FILENAME).open(encoding="utf-8", newline="") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 4)
            for filename in (REACHABILITY_PLOT_FILENAME, EFFICIENCY_PLOT_FILENAME):
                self.assertGreater((first_path / filename).stat().st_size, 0)

    def test_invalid_experiment_inputs(self) -> None:
        invalid_cases = (
            ((), (0,), 1, "fabric"),
            ((4,), (), 1, "fabric"),
            ((3,), (0,), 1, "fabric"),
            ((4,), (-1,), 1, "fabric"),
            ((4,), (0,), 0, "fabric"),
            ((4,), (0,), 1, "invalid"),
        )
        for arguments in invalid_cases:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    validate_experiment_inputs(*arguments)


if __name__ == "__main__":
    unittest.main()
