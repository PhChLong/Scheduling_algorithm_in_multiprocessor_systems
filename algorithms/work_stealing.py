from algorithms.schedule_step import ScheduleStep
from process.process import Processes, Process
from algorithms.schedule import Schedule

from collections import deque
import random as rd
class Work_Stealing(Schedule):
    def __init__(self, time_quantum: int, num_cpu: int, strat: str = "shortest_queue", migration_overhead: int = 0):
        super().__init__()
        self.algorithm_name = "Work_Stealing"
        self.time_quantum = time_quantum
        self.num_cpu = num_cpu
        self.strat = strat
        self.migration_overhead = migration_overhead
        self.cpu_queue = {i: True for i in range(self.num_cpu)}  # True = rảnh, False = bận
        self.local_deque = {i: deque() for i in range(num_cpu)}
        self.mapping = {}   #process_id -> cpu_id
    def is_cpu_available(self):
        for cpu_id, available in self.cpu_queue.items():
            if available:
                return cpu_id, available
        return None, False
    def _place_task(self, p: Process):
        if self.strat == "shortest_queue":
            target = min(self.local_deque, key=lambda cpu_id: len(self.local_deque[cpu_id]))
            self.local_deque[target].append(p)
        elif self.strat == "least_load":
            target = min(self.local_deque, key=lambda cpu_id: sum(i.remaining_time for i in self.local_deque[cpu_id]))
            self.local_deque[target].append(p)  
        elif self.strat == "power_of_two":
            if self.num_cpu == 1:
                self.local_deque[0].append(p)
                return
            cpu_a, cpu_b = rd.sample(range(self.num_cpu), 2)
            target = cpu_a if len(self.local_deque[cpu_a]) <= len(self.local_deque[cpu_b]) else cpu_b
            self.local_deque[target].append(p)
    def estimate(self, processes: Processes) -> None:
        self.steps = {i: [] for i in range(self.num_cpu)}
        self.cpu_queue = {i: True for i in range(self.num_cpu)}
        self.local_deque = {i: deque() for i in range(self.num_cpu)}
        self.mapping = {}
        processes = processes.sorted_by_arrival()
        cpu = {i: None for i in range(self.num_cpu)}
        cur = 0
        id = 0
        completed_processes = 0
        while completed_processes < len(processes):
            while id < len(processes) and processes[id].arrival_time <= cur:
                self._place_task(processes[id])
                id += 1
        # Rảnh và còn deque -> lôi task lên
            for cpu_id in range(self.num_cpu):
                if self.cpu_queue[cpu_id] and self.local_deque[cpu_id]:
                    p = self.local_deque[cpu_id].popleft()
                    self.mapping[p.id] = cpu_id
                    run_time = min(self.time_quantum, p.remaining_time)
                    cpu[cpu_id] = [p, run_time, cur]
                    self.cpu_queue[cpu_id] = False
            # Rảnh và deque trống -> steal
            for cpu_id in range(self.num_cpu):
                if self.cpu_queue[cpu_id] and not self.local_deque[cpu_id]:
                    victim = max(range(self.num_cpu), key=lambda i: len(self.local_deque[i]))
                    if victim != cpu_id and self.local_deque[victim]:
                        p = self.local_deque[victim].pop()  # steal từ back
                        p.remaining_time += self.migration_overhead
                        self.mapping[p.id] = cpu_id
                        run_time = min(self.time_quantum, p.remaining_time)
                        cpu[cpu_id] = [p, run_time, cur]
                        self.cpu_queue[cpu_id] = False

            active_cpus = {i: state for i, state in cpu.items() if state is not None}
            if not active_cpus:
                if id < len(processes):
                    cur = processes[id].arrival_time
                continue

            min_time = min(state[1] for state in active_cpus.values())
            proc_ar = 1e9
            if id < len(processes):
                proc_ar = processes[id].arrival_time - cur
            next_time = min(min_time, proc_ar)
            cur += next_time

            for cpu_id, state in active_cpus.items():
                p, run_time, start_time = state
                p.remaining_time -= next_time
                state[1] -= next_time
                if state[1] == 0:
                    self.steps[cpu_id].append(ScheduleStep(p.id, start_time, cur, cpu_id))
                    cpu[cpu_id] = None
                    self.cpu_queue[cpu_id] = True
                    while id < len(processes) and processes[id].arrival_time <= cur:
                        self._place_task(processes[id])
                        id += 1
                    if p.remaining_time == 0:
                        completed_processes += 1
                    else:
                        self.local_deque[cpu_id].append(p)

        self._update_basic_metrics(len(processes))
        return self.steps
