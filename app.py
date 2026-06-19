import time
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import algorithms
from Process_options import *
from process import Process, Processes
from process.process import InvalidInputError, MaxProcessesError


def ensure_state() -> None:
    if "process_rows" not in st.session_state:
        st.session_state.process_rows = [row.copy() for row in PROCESSES_1]
    if "process_editor_revision" not in st.session_state:
        st.session_state.process_editor_revision = 0


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


def next_available_pid(rows: list[dict[str, Any]]) -> str:
    used = {str(row["PID"]).strip() for row in rows}
    index = 1
    while f"P{index}" in used:
        index += 1
    return f"P{index}"


def add_or_update_process(pid: str, arrival: int, burst: int, priority: int) -> None:
    normalized_pid = pid.strip() or next_available_pid(st.session_state.process_rows)
    new_row = {
        "PID": normalized_pid,
        "Arrival": int(arrival),
        "Burst": int(burst),
        "Priority": int(priority),
    }
    for idx, row in enumerate(st.session_state.process_rows):
        if row["PID"] == new_row["PID"]:
            st.session_state.process_rows[idx] = new_row
            return
    if len(st.session_state.process_rows) >= Processes.MAX:
        raise ValueError(f"A maximum of {Processes.MAX} processes is supported.")
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
    first_migration_time: dict[int, int] = {}
    for event in migration_events or []:
        process_id = event["process_id"]
        first_migration_time[process_id] = min(
            event["time"],
            first_migration_time.get(process_id, event["time"]),
        )
    rows: list[dict[str, Any]] = []
    for cpu_id, steps in scheduler.steps.items():
        for step in steps:
            pid_label = pid_map.get(step.process_id, f"P{step.process_id}")
            if step.begin_time >= first_migration_time.get(step.process_id, float("inf")):
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
    max_time = int(chart_df["Finish"].max())
    tick_step = max(1, (max_time + 9) // 10)
    tick_values = list(range(0, max_time + 1, tick_step))
    if not tick_values or tick_values[-1] != max_time:
        tick_values.append(max_time)
    fig.update_xaxes(
        title="Simulation Time",
        tickmode="array",
        tickvals=[base_time + pd.to_timedelta(value, unit="s") for value in tick_values],
        ticktext=[str(value) for value in tick_values],
    )
    return fig


def process_color_map(pid_map: dict[int, str]) -> dict[int, str]:
    palette = (
        px.colors.qualitative.Plotly
        + px.colors.qualitative.Safe
        + px.colors.qualitative.Dark24
    )
    return {pid: palette[index % len(palette)] for index, pid in enumerate(sorted(pid_map))}


def snapshot_cpu_state(snapshot: dict[str, Any], cpu_id: int) -> tuple[int | None, list[int]]:
    queue = list(snapshot.get("queues", {}).get(cpu_id, []))
    running = snapshot.get("running")
    if running is None:
        return (queue[0], queue[1:]) if queue else (None, [])
    running_pid = running.get(cpu_id)
    waiting_queue = [pid for pid in queue if pid != running_pid]
    return running_pid, waiting_queue


def snapshot_global_waiting(snapshot: dict[str, Any], num_cpu: int) -> tuple[list[int], bool]:
    running_ids = {
        running_pid
        for cpu_id in range(num_cpu)
        for running_pid, _ in [snapshot_cpu_state(snapshot, cpu_id)]
        if running_pid is not None
    }
    if snapshot.get("global_queue") is not None:
        queue = list(snapshot["global_queue"])
        is_explicit = True
    else:
        queue = []
        for cpu_id in range(num_cpu):
            _, waiting_queue = snapshot_cpu_state(snapshot, cpu_id)
            queue.extend(waiting_queue)
        is_explicit = False
    return list(dict.fromkeys(pid for pid in queue if pid not in running_ids)), is_explicit


def build_live_figure(history: list[dict], pid_map: dict[int, str], num_cpu: int, show_per_cpu_local_queues: bool = False):
    """Build a Plotly Figure with animation frames from LoadBalancing.history.

    If show_per_cpu_local_queues is True, visualize each CPU's queue (running + waiting) in its own column.
    Otherwise, visualize RUNNING per CPU on the left and a GLOBAL QUEUE row under CPUs ordered by enqueue time.
    """
    if not history:
        return None

    color_map = process_color_map(pid_map)

    frames = []

    if show_per_cpu_local_queues:
        # --- NHÁNH 1: HIỂN THỊ ĐA HÀNG ĐỢI CỤC BỘ (LOCAL QUEUES) ---
        max_local_len = 1
        for frame in history:
            for cpu_id in range(num_cpu):
                running_pid, waiting_queue = snapshot_cpu_state(frame, cpu_id)
                stack_len = len(waiting_queue) + (1 if running_pid is not None else 0)
                max_local_len = max(max_local_len, stack_len)

        for frame in history:
            t = frame["time"]
            block_x, block_y, block_text, block_colors = [], [], [], []
            annotations = []

            header_y = max_local_len + 0.3
            for cpu_id in range(num_cpu):
                col_x = cpu_id * 2 + 0.5
                annotations.append(dict(x=col_x, y=header_y, text=f"CPU {cpu_id + 1}", showarrow=False, font=dict(size=12, family="Arial", color="#000000")))

            for cpu_id in range(num_cpu):
                running_pid, waiting_queue = snapshot_cpu_state(frame, cpu_id)
                q = ([running_pid] if running_pid is not None else []) + waiting_queue
                col_x = cpu_id * 2 + 0.5
                for idx, pid in enumerate(q):
                    y_center = header_y - 0.6 - idx * 0.9
                    block_x.append(col_x)
                    block_y.append(y_center)
                    block_text.append(pid_map.get(pid, f"P{pid}"))
                    block_colors.append(color_map.get(pid, "#888"))

            data = [
                go.Scatter(
                    x=block_x, y=block_y, mode="markers+text", text=block_text,
                    textposition="middle center", textfont=dict(color="#000000", size=12),
                    marker=dict(symbol="square", size=54, color=block_colors, line=dict(color="#222", width=1)),
                    hoverinfo="text", showlegend=False
                )
            ]
            frames.append(dict(name=str(t), data=data, layout=dict(annotations=annotations, title_text=f"t = {t}")))

        x_max = num_cpu * 2
        y_max = max_local_len + 1
        initial_data = frames[0]["data"] if frames else []
        fig = go.Figure(data=initial_data, layout=dict(xaxis=dict(range=[0, x_max], showgrid=False, visible=False), yaxis=dict(range=[-1, y_max], showgrid=False, visible=False), height=200 + y_max * 60, margin=dict(l=40, r=16, t=40, b=16)), frames=frames)

    else:
        # --- NHÁNH 2: HIỂN THỊ HÀNG ĐỢI TẬP TRUNG (GLOBAL QUEUE) ---
        # Tính toán thời gian Enqueue để phục vụ sắp xếp hàng đợi toàn cục
        enqueue_times: dict[int, int] = {}
        frames_temp = []
        max_wait_len = 0

        for frame in history:
            t = frame["time"]
            current_waiting, is_explicit_queue = snapshot_global_waiting(frame, num_cpu)

            for pid in current_waiting:
                if pid not in enqueue_times:
                    enqueue_times[pid] = t
            for pid in list(enqueue_times.keys()):
                if pid not in current_waiting:
                    del enqueue_times[pid]

            waiting_order = (
                current_waiting
                if is_explicit_queue
                else sorted(current_waiting, key=lambda pid: (enqueue_times.get(pid, t), pid))
            )
            max_wait_len = max(max_wait_len, len(waiting_order))
            frames_temp.append((t, waiting_order, frame))

        # Khởi tạo tọa độ tâm cho cột xử lý
        processing_x_center = 0.5
        waiting_y_center = -1.0

        for t, waiting_sorted, frame in frames_temp:
            block_x, block_y, block_text, block_colors = [], [], [], []
            annotations = []

            header_y = num_cpu + 0.3
            annotations.append(dict(x=processing_x_center, y=header_y, text="PROCESSING", showarrow=False, font=dict(size=12, family="Arial", color="#000000")))
            annotations.append(dict(x=(1.5 + (1.5 + max_wait_len)) / 2, y=header_y, text="GLOBAL QUEUE", showarrow=False, font=dict(size=12, family="Arial", color="#000000")))

            # FIX: Chuyển dữ liệu RUNNING CPU từ layout.shapes sang data (go.Scatter) để update động mượt mà
            for cpu_id in range(num_cpu):
                pid, _ = snapshot_cpu_state(frame, cpu_id)
                if pid is not None:
                    y_center = num_cpu - cpu_id - 1 + 0.4
                    block_x.append(processing_x_center)
                    block_y.append(y_center)
                    block_text.append(pid_map.get(pid, f"P{pid}"))
                    block_colors.append(color_map.get(pid, "#888"))

            # FIX: Sửa lỗi đè tọa độ bằng cách dịch tâm bắt đầu từ x = 1.5 trở đi (processing chiếm từ 0 -> 1)
            for idx, pid in enumerate(waiting_sorted):
                x_center = 1.5 + idx
                block_x.append(x_center)
                block_y.append(waiting_y_center)
                block_text.append(pid_map.get(pid, f"P{pid}"))
                block_colors.append(color_map.get(pid, "#888"))

            data = [
                go.Scatter(
                    x=block_x, y=block_y, mode="markers+text", text=block_text,
                    textposition="middle center", textfont=dict(color="#000000", size=12),
                    marker=dict(symbol="square", size=48, color=block_colors, line=dict(color="#222", width=1)),
                    hoverinfo="text", showlegend=False
                )
            ]
            frames.append(dict(name=str(t), data=data, layout=dict(annotations=annotations, title_text=f"t = {t}")))

        x_max = max(max_wait_len + 2, 4)
        initial_data = frames[0]["data"] if frames else []
        fig = go.Figure(
            data=initial_data,
            layout=dict(
                xaxis=dict(range=[0, x_max], showgrid=False, visible=False),
                yaxis=dict(range=[-1.7, num_cpu + 0.5], showgrid=False, tickmode="array", tickvals=[i + 0.4 for i in range(num_cpu)], ticktext=[f"CPU {num_cpu - i}" for i in range(num_cpu)], autorange=False),
                height=260 + num_cpu * 80, margin=dict(l=40, r=16, t=40, b=16)
            ),
            frames=frames
        )

    # Cấu hình Animation điều khiển mượt mà không delay
    if frames:
        fig.update_layout(frames[0]["layout"])

    fig.update_layout(
        updatemenus=[{
            "type": "buttons",
            "buttons": [
                {"label": "Play", "method": "animate", "args": [None, {"frame": {"duration": 400, "redraw": True}, "fromcurrent": True, "transition": {"duration": 0}}]},
                {"label": "Pause", "method": "animate", "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}]}
            ],
            "direction": "left", "pad": {"r": 10, "t": 10}, "showactive": True, "x": 0.1, "y": -0.05
        }],
        sliders=[{
            "active": 0, "y": -0.1, "x": 0.1, "len": 0.9,
            "currentvalue": {"prefix": "Time: ", "visible": True},
            "steps": [{"label": f"{f['name']}", "method": "animate", "args": [[f['name']], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}]} for f in frames]
        }]
    )
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig

def run_schedulers(
    processes: Processes,
    num_cpu: int,
    rr_quantum: int,
    affinity_quantum: int,
    work_stealing_quantum: int,
    work_stealing_strategy: str,
    threshold: int,
    migration_overhead: int,
):
    runners = [
        algorithms.GLB_FIFO(num_cpu=num_cpu),
        algorithms.GLB_RR(num_cpu=num_cpu, time_quantum=rr_quantum),
        algorithms.PAR_FIFO(num_cpu=num_cpu),
        algorithms.CPU_Affinity(num_cpu=num_cpu, time_quantum=affinity_quantum, hard=True),
        algorithms.Work_Stealing(
            num_cpu=num_cpu,
            time_quantum=work_stealing_quantum,
            strat=work_stealing_strategy,
            migration_overhead=migration_overhead,
        ),
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
            pid = st.text_input("Process ID", value=next_available_pid(st.session_state.process_rows))
            arrival = st.number_input("Arrival Time", min_value=0, step=1, value=0)
            burst = st.number_input("Burst Time", min_value=1, step=1, value=5)
            priority = st.number_input("Priority", min_value=1, step=1, value=1)
            submitted = st.form_submit_button("Save Process", width="stretch")
            if submitted:
                try:
                    add_or_update_process(pid, arrival, burst, priority)
                    st.success(f"Saved {pid.strip() or 'new process'}.")
                except ValueError as exc:
                    st.error(str(exc))

        pid_choices = [row["PID"] for row in st.session_state.process_rows]
        selected_pid = st.selectbox("Delete Process", options=pid_choices if pid_choices else [""])
        if st.button("Remove Selected", width="stretch", disabled=not pid_choices):
            delete_process_row(selected_pid)
            st.success(f"Removed {selected_pid}.")

    with right:
        edited_df = st.data_editor(
            process_table_df(),
            num_rows="dynamic",
            width="stretch",
            column_config={
                "PID": st.column_config.TextColumn("PID", required=True),
                "Arrival": st.column_config.NumberColumn("Arrival", min_value=0, step=1, required=True),
                "Burst": st.column_config.NumberColumn("Burst", min_value=1, step=1, required=True),
                "Priority": st.column_config.NumberColumn("Priority", min_value=1, step=1, required=True),
            },
            key=f"process_editor_{st.session_state.process_editor_revision}",
        )
        if st.button("Sync Table Changes", width="stretch"):
            try:
                normalized = edited_df.fillna("").to_dict(orient="records")
                if len(normalized) > Processes.MAX:
                    raise ValueError(f"A maximum of {Processes.MAX} processes is supported.")
                next_rows = []
                seen_pids = set()
                for idx, row in enumerate(normalized):
                    pid_value = str(row["PID"]).strip() or f"P{idx + 1}"
                    if pid_value in seen_pids:
                        st.error(f"Duplicate PID: {pid_value}")
                        return
                    seen_pids.add(pid_value)
                    numeric_values = (row["Arrival"], row["Burst"], row["Priority"])
                    if any(
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not float(value).is_integer()
                        for value in numeric_values
                    ):
                        raise ValueError("Arrival, Burst, and Priority must be valid integers.")
                    next_rows.append(
                        {
                            "PID": pid_value,
                            "Arrival": max(0, int(row["Arrival"])),
                            "Burst": max(1, int(row["Burst"])),
                            "Priority": max(1, int(row["Priority"])),
                        }
                    )
                st.session_state.process_rows = next_rows
                st.success("Table changes synchronized.")
            except (TypeError, ValueError) as exc:
                st.error(str(exc) or "Arrival, Burst, and Priority must be valid integers.")


def render_static_evaluation(processes: Processes, rows: list[dict[str, Any]], config: dict[str, Any]):
    st.markdown("## Static Evaluation")
    schedulers = run_schedulers(
        processes=processes,
        num_cpu=config["num_cpu"],
        rr_quantum=config["rr_quantum"],
        affinity_quantum=config["affinity_quantum"],
        work_stealing_quantum=config["work_stealing_quantum"],
        work_stealing_strategy=config["work_stealing_strategy"],
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
        st.plotly_chart(fig, width="stretch")

    summary_cols = st.columns(3)
    selected_metrics = scheduler_metrics(selected_scheduler, len(rows))
    summary_cols[0].metric("CPU Utilization", f"{selected_metrics['cpu_utilization']:.2%}")
    summary_cols[1].metric("Throughput", f"{selected_metrics['throughput']:.4f}")
    summary_cols[2].metric("Migration Events", str(len(getattr(selected_scheduler, "migration_events", []))))

    st.dataframe(pd.DataFrame(metric_rows), width="stretch", hide_index=True)
    return selected_scheduler


def step_history(scheduler, num_cpu: int) -> list[dict[str, Any]]:
    all_steps = [step for steps in scheduler.steps.values() for step in steps]
    if not all_steps:
        return []

    min_time = min(step.begin_time for step in all_steps)
    max_time = max(step.end_time for step in all_steps)
    history = []
    for current_time in range(min_time, max_time):
        queues = {cpu_id: [] for cpu_id in range(num_cpu)}
        running_by_cpu = {cpu_id: None for cpu_id in range(num_cpu)}
        for cpu_id, steps in scheduler.steps.items():
            running = [
                step.process_id
                for step in steps
                if step.begin_time <= current_time < step.end_time
            ]
            if running:
                running_by_cpu[cpu_id] = running[-1]
        history.append(
            {
                "time": current_time,
                "running": running_by_cpu,
                "queues": queues,
                "loads": {cpu_id: len(queues[cpu_id]) for cpu_id in range(num_cpu)},
            }
        )
    return history


def render_queue_snapshot(snapshot: dict[str, Any], events: list[dict[str, Any]] | None, num_cpu: int, pid_map: dict[int, str], show_per_cpu_local_queues: bool = False) -> None:
    header_left, header_right = st.columns([1, 2])
    header_left.metric("Current Time", f"t = {snapshot['time']}")
    if events is None:
        header_right.info("Timeline replay from recorded schedule steps.")
    elif events:
        lines = []
        for event in events:
            pid = pid_map.get(event["process_id"], f"P{event['process_id']}")
            lines.append(
                f"{event['reason'].upper()}: {pid} moved CPU {event['from_cpu'] + 1} -> CPU {event['to_cpu'] + 1}"
            )
        header_right.warning(" | ".join(lines))
    else:
        header_right.info("No migration event at this time.")

    if show_per_cpu_local_queues:
        # One column per CPU, show RUNNING + local waiting under each CPU (snapshot-like)
        cols = st.columns([1] * num_cpu)
        for cpu_id in range(num_cpu):
            running_pid, waiting_queue = snapshot_cpu_state(snapshot, cpu_id)
            with cols[cpu_id]:
                st.markdown(f"### CPU {cpu_id + 1}")
                if running_pid is None and not waiting_queue:
                    st.caption("Idle")
                else:
                    if running_pid is not None:
                        label = pid_map.get(running_pid, f"P{running_pid}")
                        st.success(f"{label} | RUNNING")
                    for index, process_id in enumerate(waiting_queue):
                        label = pid_map.get(process_id, f"P{process_id}")
                        st.warning(f"{index + 1}. {label}")
    else:
        # Create columns: one per CPU and one for the global waiting queue
        cols = st.columns([1] * num_cpu + [1.2])

        # Compute global waiting queue (prefer explicit snapshot 'global_queue')
        global_waiting, _ = snapshot_global_waiting(snapshot, num_cpu)

        # Render CPU columns showing only the RUNNING item
        for cpu_id in range(num_cpu):
            running_pid, _ = snapshot_cpu_state(snapshot, cpu_id)
            with cols[cpu_id]:
                st.markdown(f"### CPU {cpu_id + 1}")
                if running_pid is None:
                    st.caption("Idle")
                else:
                    label = pid_map.get(running_pid, f"P{running_pid}")
                    st.success(f"{label} | RUNNING")

        # Render global waiting column
        with cols[-1]:
            st.markdown("### Global Queue")
            if not global_waiting:
                st.caption("No waiting processes")
            else:
                for idx, pid in enumerate(global_waiting):
                    label = pid_map.get(pid, f"P{pid}")
                    st.warning(f"{idx + 1}. {label}")


def render_visualization(scheduler, rows: list[dict[str, Any]], num_cpu: int) -> None:
    st.markdown("## Dynamic Visualization")
    has_queue_history = bool(getattr(scheduler, "history", []))
    history = scheduler.history if has_queue_history else step_history(scheduler, num_cpu)
    if not history:
        st.info("Run evaluation first to generate simulation history.")
        return
    if has_queue_history:
        st.caption(f"Queue replay for {scheduler.algorithm_name}.")
    else:
        st.caption(f"Execution replay for {scheduler.algorithm_name}. Queue waiting state is not recorded by this scheduler.")

    ordered_rows = sorted(rows, key=lambda item: (item["Arrival"], item["PID"]))
    pid_map = {idx + 1: row["PID"] for idx, row in enumerate(ordered_rows)}

    # Small, immediate snapshot control (keeps original UI behaviour)
    frame_times = [snapshot["time"] for snapshot in history]
    selected_time = st.select_slider("Time Frame", options=frame_times, value=frame_times[0])
    snapshot = next(item for item in history if item["time"] == selected_time)
    migration_events = getattr(scheduler, "migration_events", None)
    events = None if migration_events is None else [event for event in migration_events if event["time"] == selected_time]
    show_per_cpu = getattr(scheduler, "queue_scope", "global") == "local"
    render_queue_snapshot(snapshot, events, num_cpu, pid_map, show_per_cpu_local_queues=show_per_cpu)

    # Build animated figure (client-side frames) and render
    fig = build_live_figure(history, pid_map, num_cpu, show_per_cpu_local_queues=show_per_cpu)
    if fig is None:
        st.info("No visualization frames available.")
        return
    st.plotly_chart(fig, width="stretch")


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
        st.markdown("## Process Workload")
        selected_process_set = st.selectbox(
            "Benchmark Set",
            options=list(PROCESS_SET_OPTIONS),
        )
        selected_process_info = PROCESS_SET_OPTIONS[selected_process_set]
        st.caption(selected_process_info["reason"])
        st.caption(f"Expected makespan with default settings: {selected_process_info['expected']}")
        if st.button("Load Selected Set", width="stretch"):
            st.session_state.process_rows = [
                row.copy() for row in selected_process_info["processes"]
            ]
            st.session_state.process_editor_revision += 1
            st.rerun()

        #@ place to add slider for parameters
        st.markdown("## Scheduler Config")
        num_cpu = st.slider("CPU Count", min_value=2, max_value=8, value=4, step=1)
        rr_quantum = st.slider("GLB_RR Quantum", min_value=1, max_value=20, value=15, step=1)
        affinity_quantum = st.slider("CPU Affinity Quantum", min_value=1, max_value=20, value=5, step=1)
        work_stealing_quantum = st.slider("Work Stealing Quantum", min_value=1, max_value=20, value=5, step=1)
        work_stealing_strategy = st.selectbox(
            "Work Stealing Strategy",
            options=["shortest_queue", "least_load", "power_of_two"],
        )
        threshold = st.slider("Load Balancing Threshold", min_value=0, max_value=20, value=2, step=1)
        migration_overhead = st.slider("Migration Overhead", min_value=0, max_value=10, value=1, step=1)

    render_process_management()

    st.markdown("---")
    rows = st.session_state.process_rows
    if not rows:
        st.warning("Add at least one process to run the schedulers.")
        return

    try:
        processes = build_processes(rows)
    except (InvalidInputError, MaxProcessesError, TypeError, ValueError) as exc:
        st.error(f"Invalid process data: {exc}")
        return
    config = {
        "num_cpu": num_cpu,
        "rr_quantum": rr_quantum,
        "affinity_quantum": affinity_quantum,
        "work_stealing_quantum": work_stealing_quantum,
        "work_stealing_strategy": work_stealing_strategy,
        "threshold": threshold,
        "migration_overhead": migration_overhead,
    }
    selected_scheduler = render_static_evaluation(processes, rows, config)

    st.markdown("---")
    render_visualization(selected_scheduler, rows, num_cpu)


if __name__ == "__main__":
    main()
