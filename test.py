import algorithms
import process

ps = process.Processes()
ps.add(process.Process(20, 0, 1))
ps.add(process.Process(15, 15, 2))
ps.add(process.Process(12, 30, 1))
ps.add(process.Process(40, 50, 3))
ps.add(process.Process(20, 80, 3))
ps.add(process.Process(30, 90, 2))
ps.add(process.Process(25, 100, 1))
ps.add(process.Process(30, 90, 4))
ps.add(process.Process(20, 105, 2))
ps.add(process.Process(40, 120, 1))

schedule = algorithms.GLB_RR(num_cpu=4, time_quantum=15)
schedule.estimate(ps.copy())

schedule1 = algorithms.CPU_Affinity(num_cpu=4, time_quantum=5, hard=True)
schedule1.estimate(ps.copy())

print(schedule.algorithm_name)
for i in schedule.steps:
    print(f"CPU {i+1}:")
    for step in schedule.steps[i]:
        print(f"  {step}")

print(schedule1.algorithm_name)
for i in schedule1.steps:
    print(f"CPU {i+1}:")
    for step in schedule1.steps[i]:
        print(f"  {step}")