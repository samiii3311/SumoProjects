# Scripts Directory

This directory contains Python automation scripts for managing, executing, and collecting data from SUMO (Simulation of Urban MObility) traffic simulations.

## Script Overview

* **`makeRoute.py`**: Generates and compiles route files (`.rou.xml`) and handles demand modeling for traffic simulation scenarios.
* **`runfile.py`**: Orchestrates and executes the SUMO simulation runs using the configured network and route files.
* **`sumo_collector.py`**: Gathers, parses, and logs output metrics or state data from simulation runs into the `Results/` directory.

## Usage Instructions

1. Ensure your environment has SUMO installed and the `SUMO_HOME` environment variable configured.
2. Verify that network files (`.net.xml`) and configuration files (`.sumocfg`) are correctly placed in the parent `Config/` directory.
3. Run the scripts in order: generate routes (`makeRoute.py`), execute simulations (`runfile.py`).

# Scripts ディレクトリ

このディレクトリには、SUMO (Simulation of Urban MObility) トラフィックシミュレーションの管理、実行、およびデータ収集を行うためのPython自動化スクリプトが格納されています。



## スクリプトの概要

* **`makeRoute.py`**: ルートファイル（`.rou.xml`）の生成・コンパイルを行い、シミュレーションシナリオの需要モデリングを処理します。
* **`runfile.py`**: 設定されたネットワークファイルとルートファイルを使用してSUMOシミュレーションの実行をオーケストレーションし、データ収集を自動的に呼び出します。
* **`sumo_collector.py`**: シミュレーション実行からの出力メトリクスや状態データを収集・解析してログに記録します（`runfile.py` 経由で自動的に呼び出されます）。

## 使用方法

* 環境にSUMOがインストールされており、`SUMO_HOME` 環境変数が正しく設定されていることを確認してください。
* ネットワークファイル（`.net.xml`）および設定ファイル（`.sumocfg`）が、親ディレクトリの `Config/` に正しく配置されていることを確認してください。
* `makeRoute.py` を実行してルートを生成した後、`runfile.py` を実行してワークフローを開始します。