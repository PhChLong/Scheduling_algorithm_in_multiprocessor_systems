import time
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

import algorithms
from process import Process, Processes


DEFAULT_PROCESSES = [
    {"PID": "P1", "Arrival": 0, "Burst": 32, "Priority": 2},
    {"PID": "P2", "Arrival": 0, "Burst": 26, "Priority": 4},
    {"PID": "P3", "Arrival": 3, "Burst": 8, "Priority": 1},
    {"PID": "P4", "Arrival": 3, "Burst": 11, "Priority": 3},
    {"PID": "P5", "Arrival": 3, "Burst": 5, "Priority": 2},
    {"PID": "P6", "Arrival": 6, "Burst": 4, "Priority": 5},
    {"PID": "P7", "Arrival": 7, "Burst": 6, "Priority": 1},
    {"PID": "P8", "Arrival": 8, "Burst": 3, "Priority": 4},
    {"PID": "P9", "Arrival": 9, "Burst": 7, "Priority": 2},
    {"PID": "P10", "Arrival": 10, "Burst": 2, "Priority": 5},
    {"PID": "P11", "Arrival": 12, "Burst": 14, "Priority": 2},
    {"PID": "P12", "Arrival": 12, "Burst": 9, "Priority": 3},
    {"PID": "P13", "Arrival": 15, "Burst": 18, "Priority": 1},
    {"PID": "P14", "Arrival": 16, "Burst": 10, "Priority": 4},
    {"PID": "P15", "Arrival": 25, "Burst": 24, "Priority": 2},
    {"PID": "P16", "Arrival": 25, "Burst": 6, "Priority": 5},
    {"PID": "P17", "Arrival": 28, "Burst": 15, "Priority": 3},
    {"PID": "P18", "Arrival": 29, "Burst": 4, "Priority": 1},
    {"PID": "P19", "Arrival": 35, "Burst": 20, "Priority": 2},
    {"PID": "P20", "Arrival": 36, "Burst": 5, "Priority": 4},
]


def ensure_state() -> None:
    if "process_rows" not in st.session_state:
        st.session_state.process_rows = DEFAULT_PROCESSES.copy()


def build_processes(rows: list[dict[str, Any]]) -> Processes:
    processes = Processes()
    clean_rows = sorted(rows, key=lambda row: (int(row["Arrival"]), str(row["PID"])))
    for row in clean_rows:
        processes.add(
            Process(
                burst_time=int(row["Burst"]),
                arrival_time=int(row["Arrival"]),
                priority=int(row["Priority"]),
            )
        )
    return processes


def process_table_df() -> pd.DataFrame:
    return pd.DataFrame(st.session_state.process_rows)


def add_or_update_process(pid: str, arrival: int, burst: int, priority: int) -> None:
    new_row = {
        "PID": pid.strip() or f"P{len(st.session_state.process_rows) + 1}",
        "Arrival": int(arrival),
        "Burst": int(burst),
        "Priority": int(priority),
    }
    for idx, row in enumerate(st.session_state.process_rows):
        if row["PID"] == new_row["PID"]:
            st.session_state.process_rows[idx] = new_row
            return
    st.session_state.process_rows.append(new_row)


def delete_process_row(pid: str) -> None:
    st.session_state.process_rows = [row for row in st.session_state.process_rows if row["PID"] != pid]


def scheduler_metrics(scheduler, process_count: int) -> dict[str, float]:
    total_time = max((step.end_time for steps in scheduler.steps.values() for step in steps), default=0)
    busy_time = sum(step.end_time - step.begin_time for steps in scheduler.steps.values() for step in steps)
    utilization = 0.0 if total_time == 0 else busy_time / (scheduler.num_cpu * total_time)
    throughput = 0.0 if total_time == 0 else process_count / total_time
    return {
        "total_time": total_time,
        "busy_time": busy_time,
        "cpu_utilization": utilization,
        "throughput": throughput,
    }


def gantt_dataframe(scheduler, pid_map: dict[int, str], migration_events: list[dict[str, Any]] | None = None) -> pd.DataFrame:
    migrated_ids = {event["process_id"] for event in (migration_events or [])}
    rows: list[dict[str, Any]] = []
    for cpu_id, steps in scheduler.steps.items():
        for step in steps:
            pid_label = pid_map.get(step.process_id, f"P{step.process_id}")
            if step.process_id in migrated_ids:
                pid_label = f"{pid_label} *"
            rows.append(
                {
                    "Process": pid_label,
                    "CPU": f"CPU {cpu_id + 1}",
                    "Start": step.begin_time,
                    "Finish": step.end_time,
                }
            )
    return pd.DataFrame(rows)


def timeline_figure(df: pd.DataFrame, num_cpu: int):
    if df.empty:
        return None

    base_time = pd.Timestamp("2026-01-01 00:00:00")
    chart_df = df.copy()
    chart_df["Start_Time"] = base_time + pd.to_timedelta(chart_df["Start"], unit="s")
    chart_df["Finish_Time"] = base_time + pd.to_timedelta(chart_df["Finish"], unit="s")

    fig = px.timeline(
        chart_df,
        x_start="Start_Time",
        x_end="Finish_Time",
        y="CPU",
        color="Process",
        text="Process",
    )
    fig.update_traces(textposition="inside")
    fig.update_layout(
        height=480,
        margin=dict(l=16, r=16, t=36, b=16),
        legend_title_text="Process",
    )
    fig.update_yaxes(
        title="CPU",
        categoryorder="array",
        categoryarray=[f"CPU {idx}" for idx in range(num_cpu, 0, -1)],
    )
    fig.update_xaxes(tickformat="%S", title="Simulation Time")
    return fig


def run_schedulers(processes: Processes, num_cpu: int, rr_quantum: int, affinity_quantum: int, threshold: int, migration_overhead: int):
    runners = [
        algorithms.GLB_RR(num_cpu=num_cpu, time_quantum=rr_quantum),
        algorithms.CPU_Affinity(num_cpu=num_cpu, time_quantum=affinity_quantum, hard=True),
        algorithms.LoadBalancing(num_cpu=num_cpu, threshold=threshold, migration_overhead=migration_overhead),
    ]
    for scheduler in runners:
        scheduler.estimate(processes.copy())
    return runners


def render_process_management() -> None:
    st.markdown("## Process Management")
    left, right = st.columns([1, 1.7])

    with left:
        with st.form("process_form", clear_on_submit=True):
            pid = st.text_input("Process ID", value=f"P{len(st.session_state.process_rows) + 1}")
            arrival = st.number_input("Arrival Time", min_value=0, step=1, value=0)
            burst = st.number_input("Burst Time", min_value=1, step=1, value=5)
            priority = st.number_input("Priority", min_value=1, step=1, value=1)
            submitted = st.form_submit_button("Save Process", use_container_width=True)
            if submitted:
                add_or_update_process(pid, arrival, burst, priority)
                st.success(f"Saved {pid.strip() or 'new process'}.")

        pid_choices = [row["PID"] for row in st.session_state.process_rows]
        selected_pid = st.selectbox("Delete Process", options=pid_choices if pid_choices else [""])
        if st.button("Remove Selected", use_container_width=True, disabled=not pid_choices):
            delete_process_row(selected_pid)
            st.success(f"Removed {selected_pid}.")

    with right:
        edited_df = st.data_editor(
            process_table_df(),
            num_rows="dynamic",
            use_container_width=True,
            key="process_editor",
        )
        if st.button("Sync Table Changes", use_container_width=True):
            normalized = edited_df.fillna(0).to_dict(orient="records")
            st.session_state.process_rows = [
                {
                    "PID": str(row["PID"]).strip() or f"P{idx + 1}",
                    "Arrival": int(row["Arrival"]),
                    "Burst": max(1, int(row["Burst"])),
                    "Priority": max(1, int(row["Priority"])),
                }
                for idx, row in enumerate(normalized)
            ]
            st.success("Table changes synchronized.")


def render_static_evaluation(processes: Processes, rows: list[dict[str, Any]], config: dict[str, int]) -> algorithms.LoadBalancing:
    st.markdown("## Static Evaluation")
    schedulers = run_schedulers(
        processes=processes,
        num_cpu=config["num_cpu"],
        rr_quantum=config["rr_quantum"],
        affinity_quantum=config["affinity_quantum"],
        threshold=config["threshold"],
        migration_overhead=config["migration_overhead"],
    )

    pid_map = {idx + 1: row["PID"] for idx, row in enumerate(sorted(rows, key=lambda item: (item["Arrival"], item["PID"])))}
    metric_rows = []
    selected_name = st.segmented_control(
        "Timeline Algorithm",
        options=[scheduler.algorithm_name for scheduler in schedulers],
        default="Load Balancing",
    )

    selected_scheduler = next(s for s in schedulers if s.algorithm_name == selected_name)

    for scheduler in schedulers:
        metrics = scheduler_metrics(scheduler, len(rows))
        migration_count = len(getattr(scheduler, "migration_events", []))
        metric_rows.append(
            {
                "Algorithm": scheduler.algorithm_name,
                "CPU Utilization": f"{metrics['cpu_utilization']:.2%}",
                "Throughput": f"{metrics['throughput']:.4f}",
                "Total Time": metrics["total_time"],
                "Migration Events": migration_count,
            }
        )

    gantt_df = gantt_dataframe(
        selected_scheduler,
        pid_map,
        getattr(selected_scheduler, "migration_events", []),
    )
    fig = timeline_figure(gantt_df, config["num_cpu"])
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)

    summary_cols = st.columns(3)
    selected_metrics = scheduler_metrics(selected_scheduler, len(rows))
    summary_cols[0].metric("CPU Utilization", f"{selected_metrics['cpu_utilization']:.2%}")
    summary_cols[1].metric("Throughput", f"{selected_metrics['throughput']:.4f}")
    summary_cols[2].metric("Migration Events", str(len(getattr(selected_scheduler, "migration_events", []))))

    st.dataframe(pd.DataFrame(metric_rows), use_container_width=True, hide_index=True)
    #! code hiện tại đang return lại load_balancing để start bước visualize, nhưng bước này cần làm cho mọi algo, cần sửa
    return next(s for s in schedulers if s.algorithm_name == "Load Balancing")


def render_queue_snapshot(snapshot: dict[str, Any], events: list[dict[str, Any]], num_cpu: int, pid_map: dict[int, str]) -> None:
    header_left, header_right = st.columns([1, 2])
    header_left.metric("Current Time", f"t = {snapshot['time']}")
    if events:
        lines = []
        for event in events:
            pid = pid_map.get(event["process_id"], f"P{event['process_id']}")
            lines.append(
                f"{event['reason'].upper()}: {pid} moved CPU {event['from_cpu'] + 1} -> CPU {event['to_cpu'] + 1}"
            )
        header_right.warning(" | ".join(lines))
    else:
        header_right.info("No migration event at this time.")

    cols = st.columns(num_cpu)
    for cpu_id in range(num_cpu):
        queue = snapshot["queues"].get(cpu_id, [])
        with cols[cpu_id]:
            st.markdown(f"### CPU {cpu_id + 1}")
            if not queue:
                st.caption("Idle")
                continue
            for index, process_id in enumerate(queue):
                label = pid_map.get(process_id, f"P{process_id}")
                if index == 0:
                    st.success(f"{label} | RUNNING")
                else:
                    st.warning(f"{label} | WAITING")


def render_visualization(load_balancer: algorithms.LoadBalancing, rows: list[dict[str, Any]], num_cpu: int) -> None:
    st.markdown("## Dynamic Visualization")
    if not load_balancer.history:
        st.info("Run evaluation first to generate simulation history.")
        return

    ordered_rows = sorted(rows, key=lambda item: (item["Arrival"], item["PID"]))
    pid_map = {idx + 1: row["PID"] for idx, row in enumerate(ordered_rows)}
    frame_times = [snapshot["time"] for snapshot in load_balancer.history]
    min_time = min(frame_times)
    max_time = max(frame_times)
    selected_time = st.slider("Time Frame", min_value=min_time, max_value=max_time, value=min_time, step=1)
    snapshot = next(item for item in load_balancer.history if item["time"] == selected_time)
    events = [event for event in load_balancer.migration_events if event["time"] == selected_time]
    render_queue_snapshot(snapshot, events, num_cpu, pid_map)

    speed = st.slider("Playback Delay (seconds)", min_value=0.1, max_value=1.5, value=0.4, step=0.1)
    if st.button("Play Live Visualization", use_container_width=True):
        frame_placeholder = st.empty()
        for frame in load_balancer.history:
            frame_events = [event for event in load_balancer.migration_events if event["time"] == frame["time"]]
            with frame_placeholder.container():
                render_queue_snapshot(frame, frame_events, num_cpu, pid_map)
            time.sleep(speed)


def main() -> None:
    st.set_page_config(page_title="Multiprocessor Scheduling Dashboard", layout="wide")
    ensure_state()

    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(22, 163, 74, 0.08), transparent 28%),
                linear-gradient(180deg, #f5f7f3 0%, #eef2ea 100%);
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3 {
            letter-spacing: -0.02em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("Multiprocessor Scheduling Dashboard")
    st.caption("CRUD process pool, evaluate multiple schedulers, and replay real load-balancing behavior.")

    with st.sidebar:
        #@ place to add slider for parameters
        st.markdown("## Scheduler Config")
        num_cpu = st.slider("CPU Count", min_value=2, max_value=8, value=4, step=1)
        rr_quantum = st.slider("GLB_RR Quantum", min_value=1, max_value=20, value=15, step=1)
        affinity_quantum = st.slider("CPU Affinity Quantum", min_value=1, max_value=20, value=5, step=1)
        threshold = st.slider("Load Balancing Threshold", min_value=0, max_value=20, value=2, step=1)
        migration_overhead = st.slider("Migration Overhead", min_value=0, max_value=10, value=1, step=1)

    render_process_management()

    st.markdown("---")
    rows = st.session_state.process_rows
    if not rows:
        st.warning("Add at least one process to run the schedulers.")
        return

    processes = build_processes(rows)
    config = {
        "num_cpu": num_cpu,
        "rr_quantum": rr_quantum,
        "affinity_quantum": affinity_quantum,
        "threshold": threshold,
        "migration_overhead": migration_overhead,
    }
    load_balancer = render_static_evaluation(processes, rows, config)

    st.markdown("---")
    render_visualization(load_balancer, rows, num_cpu)


if __name__ == "__main__":
    main()
