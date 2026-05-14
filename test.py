import algorithms
import process
print(123)
p1 = process.Process(1, 0, 10)
p2 = process.Process(2, 0, 4)
p3 = process.Process(3, 0, 8)
p4 = process.Process(4, 0, 5)
print(456)
processes = process.Processes()
processes.add(p1)
processes.add(p2)
processes.add(p3)
processes.add(p4)
print(789)
scheduler = algorithms.GLB_RR(time_quantum=1, num_processes=2)
print(10)
scheduler.estimate(processes)
for step in scheduler.steps:
    print(step)