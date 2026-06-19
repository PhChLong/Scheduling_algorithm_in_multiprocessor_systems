from algorithms.schedule import Schedule
from algorithms.schedule_step import ScheduleStep
from process.process import Processes
from collections import deque

class PAR_FIFO(Schedule):
    def __init__(self, num_cpu: int):
        super().__init__()
        self.algorithm_name = "PAR_FIFO"
        self.num_cpu = num_cpu
        self.queue_scope = "local"
        self.cpu_queue = { i: True for i in range(self.num_cpu)}
        #True la CPU đang rảnh, False là CPU đang bận
    
    def is_cpu_available(self):
        for cpu_id, available in self.cpu_queue.items()  :
            if available:
                return cpu_id, available
        return None, False
    
    def estimate(self, processes: Processes) -> None:
        self.steps = {i: [] for i in range(self.num_cpu)}
        self._reset_history()
        self.cpu_queue = {i: True for i in range(self.num_cpu)}
        processes = self._copy_sorted_processes(processes)
        cpu = {i:None for i in range(self.num_cpu)}
        cur = 0
        id = 0
        complete_processes = 0
        
        local_queues = {i: deque() for i in range(self.num_cpu)}

        def cpu_load(cpu_id: int) -> int:
            running_load = cpu[cpu_id][0].remaining_time if cpu[cpu_id] is not None else 0
            queued_load = sum(p.remaining_time for p in local_queues[cpu_id])
            return running_load + queued_load

        
        while complete_processes < len(processes):
            while id < len(processes) and processes[id].arrival_time <= cur:
                p = processes[id]
                
                target_cpu_id = min(range(self.num_cpu), key=lambda cpu_id: (cpu_load(cpu_id), cpu_id))
                local_queues[target_cpu_id].append(p)
                id+=1
                
            for cpu_id in range(self.num_cpu):
                if self.cpu_queue[cpu_id] and local_queues[cpu_id]:
                    p = local_queues[cpu_id].popleft()
                    run_time = p.remaining_time
                    cpu[cpu_id] = [p, run_time, cur]
                    self.cpu_queue[cpu_id] = False

            self._record_history(
                cur,
                running={
                    cpu_id: state[0].id if state is not None else None
                    for cpu_id, state in cpu.items()
                },
                queues={
                    cpu_id: [process.id for process in local_queues[cpu_id]]
                    for cpu_id in range(self.num_cpu)
                },
                loads={cpu_id: cpu_load(cpu_id) for cpu_id in range(self.num_cpu)},
            )

            active_cpus = {i: state for i,state in cpu.items() if state is not None}
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
                    complete_processes +=1
        self._record_history(
            cur,
            running={cpu_id: None for cpu_id in range(self.num_cpu)},
            queues={cpu_id: [] for cpu_id in range(self.num_cpu)},
            loads={cpu_id: 0 for cpu_id in range(self.num_cpu)},
        )
        self._update_basic_metrics(len(processes))
        return self.steps       
            
            
            
