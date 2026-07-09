import traci
import os
from sumolib import checkBinary

def run(config):    
    sumo_binary = checkBinary('sumo-gui')
    traci.start([sumo_binary, "-c", config, "--start"])
    
    
    vehicle_wait_times = {}

    for step in range(9999):
        # Stop if all vehicles have left the network
        if traci.simulation.getMinExpectedNumber() <= 0:
            print(f"  Simulation ended early at step {step}")
            break
            
        
        active_vehicles = traci.vehicle.getIDList()
        
        for veh_id in active_vehicles:
            vehicle_wait_times[veh_id] = traci.vehicle.getAccumulatedWaitingTime(veh_id)
            
        traci.simulationStep()
        
    traci.close()
    
    stats = {
        "entrance_to_entrance": {"total_wait": 0.0, "count": 0},
        "entrance_to_parking": {"total_wait": 0.0, "count": 0},
        "parking_to_entrance": {"total_wait": 0.0, "count": 0},
        "other": {"total_wait": 0.0, "count": 0} 
    }

    for veh_id, final_wait_time in vehicle_wait_times.items():
        base_flow_id = veh_id.split(".")[0]
        parts = base_flow_id.split("_")
        
        if len(parts) == 4 and parts[0] == "flow" and parts[2] == "to":
            start_node = parts[1]
            end_node = parts[3]
            
            if start_node.startswith("e") and end_node.startswith("e"):
                category = "entrance_to_entrance"
            elif start_node.startswith("e") and end_node.startswith("p"):
                category = "entrance_to_parking"
            elif start_node.startswith("p") and end_node.startswith("e"):
                category = "parking_to_entrance"
            else:
                category = "other"
        else:
            category = "other"

        stats[category]["total_wait"] += final_wait_time
        stats[category]["count"] += 1

    return stats


if __name__ == "__main__":
    configs = [
        "./tenjin_one_way.sumocfg",
        "./tenjin_base.sumocfg",
        "./tenjin_bottom_merge.sumocfg"
    ]

    all_results = {}

    for config in configs:
        map_name = os.path.basename(config).replace(".sumocfg", "")
        print(f"\nStarting TraCI collection for: {config}...")
        
        # Run the simulation and store the returned stats dictionary
        all_results[map_name] = run(config)
        print(f"  Finished and closed: {config}")

    print("\n" + "="*65)
    print("FINAL WAIT TIME COMPARISON REPORT (TraCI Data)")
    print("="*65)

    categories = ["entrance_to_entrance", "entrance_to_parking", "parking_to_entrance"]

    for cat in categories:
        formatted_cat = cat.replace("_", " ").title()
        print(f"\n### {formatted_cat.upper()} ###")
        print(f"{'Map Configuration':<25} | {'Avg Wait (s)':<15} | {'Total Vehicles'}")
        print("-" * 65)
        
        for map_name, stats in all_results.items():
            data = stats[cat]
            avg_wait = data["total_wait"] / data["count"] if data["count"] > 0 else 0
            
            display_name = map_name.replace("tenjin_", "").replace("_", " ").title()
            print(f"{display_name:<25} | {avg_wait:<15.2f} | {data['count']}")
            
    print("\n")