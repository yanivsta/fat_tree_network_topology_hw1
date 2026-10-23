"""Structural host-to-host metrics for fat-tree experiments."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx


@dataclass(frozen=True)
class HostPairMetrics:
    """Connectivity and distance metrics over every unordered host pair."""

    total_host_pairs: int
    reachable_host_pairs: int
    reachability_percentage: float
    average_reachable_path_length: float | None
    host_pair_efficiency: float
    normalized_efficiency_percentage: float | None


def host_nodes(graph: nx.Graph) -> tuple[str, ...]:
    """Return host node identifiers in deterministic order."""
    return tuple(sorted(node for node, data in graph.nodes(data=True) if data.get("role") == "host"))


def calculate_host_pair_metrics(
    graph: nx.Graph,
    baseline_efficiency: float | None = None,
) -> HostPairMetrics:
    """Measure reachability, path length, and efficiency among all host pairs.

    A reachable pair at distance ``d`` contributes ``1 / d`` to efficiency;
    a disconnected pair contributes zero. When ``baseline_efficiency`` is
    supplied, efficiency is also reported as a percentage of that baseline.
    """
    hosts = host_nodes(graph)
    if len(hosts) < 2:
        raise ValueError("host-pair metrics require at least two hosts")
    if baseline_efficiency is not None and baseline_efficiency <= 0:
        raise ValueError("baseline efficiency must be greater than zero")

    total_host_pairs = len(hosts) * (len(hosts) - 1) // 2
    reachable_host_pairs = 0
    path_length_sum = 0
    reciprocal_distance_sum = 0.0

    for index, source in enumerate(hosts):
        path_lengths = nx.single_source_shortest_path_length(graph, source)
        for destination in hosts[index + 1 :]:
            distance = path_lengths.get(destination)
            if distance is None:
                continue
            reachable_host_pairs += 1
            path_length_sum += distance
            reciprocal_distance_sum += 1 / distance

    reachability_percentage = 100 * reachable_host_pairs / total_host_pairs
    average_reachable_path_length = (
        path_length_sum / reachable_host_pairs if reachable_host_pairs else None
    )
    host_pair_efficiency = reciprocal_distance_sum / total_host_pairs
    normalized_efficiency_percentage = (
        100 * host_pair_efficiency / baseline_efficiency
        if baseline_efficiency is not None
        else None
    )
    return HostPairMetrics(
        total_host_pairs=total_host_pairs,
        reachable_host_pairs=reachable_host_pairs,
        reachability_percentage=reachability_percentage,
        average_reachable_path_length=average_reachable_path_length,
        host_pair_efficiency=host_pair_efficiency,
        normalized_efficiency_percentage=normalized_efficiency_percentage,
    )
