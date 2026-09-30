DNTSNE Hit & Blow Online 2.1 — クリーン版
Python / Flet で作成された Hit & Blow ゲームです。 オフライン練習モードとオンライン 1対1 対戦に対応しています。
インターフェースはすべて日本語です。
オンライン対戦では、それぞれのプレイヤーに別々の問題が割り当てられ、正解を最初にサーバーへ送信したプレイヤーが勝利します。
このリポジトリは、学習用コメントなどを削除したクリーン版のソースコードです。
デザインは黒・白・ベージュを基調としており、
DNTSNE — DeadNeuronsThatShouldNeverExist
のロゴおよびウォーターマークを使用しています。
カスタムのローディング画像は以下に配置されています。
assets/icons/loading-animation.png
実装済み機能
 • 桁数を指定したクイックマッチ
 • 6桁コードを使用したプライベートルーム
 • Split Screen UI
 • 左側：相手プレイヤーの全履歴
 • 右側：自分の履歴と入力欄
 • すべての回答をサーバー側で判定し、秘密の数字をクライアント側へ送信しない設計
 • 画面遷移、回答表示、入力エラー、結果表示のアニメーション
 • SQLite を使用した勝利数・ベストスコアランキング
 • サーバー接続なしで利用できるシングルプレイモード
 • Flet サイト、FastAPI、WebSocket API を1つの ASGI プロセスで実行
ルール：
3桁から8桁まで設定可能です。
秘密の数字および回答内では、同じ数字を重複して使用することはできません。
サイト・サーバーのローカル起動
Python 3.12 以上が必要です。
python -m venv .venv
Windows PowerShell：
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python server.py
Linux / macOS：
source .venv/bin/activate
pip install -r requirements.txt
python server.py
以下をブラウザで開きます。
http://127.0.0.1:8000
オンライン対戦をテストする場合は、2つの異なるブラウザで開くか、通常ウィンドウとシークレットウィンドウで開くだけで確認できます。
デスクトップクライアントとして起動
最初に server.py がローカルまたはリモートサーバー上で起動している必要があります。
$env:GAME_WS_URL="wss://game.example.com/api/ws"
python launch.py
GAME_WS_URL を指定しない場合、クライアントは以下へ接続します。
ws://127.0.0.1:8000/api/ws
サーバーへ接続できない場合でも、シングルプレイの練習モードは利用できます。
Docker
docker build -t hit-and-blow .

docker run --name hit-and-blow -p 8000:8000 -v hit-and-blow-data:/app/data hit-and-blow
動作確認：
http://127.0.0.1:8000/health
Cloudflare
このアプリケーションは動的な Python アプリケーションのため、常時稼働しているコンテナまたはプロセスを持つ origin サーバーが必要です。
Cloudflare はその前段に配置し、
 • DNS
 • HTTPS / WSS プロキシ
 • Cloudflare Tunnel
として利用できます。
Cloudflare Tunnel の設定例：
ingress:
  - hostname: game.example.com
    service: http://localhost:8000
  - service: http_status:404
ドメイン設定後、サイトは以下からアクセスできます。
https://game.example.com
ゲーム用 WebSocket は以下を使用します。
wss://game.example.com/api/ws
サーバー上で Web 版を起動する場合、GAME_WS_URL を変更する必要はありません。
Flet セッションは localhost 経由で API にアクセスします。
Uvicorn は 1 worker で起動してください。
ルーム情報およびクイックマッチの状態はプロセスのメモリ上に保存され、SQLite にはランキング情報のみ保存されます。
複数サーバーへ水平スケーリングする場合は、マッチ状態を Redis などの外部ストレージへ移す必要があります。
構成
 • launch.py — Flet GUI、各画面、アニメーション、イベント処理
 • generators.py — Hit & Blow の共通ルール
 • network.py — 非同期 WebSocket クライアント
 • game_core.py — マッチモデルおよび SQLite ランキング
 • game_server.py — ルーム、クイックマッチ、状態同期
 • server.py — Web サイトとゲームサーバーの統合起動ポイント
 • tests/ — ゲームルールおよびオンライン機能のテスト
テスト
python -m unittest discover -s tests -v