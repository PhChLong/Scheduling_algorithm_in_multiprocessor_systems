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

GLB_RR = algorithms.GLB_RR(num_cpu=4, time_quantum=15)
GLB_RR.estimate(ps.copy())

CPU_Affinity = algorithms.CPU_Affinity(num_cpu=4, time_quantum=5, hard=True)
CPU_Affinity.estimate(ps.copy())

load_balancing = algorithms.LoadBalancing(num_cpu= 4)
load_balancing.estimate(ps.copy())

print(GLB_RR.algorithm_name)
for i in GLB_RR.steps:
    print(f"CPU {i+1}:")
    for step in GLB_RR.steps[i]:
        print(f"  {step}")

print(CPU_Affinity.algorithm_name)
for i in CPU_Affinity.steps:
    print(f"CPU {i+1}:")
    for step in CPU_Affinity.steps[i]:
        print(f"  {step}")
    
print(load_balancing.algorithm_name)
for i in load_balancing.steps:
    print(f"CPU {i+1}:")
    for step in load_balancing.steps[i]:
        print(f"  {step}")