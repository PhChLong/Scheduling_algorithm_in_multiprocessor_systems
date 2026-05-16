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
        self.turnaround_time:     int   = 0
        self.waiting_time:        int   = 0
        self.response_time:       int   = 0
        self.cpu_utilization:     float = 0.0
        self.throughput:          float = 0.0
        self.avg_turnaround_time: float = 0.0
        self.avg_waiting_time:    float = 0.0
        self.avg_response_time:   float = 0.0
        self.num_cpu:              int   = 0
        self.steps: dict[int, list[ScheduleStep]] = {}

    @abstractmethod
    def estimate(self, processes: Processes) -> None: ...
