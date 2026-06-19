"""Curated process workloads for comparing multiprocessor schedulers.

Expected results were measured with the dashboard defaults:
- 4 CPUs
- GLB_RR quantum: 15
- CPU Affinity quantum: 5
- Work Stealing quantum: 5, strategy: shortest_queue
- Load Balancing threshold: 2
- Migration overhead: 1

Changing those parameters can change the ranking, which is useful for further
experimentation.
"""

import random


def _processes(bursts: list[int], arrivals: list[int] | None = None) -> list[dict]:
    """Build rows with padded PIDs so lexicographic sorting preserves order."""
    if arrivals is None:
        arrivals = [0] * len(bursts)
    if len(bursts) != len(arrivals):
        raise ValueError("bursts and arrivals must have the same length")
    return [
        {
            "PID": f"P{index + 1:02}",
            "Arrival": arrivals[index],
            "Burst": burst,
            "Priority": index % 5 + 1,
        }
        for index, burst in enumerate(bursts)
    ]


def _random_processes(
    seed: int,
    count: int,
    max_arrival: int,
    min_burst: int = 1,
    max_burst: int = 80,
) -> list[dict]:
    """Generate a deterministic random workload from the supplied seed."""
    generator = random.Random(seed)
    arrivals = sorted(generator.randint(0, max_arrival) for _ in range(count))
    bursts = [generator.randint(min_burst, max_burst) for _ in range(count)]
    rows = _processes(bursts, arrivals)
    for row in rows:
        row["Priority"] = generator.randint(1, 5)
    return rows


# Load Balancing wins by migrating several long waiting jobs away from queues
# that received an unfavorable initial round-robin distribution.
PROCESSES_1 = _processes(
    [8, 3, 21, 13, 2, 1, 34, 55, 55, 5, 1, 55, 1, 3, 5, 3]
)

# FIFO and PAR_FIFO perform well because non-preemptive execution avoids
# repeatedly rotating a mixture containing a few long jobs.
PROCESSES_2 = _processes(
    [1, 3, 2, 8, 13, 5, 55, 1, 13, 8, 8, 34, 3, 13, 8, 21]
)

# Round Robin performs best on staggered arrivals containing repeated long
# jobs and short jobs that benefit from global time-sliced sharing.
PROCESSES_3 = _processes(
    [57, 3, 6, 10, 81, 3, 7, 7, 81, 7, 10, 10, 80, 6, 9, 2, 69, 5, 9, 4, 90, 3, 5, 5],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 10, 6, 20, 16, 7, 22, 12, 18, 7, 11, 10, 22, 9],
)

# CPU Affinity wins narrowly because the arrival pattern and repeated quantum
# execution produce a favorable stable mapping, while migration adds overhead.
PROCESSES_4 = _processes(
    [2, 2, 5, 5, 3, 2, 40, 30, 60, 3, 3, 2, 5, 30, 40, 3, 30, 2, 5, 2],
    [0, 0, 0, 0, 5, 2, 5, 3, 6, 10, 6, 2, 15, 6, 9, 3, 12, 4, 4, 4],
)

# Work Stealing wins because local queues become uneven after later arrivals;
# idle CPUs can steal waiting tasks without continuous proactive migration.
PROCESSES_5 = _processes(
    [43, 4, 8, 8, 49, 10, 10, 5, 47, 7, 9, 10, 46, 9, 6, 2, 73, 3, 9, 8, 56, 6, 10, 2, 42, 9, 10, 6],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 24, 9, 14, 7, 7, 20, 14, 20, 18, 17, 8, 11, 8, 23],
)

# Control workload: equal jobs arriving together produce identical makespan
# for all algorithms under the default four-CPU configuration.
PROCESSES_6 = _processes([12] * 20)

# A second Load Balancing-friendly workload. Long jobs arrive in different
# waves, allowing push/pull migration to correct temporary queue imbalance.
PROCESSES_7 = _processes(
    [20, 5, 3, 10, 1, 50, 10, 1, 10, 10, 3, 1, 20, 10, 80, 80],
    [0, 30, 5, 5, 0, 20, 5, 20, 20, 10, 20, 5, 0, 20, 20, 0],
)

# FIFO and PAR_FIFO-friendly arrival waves. A small number of long jobs are
# followed by short jobs; strict affinity becomes severely imbalanced.
PROCESSES_8 = _processes(
    [64, 5, 8, 9, 88, 10, 6, 5, 73, 3, 8, 10, 60, 7, 10, 8],
    [0, 0, 0, 0, 0, 0, 0, 0, 5, 9, 6, 22, 18, 22, 20, 17],
)

# A larger Round Robin-friendly workload with heavy jobs mixed into two
# arrival phases. Global time slicing gives the lowest makespan.
PROCESSES_9 = _processes(
    [46, 2, 7, 1, 55, 7, 3, 10, 80, 5, 8, 5, 80, 10, 7, 5, 49, 6, 9, 9, 61, 6, 2, 10, 54, 8, 8, 1, 59, 5, 5, 2],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 16, 25, 19, 20, 7, 14, 13, 12, 16, 16, 7, 12, 25, 9, 5, 14],
)

# A second CPU Affinity-friendly workload. Its process-to-CPU mapping remains
# balanced, while FIFO placement and Load Balancing produce longer tails.
PROCESSES_10 = _processes(
    [50, 4, 6, 8, 74, 4, 6, 6, 40, 7, 2, 9, 53, 10, 5, 6, 74, 10, 7, 3],
    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 10, 6, 20, 16, 7, 22, 12, 18, 7],
)

# Load Balancing stress test. Long jobs repeatedly occupy the same modulo
# positions. Migration overhead and immovable running jobs make LB the worst,
# while Global Round Robin performs best.
PROCESSES_11 = _processes([40, 3, 3, 3] * 6)

# CPU Affinity stress test. Long jobs are separated by short jobs in a pattern
# that creates an unfavorable hard-affinity mapping. FIFO/PAR_FIFO win.
PROCESSES_12 = _processes(
    [50, 2, 2, 2, 45, 2, 2, 2, 40, 2, 2, 2, 35, 2, 2, 2]
)

# Random benchmark sets. Fixed seeds make the generated workloads stable
# between Streamlit reruns and across different machines.
PROCESSES_13 = _random_processes(seed=1301, count=15, max_arrival=20)
PROCESSES_14 = _random_processes(seed=1402, count=18, max_arrival=30)
PROCESSES_15 = _random_processes(seed=1503, count=20, max_arrival=15)
PROCESSES_16 = _random_processes(seed=1604, count=22, max_arrival=40)
PROCESSES_17 = _random_processes(seed=1705, count=24, max_arrival=25)
PROCESSES_18 = _random_processes(seed=1806, count=26, max_arrival=50)
PROCESSES_19 = _random_processes(seed=1907, count=28, max_arrival=35)
PROCESSES_20 = _random_processes(seed=2008, count=30, max_arrival=60)
PROCESSES_21 = _random_processes(seed=2109, count=35, max_arrival=45)
PROCESSES_22 = _random_processes(seed=2210, count=40, max_arrival=70)


PROCESS_SET_OPTIONS = {
    "Set 1 — Load Balancing advantage": {
        "processes": PROCESSES_1,
        "expected": "LB 68; RR/WS 76; FIFO/PAR 82; Affinity 131",
        "reason": "Migration repairs an unfavorable initial distribution of long waiting jobs.",
    },
    "Set 2 — FIFO/PAR_FIFO advantage": {
        "processes": PROCESSES_2,
        "expected": "FIFO/PAR 58; LB 64; RR 69; WS 73; Affinity 113",
        "reason": "Non-preemptive execution handles this all-at-once mixed workload efficiently.",
    },
    "Set 3 — Round Robin advantage": {
        "processes": PROCESSES_3,
        "expected": "RR 152; WS 160; FIFO/PAR 175; LB 181; Affinity 239",
        "reason": "Global time slicing handles staggered long and short jobs well.",
    },
    "Set 4 — CPU Affinity advantage": {
        "processes": PROCESSES_4,
        "expected": "Affinity 74; FIFO/PAR 76; RR 85; WS 87; LB 109",
        "reason": "The arrival pattern produces a favorable stable CPU mapping.",
    },
    "Set 5 — Work Stealing advantage": {
        "processes": PROCESSES_5,
        "expected": "WS 136; RR 145; FIFO/PAR 148; LB 154; Affinity 261",
        "reason": "Idle CPUs efficiently steal work created by uneven later arrivals.",
    },
    "Set 6 — Balanced control": {
        "processes": PROCESSES_6,
        "expected": "All algorithms: 60",
        "reason": "Equal jobs arriving together create a perfectly symmetric workload.",
    },
    "Set 7 — Load Balancing with arrival waves": {
        "processes": PROCESSES_7,
        "expected": "LB 107; WS 110; RR 115; FIFO/PAR 119; Affinity 211",
        "reason": "Push and pull migration correct temporary imbalance across waves.",
    },
    "Set 8 — FIFO/PAR_FIFO arrival waves": {
        "processes": PROCESSES_8,
        "expected": "FIFO/PAR 99; LB 103; RR 105; WS 106; Affinity 225",
        "reason": "Non-preemptive queues finish the staged long jobs with little overhead.",
    },
    "Set 9 — Round Robin heavy stagger": {
        "processes": PROCESSES_9,
        "expected": "RR 164; WS 171; LB 180; FIFO/PAR 193; Affinity 336",
        "reason": "Time slicing prevents several heavy processes from creating long tails.",
    },
    "Set 10 — CPU Affinity stable mapping": {
        "processes": PROCESSES_10,
        "expected": "Affinity 104; RR 118; WS 121; LB 146; FIFO/PAR 148",
        "reason": "The hard-affinity mapping remains balanced for this arrival order.",
    },
    "Set 11 — Load Balancing stress test": {
        "processes": PROCESSES_11,
        "expected": "RR 77; WS 85; FIFO/PAR 89; Affinity 92; LB 100",
        "reason": "Migration overhead cannot repair long jobs that are already running.",
    },
    "Set 12 — CPU Affinity stress test": {
        "processes": PROCESSES_12,
        "expected": "FIFO/PAR 50; RR/WS/LB 54; Affinity 82",
        "reason": "Hard affinity maps the repeated long-job pattern unevenly.",
    },
    "Set 13 — Random (15 processes)": {
        "processes": PROCESSES_13,
        "expected": "No favored algorithm; compare the measured results.",
        "reason": "Deterministic random workload, seed 1301.",
    },
    "Set 14 — Random (18 processes)": {
        "processes": PROCESSES_14,
        "expected": "No favored algorithm; compare the measured results.",
        "reason": "Deterministic random workload, seed 1402.",
    },
    "Set 15 — Random (20 processes)": {
        "processes": PROCESSES_15,
        "expected": "No favored algorithm; compare the measured results.",
        "reason": "Deterministic random workload, seed 1503.",
    },
    "Set 16 — Random (22 processes)": {
        "processes": PROCESSES_16,
        "expected": "No favored algorithm; compare the measured results.",
        "reason": "Deterministic random workload, seed 1604.",
    },
    "Set 17 — Random (24 processes)": {
        "processes": PROCESSES_17,
        "expected": "No favored algorithm; compare the measured results.",
        "reason": "Deterministic random workload, seed 1705.",
    },
    "Set 18 — Random (26 processes)": {
        "processes": PROCESSES_18,
        "expected": "No favored algorithm; compare the measured results.",
        "reason": "Deterministic random workload, seed 1806.",
    },
    "Set 19 — Random (28 processes)": {
        "processes": PROCESSES_19,
        "expected": "No favored algorithm; compare the measured results.",
        "reason": "Deterministic random workload, seed 1907.",
    },
    "Set 20 — Random (30 processes)": {
        "processes": PROCESSES_20,
        "expected": "No favored algorithm; compare the measured results.",
        "reason": "Deterministic random workload, seed 2008.",
    },
    "Set 21 — Random (35 processes)": {
        "processes": PROCESSES_21,
        "expected": "No favored algorithm; compare the measured results.",
        "reason": "Deterministic random workload, seed 2109.",
    },
    "Set 22 — Random (40 processes)": {
        "processes": PROCESSES_22,
        "expected": "No favored algorithm; compare the measured results.",
        "reason": "Deterministic random workload, seed 2210.",
    },
}


__all__ = [
    *(f"PROCESSES_{index}" for index in range(1, 23)),
    "PROCESS_SET_OPTIONS",
]
