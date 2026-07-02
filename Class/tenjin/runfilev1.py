import traci
import os
import random


from sumolib import checkBinary

sumogui = checkBinary('sumo')

configs = [
    "./tenjin_one_way.sumocfg",
    "./tenjin_base.sumocfg",
    "./tenjin_bottom_merge.sumocfg"
]

for config in configs:
    print(f"Starting: {config}")
    
    traci.start([sumogui, "-c", config, "--start"])
    
    
    for step in range(9999):
        if traci.simulation.getMinExpectedNumber() <= 0:
            print(f"Simulation ended early at step {step}")
            break
            
        traci.simulationStep()
        
    traci.close()
    print(f"Finished and closed: {config}\n")
