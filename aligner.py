"""歌詞タイミング：ボーカル音源と歌詞テキストから、区切りごとの開始・終了秒を出す（強制アライメント）"""
import difflib
import hashlib
import json
import math
import os
import re
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
SR = 16000
SECTION_RE = re.compile(r"^\s*[\[［【].*[\]］】]\s*$")
SPLIT_RE = re.compile(r"[ 　\t]+")

_model = None


def _prepare_dll_paths():
    # faster-whisper (CTranslate2) が torch 同梱の CUDA/cuDNN DLL を使えるようにする
    import torch
    lib = Path(torch.__file__).parent / "lib"
    if lib.is_dir():
        os.add_dll_directory(str(lib))
        os.environ["PATH"] = str(lib) + os.pathsep + os.environ.get("PATH", "")


def get_model(name=os.environ.get("LYRIC_TIMING_MODEL", "Systran/faster-whisper-large-v3")):
    global _model
    if _model is None:
        _prepare_dll_paths()
        import stable_whisper
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = stable_whisper.load_faster_whisper(
            name, device=device, compute_type="float16" if device == "cuda" else "int8")
    return _model


def read_text(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp932", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def parse_lyrics(text):
    """[Verse] などの見出しは区間名として残し、行を全角/半角スペースで区切りに分ける"""
    lines, section = [], ""
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if SECTION_RE.match(s):
            section = s.strip("[]［］【】 ")
            continue
        units = [u for u in SPLIT_RE.split(s) if u]
        lines.append({"section": section, "text": s, "units": units})
    return lines


def _norm(s):
    return "".join(ch for ch in unicodedata.normalize("NFKC", s).lower()
                   if not ch.isspace() and unicodedata.category(ch)[0] not in "PZ")


def load_audio(path):
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if sr != SR:
        import torch
        import torchaudio.functional as AF
        mono = AF.resample(torch.from_numpy(mono), sr, SR).numpy()
    return mono, len(data) / sr


def _char_times(result):
    """アライメント結果の各文字に (開始, 終了) を割り当てる（語の中は文字数で等分）"""
    chars, times = [], []
    for seg in result.segments:
        for w in seg.words:
            t = _norm(w.word)
            if not t:
                continue
            step = (w.end - w.start) / len(t)
            for k, ch in enumerate(t):
                chars.append(ch)
                times.append((w.start + step * k, w.start + step * (k + 1)))
    return "".join(chars), times


def find_gaps(audio, sr=SR, frame=0.02, min_gap=0.25, rel_db=-40.0, abs_db=-55.0):
    """ボーカル音源の無音区間 [(開始, 終了), ...]（ボーカルのみの音源が前提）"""
    w = int(frame * sr)
    n = len(audio) // w
    if n == 0:
        return []
    rms = np.sqrt((audio[:n * w].reshape(n, w) ** 2).mean(axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    thr = max(np.percentile(db, 99) + rel_db, abs_db)
    silent = db < thr
    gaps, i = [], 0
    while i < n:
        if silent[i]:
            j = i
            while j < n and silent[j]:
                j += 1
            if (j - i) * frame >= min_gap:
                gaps.append((i * frame, j * frame))
            i = j
        else:
            i += 1
    return gaps


def find_soft_gaps(audio, sr=SR, frame=0.02, smooth=0.3, min_gap=0.6, rel_db=-15.0):
    """息つぎ・残響だけの小さい区間（完全な無音ではないが歌っていない所）"""
    w = int(frame * sr)
    n = len(audio) // w
    if n == 0:
        return []
    db = 20 * np.log10(np.sqrt((audio[:n * w].reshape(n, w) ** 2).mean(axis=1)) + 1e-9)
    k = max(1, int(smooth / frame))
    db = np.convolve(db, np.ones(k) / k, mode="same")
    quiet = db < np.percentile(db, 99) + rel_db
    gaps, i = [], 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            if (j - i) * frame >= min_gap:
                gaps.append((i * frame, j * frame))
            i = j
        else:
            i += 1
    return gaps


def trim_edges(rows, gaps, max_stub=0.4):
    """区切りの頭やお尻だけが休みの向こう側にはみ出している時は、休みの端まで詰める"""
    for r in rows:
        for g in gaps:
            if not (r["start"] < g[0] and g[1] < r["end"]):
                continue
            if g[0] - r["start"] <= max_stub:
                r["start"] = g[1]
            elif r["end"] - g[1] <= max_stub:
                r["end"] = g[0]
    return rows


def snap_to_gaps(rows, gaps, reach=0.6):
    """Whisper の境目は無音をまたぎやすいので、近くの無音区間の端に寄せる"""
    def gap_at(t):
        return next((g for g in gaps if g[0] < t < g[1]), None)

    for r in rows:
        g = gap_at(r["start"])
        if g and g[1] < r["end"]:
            r["start"] = g[1]
        g = gap_at(r["end"])
        if g and g[0] > r["start"]:
            r["end"] = g[0]
    for a, b in zip(rows, rows[1:]):
        if abs(a["end"] - b["start"]) > 0.05:
            continue
        cand = [g for g in gaps if a["start"] < g[0] and g[1] < b["end"]
                and min(abs(g[0] - a["end"]), abs(g[1] - b["start"])) <= reach]
        if cand:
            g = min(cand, key=lambda g: min(abs(g[0] - a["end"]), abs(g[1] - b["start"])))
            a["end"], b["start"] = g[0], g[1]
    for k, r in enumerate(rows):
        inside = [g for g in gaps if r["start"] < g[0] and g[1] < r["end"] and g[1] - g[0] >= 0.8]
        for g in inside:
            nxt = rows[k + 1]["start"] if k + 1 < len(rows) else None
            prv = rows[k - 1]["end"] if k > 0 else None
            if nxt is not None and nxt - g[1] <= reach:
                r["end"] = g[0]
            elif prv is not None and g[0] - prv <= reach:
                r["start"] = g[1]
    # 長さがほぼ 0 の区切り（行末の短い語に多い）は、次の区切りの手前の無音まで伸ばす
    for k, r in enumerate(rows):
        if r["end"] - r["start"] < 0.15:
            limit = rows[k + 1]["start"] if k + 1 < len(rows) else float("inf")
            g = next((g for g in gaps if g[0] >= r["end"] - 0.01 and g[0] - r["end"] <= 1.0 and g[0] <= limit), None)
            if g:
                r["end"] = g[0]
    for r in rows:
        r["start"], r["end"] = round(r["start"], 2), round(max(r["end"], r["start"]), 2)
    return rows


def align(audio_path, lyrics_text, snap=True):
    lines = parse_lyrics(lyrics_text)
    if not lines:
        raise ValueError("歌詞が空です")
    audio, duration = load_audio(audio_path)
    model = get_model()
    text = "\n".join(" ".join(l["units"]) for l in lines)
    result = model.align(audio, text, language="ja", original_split=True,
                         fast_mode=False, verbose=None)

    got, got_t = _char_times(result)
    target, owner = [], []  # owner[i] = (line_idx, unit_idx)
    for li, l in enumerate(lines):
        for ui, u in enumerate(l["units"]):
            for ch in _norm(u):
                target.append(ch)
                owner.append((li, ui))
    target = "".join(target)

    # 歌詞の各文字 → 結果の文字（表記ゆれは difflib で吸収、取れない文字は前後から補間）
    mapped = [None] * len(target)
    sm = difflib.SequenceMatcher(None, target, got, autojunk=False)
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            mapped[a + k] = got_t[b + k]
    known = [i for i, m in enumerate(mapped) if m]
    if not known:
        raise RuntimeError("歌詞と音声を対応づけられませんでした（ボーカルのみの音源か確認してください）")
    for i in range(len(mapped)):
        if mapped[i] is None:
            prev = max((k for k in known if k < i), default=None)
            nxt = min((k for k in known if k > i), default=None)
            if prev is None:
                mapped[i] = (mapped[nxt][0], mapped[nxt][0])
            elif nxt is None:
                mapped[i] = (mapped[prev][1], mapped[prev][1])
            else:
                a, b = mapped[prev][1], mapped[nxt][0]
                f = (i - prev) / (nxt - prev)
                t = a + (b - a) * f
                mapped[i] = (t, t)

    rows = []
    for li, l in enumerate(lines):
        for ui, u in enumerate(l["units"]):
            idx = [i for i, o in enumerate(owner) if o == (li, ui)]
            if not idx:
                continue
            start = mapped[idx[0]][0]
            end = mapped[idx[-1]][1]
            rows.append({"no": len(rows) + 1, "section": l["section"], "line": li + 1,
                         "unit": u, "start": round(start, 2), "end": round(max(end, start), 2)})
    if snap:
        rows = snap_to_gaps(rows, find_gaps(audio))
        rows = trim_edges(rows, find_gaps(audio) + find_soft_gaps(audio))
    return {"duration": round(duration, 3), "rows": rows}


def cache_path(audio_path, lyrics_text):
    h = hashlib.sha1((Path(audio_path).name + "\n" + lyrics_text).encode("utf-8")).hexdigest()[:10]
    p = Path(audio_path)
    return p.with_name(f"{p.stem}_timing_{h}.json")


def align_cached(audio_path, lyrics_text):
    cp = cache_path(audio_path, lyrics_text)
    if cp.exists():
        return json.loads(cp.read_text(encoding="utf-8")), True
    res = align(audio_path, lyrics_text)
    cp.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res, False


def h3_frames(seconds, fps=24):
    n = max(5, round(seconds * fps))
    return n + (5 - n % 17) % 17


def ltx_frames(seconds, fps=24):
    n = max(1, round(seconds * fps))
    return n + (1 - n % 8) % 8


def tc(sec):
    m, s = divmod(max(sec, 0.0), 60)
    return f"{int(m)}:{s:05.2f}"


def to_srt(rows, by_line=True):
    def stamp(t):
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    items = []
    if by_line:
        groups = {}
        for r in rows:
            groups.setdefault(r["line"], []).append(r)
        for g in groups.values():
            items.append((g[0]["start"], g[-1]["end"], "　".join(r["unit"] for r in g)))
    else:
        items = [(r["start"], r["end"], r["unit"]) for r in rows]
    out = []
    for i, (a, b, t) in enumerate(items, 1):
        out.append(f"{i}\n{stamp(a)} --> {stamp(b)}\n{t}\n")
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    audio, lyr = sys.argv[1], sys.argv[2]
    res, cached = align_cached(audio, read_text(lyr))
    for r in res["rows"]:
        print(f'{r["no"]:3} L{r["line"]:<3} {tc(r["start"])} - {tc(r["end"])}  {r["unit"]}')
