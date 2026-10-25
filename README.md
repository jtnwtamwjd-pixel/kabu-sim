# 兜町トレーダー

実際の東証株価（東証プライム全銘柄＋日経平均、2000年〜最新の日足終値）で遊ぶ投資シミュレーションゲーム。

▶ https://jtnwtamwjd-pixel.github.io/kabu-sim/

- オンライン対戦は PeerJS（WebRTC）で、ルーム番号 `kabusim-room-XXXXXX` でホストに接続
- `src.html` … ゲーム本体（`__DATA__` に株価データが埋め込まれる）
- `tools/fetch_prime.py` … JPXの上場銘柄一覧からプライム銘柄を選び、yfinance で日足を取得して `manifest.json` と年別の `y/YYYY.json` を生成
- `tools/fetch.py` / `tools/build.py` … 主要銘柄だけを埋め込んだオフライン版用
- `.github/workflows/update-prices` … 平日16:30/21:00(JST)に株価を更新して `gh-pages` に公開

株価データは Yahoo Finance 経由。ゲーム内の取引は仮想で、投資助言ではありません。
