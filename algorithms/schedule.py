# schedule.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from algorithms.schedule_step import ScheduleStep
from process.process import Processes, Process


@dataclass
class SystemState:
    time:        int
    cpu:         str        # "P1", "Idle", "Finished"
    ready_queue: list[str]
    color:       str


class Schedule(ABC):
    def __init__(self):
        self.algorithm_name:      str   = ""

        self.num_cpu:              int   = 0
        self.steps: dict[int, list[ScheduleStep]] = {} # {cpu_id, list_of_scheduleStep}
        
        # cập nhật bằng estimate
        self.turnaround_time:     int   = 0
        self.waiting_time:        int   = 0
        self.response_time:       int   = 0
        self.cpu_utilization:     float = 0.0
        self.throughput:          float = 0.0
        self.avg_turnaround_time: float = 0.0
        self.avg_waiting_time:    float = 0.0
        self.avg_response_time:   float = 0.0

    @abstractmethod
    def estimate(self, processes: Processes) -> None: ...

    def _copy_sorted_processes(self, processes: Processes) -> list[Process]:
        return [process.copy() for process in processes.sorted_by_arrival()]

    def _update_basic_metrics(self, process_count_or_processes) -> None:
        if isinstance(process_count_or_processes, int):
            process_count = process_count_or_processes
            processes = []
        else:
            processes = list(process_count_or_processes)
            process_count = len(processes)

        total_time = max(
            (step.end_time for steps in self.steps.values() for step in steps),
            default=0,
        )
        busy_time = sum(
            step.end_time - step.begin_time
            for steps in self.steps.values()
            for step in steps
        )
        self.cpu_utilization = 0.0 if total_time == 0 else busy_time / (self.num_cpu * total_time)
        self.throughput = 0.0 if total_time == 0 else process_count / total_time
        self.turnaround_time = 0
        self.waiting_time = 0
        self.response_time = 0
        self.avg_turnaround_time = 0.0
        self.avg_waiting_time = 0.0
        self.avg_response_time = 0.0

        if not processes:
            return

        all_steps = [step for steps in self.steps.values() for step in steps]
        turnaround_time = 0
        waiting_time = 0
        response_time = 0
        completed_count = 0

        for process in processes:
            process_steps = [step for step in all_steps if step.process_id == process.id]
            if not process_steps:
                continue

            finish_time = max(step.end_time for step in process_steps)
            start_time = min(step.begin_time for step in process_steps)
            turnaround = finish_time - process.arrival_time
            actual_cpu_time = sum(step.end_time - step.begin_time for step in process_steps)
            waiting = turnaround - actual_cpu_time
            response = start_time - process.arrival_time

            turnaround_time += turnaround
            waiting_time += waiting
            response_time += response
            completed_count += 1

        self.turnaround_time = turnaround_time
        self.waiting_time = waiting_time
        self.response_time = response_time
        self.avg_turnaround_time = 0.0 if completed_count == 0 else turnaround_time / completed_count
        self.avg_waiting_time = 0.0 if completed_count == 0 else waiting_time / completed_count
        self.avg_response_time = 0.0 if completed_count == 0 else response_time / completed_count
