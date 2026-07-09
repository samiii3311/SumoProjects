# Your nodes (junctions)
exits = [f"e{i}" for i in range(1, 9)] # e1 to e8
parking_in = ["p1", "p3", "p5", "p7", "p9", "p11"]
parking_out = ["p2", "p4", "p6", "p8", "p10", "p12"]

# Set your desired traffic density (Vehicles per Hour)
TOTAL_VPH = 1000 
ENDLESS_TIME = 86400 * 365 # 1 year in seconds

# Calculate probabilities per second
prob_exit_to_exit = (TOTAL_VPH * 0.70) / (56 * 3600)  
prob_exit_to_park = (TOTAL_VPH * 0.30) / (48 * 3600)  
# prob_park_to_exit = (TOTAL_VPH * 0.15) / (48 * 3600)  

with open("traffic.rou.xml", "w") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<routes>\n')
    f.write('    \n')
    f.write('    <vType id="car" vClass="passenger" sigma="0.5"/>\n\n')

    f.write('    \n')

    # 1. Flows for Exit to Exit (70%)
    f.write('    \n')
    for start in exits:
        for end in exits:
            if start != end:
                f.write(f'    <flow id="flow_{start}_to_{end}" type="car" fromJunction="{start}" toJunction="{end}" begin="0" end="{ENDLESS_TIME}" probability="{prob_exit_to_exit:.6f}"/>\n')

    # 2. Flows for Exit to Parking (15%)
    f.write('\n    \n')
    for start in exits:
        for end in parking_in:
            f.write(f'    <flow id="flow_{start}_to_{end}" type="car" fromJunction="{start}" toJunction="{end}" begin="0" end="{ENDLESS_TIME}" probability="{prob_exit_to_park:.6f}"/>\n')

    # 3. Flows for Parking to Exit (15%)
    # f.write('\n    \n')
    # for start in parking_out:
    #     for end in exits:
    #         f.write(f'    <flow id="flow_{start}_to_{end}" type="car" fromJunction="{start}" toJunction="{end}" begin="0" end="{ENDLESS_TIME}" probability="{prob_park_to_exit:.6f}"/>\n')

    f.write('</routes>\n')

print("Success! 'traffic.rou.xml' generated with junction routing.")