# Project Summary

## Purpose

Multiprocessor CPU scheduling simulator and dashboard. Project models a set of processes, runs several scheduling algorithms across multiple CPUs, compares metrics, and visualizes execution timelines plus load-balancing queue state over time.

## Main Entry Points

- `app.py`: Streamlit dashboard. Provides process CRUD, scheduler configuration, static metric comparison, Gantt-style timeline, and dynamic load-balancing playback.
- `test.py`: Script-style demo runner. Builds a larger workload, runs all schedulers, and prints schedule steps plus metrics.

## Package Layout

- `process/process.py`: Process domain model and collection wrapper.
- `algorithms/schedule.py`: Abstract scheduler base class and shared metric fields.
- `algorithms/schedule_step.py`: `ScheduleStep` dataclass for one process execution interval on one CPU.
- `algorithms/GLB_RR.py`: Global queue round-robin scheduler.
- `algorithms/cpu_affinity.py`: Round-robin scheduler with CPU affinity.
- `algorithms/load_balancing.py`: Per-CPU queue scheduler with push/pull migration.
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

Important behavior: `Process.copy()` resets `remaining_time` to full burst time. Scheduler callers usually pass `processes.copy()` so algorithms can mutate `remaining_time` without corrupting the source workload.

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

The dashboard converts these steps into a Plotly timeline and labels CPU IDs as `CPU 1`, `CPU 2`, etc.

## Algorithms

### GLB_RR

Global Load Balancing Round Robin.

- Uses one global FIFO ready queue.
- Processes enter the queue when `arrival_time <= current_time`.
- Any available CPU pulls from the global queue.
- Each dispatch runs for `min(time_quantum, remaining_time)`.
- Unfinished processes return to the global queue.
- Simulation jumps to next arrival when no CPU is active.

Current limitation: class does not compute its own metric fields such as `cpu_utilization` or `throughput`; dashboard computes comparable metrics from `steps`.

### CPU_Affinity

Round robin with process-to-CPU affinity.

- Uses one global ready queue.
- Tracks preferred CPU per process ID.
- If `hard=True`, a process only runs on its assigned CPU after mapping exists.
- If `hard=False`, a process may run elsewhere when no affinity match is available.
- Each run uses `min(time_quantum, remaining_time)`.
- Unfinished processes return to the queue.

Current code issue: `mapping` starts as `{p: None for p in processes}` but later checks `p.id not in mapping`, mixing process objects and IDs. This still often behaves like "new ID has no mapping", but structure is inconsistent and should be cleaned to `dict[int, int | None]`.

### LoadBalancing

Per-CPU FIFO queue scheduler with migration.

- New arrivals go to least-loaded CPU.
- CPU load is sum of `remaining_time` in that CPU queue.
- Push migration moves waiting work from busiest CPU to least-loaded CPU when load gap exceeds `threshold`.
- Pull migration lets an idle CPU take waiting work from busiest CPU.
- Migration never moves the currently running process at queue index `0`.
- Migration adds `migration_overhead` to moved process `remaining_time`.
- Scheduler records `history` snapshots for queue visualization and `migration_events` for UI warnings/labels.
- Adjacent steps for same process on same CPU are merged.

This scheduler computes `cpu_utilization` and `throughput` internally.

## Dashboard Flow

1. `ensure_state()` initializes default workload in Streamlit session state.
2. User can add, delete, or edit processes.
3. `build_processes()` converts UI rows into `Processes`, sorted by arrival then PID.
4. Sidebar controls CPU count, round-robin quantum, affinity quantum, load-balance threshold, and migration overhead.
5. `run_schedulers()` runs:
   - `GLB_RR`
   - `CPU_Affinity`
   - `LoadBalancing`
6. Static section shows selected algorithm timeline and comparison metrics.
7. Dynamic section replays only `LoadBalancing.history`, including migration event notices.

## Dependencies

Inferred runtime dependencies:

- Python 3.10+ likely required because code uses `int | None` union syntax.
- `streamlit`
- `pandas`
- `plotly`

No dependency manifest is present in repo.

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

No automated test suite found. `test.py` is a manual/demo script that prints scheduler output. There are no assertions.

## Notable Gaps

- Add `requirements.txt` or equivalent dependency file.
- Add unit tests for scheduler step output, completion time, migration behavior, and edge cases.
- Normalize metrics across all scheduler classes.
- Fix `CPU_Affinity` mapping structure.
- Consider adding wait/turnaround/response time calculation because base `Schedule` exposes those fields but implementations do not populate them.
- Some comments contain mojibake from encoding mismatch; source intent is still understandable, but files should be normalized to UTF-8.
