# 兜町トレーダー

実際の東証株価（主要45銘柄＋日経平均、2000年〜最新の日足終値）で遊ぶ投資シミュレーションゲーム。

▶ https://jtnwtamwjd-pixel.github.io/kabu-sim/

- オンライン対戦は PeerJS（WebRTC）で、ルーム番号 `kabusim-room-XXXXXX` でホストに接続
- `src.html` … ゲーム本体（`__DATA__` に株価データが埋め込まれる）
- `tools/fetch.py` … yfinance で株価を取得
- `tools/build.py` … 取得データを圧縮して `data.json` / `index.html` を生成
- `.github/workflows/update-prices` … 平日16:30/21:00(JST)に株価を更新して `gh-pages` に公開

株価データは Yahoo Finance 経由。ゲーム内の取引は仮想で、投資助言ではありません。
