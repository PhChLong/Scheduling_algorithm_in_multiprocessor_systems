# Multiprocessor CPU Scheduling Simulator

## 1. Introduction

### 1.1. General Overview

CPU scheduling determines which ready process is assigned to a processor and when that process is allowed to run. On a single-processor system, the scheduler selects work for one CPU. On a multiprocessor system, it must additionally decide how work should be distributed across several CPUs, whether processes should remain associated with a CPU, and when work should be migrated from an overloaded CPU to an idle or lightly loaded CPU.

Scheduling policies optimize different objectives. First-In, First-Out (FIFO) is simple and predictable, but a long process can delay all shorter processes behind it. Round Robin (RR) improves responsiveness by limiting each execution interval to a time quantum, although frequent switching can increase overhead. Multiprocessor schedulers must also consider load balance, processor affinity, local versus global queues, and migration cost.

This project implements a simulation environment for comparing several multiprocessor CPU scheduling strategies. Instead of executing real operating-system processes, it models processes with arrival time, CPU burst time, priority, and remaining execution time. Each algorithm produces a schedule that can be analyzed through metrics, Gantt charts, and queue-state animations.

### 1.2. Problem Statement

The project addresses the following problem:

> Given a set of processes with different arrival times and CPU burst times, how can those processes be scheduled across multiple CPUs while maintaining good processor utilization, throughput, responsiveness, and load distribution?

The difficulty is that no single scheduling policy is optimal for every workload. A global queue is simple and naturally shares work among CPUs, but it can become a centralized scheduling point. Per-CPU queues improve locality and scalability, but they can become unbalanced. CPU affinity reduces process movement, while work stealing and explicit load balancing improve utilization by moving waiting work between CPUs.

The program therefore provides a common simulator that:

- Executes the same workload with multiple scheduling algorithms.
- Supports both global and per-CPU queues.
- Models preemptive and non-preemptive execution.
- Models process migration and migration overhead.
- Records process execution and queue state over time.
- Compares algorithms using consistent metrics and visualizations.

### 1.3. Project Objectives

The main objectives are:

1. Model processes and multiprocessor scheduling in Python.
2. Implement six scheduling approaches:
   - Global FIFO.
   - Global Round Robin.
   - Partitioned FIFO.
   - CPU Affinity.
   - Work Stealing.
   - Dynamic Load Balancing.
3. Compare their behavior under the same workload.
4. Visualize CPU execution and queue state.
5. Provide an interactive graphical interface for editing workloads and scheduler parameters.

---

## 2. Main Content

### 2.1. Process and System Model

Each simulated process contains:

| Field | Meaning |
|---|---|
| `id` | Internal numeric identifier assigned by the program |
| `burst_time` | Total CPU time required by the process |
| `arrival_time` | Simulation time at which the process becomes ready |
| `priority` | Positive priority value stored with the process |
| `remaining_time` | CPU time still required during simulation |

The current algorithms primarily use arrival time, burst time, and remaining time. Priority is validated and stored but is not currently used to choose the next process.

The system supports between 2 and 8 CPUs through the graphical interface and up to 100 processes in the `Processes` collection. CPU identifiers are zero-based internally and displayed as CPU 1, CPU 2, and so on.

Every scheduler produces:

```python
steps: dict[int, list[ScheduleStep]]
```

Each `ScheduleStep` records:

```text
process_id, begin_time, end_time, cpu_id
```

Schedulers also record a `history` containing running processes and waiting queues at scheduling decision points. This history is used by the dynamic visualization.

### 2.2. Scheduling Algorithms

#### 2.2.1. Global FIFO (`GLB_FIFO`)

Global FIFO uses one shared ready queue for all CPUs. Processes enter the queue when their arrival time is reached. An available CPU removes the process at the front of the queue and runs it until completion.

Main characteristics:

- One global FIFO queue.
- Non-preemptive execution.
- Any available CPU can run the next process.
- Simple dispatch behavior.
- Long processes can cause a convoy effect for processes behind them.

The global queue naturally allows an idle CPU to obtain waiting work without explicit migration logic.

#### 2.2.2. Global Round Robin (`GLB_RR`)

Global Round Robin also uses one shared ready queue. Unlike FIFO, a process runs for at most one time quantum:

```text
run time = min(time quantum, remaining time)
```

If the process does not finish, it returns to the end of the global queue.

Main characteristics:

- One global ready queue.
- Preemptive time-sliced execution.
- Better response time than non-preemptive FIFO.
- The quantum controls the balance between responsiveness and switching frequency.
- A very small quantum creates many schedule intervals, while a large quantum approaches FIFO behavior.

#### 2.2.3. Partitioned FIFO (`PAR_FIFO`)

Partitioned FIFO maintains one FIFO queue per CPU. When a process arrives, it is assigned to the CPU with the smallest current workload. The workload includes the remaining time of the running process and all queued processes.

After assignment, a process stays on that CPU and runs to completion when it reaches the front of the local queue.

Main characteristics:

- One local queue per CPU.
- Non-preemptive FIFO execution.
- Initial load-aware placement.
- No migration after placement.
- Better queue locality than a global queue.
- A poor early placement cannot be corrected later.

#### 2.2.4. CPU Affinity (`CPU_Affinity`)

CPU Affinity uses a global ready queue and a time quantum. The first time a process executes, it is mapped to a CPU. With hard affinity enabled, subsequent execution intervals of that process must occur on the same CPU.

Main characteristics:

- Global waiting queue.
- Preemptive Round Robin execution.
- Process-to-CPU mapping.
- Hard affinity preserves CPU placement.
- Affinity can represent cache-locality benefits.
- Strict affinity may leave a CPU idle even when runnable work exists for another CPU.

The implementation also supports soft affinity through the `hard=False` option, although the dashboard currently creates the scheduler with hard affinity enabled.

#### 2.2.5. Work Stealing (`Work_Stealing`)

Work Stealing maintains one deque per CPU. New processes can be assigned using one of three strategies:

- `shortest_queue`: select the CPU with the fewest queued processes.
- `least_load`: select the CPU with the lowest queued remaining time.
- `power_of_two`: randomly select two CPUs and use the shorter queue.

When a CPU has no local work, it selects the CPU with the longest deque and steals a process from the back of that deque. A stolen process receives the configured migration overhead.

Main characteristics:

- Distributed per-CPU queues.
- Idle CPUs initiate balancing.
- Migration occurs only when a CPU needs work.
- Local execution can reduce unnecessary movement.
- Stealing improves utilization for irregular workloads.
- Victim selection is based on queue length rather than a complete cost model.

#### 2.2.6. Dynamic Load Balancing (`LoadBalancing`)

The Load Balancing scheduler maintains one FIFO queue per CPU and uses proactive push migration.

New processes are currently distributed in round-robin order:

```python
target_cpu = next_process_index % num_cpu
```

The scheduler then continuously evaluates CPU load:

```text
CPU load = sum of remaining time of all processes in that CPU queue
```

Push migration:

1. Find the busiest CPU.
2. Find the least-loaded CPU.
3. Check whether their load difference exceeds `max(1, 2 * migration_overhead)`.
4. Select a waiting process from the busiest CPU.
5. Migrate it only if the predicted load difference becomes smaller.

The running process is never migrated. Migration candidates are selected from waiting processes, preferring the process with the greatest remaining time. Migration overhead is added to the process's remaining time.

Strengths:

- Corrects load imbalance after initial assignment.
- Uses proactive migration before each execution tick.
- Avoids migrating the currently running process.
- Rejects migrations that do not improve the load difference.
- Records migration events and detailed queue history.

Limitations:

- Tick-by-tick simulation can be expensive for very large burst times.
- Round-robin initial placement does not use current load.
- Migration cost is represented only as additional execution time.
- CPU cache, memory locality, NUMA topology, and communication cost are not modeled.
- Priority is not used.

### 2.3. Program Architecture

The project is divided into three main layers.

#### Domain Model

`process/process.py` defines:

- `Process`: one process and its validated properties.
- `Processes`: a collection that assigns IDs, limits the process count, copies workloads, and provides sorted views.
- Input-related exceptions.

#### Scheduling Layer

The `algorithms` package defines:

- `Schedule`: abstract base class and shared metric/history support.
- `ScheduleStep`: one continuous execution interval.
- The six scheduler implementations.

#### Presentation Layer

`app.py` defines the Streamlit interface and Plotly visualizations. It converts table rows into domain objects, executes all schedulers, computes comparison data, and renders static and dynamic results.

### 2.4. Input Data

The program accepts process data through a form or editable table.

| Input | Validation |
|---|---|
| Process ID | Required text label; duplicate IDs are rejected |
| Arrival Time | Integer greater than or equal to 0 |
| Burst Time | Integer greater than 0 |
| Priority | Integer greater than 0 |

Scheduler configuration includes:

| Parameter | Purpose |
|---|---|
| CPU Count | Number of simulated processors |
| GLB_RR Quantum | Time slice for Global Round Robin |
| CPU Affinity Quantum | Time slice for CPU Affinity |
| Work Stealing Quantum | Time slice for Work Stealing |
| Work Stealing Strategy | Initial local-queue placement strategy |
| Load Balancing Threshold | Derived as `max(1, 2 * migration_overhead)` |
| Migration Overhead | Additional execution time caused by migration |

The dashboard begins with a default workload of 20 processes designed to create uneven CPU loads and observable migration behavior.

### 2.5. Output Data

The program produces:

- A Gantt-style execution timeline.
- CPU utilization.
- Throughput.
- Total completion time.
- Migration event count.
- A comparison table for all schedulers.
- A time-frame selector for inspecting a specific state.
- Per-CPU running process information.
- Global or local waiting queues.
- An animated queue replay.

The shared metric formulas are:

```text
Total time = maximum ScheduleStep end time

Busy time = sum of all execution interval lengths

CPU utilization = busy time / (number of CPUs × total time)

Throughput = completed process count / total time

Turnaround time = completion time − arrival time

Waiting time = turnaround time − actual CPU execution time

Response time = first execution time − arrival time
```

### 2.6. Important Functions and Their Purposes

#### Process Functions and Classes

| Component | Purpose |
|---|---|
| `Process._validate()` | Rejects invalid burst, arrival, and priority values |
| `Process.copy()` | Creates an independent simulation copy |
| `Processes.add()` | Adds a process and assigns an ID |
| `Processes.copy()` | Copies the complete workload |
| `Processes.sorted_by_arrival()` | Returns processes ordered for simulation |

#### Shared Scheduler Functions

| Component | Purpose |
|---|---|
| `Schedule._copy_sorted_processes()` | Copies and sorts input without mutating the original workload |
| `Schedule._reset_history()` | Clears history before a new simulation |
| `Schedule._record_history()` | Stores running and queue state |
| `Schedule._update_basic_metrics()` | Calculates utilization, throughput, turnaround, waiting, and response metrics |

#### Load Balancing Functions

| Function | Purpose |
|---|---|
| `_reset()` | Clears schedule, queue, history, and migration state |
| `_normalize_processes()` | Copies and sorts the workload |
| `_cpu_load()` | Sums remaining execution time on one CPU |
| `_least_loaded_cpu()` | Selects the lightest CPU |
| `_busiest_cpu()` | Selects the busiest eligible CPU |
| `_append_step()` | Records execution and merges adjacent intervals |
| `_record_state()` | Records running, waiting, and load state |
| `_assign_new_arrivals()` | Places newly arrived processes using round-robin distribution |
| `_migration_candidate_index()` | Selects an eligible waiting process |
| `_pop_migration_candidate()` | Removes the selected process from its source queue |
| `_migrate()` | Moves a process and records migration overhead/event data |
| `_migration_reduces_imbalance()` | Predicts whether migration improves balance |
| `push_migration()` | Proactively moves work away from overloaded CPUs |
| `estimate()` | Executes the complete load-balancing simulation |

#### Interface and Visualization Functions

| Function | Purpose |
|---|---|
| `ensure_state()` | Initializes the default workload in Streamlit session state |
| `build_processes()` | Converts UI rows into validated process objects |
| `next_available_pid()` | Generates a non-conflicting process label |
| `add_or_update_process()` | Creates or updates a process row |
| `delete_process_row()` | Removes a process row |
| `scheduler_metrics()` | Calculates consistent comparison metrics from schedule steps |
| `gantt_dataframe()` | Converts execution intervals into timeline data |
| `timeline_figure()` | Creates the static Plotly execution timeline |
| `snapshot_cpu_state()` | Separates a running process from waiting processes |
| `snapshot_global_waiting()` | Builds or reads the global waiting queue |
| `build_live_figure()` | Creates animated global/local queue figures |
| `run_schedulers()` | Runs all six algorithms on copies of the same workload |
| `render_process_management()` | Displays process CRUD controls |
| `render_static_evaluation()` | Displays the Gantt chart and metric comparison |
| `step_history()` | Reconstructs running-only history when queue history is unavailable |
| `render_queue_snapshot()` | Displays one selected simulation state |
| `render_visualization()` | Coordinates snapshot and animation display |
| `main()` | Builds and runs the complete Streamlit page |

### 2.7. Testing

`test.py` contains regression checks for:

- Protection against input mutation.
- Correct Partitioned FIFO workload accounting.
- Empty queues after completion.
- Separation of running processes from waiting queues.
- History availability for all schedulers.
- Final idle snapshots.

The application was also exercised through Streamlit's application testing interface to verify that each scheduler can be selected without producing UI exceptions.

---

## 3. Program Interface

The graphical interface is implemented with Streamlit.

### 3.1. Process Management

The process management area provides:

- A form for adding or updating one process.
- A selector for removing a process.
- An editable process table.
- Validation messages for invalid or duplicate data.

The table is stored in Streamlit session state so it remains available when the page reruns after user interaction.

### 3.2. Scheduler Configuration

The sidebar contains sliders and selectors for CPU count, time quanta, work-stealing strategy, and migration overhead. The load-balancing threshold is calculated automatically.

Changing a setting causes all schedulers to run again using the updated configuration.

### 3.3. Static Evaluation

The user selects an algorithm using a segmented control. The interface then displays:

- A Gantt chart showing process execution on each CPU.
- CPU utilization.
- Throughput.
- Migration count.
- A comparison table containing all algorithms.

Migrated process intervals are marked with an asterisk after migration occurs.

### 3.4. Dynamic Visualization

The dynamic view contains:

- A time slider.
- The process currently running on each CPU.
- Waiting processes.
- Migration messages.
- Play and Pause controls for animation.

The visualization layout depends on queue organization:

- Global-queue algorithms show one shared waiting queue.
- Local-queue algorithms show a separate queue for each CPU.

This interface makes scheduling decisions observable instead of presenting only final numerical metrics.

---

## 4. Teamwork

The following contribution summary is derived from the repository's Git commit history. Team members should verify the displayed names and add student IDs before submission.

| Team Member / Git Identity | Main Contributions |
|---|---|
| PhChLong | Created and developed the Load Balancing algorithm; implemented push migration, migration history, metrics integration, Streamlit visualization, queue replay, bug fixes, and shared scheduler-history improvements |
| trantatdat123 | Implemented Global Round Robin and CPU Affinity; contributed the package structure, shared scheduling classes, tests, application interface changes, README documentation, and integration work |
| Hong Nam | Implemented Global FIFO and Partitioned FIFO |
| dduhC | Implemented Work Stealing and contributed later Work Stealing bug fixes and tests |

Suggested final submission format:

| Full Name | Student ID | Confirmed Contribution |
|---|---|---|
| _Replace with full name_ | _Student ID_ | Load Balancing, UI, visualization, integration, testing |
| _Replace with full name_ | _Student ID_ | Global RR, CPU Affinity, architecture, integration, documentation |
| _Replace with full name_ | _Student ID_ | Global FIFO and Partitioned FIFO |
| _Replace with full name_ | _Student ID_ | Work Stealing and related testing |

The team used a modular structure so each scheduling algorithm could be developed independently and integrated through the common `Schedule` interface and `ScheduleStep` output format.

---

## 5. References

1. R. H. Arpaci-Dusseau and A. C. Arpaci-Dusseau, “Scheduling: Introduction,” *Operating Systems: Three Easy Pieces*, Version 1.10. [https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched.pdf](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched.pdf)

2. R. H. Arpaci-Dusseau and A. C. Arpaci-Dusseau, “Multiprocessor Scheduling,” *Operating Systems: Three Easy Pieces*, Version 1.10. [https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched-multi.pdf](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched-multi.pdf)

3. R. D. Blumofe and C. E. Leiserson, “Scheduling Multithreaded Computations by Work Stealing,” *Journal of the ACM*, vol. 46, no. 5, pp. 720–748, 1999. [https://doi.org/10.1145/324133.324234](https://doi.org/10.1145/324133.324234)

4. Python Software Foundation, “`collections` — Container Datatypes: `deque`,” *Python Documentation*. [https://docs.python.org/3/library/collections.html#collections.deque](https://docs.python.org/3/library/collections.html#collections.deque)

5. Streamlit, “`st.data_editor`,” *Streamlit API Reference*. [https://docs.streamlit.io/develop/api-reference/data/st.data_editor](https://docs.streamlit.io/develop/api-reference/data/st.data_editor)

6. Streamlit, “Session State,” *Streamlit API Reference*. [https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)

7. Plotly, “Gantt Charts in Python,” *Plotly Python Documentation*. [https://plotly.com/python/gantt/](https://plotly.com/python/gantt/)

8. Plotly, “Animations in Python,” *Plotly Python Documentation*. [https://plotly.com/python/animations/](https://plotly.com/python/animations/)

9. Project source code and Git history, “Scheduling Algorithm in Multiprocessor Systems,” local repository, accessed June 19, 2026.
