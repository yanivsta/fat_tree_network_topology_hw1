"""Construction and validation of a canonical three-tier k-ary fat-tree.

Node names are deliberately descriptive rather than numeric port identifiers.
For an even port count ``k``, let ``m = k / 2``. Aggregation switch
``agg:p:a`` connects to every core position in core group ``a``. Consequently
core ``core:g:c`` has one neighbour, ``agg:p:g``, in every pod.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import random

import networkx as nx


MAX_DRAW_K = 4
FAILURE_SCOPES = frozenset({"all", "fabric"})
ALL_LINK_LAYERS = frozenset({"host-edge", "edge-aggregation", "aggregation-core"})
FABRIC_LAYERS = frozenset({"edge-aggregation", "aggregation-core"})

Link = tuple[str, str]


@dataclass(frozen=True)
class FailureResult:
    """Result of removing a sampled set of links from a topology copy."""

    graph: nx.Graph
    requested_rate: float
    scope: str
    seed: int | None
    eligible_links: tuple[Link, ...]
    removed_links: tuple[Link, ...]
    removed_by_layer: dict[str, int]

    @property
    def realized_rate(self) -> float:
        """Return the percentage of eligible links that were removed."""
        if not self.eligible_links:
            return 0.0
        return 100 * len(self.removed_links) / len(self.eligible_links)


def validate_k(k: int) -> int:
    """Return *k* when it is a valid fat-tree switch port count.

    A bool is rejected even though Python considers it an ``int``.
    """
    if isinstance(k, bool) or not isinstance(k, int):
        raise ValueError("k must be an even integer greater than or equal to 2")
    if k < 2 or k % 2 != 0:
        raise ValueError("k must be an even integer greater than or equal to 2")
    return k


def expected_counts(k: int) -> dict[str, int]:
    """Return the expected node and link counts for a k-ary fat-tree."""
    k = validate_k(k)
    m = k // 2
    return {
        "pods": k,
        "hosts": k * m * m,
        "edge": k * m,
        "aggregation": k * m,
        "core": m * m,
        "switches": 5 * k * k // 4,
        "links": 3 * k * k * k // 4,
    }


def validate_failure_rate(failure_rate: float) -> float:
    """Return a valid link-failure percentage in the inclusive range 0--100."""
    if isinstance(failure_rate, bool) or not isinstance(failure_rate, (int, float)):
        raise ValueError("failure rate must be a number between 0 and 100")
    rate = float(failure_rate)
    if not math.isfinite(rate) or not 0 <= rate <= 100:
        raise ValueError("failure rate must be a number between 0 and 100")
    return rate


def validate_failure_scope(scope: str) -> str:
    """Return a supported link-failure scope."""
    if scope not in FAILURE_SCOPES:
        allowed = ", ".join(sorted(FAILURE_SCOPES))
        raise ValueError(f"failure scope must be one of: {allowed}")
    return scope


def inject_link_failures(
    graph: nx.Graph,
    failure_rate: float = 0,
    scope: str = "all",
    seed: int | None = None,
) -> FailureResult:
    """Return a copy of *graph* after uniformly sampled link failures.

    ``scope='all'`` includes every link. ``scope='fabric'`` includes only
    edge--aggregation and aggregation--core links. The requested percentage is
    converted to a count with nearest-integer rounding, where a .5 rounds up.
    """
    rate = validate_failure_rate(failure_rate)
    scope = validate_failure_scope(scope)
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ValueError("seed must be an integer or None")

    eligible_layers = ALL_LINK_LAYERS if scope == "all" else FABRIC_LAYERS
    eligible_links = tuple(
        sorted(
            tuple(sorted((left, right)))
            for left, right, data in graph.edges(data=True)
            if data.get("layer") in eligible_layers
        )
    )
    failure_count = math.floor(len(eligible_links) * rate / 100 + 0.5)
    removed_links = tuple(sorted(random.Random(seed).sample(eligible_links, failure_count)))
    removed_by_layer = Counter(graph.edges[left, right]["layer"] for left, right in removed_links)

    damaged_graph = graph.copy()
    damaged_graph.remove_edges_from(removed_links)
    return FailureResult(
        graph=damaged_graph,
        requested_rate=rate,
        scope=scope,
        seed=seed,
        eligible_links=eligible_links,
        removed_links=removed_links,
        removed_by_layer=dict(sorted(removed_by_layer.items())),
    )


def build_fat_tree(k: int) -> nx.Graph:
    """Build and return a deterministic canonical k-ary fat-tree graph.

    Attributes use ``role`` for the node role. Pod-local edge and aggregation
    indices are stored as ``index``; hosts additionally store ``edge_index``
    and ``host_index``. Core switches store ``group`` and ``position``.
    """
    k = validate_k(k)
    m = k // 2
    graph = nx.Graph(k=k, topology="canonical k-ary fat-tree")

    for pod in range(k):
        for edge_index in range(m):
            edge = f"edge:p{pod}:e{edge_index}"
            graph.add_node(edge, role="edge", pod=pod, index=edge_index)
            for host_index in range(m):
                host = f"host:p{pod}:e{edge_index}:h{host_index}"
                graph.add_node(
                    host,
                    role="host",
                    pod=pod,
                    edge_index=edge_index,
                    host_index=host_index,
                )
                graph.add_edge(host, edge, layer="host-edge")

        for aggregation_index in range(m):
            aggregation = f"agg:p{pod}:a{aggregation_index}"
            graph.add_node(
                aggregation, role="aggregation", pod=pod, index=aggregation_index
            )

        # A complete bipartite edge--aggregation layer inside each pod.
        for edge_index in range(m):
            for aggregation_index in range(m):
                graph.add_edge(
                    f"edge:p{pod}:e{edge_index}",
                    f"agg:p{pod}:a{aggregation_index}",
                    layer="edge-aggregation",
                )

    for group in range(m):
        for position in range(m):
            core = f"core:g{group}:c{position}"
            graph.add_node(core, role="core", group=group, position=position)

    # agg:p:a uses all positions in core group a: core:a:c.
    for pod in range(k):
        for aggregation_index in range(m):
            for position in range(m):
                graph.add_edge(
                    f"agg:p{pod}:a{aggregation_index}",
                    f"core:g{aggregation_index}:c{position}",
                    layer="aggregation-core",
                )

    return graph


def validate_fat_tree(graph: nx.Graph, k: int) -> None:
    """Raise ``ValueError`` if *graph* violates canonical fat-tree invariants."""
    k = validate_k(k)
    m = k // 2
    counts = expected_counts(k)
    if graph.number_of_edges() != counts["links"]:
        raise ValueError(f"expected {counts['links']} links, found {graph.number_of_edges()}")

    roles = Counter(data.get("role") for _, data in graph.nodes(data=True))
    count_keys = {"host": "hosts", "edge": "edge", "aggregation": "aggregation", "core": "core"}
    for role, count_key in count_keys.items():
        if roles[role] != counts[count_key]:
            raise ValueError(
                f"expected {counts[count_key]} {role} nodes, found {roles[role]}"
            )
    if sum(roles.values()) != graph.number_of_nodes():
        raise ValueError("every node must have a recognized role")

    if not nx.is_connected(graph):
        raise ValueError("fat-tree graph must be connected")

    for node, data in graph.nodes(data=True):
        role = data["role"]
        neighbours = list(graph.neighbors(node))
        expected_degree = 1 if role == "host" else k
        if len(neighbours) != expected_degree:
            raise ValueError(f"{node} has degree {len(neighbours)}, expected {expected_degree}")

        if role == "host":
            expected_edge = f"edge:p{data.get('pod')}:e{data.get('edge_index')}"
            if set(neighbours) != {expected_edge}:
                raise ValueError(f"{node} must connect to {expected_edge}")
        elif role == "edge":
            pod = data.get("pod")
            index = data.get("index")
            expected_hosts = {
                f"host:p{pod}:e{index}:h{host_index}" for host_index in range(m)
            }
            expected_aggregations = {
                f"agg:p{pod}:a{aggregation_index}" for aggregation_index in range(m)
            }
            if set(neighbours) != expected_hosts | expected_aggregations:
                raise ValueError(f"{node} has invalid edge-layer neighbours")
        elif role == "aggregation":
            pod = data.get("pod")
            index = data.get("index")
            expected_edges = {f"edge:p{pod}:e{edge_index}" for edge_index in range(m)}
            expected_cores = {f"core:g{index}:c{position}" for position in range(m)}
            if set(neighbours) != expected_edges | expected_cores:
                raise ValueError(f"{node} has invalid aggregation-layer neighbours")
        elif role == "core":
            group = data["group"]
            expected_aggs = {f"agg:p{pod}:a{group}" for pod in range(k)}
            if set(neighbours) != expected_aggs:
                raise ValueError(f"{node} has incorrect pod connections")


def draw_fat_tree(
    graph: nx.Graph,
    max_k: int = MAX_DRAW_K,
    *,
    output_path: str | None = None,
) -> None:
    """Display or save a layered drawing of a small fat-tree graph.

    Drawing is intentionally limited to small examples because the number of
    links grows as ``3k^3/4``. Matplotlib is imported here, rather than at
    module import time, so normal topology generation remains lightweight.
    """
    k = graph.graph.get("k")
    if not isinstance(k, int):
        raise ValueError("graph is missing its integer k metadata")
    if k > max_k:
        raise ValueError(
            f"drawing is limited to k <= {max_k}; k={k} would be too crowded"
        )

    if output_path is not None:
        import matplotlib

        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    m = k // 2
    pod_width = m + 1
    graph_width = k * pod_width
    positions: dict[str, tuple[float, float]] = {}
    for node, data in graph.nodes(data=True):
        role = data["role"]
        if role == "host":
            x = (
                data["pod"] * pod_width
                + data["edge_index"]
                + (data["host_index"] + 1) / (m + 1)
            )
            positions[node] = (x, 0)
        elif role == "edge":
            positions[node] = (data["pod"] * pod_width + data["index"] + 0.5, 1)
        elif role == "aggregation":
            positions[node] = (data["pod"] * pod_width + data["index"] + 0.5, 2)
        else:  # core
            core_index = data["group"] * m + data["position"]
            positions[node] = ((core_index + 0.5) * graph_width / (m * m), 3)

    colors = {
        "host": "#8ecae6",
        "edge": "#219ebc",
        "aggregation": "#ffb703",
        "core": "#fb8500",
    }
    figure, axis = plt.subplots(figsize=(16, 8))
    nx.draw_networkx_edges(graph, positions, ax=axis, edge_color="#6c757d", alpha=0.55)
    for role, color in colors.items():
        nodes = [node for node, data in graph.nodes(data=True) if data["role"] == role]
        nx.draw_networkx_nodes(
            graph,
            positions,
            nodelist=nodes,
            node_color=color,
            node_size=650,
            label=role,
            ax=axis,
        )
    # Host IDs are intentionally omitted: at k=4 they would overlap and hide
    # the host-to-edge structure. Switch IDs remain visible for discussion.
    switch_labels = {}
    for node, data in graph.nodes(data=True):
        if data["role"] == "edge":
            switch_labels[node] = f"e{data['index']}"
        elif data["role"] == "aggregation":
            switch_labels[node] = f"a{data['index']}"
        elif data["role"] == "core":
            switch_labels[node] = f"g{data['group']}:c{data['position']}"
    nx.draw_networkx_labels(graph, positions, labels=switch_labels, font_size=7, ax=axis)
    for pod in range(k):
        axis.text(
            pod * pod_width + m / 2,
            -0.4,
            f"Pod {pod}",
            horizontalalignment="center",
            fontweight="bold",
        )
    axis.set_title(f"Canonical {k}-ary Fat-Tree")
    axis.set_ylim(-0.6, 3.35)
    axis.set_axis_off()
    axis.legend(title="Node role", loc="upper left", bbox_to_anchor=(1.01, 1))
    figure.tight_layout()
    if output_path is None:
        plt.show()
    else:
        figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)
