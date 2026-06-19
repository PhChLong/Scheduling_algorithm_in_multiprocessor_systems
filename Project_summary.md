# Project Summary

## Purpose

Multiprocessor CPU scheduling simulator and Streamlit dashboard. The project models a workload of processes, runs several scheduling algorithms on multiple CPUs, compares schedule metrics, renders Gantt-style execution timelines, and replays queue state for visualization.

## Main Entry Points

- `app.py`: Streamlit dashboard for process CRUD, scheduler configuration, metric comparison, timeline rendering, and dynamic schedule/queue replay.
- `test.py`: Console demo runner. Builds a larger workload, runs `GLB_RR`, `CPU_Affinity`, and `LoadBalancing`, then prints schedule steps plus utilization/throughput.

## Package Layout

- `process/process.py`: Process domain model, validation errors, and `Processes` collection wrapper.
- `algorithms/schedule.py`: Abstract scheduler base class, shared metric fields, and `_update_basic_metrics()`.
- `algorithms/schedule_step.py`: `ScheduleStep` dataclass for one process execution interval on one CPU.
- `algorithms/GLB_FIFO.py`: Global FIFO scheduler.
- `algorithms/GLB_RR.py`: Global round-robin scheduler.
- `algorithms/PAR_FIFO.py`: Per-CPU FIFO scheduler.
- `algorithms/cpu_affinity.py`: Round-robin scheduler with CPU affinity.
- `algorithms/work_stealing.py`: Per-CPU deque scheduler with idle CPU stealing.
- `algorithms/load_balancing.py`: Per-CPU queue scheduler with push/pull migration and queue history.
- `algorithms/__init__.py`: Public exports for scheduler classes.

## Process Model

`Process` stores:

- `id`
- `burst_time`
- `arrival_time`
- `priority`
- `remaining_time`

Validation rejects non-positive burst time, negative arrival time, and non-positive priority.

`Processes` stores up to 100 processes. It assigns sequential IDs when adding, supports delete/modify/get/copy, and exposes sorted views by arrival, burst, or priority.

Important behavior: `Process.copy()` preserves the process ID and resets `remaining_time` to full burst time. Scheduler callers usually pass `processes.copy()` because algorithms mutate `remaining_time` while simulating.

## Scheduler Result Format

All schedulers populate:

```python
self.steps: dict[int, list[ScheduleStep]]
```

Keys are zero-based CPU IDs. Each `ScheduleStep` contains:

- `process_id`
- `begin_time`
- `end_time`
- `cpu_id`

The dashboard converts these steps into Plotly timelines and labels CPU IDs as `CPU 1`, `CPU 2`, etc.

## Shared Metrics

`Schedule._update_basic_metrics()` computes:

- `cpu_utilization`
- `throughput`
- total and average turnaround time
- total and average waiting time
- total and average response time

Algorithms that call `_update_basic_metrics(processes)` compute all of those values. Algorithms that call `_update_basic_metrics(len(processes))` compute utilization and throughput only; turnaround, waiting, and response fields stay zero.

The dashboard currently recomputes displayed utilization, throughput, total time, and migration count from `steps`, so the UI comparison is consistent even when scheduler metric fields differ.

## Algorithms

### GLB_FIFO

Global Load Balancing FIFO.

- Uses one global FIFO ready queue.
- Processes enter the queue when `arrival_time <= current_time`.
- Any available CPU pulls the next process from the queue.
- Each dispatch runs the process to completion.
- Simulation jumps to the next arrival when no CPU is active.
- Calls `_update_basic_metrics(len(processes))`, so only utilization and throughput are populated internally.

### GLB_RR

Global Load Balancing Round Robin.

- Uses one global FIFO ready queue.
- Processes enter the queue when `arrival_time <= current_time`.
- Any available CPU pulls from the global queue.
- Each dispatch runs for `min(time_quantum, remaining_time)`.
- Unfinished processes return to the global queue.
- Simulation jumps to the next arrival when no CPU is active.
- Calls `_update_basic_metrics(processes)`, so average turnaround/waiting/response metrics are populated internally.

### PAR_FIFO

Partitioned FIFO.

- Uses one FIFO queue per CPU.
- New arrivals are assigned to the CPU with the smallest tracked workload.
- Each CPU runs only its local queue.
- Each dispatch runs the process to completion.
- No migration or stealing occurs after assignment.
- Calls `_update_basic_metrics(len(processes))`, so only utilization and throughput are populated internally.

### CPU_Affinity

Round robin with process-to-CPU affinity.

- Uses one global ready queue.
- Tracks a preferred CPU per process ID.
- On first run, a process can bind to an available CPU.
- If `hard=True`, an already mapped process only runs on its mapped CPU.
- If `hard=False`, a process may run on another CPU when no affinity match is available.
- Each dispatch runs for `min(time_quantum, remaining_time)`.
- Unfinished processes return to the global queue.
- Calls `_update_basic_metrics(processes)`, so average turnaround/waiting/response metrics are populated internally.

### Work_Stealing

Work-stealing scheduler with local deques.

- Uses one local deque per CPU.
- New arrivals are placed by one of three strategies:
  - `shortest_queue`: CPU with the fewest queued processes.
  - `least_load`: CPU with the smallest sum of queued `remaining_time`.
  - `power_of_two`: randomly samples two CPUs and chooses the shorter queue.
- Idle CPUs steal from the back of the busiest local deque.
- Each dispatch runs for `min(time_quantum, remaining_time)`.
- Unfinished processes return to the same CPU's local deque.
- Calls `_update_basic_metrics(len(processes))`, so only utilization and throughput are populated internally.

### LoadBalancing

Per-CPU FIFO queue scheduler with push/pull migration.

- Uses one FIFO queue per CPU.
- New arrivals are currently assigned round-robin by process index (`next_index % num_cpu`). Older comments mention least-loaded assignment, but that implementation is commented out.
- Queue load is the sum of `remaining_time` for every process in a CPU queue.
- Push migration moves waiting work from a busy CPU to the least-loaded CPU when the load gap exceeds `threshold`.
- Pull migration lets an idle CPU take waiting work from a busy CPU.
- Migration never moves the currently running process at queue index `0`.
- Migration selects the waiting process with the largest `remaining_time`, with arrival time and ID tie-breakers.
- Migration adds `migration_overhead` to the moved process's `remaining_time`.
- Adjacent steps for the same process on the same CPU are merged.
- Records `history` snapshots for queue visualization and `migration_events` for UI warnings/labels.
- Calls `_update_basic_metrics(processes)`, so average turnaround/waiting/response metrics are populated internally.

## Dashboard Flow

1. `ensure_state()` initializes a default workload in Streamlit session state.
2. The user can add, delete, or edit process rows.
3. `build_processes()` converts UI rows into a `Processes` object sorted by arrival time and PID label.
4. Sidebar controls CPU count, GLB round-robin quantum, affinity quantum, work-stealing quantum/strategy, load-balancing threshold, and migration overhead.
5. `run_schedulers()` runs:
   - `GLB_FIFO`
   - `GLB_RR`
   - `PAR_FIFO`
   - `CPU_Affinity`
   - `Work_Stealing`
   - `LoadBalancing`
6. Static evaluation shows a selected algorithm timeline, summary metrics, and a comparison table.
7. Dynamic visualization replays the selected scheduler. `LoadBalancing` uses real queue `history`; other schedulers use a derived execution-only history from `steps`.

## Visualization Notes

- Gantt charts are built with Plotly Express timelines.
- Dynamic replay is built with Plotly animation frames.
- For `LoadBalancing`, the replay can show each CPU's full local queue because the scheduler records queue snapshots.
- For other schedulers, replay only shows currently running processes because queue history is not recorded.
- Migrated process labels are marked with `*` in Gantt output.

## Dependencies

Inferred runtime dependencies:

- Python 3.10+ because code uses `int | None` union syntax.
- `streamlit`
- `pandas`
- `plotly`

No dependency manifest is present in the repository.

## Run Commands

Dashboard:

```powershell
streamlit run app.py
```

Console demo:

```powershell
python test.py
```

## Testing State

No automated test suite is present. `test.py` is a manual/demo script with printed output and no assertions. There is also no dependency file, so setup is currently implicit.

## Notable Gaps

- Add `requirements.txt` or another dependency manifest.
- Add unit tests for scheduler step output, completion behavior, metric calculation, CPU affinity, work stealing, and migration behavior.
- Normalize metric updates so every scheduler calls `_update_basic_metrics(processes)` when full process-level metrics are desired.
- Decide whether `LoadBalancing._assign_new_arrivals()` should use round-robin assignment or the documented least-loaded assignment, then align comments and README.
- Consider recording queue history for `GLB_FIFO`, `GLB_RR`, `PAR_FIFO`, `CPU_Affinity`, and `Work_Stealing` so dynamic replay can show waiting queues for every algorithm.
- Fix README references to `app_explain.md`; that file is not present in the current repository.
- Some source comments are Vietnamese without diacritics while others include diacritics. Standardizing encoding/comment style would make the codebase easier to maintain.
