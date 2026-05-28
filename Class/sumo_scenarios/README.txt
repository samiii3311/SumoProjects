======================================================
 SUMO 天神地区シミュレーション - シナリオ別XMLファイル
======================================================

【ファイル構成】
sumo_scenarios/
├── scenarioA/          ← 整備前（天神通線一方通行）
│   ├── tenjin_A.sumocfg      メイン設定ファイル
│   ├── routes_A.rou.xml      車両ルート・フロー定義
│   └── tl_A.add.xml          信号制御設定
├── scenarioB/          ← 現状（天神通線2車線対面通行）
│   ├── tenjin_B.sumocfg
│   ├── routes_B.rou.xml
│   └── tl_B.add.xml
├── scenarioC/          ← 将来計画（都市高速出口・PA追加）
│   ├── tenjin_C.sumocfg
│   ├── routes_C.rou.xml
│   └── tl_C.add.xml
└── traci_dynamic_routing.py  ← TraCI制御スクリプト（共通）

【ネットワークファイルについて】
.net.xml は netconvert で生成します（シナリオ共通、または差分あり）。

  # 基本ネットワーク取得 & 変換
  python osmWebWizard.py  ← SUMOツール
  または
  netconvert --osm-files tenjin.osm.xml \
             --output-file tenjin.net.xml \
             --geometry.remove --roundabouts.guess \
             --junctions.join --tls.guess

  シナリオA: 天神通線エッジを one-way に設定
  シナリオB: 天神通線エッジを両方向2車線に設定
  シナリオC: B + 都市高速出口エッジ・PAエッジを追加

【エッジID凡例（.net.xml内のID）】
  watanabe_n  : 渡辺通り（北向き）
  watanabe_s  : 渡辺通り（南向き）
  meiji_e     : 明治通り（東向き）
  meiji_w     : 明治通り（西向き）
  showa_e     : 昭和通り（東向き）
  showa_w     : 昭和通り（西向き）
  kokutai_n   : 国体道路（北向き）
  tenjin_dori_n : 天神通線（北向き）
  tenjin_dori_s : 天神通線（南向き）
  tenjin_center : 天神中心部（内部エッジ）
  highway_exit  : 都市高速出口（シナリオCのみ）
  parking_area  : パーキングエリア（シナリオCのみ）

【実行コマンド】
  sumo-gui -c scenarioA/tenjin_A.sumocfg
  または TraCI制御:
  python traci_dynamic_routing.py --scenario A
