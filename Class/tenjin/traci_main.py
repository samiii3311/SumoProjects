"""
traci_main.py
============================================================
天神地区 SUMOシミュレーション - TraCI制御スクリプト

機能:
    1. 車両の動的追加（1時間1000台 / 3.6秒に1台 / ランダムルート）
    2. 駐車場での1時間待機
    3. 混雑検知 → Dijkstra経路再探索

実行方法:
    python traci_main.py
============================================================
"""

import traci
import random

random.seed(42)

# ============================================================
# 設定値
# ============================================================

SUMO_CFG         = "tenjin.sumocfg"
PARKING_WAIT_SEC = 3600              # 駐車場待機時間（1時間）
CHECK_INTERVAL   = 60                # 混雑チェック間隔（秒）
CONGESTION_SPEED = 10 / 3.6         # 混雑判定速度（10km/h → m/s）
CONGESTION_COUNT = 2                 # 連続n回で再探索トリガー
REROUTE_COOLDOWN = 120               # 再探索クールダウン（秒）
PARKING_PROB     = 0.2               # 駐車場へ向かう確率
SIM_END=10800

# 車両投入設定（1時間1000台）
VEHICLE_PER_HOUR = 1000
INSERT_INTERVAL  = 3600 / VEHICLE_PER_HOUR  # 3.6秒に1台

# ============================================================
# ノード定義 ※数字順
# ============================================================

E_NODES    = ["e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8"]
P_ENTRANCE = ["p1", "p3", "p5", "p7", "p9",  "p11"]  # 奇数=入口
P_EXIT     = ["p2", "p4", "p6", "p8", "p10", "p12"]  # 偶数=出口

# ルートID一覧（routes_pattern2_vehicle.rou.xmlで定義済み）
E2E_ROUTES = [f"route_{fr}_{to}" for fr in E_NODES for to in E_NODES if fr != to]
E2P_ROUTES = [f"route_{fr}_{to}" for fr in E_NODES for to in P_ENTRANCE]
P2E_ROUTES = [f"route_{fr}_{to}" for fr in P_EXIT   for to in E_NODES]

# 駐車場入口エッジ（p奇数ノードへの入口エッジ）
# ※ sumolib で事前に取得した値
P_ENTRANCE_EDGES = {
    "p1":  "E2",
    "p3":  "E31",
    "p5":  "E10",
    "p7":  "E32",
    "p9":  "j22",
    "p11": "E33",
}

# ============================================================
# 状態管理
# ============================================================

parked_vehicles   = {}
rerouted_vehicles = {}
congestion_count  = {}
veh_counter       = 0
last_insert_time  = 0


# ============================================================
# 車両追加関数
# ============================================================

def add_veh(n, route_id, type_id="car"):
    """
    n台の車両をrouteIDを指定して追加する

    Parameters:
        n        : 追加する台数
        route_id : XMLで定義したrouteのID
        type_id  : vTypeのID（デフォルト: "car"）
    """
    global veh_counter
    for _ in range(n):
        veh_id = f"veh_{veh_counter:05d}"
        veh_counter += 1
        try:
            traci.vehicle.add(
                vehID       = veh_id,
                routeID     = route_id,
                typeID      = type_id,
                depart      = "now",
                departLane  = "best",
                departPos   = "base",
                departSpeed = "0"
            )
        except traci.exceptions.TraCIException as e:
            print(f"  [警告] 車両追加失敗: {veh_id} -> {e}")


def add_veh_random():
    """ランダムなルートで1台追加（3.6秒に1台ペース）"""
    global veh_counter
    veh_id = f"veh_{veh_counter:05d}"
    veh_counter += 1

    r = random.random()
    if r < 0.70:
        route_id = random.choice(E2E_ROUTES)
    elif r < 0.85:
        route_id = random.choice(E2P_ROUTES)
    else:
        route_id = random.choice(P2E_ROUTES)

    try:
        traci.vehicle.add(
            vehID       = veh_id,
            routeID     = route_id,
            typeID      = "car",
            depart      = "now",
            departLane  = "best",
            departPos   = "base",
            departSpeed = "0"
        )
    except traci.exceptions.TraCIException as e:
        print(f"  [警告] 車両追加失敗: {veh_id} ({route_id}) -> {e}")


# ============================================================
# 駐車場制御関数
# ============================================================

def send_to_parking(veh_id, current_time):
    """車両をパーキングエッジへ誘導し、待機時間を登録"""
    try:
        parking_node = random.choice(list(P_ENTRANCE_EDGES.keys()))
        parking_edge = P_ENTRANCE_EDGES[parking_node]
        traci.vehicle.changeTarget(veh_id, parking_edge)
        end_time = current_time + PARKING_WAIT_SEC
        parked_vehicles[veh_id] = end_time
        print(f"  [入庫] {veh_id} -> {parking_node}({parking_edge}) "
              f"(出庫予定: {int(end_time)//3600:02d}:{(int(end_time)%3600)//60:02d})")
    except traci.exceptions.TraCIException:
        pass


def handle_parking(current_time):
    """1時間経過した駐車車両を出庫させる"""
    finished = []
    for veh_id, end_time in parked_vehicles.items():
        if current_time >= end_time:
            try:
                route_id = random.choice(E2E_ROUTES)
                traci.vehicle.setRouteID(veh_id, route_id)
                traci.vehicle.rerouteTraveltime(veh_id, currentTravelTimes=True)
                print(f"  [出庫] {veh_id} -> {route_id}")
            except traci.exceptions.TraCIException:
                pass
            finished.append(veh_id)
    for veh_id in finished:
        del parked_vehicles[veh_id]


# ============================================================
# 混雑制御関数
# ============================================================

def check_congestion_and_reroute(current_time):
    """混雑エッジの車両をDijkstra法で再探索する"""
    total = 0
    for edge_id in traci.edge.getIDList():
        if edge_id.startswith(":"):
            continue

        speed = traci.edge.getLastStepMeanSpeed(edge_id)
        if 0 <= speed < CONGESTION_SPEED:
            congestion_count[edge_id] = congestion_count.get(edge_id, 0) + 1
        else:
            congestion_count[edge_id] = 0

        if congestion_count.get(edge_id, 0) >= CONGESTION_COUNT:
            for veh_id in traci.edge.getLastStepVehicleIDs(edge_id):
                if veh_id in parked_vehicles:
                    continue
                last = rerouted_vehicles.get(veh_id, -REROUTE_COOLDOWN)
                if current_time - last < REROUTE_COOLDOWN:
                    continue
                try:
                    traci.vehicle.rerouteTraveltime(veh_id, currentTravelTimes=True)
                    rerouted_vehicles[veh_id] = current_time
                    total += 1
                except traci.exceptions.TraCIException:
                    pass
    return total


# ============================================================
# メインループ
# ============================================================

def run():
    global last_insert_time
    traci.start(["sumo-gui", "-c", SUMO_CFG])
    add_veh_random()
    step           = 0
    last_check     = 0
    total_reroutes = 0
    total_parked   = 0

    print("=" * 55)
    print("TraCI制御開始")
    print(f"  車両投入ペース: {VEHICLE_PER_HOUR}台/時間（{INSERT_INTERVAL}秒に1台）")
    print(f"  駐車場待機時間: {PARKING_WAIT_SEC}秒（{PARKING_WAIT_SEC//3600}時間）")
    print(f"  駐車場確率    : {int(PARKING_PROB*100)}%")
    print("=" * 55)

    while traci.simulation.getTime() < SIM_END:
        traci.simulationStep()
        current_time = traci.simulation.getTime()
        step += 1

        # ── 車両をランダムルートで自動投入（3.6秒に1台）──
        if current_time - last_insert_time >= INSERT_INTERVAL:
            add_veh_random()
            last_insert_time = current_time

        # ── 新しく出発した車両を一部駐車場へ ──
        for veh_id in traci.simulation.getDepartedIDList():
            if random.random() < PARKING_PROB:
                send_to_parking(veh_id, current_time)
                total_parked += 1

        # ── 駐車出庫管理 ──
        handle_parking(current_time)

        # ── 混雑チェック（60秒ごと）──
        if current_time - last_check >= CHECK_INTERVAL:
            last_check = current_time
            total_reroutes += check_congestion_and_reroute(current_time)

        # ── 進捗表示（10分ごと）──
        if step % 600 == 0:
            print(f"[{int(current_time)//3600:02d}:{(int(current_time)%3600)//60:02d}] "
                  f"走行中:{traci.vehicle.getIDCount()}台 / "
                  f"駐車中:{len(parked_vehicles)}台 / "
                  f"累計投入:{veh_counter}台 / "
                  f"累計再探索:{total_reroutes}台")

    traci.close()
    print("=" * 55)
    print("シミュレーション完了")
    print(f"  累計投入     : {veh_counter}台")
    print(f"  累計経路再探索: {total_reroutes}台")
    print(f"  累計駐車入庫 : {total_parked}台")
    print("=" * 55)


if __name__ == "__main__":
    run()
