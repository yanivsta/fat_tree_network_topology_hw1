"""Tests for the Phase 1 canonical fat-tree generator."""

import unittest
from pathlib import Path
import subprocess
import sys

import networkx as nx

from fat_tree import (
    build_fat_tree,
    draw_fat_tree,
    expected_counts,
    inject_link_failures,
    validate_failure_rate,
    validate_failure_scope,
    validate_fat_tree,
    validate_k,
)


class FatTreeTests(unittest.TestCase):
    def test_reference_sizes_and_validation(self) -> None:
        expected = {4: (16, 20, 48), 6: (54, 45, 162), 8: (128, 80, 384)}
        for k, (hosts, switches, links) in expected.items():
            with self.subTest(k=k):
                graph = build_fat_tree(k)
                counts = expected_counts(k)
                self.assertEqual(counts["hosts"], hosts)
                self.assertEqual(counts["switches"], switches)
                self.assertEqual(graph.number_of_edges(), links)
                self.assertEqual(graph.number_of_nodes(), hosts + switches)
                validate_fat_tree(graph, k)

    def test_roles_degrees_and_connectivity(self) -> None:
        k = 4
        graph = build_fat_tree(k)
        self.assertTrue(nx.is_connected(graph))
        for node, data in graph.nodes(data=True):
            expected_degree = 1 if data["role"] == "host" else k
            self.assertEqual(graph.degree[node], expected_degree)
        self.assertEqual(graph.nodes["host:p0:e0:h0"]["role"], "host")
        self.assertEqual(graph.nodes["edge:p0:e0"]["pod"], 0)
        self.assertEqual(graph.nodes["agg:p0:a0"]["index"], 0)
        self.assertEqual(graph.nodes["core:g0:c0"]["group"], 0)

    def test_exact_core_wiring(self) -> None:
        graph = build_fat_tree(4)
        self.assertEqual(
            set(graph.neighbors("agg:p2:a1")),
            {"edge:p2:e0", "edge:p2:e1", "core:g1:c0", "core:g1:c1"},
        )
        self.assertEqual(
            set(graph.neighbors("core:g1:c0")),
            {"agg:p0:a1", "agg:p1:a1", "agg:p2:a1", "agg:p3:a1"},
        )

    def test_invalid_k(self) -> None:
        for value in (0, 1, 3, -2, True, "4"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_k(value)  # type: ignore[arg-type]

    def test_validator_detects_broken_link(self) -> None:
        graph = build_fat_tree(4)
        graph.remove_edge("agg:p0:a0", "core:g0:c0")
        with self.assertRaises(ValueError):
            validate_fat_tree(graph, 4)

    def test_validator_detects_cross_pod_host_swap(self) -> None:
        graph = build_fat_tree(4)
        first_host = "host:p0:e0:h0"
        second_host = "host:p1:e0:h0"
        first_edge = "edge:p0:e0"
        second_edge = "edge:p1:e0"
        graph.remove_edges_from(((first_host, first_edge), (second_host, second_edge)))
        graph.add_edge(first_host, second_edge, layer="host-edge")
        graph.add_edge(second_host, first_edge, layer="host-edge")

        with self.assertRaises(ValueError):
            validate_fat_tree(graph, 4)

    def test_drawing_rejects_large_topologies(self) -> None:
        with self.assertRaisesRegex(ValueError, "limited to k <= 4"):
            draw_fat_tree(build_fat_tree(6))

    def test_zero_and_full_failure_rates(self) -> None:
        graph = build_fat_tree(4)
        no_failures = inject_link_failures(graph, 0, seed=4)
        all_failures = inject_link_failures(graph, 100, seed=4)
        self.assertEqual(no_failures.graph.number_of_edges(), graph.number_of_edges())
        self.assertEqual(len(no_failures.removed_links), 0)
        self.assertEqual(all_failures.graph.number_of_edges(), 0)
        self.assertEqual(len(all_failures.removed_links), graph.number_of_edges())

    def test_failure_count_scope_and_original_graph(self) -> None:
        graph = build_fat_tree(4)
        result = inject_link_failures(graph, 5, scope="fabric", seed=19)
        # There are 32 fabric links for k=4, so 5% rounds to two links.
        self.assertEqual(len(result.eligible_links), 32)
        self.assertEqual(len(result.removed_links), 2)
        self.assertEqual(graph.number_of_edges(), 48)
        self.assertEqual(result.graph.number_of_edges(), 46)
        for left, right in result.removed_links:
            self.assertIn(graph.edges[left, right]["layer"], {"edge-aggregation", "aggregation-core"})

    def test_seed_reproduces_the_same_link_set(self) -> None:
        graph = build_fat_tree(4)
        first = inject_link_failures(graph, 25, scope="all", seed=23)
        second = inject_link_failures(graph, 25, scope="all", seed=23)
        self.assertEqual(first.removed_links, second.removed_links)
        self.assertEqual(first.removed_by_layer, second.removed_by_layer)

    def test_invalid_failure_inputs(self) -> None:
        for value in (-0.1, 100.1, float("nan"), float("inf"), True, "10"):
            with self.subTest(rate=value):
                with self.assertRaises(ValueError):
                    validate_failure_rate(value)  # type: ignore[arg-type]
        for scope in ("hosts", "core", "", None):
            with self.subTest(scope=scope):
                with self.assertRaises(ValueError):
                    validate_failure_scope(scope)  # type: ignore[arg-type]

    def test_cli_failure_summary(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                "main.py",
                "--k",
                "4",
                "--failure-rate",
                "25",
                "--failure-scope",
                "fabric",
                "--seed",
                "7",
            ],
            cwd=project_root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Failure simulation:", completed.stdout)
        self.assertIn("Scope: fabric", completed.stdout)
        self.assertIn("Seed: 7", completed.stdout)
        self.assertIn("Eligible links: 32", completed.stdout)
        self.assertIn("Removed links: 8", completed.stdout)


if __name__ == "__main__":
    unittest.main()
