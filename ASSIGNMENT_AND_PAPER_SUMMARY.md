# Homework 1 and Fat-Tree Paper Summary

This document summarizes the homework instructions and the cited paper, with emphasis on the information needed to design, implement, test, analyze, and document the assignment.

## Sources

- Homework: *Homework 1 (version 2): Fat-Tree Network Topology Generation and Analysis*.
- Paper: Mohammad Al-Fares, Alexander Loukissas, and Amin Vahdat, *A Scalable, Commodity Data Center Network Architecture*, ACM SIGCOMM 2008, pages 63-74.
- Official paper page: <https://doi.org/10.1145/1402958.1402967>
- Local files: `Homework_1-2026.pdf` and `1402958.1402967.pdf`.

The assignment prints DOI `10.1145/1402946.1402967`, which identifies the journal issue form of the citation. The ACM conference-paper page uses DOI `10.1145/1402958.1402967`.

## 1. Assignment Objective

The assignment is about generating and analyzing a fat-tree data-center network. The implementation must:

1. Construct a three-tier fat-tree topology consistent with the cited paper.
2. Accept documented inputs that allow different network scales or configurations.
3. Accept an optional percentage of failed links through the command line or a configuration file.
4. Measure a non-trivial network metric as a function of an input parameter.
5. Visualize the experimental results.
6. Explain the setup, parameters, results, and significance of every analysis in `README.md`.

The purpose is not only to draw the topology. The final submission must use experiments to explain something meaningful about scalability, robustness, or performance.

## 2. Required Submission

Submit a link to a GitHub repository containing:

- The complete source code.
- A `README.md` that explains the approach.
- Clear installation and execution instructions.
- A description of all input parameters.
- Experimental plots or charts.
- An illustrative example for every analysis.
- A discussion of the results and why they matter.
- A clear acknowledgment of any AI assistance.

The assignment lists these deadlines:

- Initial code and `README.md`: 22 October 2026 at 08:00 - 20%.
- Full homework: 25 October 2026 at 12:00 - 80%.
- Results may be discussed in class on 22 October, 25 October, and 1 November 2026.

You are expected to understand and be able to explain everything submitted.

## 3. Why the Paper Proposes a Fat-Tree

Traditional data-center networks used a hierarchy of edge, aggregation, and core switches. The higher tiers relied on large, expensive switches and faster uplinks. This caused several problems:

- The root and upper layers became bandwidth bottlenecks.
- The network was often oversubscribed, so not all hosts could communicate at full interface speed at the same time.
- The largest possible cluster was limited by the port density of expensive high-end switches.
- Single-path routing failed to use the many alternative paths that a multi-rooted topology could provide.

The paper proposes building the entire network from identical commodity Ethernet switches connected as a fat-tree. Its goals are:

- Scalable bandwidth between arbitrary hosts.
- A 1:1 oversubscription ratio in principle, meaning full bisection bandwidth.
- Lower cost through commodity hardware.
- Compatibility with Ethernet, IP, TCP, existing operating systems, and existing applications.

The topology is a special case of a Clos network. It is rearrangeably non-blocking: for an arbitrary traffic pattern, some assignment of paths can use all bandwidth available to the hosts. Achieving that potential depends on choosing paths well.

## 4. Canonical `k`-Ary Fat-Tree Structure

`k` is the number of ports on every switch. In the canonical construction, `k` must be an even integer greater than or equal to 2. Let:

```text
m = k / 2
```

### 4.1 Three switch tiers

The network has three switch tiers:

1. **Edge tier** - connects directly to hosts.
2. **Aggregation tier** - connects edge switches within a pod to the core.
3. **Core tier** - connects different pods.

Hosts are endpoints below the edge tier; they are not a fourth switch tier.

### 4.2 Pods

There are exactly `k` pods. Every pod contains:

- `k/2` edge switches.
- `k/2` aggregation switches.

Every edge switch uses:

- `k/2` ports for hosts.
- `k/2` ports for connections to every aggregation switch in its pod.

Thus, the edge and aggregation tiers inside each pod form a complete bipartite graph.

Every aggregation switch uses:

- `k/2` ports for the edge switches in its pod.
- `k/2` ports for core switches.

### 4.3 Core tier

The core contains:

```text
(k/2)^2 = k^2/4 core switches
```

Each core switch has one connection to every pod. A useful implementation model is to arrange the core switches into `k/2` groups, with `k/2` switches per group. Aggregation switch `a` in every pod connects to all `k/2` core switches in core group `a`.

This rule guarantees that:

- Every aggregation switch has exactly `k/2` core links.
- Every core switch has exactly one link into every pod.
- Every switch uses exactly `k` ports.

### 4.4 Size formulas

For an even `k`, the canonical topology has:

| Quantity | Formula |
|---|---:|
| Pods | `k` |
| Hosts per edge switch | `k/2` |
| Hosts per pod | `k^2/4` |
| Total hosts | `k^3/4` |
| Edge switches | `k^2/2` |
| Aggregation switches | `k^2/2` |
| Core switches | `k^2/4` |
| Total switches | `5k^2/4` |
| Host-edge links | `k^3/4` |
| Edge-aggregation links | `k^3/4` |
| Aggregation-core links | `k^3/4` |
| Total links | `3k^3/4` |

Reference cases:

| `k` | Hosts | Switches | Links |
|---:|---:|---:|---:|
| 4 | 16 | 20 | 48 |
| 6 | 54 | 45 | 162 |
| 8 | 128 | 80 | 384 |
| 48 | 27,648 | 2,880 | 82,944 |

The paper uses `k = 4` as its smallest non-trivial example and `k = 48` as its large example. For `k = 48`, the topology has 48 pods, 24 edge and 24 aggregation switches per pod, 576 core switches, and 27,648 hosts.

### 4.5 Path properties

For an intact canonical topology, the shortest host-to-host path length is:

- 2 links for hosts under the same edge switch.
- 4 links for hosts under different edge switches in the same pod.
- 6 links for hosts in different pods.

Hosts in different pods have `(k/2)^2` equal-cost shortest paths, one through each suitable core choice. For `k = 48`, this gives 576 equal-cost paths between an inter-pod host pair.

These redundant paths are the main source of both high bisection bandwidth and fault tolerance.

## 5. Oversubscription and Bisection Bandwidth

Oversubscription describes how much host demand exceeds the worst-case capacity available through the network. The paper treats 1:1 as the goal: arbitrary hosts should be able to communicate at full interface speed simultaneously.

Traditional hierarchical designs often deliberately oversubscribe upper links to reduce cost. The paper reports typical ratios from 2.5:1 to 8:1. The fat-tree avoids faster upper-tier links by providing many parallel paths through many identical switches.

Full bisection bandwidth is a property of both topology and routing. Merely constructing the fat-tree does not guarantee that traffic will be balanced. A routing method that repeatedly selects the same path can still create congestion while other equal-cost paths remain idle.

## 6. Addressing and Routing in the Paper

The homework primarily requires topology generation and analysis, so a full implementation of the paper's routing system is optional unless the chosen metric depends on traffic routing. The following details explain how the paper attempts to use the topology's path diversity.

### 6.1 IP address scheme

The paper allocates addresses from `10.0.0.0/8`:

- Pod switch: `10.pod.switch.1`.
- Host: `10.pod.switch.ID`.
- Core switch: `10.k.j.i`, where `j` and `i` locate the switch in the core grid.

Each edge switch owns a `/24` subnet containing its attached hosts. The scheme wastes address space but makes route generation simple.

### 6.2 Why ordinary shortest-path routing is insufficient

Between hosts in different pods, all `(k/2)^2` core paths have the same hop count. Ordinary single-path routing may choose only one and concentrate traffic on a small number of links. Basic ECMP can also suffer from path-count limits, large forwarding tables, and collisions between large flows.

### 6.3 Two-level routing table

The paper proposes a two-level lookup:

- First, match a conventional left-handed destination prefix.
- If that prefix is non-terminating, match a right-handed suffix based on the destination host ID.

The destination host ID provides deterministic spreading across upward ports. Packets belonging to the same source-destination communication follow the same path, which helps avoid TCP packet reordering. Core switches use simple `/16` pod prefixes, and pod switches use `/24` local-subnet prefixes.

The tables remain small: no switch needs more than `k` first-level prefixes or `k/2` second-level suffixes.

### 6.4 Flow classification

The paper also tests a dynamic local flow classifier. It:

- Keeps packets from the same flow on the same output port.
- Initially assigns a new flow to the least-loaded upward port.
- Periodically moves a small number of flows to reduce load imbalance.

This adapts to changing flow sizes but uses only local information and can occasionally reorder packets when flows are moved.

### 6.5 Central flow scheduler

A central scheduler handles large flows using global information. Edge switches report large flows, and the scheduler searches the equal-cost paths for one whose links are not already reserved by other large flows.

The paper gives scheduler complexity as:

- `O(k^3)` space for link and flow state.
- `O(k^2)` time to search candidate paths for a new flow.

For `k = 48`, the prototype used about 5.6 MB of state and placed a flow in under 0.8 ms on the tested machine.

## 7. Failure Handling in the Paper

Path redundancy makes fat-trees naturally useful for failure recovery, but a routing mechanism must detect a failure and avoid affected paths.

The paper proposes Bidirectional Forwarding Detection between neighboring switches and a failure-broadcast mechanism.

### 7.1 Edge-to-aggregation link failure

When a link between an edge and aggregation switch fails:

- New outgoing flows use another aggregation switch.
- Other edge switches in the pod are told not to use the affected aggregation path for the unreachable subnet.
- Core and remote aggregation switches receive enough information to avoid paths that can no longer reach that subnet.

### 7.2 Aggregation-to-core link failure

When an aggregation-to-core link fails:

- Outgoing inter-pod traffic selects another core link.
- The core advertises that it cannot reach the affected pod through that path.
- Other aggregation switches avoid that core for traffic to the affected pod.

### 7.3 Failures that cannot be hidden

Failure of an edge switch disconnects its directly attached hosts unless the design adds redundant host-facing switches. The paper's redundancy protects the fabric above the edge tier; it does not provide redundant host attachments.

This distinction matters in the homework. If random failures include host-edge links, even one failed host link isolates that host. If the goal is to study fabric robustness, sample only edge-aggregation and aggregation-core links, and clearly document that choice.

## 8. Paper Evaluation and Main Results

The paper evaluates a `k = 4` fat-tree with:

- 4 pods.
- 16 hosts.
- 20 switches.
- 4 core switches.
- 96 Mbit/s emulated links.
- Constant traffic from every host.

It compares a traditional oversubscribed tree with three fat-tree forwarding approaches: two-level tables, local flow classification, and centralized flow scheduling.

The benchmark includes random, stride, staggered, and deliberately difficult traffic patterns. Each reported result is the average of five one-minute runs or permutations.

Important results, expressed as a percentage of ideal bisection bandwidth, include:

| Traffic pattern | Traditional tree | Two-level table | Flow classifier | Flow scheduler |
|---|---:|---:|---:|---:|
| Random | 53.4% | 75.0% | 76.3% | 93.5% |
| Stride 4 | 27.9% | 100.0% | 100.0% | 100.0% |
| Inter-pod incoming worst case | 28.0% | 50.6% | 75.1% | 99.9% |
| Same-ID outgoing worst case | 27.8% | 38.5% | 75.4% | 87.4% |

The results show:

- The topology provides many paths, but static routing does not always use them well.
- The two-level table performs well for many patterns but suffers when several flows map to the same suffix-selected path.
- A local dynamic classifier improves balance but cannot predict congestion elsewhere in the network.
- A global scheduler makes the best use of path diversity, reaching 93.5% of ideal bandwidth for random mappings in the prototype.

The paper also estimates that its 27,648-host fat-tree uses 56.6% less power and produces 56.5% less heat than the compared hierarchical design, despite using more switches. These values were calculated from vendor data sheets rather than measured in a full deployment.

## 9. Recommended Homework Experiment

A good experiment for this repository is:

> How does random fabric-link failure affect host-to-host communication efficiency and reachability as fat-tree size increases?

This question is meaningful because the paper emphasizes redundant paths and fault tolerance. It is also practical to evaluate with a graph library without implementing packet-level traffic or the paper's custom routing system.

### 9.1 Independent variable

Use link-failure percentage as the independent variable:

```text
0%, 5%, 10%, 15%, 20%, 25%, 30%, 35%, 40%, 45%, 50%
```

Run the experiment for `k = 4, 6, 8`.

### 9.2 Failure scope

Prefer fabric-only failures:

```text
edge-aggregation and aggregation-core links
```

This measures the redundancy of the fat-tree fabric. If host-edge failures are included, report that separately because those links have no alternate path.

### 9.3 Primary metric: normalized host-pair efficiency

For `H` hosts, there are:

```text
H(H - 1) / 2
```

unordered host pairs. For every reachable pair at shortest-path distance `d`, assign a score of `1/d`. A disconnected pair receives zero. Define:

```text
host_pair_efficiency = sum(pair scores) / total_host_pairs
```

Normalize the damaged topology against the intact topology for the same `k`:

```text
normalized_efficiency = damaged_efficiency / intact_efficiency * 100
```

This metric decreases for both longer detours and disconnected pairs.

### 9.4 Companion metric: reachable host-pair ratio

Define:

```text
reachable_host_pair_ratio = reachable_host_pairs / total_host_pairs
```

This directly measures how much end-to-end connectivity survives failures and makes the efficiency result easier to interpret.

Average shortest path among reachable pairs may be recorded as a diagnostic, but it should not be the primary metric. Once distant pairs disconnect, excluding them can make the surviving network look artificially good.

### 9.5 Repetitions and randomness

For every combination of `k` and failure percentage:

1. Build a fresh intact topology.
2. Randomly remove the requested percentage of eligible links without replacement.
3. Compute the metrics.
4. Repeat with 30 deterministic seeds, numbered 0 through 29.
5. Report the mean and sample standard deviation.

Multiple runs are necessary because one random failure set may be unusually harmless or unusually destructive.

### 9.6 Recommended plots

Create at least these plots:

1. Reachable host-pair percentage versus link-failure percentage, with one curve per `k`.
2. Normalized host-pair efficiency versus link-failure percentage, with one curve per `k`.

Use error bars or shaded uncertainty bands. Save the plot files in the repository and embed them in `README.md`.

### 9.7 Interpretation questions

The README discussion should answer:

- At what failure rate does reachability first decrease noticeably?
- Does a larger `k` improve robustness because it creates more equal-cost paths?
- Does efficiency fall before the network fragments?
- Which layer's failures cause the most damage?
- How different are fabric-only failures from failures over all link types?
- How much variation exists between random seeds?

## 10. Other Valid Metric Choices

The assignment gives these examples:

- Average path length or number of paths as a function of failure probability - advanced.
- Number of switches with multiple failed links at a 1% failure rate as a function of switch port count - intermediate.
- Number of supported hosts as a function of switch port count - basic.

Additional suitable metrics include:

- Size of the largest connected host component.
- Fraction of isolated hosts.
- Number of connected components.
- Edge connectivity or number of edge-disjoint paths between sampled host pairs.
- Diameter of the surviving connected component.
- Failure rate at which a chosen reachability threshold is crossed.

The host-count experiment is easy because `H = k^3/4`, but it says little about failures. The reachability experiment provides a stronger connection to the paper's fault-tolerance claims.

## 11. Implementation and Validation Checklist

### Topology generation

- Reject non-integer, odd, or invalid values of `k`.
- Generate exactly `k` pods.
- Generate `k/2` edge and `k/2` aggregation switches per pod.
- Connect every edge switch to `k/2` hosts.
- Fully connect edge and aggregation switches inside each pod.
- Generate `(k/2)^2` core switches.
- Connect each aggregation switch to the correct core group.
- Store node roles and pod/index metadata.
- Label link layers so failure scopes can be selected precisely.

### Structural validation

- Every host has degree 1.
- Every switch has degree `k` in the intact topology.
- The intact graph is connected.
- Node, switch, host, and link counts match the formulas.
- Edge switches connect only to hosts and aggregation switches.
- Aggregation switches connect only to edge and core switches.
- Core switches connect to exactly one aggregation switch in each pod.
- Host and switch identities agree with the pod and local index encoded in their metadata.

### Failure model

- Accept a failure percentage from 0 through 100.
- State how percentages are converted to an integer number of links.
- Sample links uniformly without replacement.
- Support a deterministic random seed for reproducibility.
- Preserve the intact graph and apply failures to a copy.
- Document whether failures include host-edge links or only fabric links.
- Record which links and link layers failed.

### Experiment

- State the research question.
- Define independent and dependent variables.
- State `k`, failure rates, failure scope, seeds, and number of repetitions.
- Aggregate multiple runs.
- Plot the results with labeled axes, units, title, and legend.
- Include uncertainty when random sampling is used.
- Explain the observed trend and its significance.

### Documentation

- Explain installation and dependencies.
- Give exact commands for topology generation and experiments.
- Give at least one example command and its output.
- Embed every result plot in `README.md`.
- Explain every plot's setup and parameters.
- Discuss limitations, including the difference between graph connectivity and real traffic throughput.
- Cite the paper.
- Acknowledge AI assistance clearly.

## 12. Important Scope Distinctions

Keep these concepts separate in the report:

- **Topology correctness** means nodes and links match the canonical fat-tree construction.
- **Connectivity** means a path exists between hosts.
- **Shortest path length** counts graph links, not delay or throughput.
- **Path diversity** counts alternative routes but does not prove they are used evenly.
- **Bisection bandwidth** is a traffic-capacity property and requires a traffic and routing model.
- **Topology visualization** illustrates network structure; it is not the experimental result plot required by the assignment.

A NetworkX-style graph model is sufficient for structural metrics such as reachability, components, path length, and path diversity. It is not sufficient by itself to reproduce the paper's throughput percentages because those results depend on link capacities, traffic matrices, flow sizes, and routing decisions.

## 13. Suggested README Results Structure

```text
## Experiment: Robustness Under Fabric-Link Failures

### Question
How does fabric-link failure percentage affect host reachability?

### Setup
- k values
- failure percentages
- failure scope
- number of seeds/repetitions
- sampling method

### Metric
- precise definition and formula
- treatment of disconnected pairs

### Results
- embedded plot
- small table of representative values

### Interpretation
- main trend
- comparison between k values
- explanation using fat-tree path redundancy
- limitations
```

## 14. Key Takeaway

The paper's central lesson is that many inexpensive switches, connected as a regular fat-tree, can provide far more path diversity and aggregate bandwidth than a traditional single-rooted hierarchy. The assignment asks you to demonstrate one consequence of that structure quantitatively. A strong submission therefore combines a correct canonical generator, reproducible failure injection, a carefully defined metric, repeated experiments, clear plots, and an explanation that connects the observed behavior to the fat-tree's redundant equal-cost paths.
