"""Command-line entry point for the fat-tree generator."""

from __future__ import annotations

import argparse

from fat_tree import (
    FAILURE_SCOPES,
    MAX_DRAW_K,
    build_fat_tree,
    draw_fat_tree,
    expected_counts,
    inject_link_failures,
    validate_fat_tree,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a canonical k-ary fat-tree.")
    parser.add_argument("--k", required=True, type=int, help="even switch port count (>= 2)")
    parser.add_argument(
        "--failure-rate",
        type=float,
        default=0,
        metavar="PERCENT",
        help="percentage of eligible links to remove, from 0 to 100 (default: 0)",
    )
    parser.add_argument(
        "--failure-scope",
        choices=sorted(FAILURE_SCOPES),
        default="all",
        help="eligible links: all links or fabric links only (default: all)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="integer seed for reproducible link-failure selection",
    )
    parser.add_argument(
        "--draw",
        action="store_true",
        help=f"display a layered topology drawing (available only for k <= {MAX_DRAW_K})",
    )
    args = parser.parse_args()

    try:
        graph = build_fat_tree(args.k)
        validate_fat_tree(graph, args.k)
        failure_result = inject_link_failures(
            graph, args.failure_rate, args.failure_scope, args.seed
        )
    except ValueError as error:
        parser.error(str(error))
    if args.draw and args.k > MAX_DRAW_K:
        parser.error(f"drawing is limited to k <= {MAX_DRAW_K}; k={args.k} would be too crowded")

    counts = expected_counts(args.k)
    print(f"Canonical {args.k}-ary fat-tree")
    print(f"Pods: {counts['pods']}")
    print(f"Hosts: {counts['hosts']}")
    print(f"Switches: {counts['switches']} "
          f"(edge={counts['edge']}, aggregation={counts['aggregation']}, core={counts['core']})")
    print(f"Links: {counts['links']}")
    print("Validation: passed (connected; host degree 1; switch degree k)")
    print("Failure simulation:")
    print(f"  Requested rate: {failure_result.requested_rate:g}%")
    print(f"  Scope: {failure_result.scope}")
    if failure_result.seed is not None:
        print(f"  Seed: {failure_result.seed}")
    print(f"  Eligible links: {len(failure_result.eligible_links)}")
    print(f"  Removed links: {len(failure_result.removed_links)}")
    print(f"  Realized rate: {failure_result.realized_rate:.2f}%")
    if failure_result.removed_by_layer:
        layer_counts = ", ".join(
            f"{layer}={count}" for layer, count in failure_result.removed_by_layer.items()
        )
        print(f"  Removed by layer: {layer_counts}")
    else:
        print("  Removed by layer: none")
    if args.draw:
        draw_fat_tree(graph)


if __name__ == "__main__":
    main()
