import traci
import os
import random
import xml.etree.ElementTree as ET
import sumolib 
from sumolib import checkBinary

# Map the entrance of a parking lot to its corresponding exit node
PARKING_MAP = {
    "p1": "p2", 
    "p3": "p4", 
    "p5": "p6", 
    "p7": "p8", 
    "p9": "p10", 
    "p11": "p12"
}
EXTERNAL_EDGES = [f"e{i}" for i in range(1, 9)] 

def run_and_collect_traci_data(config):
    """Runs the SUMO simulation with A* routing and collects wait times."""
    
    tree = ET.parse(config)
    net_file_name = tree.find('input/net-file').get('value')
    net_path = os.path.join(os.path.dirname(config), net_file_name)
    net = sumolib.net.readNet(net_path, withPrograms=False, withLatestPrograms=False)

    sumo_binary = checkBinary('sumo')
    
    # Start TraCI with A* routing enabled
    traci.start([
        sumo_binary, 
        "-c", config, 
        "--start",
        "--routing-algorithm", "astar"
    ])
    
    vehicle_wait_times = {}
    parked_cars = [] 
    
    for step in range(14400): 
        # 1. CHECK FOR ARRIVALS
        arrived_vehicles = traci.simulation.getArrivedIDList()
        for veh_id in arrived_vehicles:
            if "_to_p" in veh_id:
                base_flow_id = veh_id.split(".")[0]
                parts = base_flow_id.split("_")
                
                if len(parts) == 4:
                    park_in_node = parts[3] 
                    if park_in_node in PARKING_MAP:
                        park_out_node = PARKING_MAP[park_in_node] 
                        respawn_step = step + 1800 + random.randint(0, 1800)
                        
                        parked_cars.append({
                            "original_id": veh_id,
                            "out_node": park_out_node,
                            "respawn_time": respawn_step
                        })

        # 2. CHECK FOR DEPARTURES (Respawning with dynamic routing)
        ready_to_spawn = [car for car in parked_cars if car["respawn_time"] <= step]
        parked_cars = [car for car in parked_cars if car["respawn_time"] > step]
        
        for car in ready_to_spawn:
            park_out_node = car["out_node"]
            random_exit = random.choice(EXTERNAL_EDGES)
            new_veh_id = f"flow_{park_out_node}_to_{random_exit}.respawn_{car['original_id']}"
            
            try:
                out_edges = net.getNode(park_out_node).getOutgoing()
                in_edges = net.getNode(random_exit).getIncoming()
                
                if out_edges and in_edges:
                    start_edge = out_edges[0].getID() 
                    end_edge = in_edges[0].getID()    
                    
                    route_edges = traci.simulation.findRoute(start_edge, end_edge).edges
                    
                    if route_edges:
                        route_id = f"route_{new_veh_id}"
                        traci.route.add(route_id, route_edges)
                        traci.vehicle.add(new_veh_id, routeID=route_id)
                        print(f"  Respawned vehicle {new_veh_id} from {park_out_node} to {random_exit} at step {step}")

            except Exception as e:
                pass 

        # 3. TRACK LIVE WAIT TIMES
        newly_departed = traci.simulation.getDepartedIDList()
        for veh_id in newly_departed:
            traci.vehicle.rerouteTraveltime(veh_id, currentTravelTimes=True)

        # Track the wait times for all active cars
        active_vehicles = traci.vehicle.getIDList()
        for veh_id in active_vehicles:
            vehicle_wait_times[veh_id] = traci.vehicle.getAccumulatedWaitingTime(veh_id)
            
        # 4. CHECK EXIT CONDITION
        if traci.simulation.getMinExpectedNumber() <= 0 and len(parked_cars) == 0:
            print(f"  Simulation ended naturally at step {step}")
            break
            
        traci.simulationStep()
        
    traci.close()
    
    # 5. SORT THE DATA
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