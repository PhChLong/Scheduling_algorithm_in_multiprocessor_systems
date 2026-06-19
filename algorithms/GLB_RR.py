from algorithms.schedule_step import ScheduleStep
from process.process import Processes, Process
from algorithms.schedule import Schedule

from collections import deque
class GLB_RR(Schedule):
    def __init__(self, time_quantum: int, num_cpu: int):
        super().__init__()
        self.algorithm_name = "GLB_RR"
        self.time_quantum = time_quantum
        self.num_cpu = num_cpu
        self.cpu_queue = {i: True for i in range(self.num_cpu)}
        #True la CPU đang rảnh, False là CPU đang bận
    def is_cpu_available(self):
        for cpu_id, available in self.cpu_queue.items():
            if available:
                return cpu_id, available
        return None, False
    def estimate(self, processes: Processes) -> None:
        self.steps = {i: [] for i in range(self.num_cpu)}
        self._reset_history()
        self.cpu_queue = {i: True for i in range(self.num_cpu)}
        processes = self._copy_sorted_processes(processes)
        cpu = {i: None for i in range(self.num_cpu)}
        cur=0
        id=0
        complete_processes = 0
        queue = deque()
        
        while complete_processes < len(processes):
            while id < len(processes) and processes[id].arrival_time <= cur:
                queue.append(processes[id])
                id += 1
            for cpu_id in range(self.num_cpu):
                if self.cpu_queue[cpu_id] and queue:
                    p = queue.popleft()
                    run_time = min(self.time_quantum, p.remaining_time)
                    cpu[cpu_id] = [p, run_time, cur]
                    self.cpu_queue[cpu_id] = False
            self._record_history(
                cur,
                running={
                    cpu_id: state[0].id if state is not None else None
                    for cpu_id, state in cpu.items()
                },
                queues={cpu_id: [] for cpu_id in range(self.num_cpu)},
                global_queue=[process.id for process in queue],
            )
            active_cpus = {i:state for i, state in cpu.items() if state is not None}
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
                        queue.append(processes[id])
                        id += 1
                    if p.remaining_time == 0:
                        complete_processes += 1
                    else:
                        queue.append(p)
        self._record_history(
            cur,
            running={cpu_id: None for cpu_id in range(self.num_cpu)},
            queues={cpu_id: [] for cpu_id in range(self.num_cpu)},
            global_queue=[],
        )
        self._update_basic_metrics(processes)
        return self.steps
