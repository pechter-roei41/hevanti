"""Compares the engines that can read the text on the slides, on YOUR slides: Tesseract (what Hevanti uses now)
and the Hebrew OCR models of Rivok Labs (github.com/RivoksLab/paddleocr-hebrew, Apache-2.0, ONNX).

  python tools/ocr_compare.py "<the courses folder or a slides folder>" [--limit 20] [--rivok-models <dir>]

Nothing is changed or sent anywhere: it reads pictures and writes a report (ocr_compare_report.html, next to where you
run it) and a small json. Only Pillow is needed (python -m pip install pillow). Tesseract is found the way Hevanti
finds it; Rivok's engine only if it is installed (see "Rivok's engine" below), else only Tesseract runs and the
report says how to add the other.

How to judge - two ways:
  1. Look: the report puts the picture and what each engine read side by side. 20 slides is enough to see.
  2. Measure: run once with --make-truth (writes truth.json with Tesseract's text), fix the text in that file to what
     is really on each slide (just the slides you care about; delete the others), and run again with --truth truth.json.
     The report then gives, per engine: word recall (how many of the real words were found - what matters for search
     and for the hotwords) and CER (character error rate, strict, also counts wrong line order).

Rivok's engine, once:
  python -m pip install "git+https://github.com/RivoksLab/paddleocr-hebrew" huggingface_hub
  hf download Rivok/paddleocr-hebrew --include "charset_v2f.txt" "word-det/*" "server-svtrv2/*" --local-dir hebrew-ocr-models
(the folder hebrew-ocr-models is found by itself when it is next to where you run this, or give --rivok-models)."""
import argparse
import base64
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

IMG = (".jpg", ".jpeg", ".png")
MARKS = re.compile("[‎‏‪-‮⁦-⁩֑-ׇ]")


def clean(text):
    """The same cleaning Hevanti does: no direction marks, empty lines out, one space between words."""
    text = re.sub("[‎‏‪-‮⁦-⁩]", "", str(text or ""))
    out = []
    for ln in text.splitlines():
        ln = " ".join(ln.split())
        if sum(ch.isalnum() for ch in ln) >= 2:
            out.append(ln)
    return "\n".join(out)[:4000]


# ---------- the engines ----------
class Tesseract:
    name = "Tesseract"

    def __init__(self):
        local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.local/share")
        cands = [os.environ.get("HEVANTI_TESSERACT", ""), shutil.which("tesseract") or ""]
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.path.join(local, "Programs")):
            if base:
                cands.append(os.path.join(base, "Tesseract-OCR", "tesseract.exe"))
        cands += ["/usr/local/bin/tesseract", "/usr/bin/tesseract"]
        self.exe = next((c for c in cands if c and os.path.isfile(c)), None)
        if not self.exe:
            raise RuntimeError("Tesseract not found (run install_ocr in the System folder, or set HEVANTI_TESSERACT)")
        td = os.environ.get("HEVANTI_TESSDATA") or os.path.join(local, "Hevanti", "tessdata")
        extra = ["--tessdata-dir", td] if os.path.isdir(td) else []
        r = subprocess.run([self.exe, "--list-langs", *extra], capture_output=True, timeout=30)
        have = {ln.strip() for ln in r.stdout.decode("utf-8", "replace").splitlines()[1:]}
        langs = [x for x in ("heb", "eng") if x in have]
        if "heb" not in langs:
            raise RuntimeError("Tesseract has no Hebrew language file (run install_ocr)")
        self.extra, self.langs = extra, "+".join(langs)
        v = subprocess.run([self.exe, "--version"], capture_output=True, timeout=30)
        self.version = (v.stdout or v.stderr).decode("utf-8", "replace").splitlines()[0]

    def read(self, path):
        r = subprocess.run([self.exe, path, "stdout", "-l", self.langs, "--psm", "3", *self.extra],
                           capture_output=True, timeout=180)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode("utf-8", "replace")[:200])
        return r.stdout.decode("utf-8", "replace")


class Rivok:
    name = "Rivok (Hebrew, ONNX)"

    def __init__(self, models_dir):
        try:
            from ocr import HebrewOCR          # installed from github.com/RivoksLab/paddleocr-hebrew
        except ImportError as e:
            raise RuntimeError("Rivok's engine is not installed (see the top of this file): " + str(e))
        if not models_dir or not os.path.isdir(models_dir):
            raise RuntimeError("the models folder was not found - download it (see the top of this file) "
                               "or give --rivok-models")
        self.engine = HebrewOCR(models_dir=models_dir)
        self.version = "models: " + os.path.abspath(models_dir)

    def read(self, path):
        res = self.engine.read(path)
        return "\n".join(str(ln.get("text", "")) for ln in res.get("lines", []))


# ---------- measuring ----------
def words(text):
    return re.findall(r"\w+", MARKS.sub("", str(text or "")).lower().replace("ך", "כ").replace("ם", "מ")
                      .replace("ן", "נ").replace("ף", "פ").replace("ץ", "צ"))


def recall_precision(truth, got):
    """Word recall: how many of the true words were read (each word counted as many times as it is there);
    precision: how many of the read words are real."""
    t, g = words(truth), words(got)
    if not t:
        return None, None
    pool = {}
    for w in t:
        pool[w] = pool.get(w, 0) + 1
    hit = 0
    for w in g:
        if pool.get(w, 0) > 0:
            pool[w] -= 1
            hit += 1
    return hit / len(t), (hit / len(g) if g else 0.0)


def cer(truth, got):
    """Character error rate: edit distance / length of the truth (strict: the order of the lines counts)."""
    a = " ".join(MARKS.sub("", truth).split())[:2500]
    b = " ".join(MARKS.sub("", got).split())[:2500]
    if not a:
        return None
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / len(a)


# ---------- the pictures ----------
def find_images(folder):
    out = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if os.path.basename(root) != "שקופיות" and os.path.abspath(root) != os.path.abspath(folder):
            continue
        out += [os.path.join(root, f) for f in files if f.lower().endswith(IMG)]
    return sorted(out)


def sample(items, n):
    if n <= 0 or len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def thumb(path, width=520):
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im.thumbnail((width, 900))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=70)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def pct(x):
    return "-" if x is None else f"{x * 100:.1f}%"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("folder", help="the courses folder, or a folder of slide pictures")
    ap.add_argument("--limit", type=int, default=20, help="how many slides (spread over all of them); 0 = all")
    ap.add_argument("--rivok-models", default="", help="Rivok's models folder (default: ./hebrew-ocr-models)")
    ap.add_argument("--truth", default="", help="json {file name: the real text of the slide}")
    ap.add_argument("--make-truth", action="store_true", help="write truth.json from Tesseract's text, to be corrected")
    ap.add_argument("--out", default="ocr_compare_report.html")
    a = ap.parse_args()

    images = sample(find_images(a.folder), a.limit)
    if not images:
        sys.exit("No pictures found (jpg / png), also looked in folders named שקופיות.")
    truth = {}
    if a.truth:
        with open(a.truth, encoding="utf-8") as f:
            truth = json.load(f)
        images = [p for p in images if os.path.basename(p) in truth] or images
    print(f"{len(images)} slides")

    engines, notes = [], []
    models = a.rivok_models or next((p for p in ("hebrew-ocr-models", os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Hevanti", "hebrew-ocr-models")) if os.path.isdir(p)), "")
    for make in (Tesseract, lambda: Rivok(models)):
        try:
            e = make()
            engines.append(e)
            print("engine:", e.name, "-", e.version)
        except Exception as ex:
            nm = "Tesseract" if make is Tesseract else "Rivok"
            notes.append(f"{nm}: {ex}")
            print(f"{nm} is not used: {ex}")
    if not engines:
        sys.exit("No engine could start.")

    rows, total = [], {e.name: {"s": 0.0, "n": 0, "rec": [], "pre": [], "cer": [], "chars": 0} for e in engines}
    for i, path in enumerate(images, 1):
        row = {"file": path, "name": os.path.basename(path), "res": {}}
        for e in engines:
            t0 = time.time()
            try:
                txt = clean(e.read(path))
                err = ""
            except Exception as ex:
                txt, err = "", str(ex)[:200]
            dt = time.time() - t0
            tt = total[e.name]
            tt["s"] += dt
            tt["n"] += 1
            tt["chars"] += len(txt)
            r = {"text": txt, "sec": dt, "err": err}
            real = truth.get(row["name"])
            if real is not None:
                r["rec"], r["pre"] = recall_precision(real, txt)
                r["cer"] = cer(real, txt)
                for k, v in (("rec", r["rec"]), ("pre", r["pre"]), ("cer", r["cer"])):
                    if v is not None:
                        tt[k].append(v)
            row["res"][e.name] = r
        rows.append(row)
        print(f"  {i}/{len(images)} {row['name']}: " + ", ".join(f"{e.name} {row['res'][e.name]['sec']:.1f}s "
              f"{len(row['res'][e.name]['text'])} chars" for e in engines))

    if a.make_truth:
        first = engines[0].name
        with open("truth.json", "w", encoding="utf-8") as f:
            json.dump({r["name"]: r["res"][first]["text"] for r in rows}, f, ensure_ascii=False, indent=1)
        print("truth.json written: correct the text of the slides you care about, delete the others, then run again with --truth truth.json")

    # a short table
    print("\n" + "engine".ljust(26) + "avg sec".rjust(9) + "avg chars".rjust(11) + ("word recall".rjust(13) + "precision".rjust(11) + "CER".rjust(8) if truth else ""))
    for e in engines:
        t = total[e.name]
        avg = lambda xs: sum(xs) / len(xs) if xs else None
        line = e.name.ljust(26) + f"{t['s'] / max(1, t['n']):.2f}".rjust(9) + f"{t['chars'] / max(1, t['n']):.0f}".rjust(11)
        if truth:
            line += pct(avg(t["rec"])).rjust(13) + pct(avg(t["pre"])).rjust(11) + pct(avg(t["cer"])).rjust(8)
        print(line)

    # the report
    h = ["<!doctype html><meta charset=utf-8><title>OCR compare</title><style>",
         "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;max-width:1500px}table{border-collapse:collapse}",
         "td,th{border:1px solid #ccc;padding:6px 10px;vertical-align:top}pre{white-space:pre-wrap;margin:0;font:14px Consolas,monospace}",
         ".row{display:grid;grid-template-columns:repeat(" + str(len(engines) + 1) + ",1fr);gap:12px;border-top:2px solid #888;padding:12px 0}",
         "img{max-width:100%;border:1px solid #ccc}.m{color:#555;font-size:13px}.err{color:#b00}</style>",
         "<h2>OCR compare</h2>", f"<p class=m>{len(images)} slides. " + html.escape(" | ".join(notes)) + "</p>",
         "<table><tr><th>engine<th>avg sec<th>avg chars" + ("<th>word recall<th>precision<th>CER" if truth else "")]
    for e in engines:
        t = total[e.name]
        avg = lambda xs: sum(xs) / len(xs) if xs else None
        h.append(f"<tr><td>{html.escape(e.name)} <span class=m>{html.escape(e.version)}</span><td>{t['s'] / max(1, t['n']):.2f}"
                 f"<td>{t['chars'] / max(1, t['n']):.0f}" + (f"<td>{pct(avg(t['rec']))}<td>{pct(avg(t['pre']))}<td>{pct(avg(t['cer']))}" if truth else ""))
    h.append("</table>")
    for r in rows:
        h.append("<div class=row><div><b>" + html.escape(r["name"]) + "</b><br>" + (f'<img src="{thumb(r["file"])}">' if thumb(r["file"]) else "") + "</div>")
        for e in engines:
            x = r["res"][e.name]
            extra = (f" &nbsp; recall {pct(x.get('rec'))}, CER {pct(x.get('cer'))}" if "rec" in x else "")
            h.append(f"<div dir=rtl><div class=m dir=ltr>{html.escape(e.name)} - {x['sec']:.1f}s{extra}</div>"
                     + (f"<div class=err>{html.escape(x['err'])}</div>" if x["err"] else "")
                     + f"<pre>{html.escape(x['text'])}</pre></div>")
        h.append("</div>")
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(h))
    print("\nreport:", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
