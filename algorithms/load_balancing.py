from .schedule import Schedule
from .schedule_step import ScheduleStep

class LoadBalancing(Schedule):
    def __init__(self, num_cpu: int = 4):
        super().__init__()
        self.algorithm_name = "Load Balancing"
        self.num_cpu = num_cpu
        
    def push_migration(self):
        
        