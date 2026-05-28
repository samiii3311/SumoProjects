#!/usr/bin/env python3
"""
traci_dynamic_routing.py
============================================================
天神地区 SUMOシミュレーション - TraCI動的ルーティング制御スクリプト
シナリオA / B / C 共通

使用方法:
    python traci_dynamic_routing.py --scenario A
    python traci_dynamic_routing.py --scenario B
    python traci_dynamic_routing.py --scenario C

オプション:
    --scenario  A / B / C  (必須)
    --gui       sumo-gui を使用 (デフォルト: sumo)
    --port      TraCIポート番号 (デフォルト: 8813)

Excelパラメータ設定ファイル「TraCI閾値設定」シートの値を
THRESHOLD_* 定数として使用する。値を変更する場合はここを編集。
============================================================
"""

import os
import sys
import argparse
import traci
import sumolib

# ============================================================
# TraCI閾値設定（Excelパラメータ設定ファイルより）
# ============================================================

# 混雑判定
THRESHOLD_TRAVEL_TIME_SEC     = 90      # 旅行時間閾値（秒）
THRESHOLD_MEAN_SPEED_MS       = 10/3.6  # 平均速度閾値（m/s） ← 10km/h
CHECK_INTERVAL_SEC            = 60      # 混雑チェック間隔（秒）
CONGESTION_COUNT_TRIGGER      = 2       # 連続混雑回数でトリガー

# 経路再探索
REROUTE_LOOKAHEAD_M           = 500.0   # 先読み距離（m）
COST_WEIGHT_TRAVELTIME        = 1.0     # 旅行時間コスト重み
COST_WEIGHT_DISTANCE          = 0.1     # 距離コスト重み
MAX_DETOUR_RATIO              = 1.5     # 最大迂回距離倍率
REROUTE_COOLDOWN_SEC          = 120     # 再探索クールダウン（秒）

# 天神通線誘導
TENJIN_DORI_COST_BONUS        = 0.8     # 天神通線コストボーナス（<1で優先）
REROUTE_ONLY_WHEN_WATANABE_CONG = True  # 渡辺通り混雑時のみ誘導

# ============================================================
# 監視対象エッジID（tenjin.net.xml のエッジIDに合わせて変更）
# ============================================================

MONITORED_EDGES = {
    "watanabe_n":    {"name": "渡辺通り（北向き）", "congestion_count": 0},
    "watanabe_s":    {"name": "渡辺通り（南向き）", "congestion_count": 0},
    "meiji_e":       {"name": "明治通り（東向き）", "congestion_count": 0},
    "meiji_w":       {"name": "明治通り（西向き）", "congestion_count": 0},
    "showa_w":       {"name": "昭和通り（西向き）", "congestion_count": 0},
    "tenjin_center": {"name": "天神中心部",         "congestion_count": 0},
}

# シナリオBとCのみ存在するエッジ
EDGES_SCENARIO_B_C = {
    "tenjin_dori_n": {"name": "天神通線（北向き）", "congestion_count": 0},
    "tenjin_dori_s": {"name": "天神通線（南向き）", "congestion_count": 0},
}

# シナリオCのみ存在するエッジ
EDGES_SCENARIO_C = {
    "highway_exit":   {"name": "都市高速出口",       "congestion_count": 0},
    "parking_access": {"name": "PAアクセス道",        "congestion_count": 0},
}

# ============================================================
# コンフィグ設定
# ============================================================

SCENARIO_CONFIGS = {
    "A": {
        "cfg": "scenarioA/tenjin_A.sumocfg",
        "output_prefix": "scenarioA/output/",
        "has_tenjin_dori_s": False,
        "has_highway":       False,
    },
    "B": {
        "cfg": "scenarioB/tenjin_B.sumocfg",
        "output_prefix": "scenarioB/output/",
        "has_tenjin_dori_s": True,
        "has_highway":       False,
    },
    "C": {
        "cfg": "scenarioC/tenjin_C.sumocfg",
        "output_prefix": "scenarioC/output/",
        "has_tenjin_dori_s": True,
        "has_highway":       True,
    },
}


# ============================================================
# ヘルパー関数
# ============================================================

def get_edge_travel_time(edge_id: str) -> float:
    """道路の現在の旅行時間（秒）を取得する。"""
    try:
        length     = traci.edge.getLastStepLength(edge_id)        # 平均車両長
        mean_speed = traci.edge.getLastStepMeanSpeed(edge_id)     # m/s
        edge_length = traci.lane.getLength(edge_id + "_0")        # レーン長(m)
        if mean_speed > 0.1:
            return edge_length / mean_speed
        else:
            return THRESHOLD_TRAVEL_TIME_SEC * 3  # 停止中とみなす
    except traci.exceptions.TraCIException:
        return 0.0


def is_congested(edge_id: str) -> bool:
    """道路が混雑しているか判定する。"""
    travel_time = get_edge_travel_time(edge_id)
    mean_speed  = traci.edge.getLastStepMeanSpeed(edge_id)
    return (travel_time > THRESHOLD_TRAVEL_TIME_SEC or
            mean_speed   < THRESHOLD_MEAN_SPEED_MS)


def update_congestion_counts(monitored: dict) -> dict:
    """全監視エッジの混雑カウントを更新し、集計結果を返す。"""
    status = {}
    for edge_id, info in monitored.items():
        try:
            cong = is_congested(edge_id)
            if cong:
                info["congestion_count"] += 1
            else:
                info["congestion_count"] = 0
            status[edge_id] = {
                "congested":      cong,
                "count":          info["congestion_count"],
                "trigger":        info["congestion_count"] >= CONGESTION_COUNT_TRIGGER,
                "travel_time":    get_edge_travel_time(edge_id),
                "mean_speed_kph": traci.edge.getLastStepMeanSpeed(edge_id) * 3.6,
            }
        except traci.exceptions.TraCIException:
            status[edge_id] = {"congested": False, "count": 0, "trigger": False,
                                "travel_time": 0, "mean_speed_kph": 0}
    return status


def reroute_vehicles_on_congested_edge(edge_id: str,
                                       scenario: str,
                                       rerouted_vehicles: dict,
                                       current_time: float) -> int:
    """
    指定エッジで混雑が発生した場合、後続車両をDijkstra法で再探索する。
    戻り値: 再探索した車両台数
    """
    count = 0
    # 対象エッジに近い車両を取得
    try:
        vehicle_ids = traci.edge.getLastStepVehicleIDs(edge_id)
    except traci.exceptions.TraCIException:
        return 0

    for veh_id in vehicle_ids:
        # クールダウン確認
        if veh_id in rerouted_vehicles:
            if current_time - rerouted_vehicles[veh_id] < REROUTE_COOLDOWN_SEC:
                continue

        try:
            # 現在位置から目的地まで旅行時間を重みとして再探索
            traci.vehicle.rerouteTraveltime(veh_id, currentTravelTimes=True)
            rerouted_vehicles[veh_id] = current_time
            count += 1
        except traci.exceptions.TraCIException:
            pass

    return count


def adjust_tenjin_dori_cost(factor: float = TENJIN_DORI_COST_BONUS):
    """
    天神通線のルーティングコストを調整し、迂回を促進する。
    factor < 1.0: 天神通線を優先（コストを下げる）
    """
    for edge_id in ["tenjin_dori_n", "tenjin_dori_s"]:
        try:
            current_tt = traci.edge.getTraveltime(edge_id)
            traci.edge.adaptTraveltime(edge_id, current_tt * factor)
        except traci.exceptions.TraCIException:
            pass


# ============================================================
# メインシミュレーション制御
# ============================================================

def run_simulation(scenario: str, use_gui: bool = False, port: int = 8813):
    """TraCIを使ってシミュレーションを実行する。"""
    config = SCENARIO_CONFIGS[scenario]

    # 出力ディレクトリ作成
    os.makedirs(config["output_prefix"], exist_ok=True)

    # SUMO起動コマンド
    sumo_binary = "sumo-gui" if use_gui else "sumo"
    sumo_cmd = [
        sumo_binary,
        "-c", config["cfg"],
        "--remote-port", str(port),
        "--no-step-log",
    ]

    print(f"[TraCI] シナリオ {scenario} 開始")
    print(f"[TraCI] 設定ファイル: {config['cfg']}")

    traci.start(sumo_cmd, port=port)

    # 監視エッジをシナリオに応じて設定
    monitored = dict(MONITORED_EDGES)
    if config["has_tenjin_dori_s"]:
        monitored.update(EDGES_SCENARIO_B_C)
    if config["has_highway"]:
        monitored.update(EDGES_SCENARIO_C)

    rerouted_vehicles  = {}    # {vehicle_id: last_reroute_time}
    total_reroutes     = 0
    last_check_time    = 0

    step = 0
    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        current_time = traci.simulation.getTime()
        step += 1

        # CHECK_INTERVAL_SEC 秒ごとに混雑チェック
        if current_time - last_check_time >= CHECK_INTERVAL_SEC:
            last_check_time = current_time

            congestion_status = update_congestion_counts(monitored)

            # 渡辺通り混雑判定
            watanabe_cong = (
                congestion_status.get("watanabe_n", {}).get("trigger", False) or
                congestion_status.get("watanabe_s", {}).get("trigger", False)
            )

            # 天神通線コスト調整（シナリオB/C）
            if config["has_tenjin_dori_s"]:
                if not REROUTE_ONLY_WHEN_WATANABE_CONG or watanabe_cong:
                    adjust_tenjin_dori_cost(TENJIN_DORI_COST_BONUS)
                else:
                    # 混雑なければコストをリセット
                    adjust_tenjin_dori_cost(1.0)

            # 混雑トリガーが立っているエッジで再探索
            for edge_id, status in congestion_status.items():
                if status["trigger"]:
                    n = reroute_vehicles_on_congested_edge(
                        edge_id, scenario, rerouted_vehicles, current_time
                    )
                    total_reroutes += n
                    if n > 0:
                        print(f"  [t={int(current_time):6d}s] {edge_id} 混雑 "
                              f"(TT={status['travel_time']:.1f}s, "
                              f"{status['mean_speed_kph']:.1f}km/h) "
                              f"→ {n}台再探索")

        # 進捗表示（1時間ごと）
        if step % 3600 == 0:
            n_vehicles = traci.vehicle.getIDCount()
            print(f"[t={int(current_time):6d}s = "
                  f"{int(current_time)//3600:02d}:{(int(current_time)%3600)//60:02d}] "
                  f"走行中: {n_vehicles}台 / 累計再探索: {total_reroutes}台")

    traci.close()
    print(f"\n[TraCI] シミュレーション完了")
    print(f"  累計経路再探索件数: {total_reroutes} 台")
    print(f"  出力先: {config['output_prefix']}")


# ============================================================
# エントリポイント
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="天神地区 SUMOシミュレーション TraCI動的ルーティング制御"
    )
    parser.add_argument(
        "--scenario", choices=["A", "B", "C"], required=True,
        help="実行するシナリオ: A（整備前）/ B（現状）/ C（将来計画）"
    )
    parser.add_argument(
        "--gui", action="store_true",
        help="sumo-gui を使用する（デフォルト: sumo）"
    )
    parser.add_argument(
        "--port", type=int, default=8813,
        help="TraCIポート番号（デフォルト: 8813）"
    )
    args = parser.parse_args()

    run_simulation(scenario=args.scenario, use_gui=args.gui, port=args.port)


if __name__ == "__main__":
    main()
