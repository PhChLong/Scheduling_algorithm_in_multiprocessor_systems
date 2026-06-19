"""Evaluate all schedulers on every workload in Process_options.py.

The script uses the same default configuration as the Streamlit dashboard and
writes one CSV file for each requested metric.
"""

from dataclasses import dataclass

import pandas as pd

import algorithms
from Process_options import PROCESS_SET_OPTIONS
from process import Process, Processes


NUM_CPU = 4
RR_QUANTUM = 15
AFFINITY_QUANTUM = 5
WORK_STEALING_QUANTUM = 5
WORK_STEALING_STRATEGY = "shortest_queue"
MIGRATION_OVERHEAD = 1
PREEMPTIVE_LOAD_BALANCING_QUANTUM = 5


@dataclass(frozen=True)
class EvaluationMetrics:
    turnaround_time: float
    waiting_time: float
    response_time: float
    cpu_utilization: float


def build_processes(rows: list[dict]) -> tuple[Processes, dict[int, Process]]:
    """Convert process rows and retain an ID-to-original-process mapping."""
    processes = Processes()
    ordered_rows = sorted(rows, key=lambda row: (int(row["Arrival"]), str(row["PID"])))

    for row in ordered_rows:
        processes.add(
            Process(
                burst_time=int(row["Burst"]),
                arrival_time=int(row["Arrival"]),
                priority=int(row["Priority"]),
            )
        )

    process_map = {process.id: process for process in processes.all()}
    return processes, process_map


def create_schedulers() -> list:
    """Create the six original schedulers and preemptive load balancing."""
    return [
        algorithms.GLB_FIFO(num_cpu=NUM_CPU),
        algorithms.GLB_RR(num_cpu=NUM_CPU, time_quantum=RR_QUANTUM),
        algorithms.PAR_FIFO(num_cpu=NUM_CPU),
        algorithms.CPU_Affinity(
            num_cpu=NUM_CPU,
            time_quantum=AFFINITY_QUANTUM,
            hard=True,
        ),
        algorithms.Work_Stealing(
            num_cpu=NUM_CPU,
            time_quantum=WORK_STEALING_QUANTUM,
            strat=WORK_STEALING_STRATEGY,
            migration_overhead=MIGRATION_OVERHEAD,
        ),
        algorithms.LoadBalancing(
            num_cpu=NUM_CPU,
            migration_overhead=MIGRATION_OVERHEAD,
        ),
    ]


def calculate_metrics(scheduler, process_map: dict[int, Process]) -> EvaluationMetrics:
    """Calculate average process metrics and overall CPU utilization."""
    all_steps = [
        step
        for cpu_steps in scheduler.steps.values()
        for step in cpu_steps
    ]

    if not all_steps or not process_map:
        return EvaluationMetrics(0.0, 0.0, 0.0, 0.0)

    turnaround_values = []
    waiting_values = []
    response_values = []

    for process_id, process in process_map.items():
        process_steps = [
            step for step in all_steps if step.process_id == process_id
        ]
        if not process_steps:
            continue

        start_time = min(step.begin_time for step in process_steps)
        finish_time = max(step.end_time for step in process_steps)
        actual_cpu_time = sum(
            step.end_time - step.begin_time for step in process_steps
        )

        turnaround = finish_time - process.arrival_time
        waiting = turnaround - actual_cpu_time
        response = start_time - process.arrival_time

        turnaround_values.append(turnaround)
        waiting_values.append(waiting)
        response_values.append(response)

    total_time = max(step.end_time for step in all_steps)
    busy_time = sum(step.end_time - step.begin_time for step in all_steps)
    cpu_utilization = (
        0.0
        if total_time == 0
        else busy_time / (scheduler.num_cpu * total_time)
    )

    completed_count = len(turnaround_values)
    if completed_count == 0:
        return EvaluationMetrics(0.0, 0.0, 0.0, cpu_utilization)

    return EvaluationMetrics(
        turnaround_time=sum(turnaround_values) / completed_count,
        waiting_time=sum(waiting_values) / completed_count,
        response_time=sum(response_values) / completed_count,
        cpu_utilization=cpu_utilization,
    )


def add_mean_column(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Add each algorithm's mean across all 22 process sets."""
    dataframe["Mean"] = dataframe.mean(axis=1)
    return dataframe


def evaluate_all_sets() -> dict[str, pd.DataFrame]:
    """Run all schedulers and build metric tables indexed by algorithm."""
    algorithm_names = [
        scheduler.algorithm_name for scheduler in create_schedulers()
    ]
    metric_results = {
        "turnaround_time": {name: {} for name in algorithm_names},
        "waiting_time": {name: {} for name in algorithm_names},
        "response_time": {name: {} for name in algorithm_names},
        "cpu_utilization": {name: {} for name in algorithm_names},
    }

    for set_number, (set_name, set_info) in enumerate(
        PROCESS_SET_OPTIONS.items(),
        start=1,
    ):
        processes, process_map = build_processes(set_info["processes"])
        process_set_name = f"PROCESSES_{set_number}"

        print(f"\n{set_name} ({len(set_info['processes'])} processes)")

        for scheduler in create_schedulers():
            scheduler.estimate(processes.copy())
            metrics = calculate_metrics(scheduler, process_map)
            algorithm_name = scheduler.algorithm_name

            metric_results["turnaround_time"][algorithm_name][
                process_set_name
            ] = metrics.turnaround_time
            metric_results["waiting_time"][algorithm_name][
                process_set_name
            ] = metrics.waiting_time
            metric_results["response_time"][algorithm_name][
                process_set_name
            ] = metrics.response_time
            metric_results["cpu_utilization"][algorithm_name][
                process_set_name
            ] = metrics.cpu_utilization

            print(
                f"  {algorithm_name:<16} "
                f"turnaround={metrics.turnaround_time:8.3f}  "
                f"waiting={metrics.waiting_time:8.3f}  "
                f"response={metrics.response_time:8.3f}  "
                f"cpu_utilization={metrics.cpu_utilization:7.3%}"
            )

    dataframes = {}
    for metric_name, algorithm_results in metric_results.items():
        dataframe = pd.DataFrame.from_dict(
            algorithm_results,
            orient="index",
        )
        dataframe.index.name = "Algorithm"
        dataframes[metric_name] = add_mean_column(dataframe)

    return dataframes


def save_results(dataframes: dict[str, pd.DataFrame]) -> None:
    """Print each DataFrame and save it as a CSV file."""
    output_files = {
        "turnaround_time": "turnaround_time.csv",
        "waiting_time": "waiting_time.csv",
        "response_time": "response_time.csv",
        "cpu_utilization": "cpu_utilization.csv",
    }

    for metric_name, output_file in output_files.items():
        dataframe = dataframes[metric_name].copy()
        process_set_columns = [
            column for column in dataframe.columns if column != "Mean"
        ]
        dataframe[process_set_columns] = dataframe[process_set_columns].round(6)
        dataframe["Mean"] = (
            dataframe[process_set_columns].mean(axis=1).round(6)
        )
        dataframes[metric_name] = dataframe
        print(f"\n{'=' * 24} {metric_name.upper()} {'=' * 24}")
        print(dataframe.to_string(float_format=lambda value: f"{value:.6f}"))
        dataframe.to_csv(output_file, float_format="%.6f")
        print(f"Saved: {output_file}")


def main() -> None:
    dataframes = evaluate_all_sets()
    save_results(dataframes)


if __name__ == "__main__":
    main()
