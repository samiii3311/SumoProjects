import os

# Import our custom function from the other file
from sumo_collector import run_and_collect_traci_data

if __name__ == "__main__":
    
    # 1. LIST YOUR MAPS
    configs = [
        "../Config/tenjin_one_way.sumocfg",#A
        "../Config/tenjin_base.sumocfg",#B
        "../Config/tenjin_bottom_merge.sumocfg"#C
    ]

    terminal = 'sumo-gui'  # 'sumo-gui' for gui, 'sumo' for command-line mode
    runTime = 86400  # 24 hours in seconds

    all_results = {}

    # 2. RUN THE SIMULATIONS
    for config in configs:
        map_name = os.path.basename(config).replace(".sumocfg", "")
        print(f"\nStarting TraCI collection for: {config}...")
        
        # Call the imported function
        all_results[map_name] = run_and_collect_traci_data(config,terminal,runTime)
        print(f"  Finished and closed: {config}")

    # 3. PRINT THE FINAL REPORT
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