# 歌詞タイミング（Lyric Timing）

ボーカル音源と歌詞テキストから、**歌詞の区切りごとの開始・終了秒**を出すツールです。
「カフェテラスにおいた　ドライシェリーに」のように、1行の途中（ドライシェリー の頭）の秒数まで分かります。
動画生成（MiniMax H3 / LTX など）でリップシンクする区間を決めるときに、開始秒・秒数・フレーム数をそのまま出せます。

- パソコンの中だけで動きます（初回のセットアップ以外はインターネット不要、音声はどこにも送られません）
- 歌詞の区切りごとの秒数を表で表示、手で直すこともできます
- 範囲を選ぶと 開始秒 / 秒数 / MiniMax H3 の length（17の倍数+5）/ LTX の length（8の倍数+1）を表示
- 選んだ範囲をその場で試聴
- SRT（字幕）/ CSV で書き出し

## 必要なもの

- Windows 10 / 11（64bit）
- 空き容量 約 10GB
- NVIDIA の GPU を推奨（なくても動きますが、解析に時間がかかります）
- 初回のセットアップ時のみインターネット接続（約 6GB ダウンロード）

## インストール

1. 右上の **Code → Download ZIP**（または Releases の zip）をダウンロードして解凍します
2. 解凍したフォルダを、**日本語やスペースを含まない場所**に置きます（例：`C:\lyric-timing`）
3. `setup.bat` をダブルクリックします。10〜30分ほどで終わります
   - Python や必要な部品、音声認識モデルは、すべてこのフォルダの中に入ります（パソコン本体の設定は変えません）
   - 途中で止まった場合は、もう一度 `setup.bat` を実行すると続きから進みます

## 使い方

1. `run.bat` をダブルクリックすると、ブラウザで画面が開きます（終了するときは黒い画面を閉じます）
2. **ボーカルのみの音源**（wav / mp3 など）と **歌詞（txt）** を入れて「解析」を押します
   - 伴奏入りの音源ではうまくいきません。ボーカルを分離した音源を使ってください
3. 「最初の区切り」「最後の区切り」を選ぶと、開始秒・秒数・フレーム数が出ます
4. 必要なら「SRT / CSV を書き出す」で保存します

### 歌詞の書き方

- 全角／半角スペースで区切った単位ごとに秒数が出ます。細かく知りたい所はスペースで区切ってください

```
[Verse 1]
カフェテラスにおいた　ドライシェリーに
傘がない　から　と
```

- `[Verse]` `【サビ】` などの見出し行は区間名として表示されます
- 歌詞と実際の歌が違う所（アドリブ・繰り返し）は、歌っているとおりに書くと精度が上がります

### 精度について

- 無音や息つぎの位置を使って境目を補正していますが、伸ばす音や英語の部分は 0.1〜0.3 秒ずれることがあります
- ずれていた時は、表の **開始秒・終了秒** を直接書き換えてください。書き換えた値で計算されます
- 解析結果は音源と同じフォルダに `〇〇_timing_xxxx.json` として保存され、次回はすぐに表示されます

### VRAM について（ComfyUI などと同時に使う場合）

最初に「解析」を押した時に音声認識モデルを読み込み、**黒い画面を閉じるまで VRAM を約 4GB 使い続けます**。

- VRAM に余裕がある方は、ComfyUI などと同時に使えます
- VRAM 12GB 以下で動画生成（MiniMax H3 など）をする方は、**先に必要な区間の秒数をまとめて控えてから、黒い画面を閉じて** ComfyUI を起動してください。同時に使うと、生成が遅くなったりメモリ不足で止まったりすることがあります
- 一度解析した曲は結果が保存されているので、開き直しても（同じ音源・歌詞なら）すぐ表示され、VRAM もほとんど使いません

## アンインストール

フォルダごと削除するだけです。

## ライセンス

MIT License（`LICENSE` を参照）。使用しているライブラリ・モデルのライセンスは `THIRD_PARTY_NOTICES.md` を参照してください。

---

## English

Lyric Timing aligns lyrics to a vocal stem and shows the start/end time of each lyric phrase (split by spaces), fully offline after setup.
Pick a range of phrases to get the start time, duration, and frame counts for MiniMax H3 (17k+5) and LTX (8k+1), preview the audio, and export SRT/CSV.

1. Download and unzip into a path without spaces or non-ASCII characters (e.g. `C:\lyric-timing`)
2. Run `setup.bat` once (downloads about 6 GB: Python, PyTorch, faster-whisper large-v3)
3. Run `run.bat`, drop a **vocal-only** audio file and a lyrics text file, then press 解析 (Analyze)

The UI is in Japanese and alignment is tuned for Japanese lyrics.

VRAM: after the first analysis the model stays loaded (about 4 GB VRAM) until you close the console window. On GPUs with 12 GB or less, note your timings first and close Lyric Timing before generating video in ComfyUI. Re-opening is instant for songs already analyzed (results are cached) and uses almost no VRAM.
