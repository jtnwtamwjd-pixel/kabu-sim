# 兜町トレーダー

実際の東証株価（東証プライム全銘柄＋日経平均、2000年〜最新の日足終値）で遊ぶ投資シミュレーションゲーム。

▶ https://jtnwtamwjd-pixel.github.io/kabu-sim/

- オンライン対戦は PeerJS（WebRTC）で、ルーム番号 `kabusim-room-XXXXXX` でホストに接続
- `src.html` … ゲーム本体（`__DATA__` に株価データが埋め込まれる）
- `tools/fetch_prime.py` … JPXの上場銘柄一覧からプライム銘柄を選び、yfinance で日足を取得して `manifest.json` と年別の `y/YYYY.json` を生成
- `tools/fetch_profile.py` … 企業プロフィール（Wikipedia の概要・Wikidata の設立/本社・Yahoo Finance の財務指標）を `data/profile.json` に生成（毎週日曜に自動更新）
- `tools/fetch.py` / `tools/build.py` … 主要銘柄だけを埋め込んだオフライン版用
- `.github/workflows/update-prices` … 平日16:30/21:00(JST)に株価を更新して `gh-pages` に公開

## 割安株スクリーナー

▶ https://jtnwtamwjd-pixel.github.io/kabu-sim/screen/

東証全銘柄（プライム・スタンダード・グロース）を PBR・ROE・自己資本比率（初期値 1倍以下・10%以上・40%以上）に加え、PER・予想PER・PSR・EV/EBITDA・ネットキャッシュ比率・ROA・利益率・流動比率・D/E・成長率・配当性向・連続増配・52週高値比など全27指標の上限/下限で絞り込む。

- `screen.html` … 画面（`screen/index.html` として公開、`screen/data.json` を読む）
- `tools/fetch_screen.py` … JPX の銘柄一覧＋ yfinance で指標を取得して `data/screen.json` を生成
- `.github/workflows/update-screen` … 平日15:45(JST)に指標を更新し、終わったら update-prices を起動して公開

株価データは Yahoo Finance 経由。ゲーム内の取引は仮想で、投資助言ではありません。
