# `app.py` Explanation

`app.py` is the main Streamlit application for the multiprocessor scheduling dashboard. It builds a web UI where users can add/edit/delete processes, choose scheduler settings, run several scheduling algorithms, compare their metrics, and replay the load-balancing simulation over time.

This file does not implement most scheduling algorithms itself. It imports them from the `algorithms` package. Its main job is to connect user input, scheduler execution, result formatting, and visual display.

## Libraries and Project Imports

```python
import time
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

import algorithms
from process import Process, Processes
```

- `time` is used for playback delay in the live visualization.
- `Any` is used in type hints for dictionaries that can contain different value types.
- `pandas` creates and edits tabular data.
- `plotly.express` builds the Gantt-style timeline chart.
- `streamlit` creates the web interface.
- `algorithms` gives access to `GLB_RR`, `CPU_Affinity`, and `LoadBalancing`.
- `Process` and `Processes` are project classes used to represent scheduler input.

Streamlit programs run top-to-bottom every time the user changes a widget or clicks a button. Because of that, persistent UI data must be stored in `st.session_state`.

## Default Processes

```python
DEFAULT_PROCESSES = [
    {"PID": "P1", "Arrival": 0, "Burst": 32, "Priority": 2},
    ...
]
```

This is the initial process list shown in the app. Each process row has:

- `PID`: display label shown to the user, such as `P1`.
- `Arrival`: time when the process becomes available.
- `Burst`: total CPU time needed.
- `Priority`: priority value. The current UI stores it, but the algorithms shown in this app mostly use arrival/burst and scheduler-specific behavior.

## Session State Setup

```python
def ensure_state() -> None:
    if "process_rows" not in st.session_state:
        st.session_state.process_rows = DEFAULT_PROCESSES.copy()
```

Streamlit reruns `app.py` after interactions. Normal Python variables reset during each rerun. `st.session_state` keeps values between reruns for the current browser session.

`ensure_state()` checks whether the app already has `process_rows`. If not, it initializes the list from `DEFAULT_PROCESSES`.

Important detail: `DEFAULT_PROCESSES.copy()` is a shallow copy. It creates a new list, but each dictionary inside is still the same dictionary object from `DEFAULT_PROCESSES`. In normal app use this is usually fine because later code replaces whole row dictionaries, but a deep copy would be safer if rows were modified in place.

## Converting UI Rows Into Scheduler Objects

```python
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
```

The UI stores processes as dictionaries because that format works well with tables and forms. The scheduler classes expect a `Processes` object containing `Process` objects.

`build_processes()` performs that conversion:

1. Sort rows by arrival time, then by PID.
2. Create a new `Processes()` container.
3. For each row, create a `Process`.
4. Add it to the container.
5. Return the scheduler-ready object.

The `Processes.add()` method assigns internal numeric IDs starting from 1. These internal IDs are what scheduler results use. The visible PID labels, such as `P1`, are mapped back later for charts.

## Turning Process Rows Into a Table

```python
def process_table_df() -> pd.DataFrame:
    return pd.DataFrame(st.session_state.process_rows)
```

Streamlit table widgets work naturally with pandas DataFrames. This function converts the stored list of dictionaries into a DataFrame for display and editing.

## Adding or Updating a Process

```python
def add_process_row(pid: str, arrival: int, burst: int, priority: int) -> None:
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
```

This function handles the "Save Process" form.

If the user leaves PID blank, the app creates a default PID like `P7`. If the PID already exists, the existing row is replaced. If it does not exist, the new row is appended.

This means the form acts as both "add new process" and "update existing process".

## Deleting a Process

```python
def delete_process_row(pid: str) -> None:
    st.session_state.process_rows = [row for row in st.session_state.process_rows if row["PID"] != pid]
```

This removes every row whose `PID` matches the selected PID. It rebuilds the list and stores it back into session state.

## Scheduler Metrics

```python
def scheduler_metrics(scheduler, process_count: int) -> dict[str, float]:
    total_time = max((step.end_time for steps in scheduler.steps.values() for step in steps), default=0)
    busy_time = sum(step.end_time - step.begin_time for steps in scheduler.steps.values() for step in steps)
    utilization = 0.0 if total_time == 0 else busy_time / (scheduler.num_cpu * total_time)
    throughput = 0.0 if total_time == 0 else process_count / total_time
    return {...}
```

Schedulers produce `steps`. A step represents one continuous run of one process on one CPU:

```python
ScheduleStep(process_id, begin_time, end_time, cpu_id)
```

This function calculates:

- `total_time`: end time of the latest schedule step.
- `busy_time`: total CPU time actually spent running processes.
- `cpu_utilization`: `busy_time / (number of CPUs * total_time)`.
- `throughput`: `number of processes / total_time`.

If no work has run, it avoids division by zero and returns `0.0`.

## Building Data for the Gantt Chart

```python
def gantt_dataframe(scheduler, pid_map: dict[int, str], migration_events: list[dict[str, Any]] | None = None) -> pd.DataFrame:
    migrated_ids = {event["process_id"] for event in (migration_events or [])}
    rows: list[dict[str, Any]] = []
    for cpu_id, steps in scheduler.steps.items():
        for step in steps:
            pid_label = pid_map.get(step.process_id, f"P{step.process_id}")
            if step.process_id in migrated_ids:
                pid_label = f"{pid_label} *"
            rows.append(...)
    return pd.DataFrame(rows)
```

Plotly needs table-like data. This function converts scheduler steps into chart rows with:

- process label,
- CPU label,
- start time,
- finish time.

`pid_map` converts internal numeric process IDs back to visible labels from the UI. For example, internal ID `1` may map to `P1`.

If a process appears in load-balancing migration events, the label gets `*`. That makes migrated processes visible in the chart legend and bars.

## Creating the Timeline Figure

```python
def timeline_figure(df: pd.DataFrame, num_cpu: int):
    if df.empty:
        return None
```

If there are no steps, there is no chart.

```python
base_time = pd.Timestamp("2026-01-01 00:00:00")
chart_df["Start_Time"] = base_time + pd.to_timedelta(chart_df["Start"], unit="s")
chart_df["Finish_Time"] = base_time + pd.to_timedelta(chart_df["Finish"], unit="s")
```

Plotly's `px.timeline()` expects date/time values for start and end. The scheduler uses plain integer simulation time. The app converts each integer into a timestamp by adding seconds to a fake base date.

```python
fig = px.timeline(
    chart_df,
    x_start="Start_Time",
    x_end="Finish_Time",
    y="CPU",
    color="Process",
    text="Process",
)
```

This creates horizontal bars:

- x-axis = simulation time,
- y-axis = CPU,
- color = process,
- text inside each bar = process label.

The x-axis display is formatted as seconds with:

```python
fig.update_xaxes(tickformat="%S", title="Simulation Time")
```

The y-axis is ordered so CPU 1 appears near the top in a predictable order.

## Running All Schedulers

```python
def run_schedulers(processes: Processes, num_cpu: int, rr_quantum: int, affinity_quantum: int, threshold: int, migration_overhead: int):
    runners = [
        algorithms.GLB_RR(num_cpu=num_cpu, time_quantum=rr_quantum),
        algorithms.CPU_Affinity(num_cpu=num_cpu, time_quantum=affinity_quantum, hard=True),
        algorithms.LoadBalancing(num_cpu=num_cpu, threshold=threshold, migration_overhead=migration_overhead),
    ]
    for scheduler in runners:
        scheduler.estimate(processes.copy())
    return runners
```

This function creates one scheduler object for each algorithm:

- `GLB_RR`: global round-robin scheduler.
- `CPU_Affinity`: keeps processes tied to CPUs after assignment when `hard=True`.
- `LoadBalancing`: places work on CPU queues and migrates processes when load imbalance is too large.

Each scheduler receives `processes.copy()`. This matters because schedulers modify `remaining_time` while simulating. Without copying, the first algorithm could consume the process burst times and break later algorithms.

After `estimate()` runs, each scheduler has result data such as `steps`. The load-balancing scheduler also stores `history` and `migration_events`, which the dynamic visualization uses.

## Process Management UI

```python
def render_process_management() -> None:
    st.markdown("## Process Management")
    left, right = st.columns([1, 1.7])
```

This function draws the process editing area. It splits the page into two columns:

- left column: form for adding/updating and dropdown for deleting,
- right column: editable table.

### Add/Update Form

```python
with st.form("process_form", clear_on_submit=True):
    pid = st.text_input("Process ID", value=f"P{len(st.session_state.process_rows) + 1}")
    arrival = st.number_input("Arrival Time", min_value=0, step=1, value=0)
    burst = st.number_input("Burst Time", min_value=1, step=1, value=5)
    priority = st.number_input("Priority", min_value=1, step=1, value=1)
    submitted = st.form_submit_button("Save Process", use_container_width=True)
```

`st.form()` groups inputs so changing numbers does not immediately save. User edits fields, then clicks "Save Process".

When submitted:

```python
add_process_row(pid, arrival, burst, priority)
st.success(...)
```

The row is added or updated, then Streamlit shows a success message.

### Delete Controls

```python
pid_choices = [row["PID"] for row in st.session_state.process_rows]
selected_pid = st.selectbox("Delete Process", options=pid_choices if pid_choices else [""])
if st.button("Remove Selected", use_container_width=True, disabled=not pid_choices):
    delete_process_row(selected_pid)
```

The selectbox lists existing PIDs. The remove button is disabled if there are no processes.

### Editable Table

```python
edited_df = st.data_editor(
    process_table_df(),
    num_rows="dynamic",
    use_container_width=True,
    key="process_editor",
)
```

`st.data_editor()` displays a spreadsheet-like table. `num_rows="dynamic"` lets users add or remove rows inside the table widget.

However, edits in `st.data_editor()` are not copied into `st.session_state.process_rows` automatically by this app. The user must click:

```python
if st.button("Sync Table Changes", use_container_width=True):
```

Then the app normalizes the table:

- missing values become `0`,
- PID becomes non-empty string,
- arrival becomes integer,
- burst is at least `1`,
- priority is at least `1`.

After syncing, later scheduler runs use the updated table.

## Static Evaluation UI

```python
def render_static_evaluation(processes: Processes, rows: list[dict[str, Any]], config: dict[str, int]) -> algorithms.LoadBalancing:
```

This section runs the schedulers and displays chart + summary metrics.

```python
schedulers = run_schedulers(...)
```

All three algorithms run using current process rows and sidebar settings.

```python
pid_map = {idx + 1: row["PID"] for idx, row in enumerate(sorted(rows, key=lambda item: (item["Arrival"], item["PID"])))}
```

Because `build_processes()` sorted rows before assigning numeric IDs, this code builds the same ordering to map internal IDs back to user PIDs.

```python
selected_name = st.segmented_control(
    "Timeline Algorithm",
    options=[scheduler.algorithm_name for scheduler in schedulers],
    default="Load Balancing",
)
```

`st.segmented_control()` lets the user choose which algorithm's timeline to display. The default is `Load Balancing`.

Then the code finds the matching scheduler:

```python
selected_scheduler = next(s for s in schedulers if s.algorithm_name == selected_name)
```

### Metrics Table

The function loops through all schedulers and calculates:

- CPU utilization,
- throughput,
- total time,
- migration event count.

For schedulers without `migration_events`, `getattr(..., [])` returns an empty list.

```python
migration_count = len(getattr(scheduler, "migration_events", []))
```

### Timeline Chart

```python
gantt_df = gantt_dataframe(...)
fig = timeline_figure(gantt_df, config["num_cpu"])
if fig is not None:
    st.plotly_chart(fig, use_container_width=True)
```

Scheduler steps become a DataFrame. DataFrame becomes a Plotly timeline. Streamlit renders it.

### Summary Cards

```python
summary_cols = st.columns(3)
summary_cols[0].metric("CPU Utilization", ...)
summary_cols[1].metric("Throughput", ...)
summary_cols[2].metric("Migration Events", ...)
```

`st.metric()` shows compact KPI-style values for the selected scheduler.

### Comparison Table

```python
st.dataframe(pd.DataFrame(metric_rows), use_container_width=True, hide_index=True)
```

This displays all scheduler metrics in one table.

### Return Value

```python
return next(s for s in schedulers if s.algorithm_name == "Load Balancing")
```

Even if the selected timeline algorithm is different, this function returns the load-balancing scheduler. The dynamic visualization needs load-balancing-specific `history` and `migration_events`.

## Queue Snapshot Visualization

```python
def render_queue_snapshot(snapshot: dict[str, Any], events: list[dict[str, Any]], num_cpu: int, pid_map: dict[int, str]) -> None:
```

This draws one frame of the load-balancing simulation.

Each snapshot comes from `LoadBalancing.history` and contains:

- current time,
- per-CPU process queues,
- per-CPU loads.

The header shows current time:

```python
header_left.metric("Current Time", f"t = {snapshot['time']}")
```

If migration events happened at this time, the app displays a warning message like:

```text
PUSH: P5 moved CPU 1 -> CPU 3
```

If no migration happened, it displays an info message.

Then it creates one column per CPU:

```python
cols = st.columns(num_cpu)
```

For each CPU:

- empty queue shows `Idle`,
- first process in queue is shown as `RUNNING`,
- later processes are shown as `WAITING`.

This mirrors the load-balancing scheduler design, where each CPU has a FIFO queue and the first process is the one currently executing.

## Dynamic Visualization

```python
def render_visualization(load_balancer: algorithms.LoadBalancing, rows: list[dict[str, Any]], num_cpu: int) -> None:
```

This section lets the user inspect and replay the load-balancing queue state over simulation time.

If no history exists:

```python
if not load_balancer.history:
    st.info("Run evaluation first to generate simulation history.")
    return
```

In normal page flow, static evaluation runs before visualization, so history should exist unless there are no processes or simulation did not produce frames.

The function rebuilds `pid_map`, gets all frame times, and creates a time slider:

```python
selected_time = st.slider("Time Frame", min_value=min_time, max_value=max_time, value=min_time, step=1)
```

The user can choose a simulation time. The app finds the snapshot and migration events for that time, then calls `render_queue_snapshot()`.

### Live Playback

```python
speed = st.slider("Playback Delay (seconds)", min_value=0.1, max_value=1.5, value=0.4, step=0.1)
if st.button("Play Live Visualization", use_container_width=True):
    frame_placeholder = st.empty()
    for frame in load_balancer.history:
        ...
        time.sleep(speed)
```

`st.empty()` creates a placeholder area. During playback, each frame replaces the previous frame inside that same area.

`time.sleep(speed)` pauses between frames, making the simulation look animated. In Streamlit this blocks the script while playback runs, so the UI will not process other interactions until playback finishes.

## Main App Function

```python
def main() -> None:
```

`main()` controls full page layout and execution order.

### Page Setup

```python
st.set_page_config(page_title="Multiprocessor Scheduling Dashboard", layout="wide")
ensure_state()
```

This sets browser title and wide layout, then initializes session state.

### Custom CSS

```python
st.markdown(
    """
    <style>
    ...
    </style>
    """,
    unsafe_allow_html=True,
)
```

Streamlit supports Markdown. With `unsafe_allow_html=True`, the app injects raw HTML/CSS. Here it customizes background, page padding, and heading letter spacing.

`unsafe_allow_html=True` should be used carefully in apps that display untrusted user content. In this file, the HTML is hardcoded by the developer, so the risk is low.

### Title and Caption

```python
st.title("Multiprocessor Scheduling Dashboard")
st.caption("CRUD process pool, evaluate multiple schedulers, and replay real load-balancing behavior.")
```

These create the top page heading and short description.

### Sidebar Configuration

```python
with st.sidebar:
    st.markdown("## Scheduler Config")
    num_cpu = st.slider("CPU Count", min_value=2, max_value=8, value=4, step=1)
    rr_quantum = st.slider("GLB_RR Quantum", min_value=1, max_value=20, value=15, step=1)
    affinity_quantum = st.slider("CPU Affinity Quantum", min_value=1, max_value=20, value=5, step=1)
    threshold = st.slider("Load Balancing Threshold", min_value=0, max_value=20, value=2, step=1)
    migration_overhead = st.slider("Migration Overhead", min_value=0, max_value=10, value=1, step=1)
```

`with st.sidebar:` means all widgets inside appear in the sidebar instead of the main page.

The sliders control:

- number of CPUs,
- round-robin time quantum,
- CPU-affinity time quantum,
- load-balancing threshold,
- migration overhead.

Changing any slider causes Streamlit to rerun the file. The new values are used immediately.

### Process Editing

```python
render_process_management()
```

This draws the process form, delete controls, and editable table.

### Stop If No Processes Exist

```python
rows = st.session_state.process_rows
if not rows:
    st.warning("Add at least one process to run the schedulers.")
    return
```

Schedulers need at least one process. If the list is empty, the app shows a warning and exits `main()` early.

### Build Scheduler Input and Config

```python
processes = build_processes(rows)
config = {
    "num_cpu": num_cpu,
    "rr_quantum": rr_quantum,
    "affinity_quantum": affinity_quantum,
    "threshold": threshold,
    "migration_overhead": migration_overhead,
}
```

The UI rows are converted into `Processes`, and sidebar settings are collected in one dictionary.

### Run Evaluation and Visualization

```python
load_balancer = render_static_evaluation(processes, rows, config)
render_visualization(load_balancer, rows, num_cpu)
```

First, all schedulers are run and compared. Then the returned load-balancing scheduler is used for dynamic visualization.

## Script Entry Point

```python
if __name__ == "__main__":
    main()
```

This means `main()` runs when executing:

```bash
streamlit run app.py
```

Streamlit imports/runs the script and executes the app from top to bottom. Each user interaction reruns the script, but `st.session_state` preserves the process list.

## Full Data Flow

1. App starts.
2. `ensure_state()` initializes default process rows.
3. User edits processes in form or data table.
4. User changes scheduler config in sidebar.
5. `build_processes()` converts rows into project `Process` objects.
6. `run_schedulers()` creates and runs three scheduler classes.
7. Scheduler `steps` become a Gantt DataFrame.
8. Plotly renders the selected scheduler timeline.
9. Metrics are calculated and shown.
10. Load-balancing `history` drives the queue snapshot and playback UI.

## Streamlit Concepts Used Here

### Rerun Model

Streamlit reruns the whole script after widget changes. Code should be written as if it rebuilds the page from scratch every time.

### Session State

`st.session_state` stores data that must survive reruns. This app uses it for `process_rows`.

### Widgets

Widgets such as `st.slider`, `st.text_input`, `st.number_input`, `st.selectbox`, and `st.button` both display UI and return current values.

### Forms

`st.form()` delays processing until the user clicks submit. Without a form, every field edit could trigger immediate rerun behavior.

### Columns

`st.columns()` lays out content horizontally. This app uses columns for process management, metrics, and per-CPU queue views.

### Data Editor

`st.data_editor()` lets users edit DataFrames in the browser. This app requires a separate "Sync Table Changes" button to copy those edits back into session state.

### Plotly Chart

`st.plotly_chart()` embeds an interactive Plotly figure inside Streamlit.

### Placeholders

`st.empty()` creates a replaceable UI area. The live visualization uses it to redraw queue snapshots frame by frame.

## Important Design Notes

- `app.py` treats user-facing PIDs and scheduler internal IDs separately. Internal IDs are assigned after sorting by arrival time.
- Scheduler objects mutate process remaining time, so the app passes copies into each scheduler.
- Only `LoadBalancing` has dynamic history and migration events. The other schedulers only provide timeline steps.
- The timeline chart uses fake timestamps because Plotly timeline charts expect datetime-like values.
- The load-balancing playback is synchronous. While it plays, Streamlit waits inside `time.sleep()`.
- Table edits only affect scheduler input after pressing "Sync Table Changes".

## Quick Mental Model

Think of `app.py` as glue code:

- Streamlit collects input.
- `process` classes turn input into scheduler objects.
- `algorithms` run simulations.
- pandas reshapes results.
- Plotly draws the timeline.
- Streamlit displays metrics, tables, and playback controls.

