"""歌詞タイミング（画面）：ボーカル音源＋歌詞 → 区切りごとの秒数、範囲を選ぶと開始秒・秒数・フレーム数"""
import os
import tempfile
from pathlib import Path

import gradio as gr
import numpy as np
import pandas as pd
import soundfile as sf

import aligner as A

COLS = ["No", "区間", "行", "区切り", "開始", "終了", "長さ", "開始秒", "終了秒"]


def rows_to_df(rows):
    data = [[r["no"], r["section"], r["line"], r["unit"], A.tc(r["start"]), A.tc(r["end"]),
             round(r["end"] - r["start"], 2), r["start"], r["end"]] for r in rows]
    return pd.DataFrame(data, columns=COLS)


def df_to_rows(df):
    rows = []
    for _, r in df.iterrows():
        rows.append({"no": int(r["No"]), "section": r["区間"], "line": int(r["行"]), "unit": str(r["区切り"]),
                     "start": float(r["開始秒"]), "end": float(r["終了秒"])})
    return rows


def choices(rows):
    return [f'{r["no"]}: {r["unit"]}  ({A.tc(r["start"])})' for r in rows]


def load_lyrics_file(f):
    return A.read_text(f) if f else gr.update()


def analyze(audio, lyrics, force):
    if not audio:
        raise gr.Error("ボーカル音源を入れてください")
    if not lyrics or not lyrics.strip():
        raise gr.Error("歌詞を入れてください")
    if force:
        A.cache_path(audio, lyrics).unlink(missing_ok=True)
    gr.Info("解析中…（初回はモデル読み込みで少しかかります）")
    res, cached = A.align_cached(audio, lyrics)
    rows = res["rows"]
    df = rows_to_df(rows)
    ch = choices(rows)
    msg = f'{len(rows)} 区切り / 曲の長さ {A.tc(res["duration"])}' + ("（前回の解析結果を使用）" if cached else "")
    return df, gr.update(choices=ch, value=ch[0]), gr.update(choices=ch, value=ch[0]), msg


def _idx(sel):
    return int(sel.split(":")[0]) - 1 if sel else None


def calc(df, a_sel, b_sel, pre, post, audio, mix):
    if df is None or len(df) == 0 or a_sel is None or b_sel is None:
        return "", None, None
    rows = df_to_rows(df)
    i, j = sorted((_idx(a_sel), _idx(b_sel)))
    first, last = rows[i], rows[j]
    start = max(0.0, first["start"] - pre)
    end = last["end"] + post
    dur = end - start
    text = "　".join(r["unit"] for r in rows[i:j + 1])
    h3 = A.h3_frames(dur)
    ltx = A.ltx_frames(dur)
    out = (f"歌詞　　：{text}\n"
           f"歌の区間：{A.tc(first['start'])} 〜 {A.tc(last['end'])}（{last['end'] - first['start']:.2f} 秒）\n"
           f"\n"
           f"開始秒　：{start:.2f}\n"
           f"秒数　　：{dur:.2f}\n"
           f"タイムコード：{A.tc(start)} 〜 {A.tc(end)}\n"
           f"\n"
           f"MiniMax H3 length：{h3} フレーム（{h3 / 24:.2f} 秒, 24fps・17の倍数+5）\n"
           f"LTX length　　　 ：{ltx} フレーム（{ltx / 24:.2f} 秒, 24fps・8の倍数+1）")
    clips = []
    for src in (audio, mix):
        if not src:
            clips.append(None)
            continue
        info = sf.info(src)
        data, sr = sf.read(src, start=int(start * info.samplerate), stop=int(end * info.samplerate), dtype="float32")
        clips.append((sr, data))
    return out, clips[0], clips[1]


def export(df, audio):
    if df is None or len(df) == 0:
        raise gr.Error("先に解析してください")
    rows = df_to_rows(df)
    base = Path(audio).stem if audio else "lyrics"
    outdir = Path(tempfile.mkdtemp())
    p_line = outdir / f"{base}_行.srt"
    p_unit = outdir / f"{base}_区切り.srt"
    p_csv = outdir / f"{base}_タイミング.csv"
    p_line.write_text(A.to_srt(rows, by_line=True), encoding="utf-8")
    p_unit.write_text(A.to_srt(rows, by_line=False), encoding="utf-8")
    df.to_csv(p_csv, index=False, encoding="utf-8-sig")
    return [str(p_line), str(p_unit), str(p_csv)]


HELP = """### 使い方
1. **ボーカル音源**（ボーカルのみの wav / mp3）と **歌詞** を入れて「解析」
2. 歌詞は **全角／半角スペースで区切った単位** ごとに秒数が出ます（例：`カフェテラスにおいた　ドライシェリーに` → 2つ）。細かく知りたい所はスペースで区切ってから解析してください。`[Verse]` などの見出し行は区間名になります
3. 「最初」「最後」の区切りを選ぶと、開始秒・秒数・フレーム数が出ます。前後の余裕も足せます
4. 表の **開始秒・終了秒** は直接書き換えられます（ずれていた時の手直し用）。書き換えた値で計算されます
"""

with gr.Blocks(title="歌詞タイミング") as demo:
    gr.Markdown("# 歌詞タイミング\nボーカル音源と歌詞から、歌詞の区切りごとの開始・終了秒を出します（ローカルで動作）")
    with gr.Row():
        with gr.Column(scale=1):
            audio = gr.File(label="① ボーカル音源（ボーカルのみ）", file_types=["audio"], type="filepath")
            mix = gr.File(label="（任意）完成ミックス：試聴用", file_types=["audio"], type="filepath")
            lyr_file = gr.File(label="② 歌詞ファイル（txt）", file_types=[".txt"], type="filepath")
        with gr.Column(scale=1):
            lyrics = gr.Textbox(label="歌詞（ファイルを入れると自動で入ります。直接貼り付けても OK）", lines=14)
            with gr.Row():
                force = gr.Checkbox(label="前回の結果を使わず解析し直す", value=False)
                run = gr.Button("解析", variant="primary")
            status = gr.Markdown()
    gr.Markdown(HELP)
    table = gr.Dataframe(headers=COLS, interactive=True, wrap=True, label="区切りごとの時間（開始秒・終了秒は編集可）",
                         column_widths=["5%", "8%", "5%", "32%", "10%", "10%", "8%", "11%", "11%"])
    gr.Markdown("### 範囲を選ぶ")
    with gr.Row():
        a_sel = gr.Dropdown(label="最初の区切り", choices=[])
        b_sel = gr.Dropdown(label="最後の区切り", choices=[])
    with gr.Row():
        pre = gr.Slider(0, 2, value=0.2, step=0.05, label="前の余裕（秒）")
        post = gr.Slider(0, 2, value=0.2, step=0.05, label="後の余裕（秒）")
    result = gr.Textbox(label="結果", lines=10, buttons=["copy"])
    with gr.Row():
        clip_v = gr.Audio(label="この範囲（ボーカル）", interactive=False)
        clip_m = gr.Audio(label="この範囲（ミックス）", interactive=False)
    with gr.Row():
        exp = gr.Button("SRT / CSV を書き出す")
        files = gr.File(label="書き出したファイル", file_count="multiple")

    lyr_file.change(load_lyrics_file, lyr_file, lyrics)
    run.click(analyze, [audio, lyrics, force], [table, a_sel, b_sel, status])
    calc_in = [table, a_sel, b_sel, pre, post, audio, mix]
    calc_out = [result, clip_v, clip_m]
    for c in (a_sel, b_sel, pre, post, table):
        c.change(calc, calc_in, calc_out)
    exp.click(export, [table, audio], files)

if __name__ == "__main__":
    demo.queue().launch(inbrowser=True, server_name="127.0.0.1", server_port=int(os.environ["LYRIC_TIMING_PORT"]) if os.environ.get("LYRIC_TIMING_PORT") else None)
