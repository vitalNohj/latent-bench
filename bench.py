#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["tiktoken"]
# ///
"""latent-bench: measure what a response-style skill does to replies, through the real pi CLI.

Arms
  base     the prompt as-is
  terse    "Answer concisely." + prompt, the cheap control any style skill has to beat
  <skill>  /skill:<name> + prompt, one arm per --skill NAME=DIR (the first one is the focus arm)

Phases (each one resumes: finished items are skipped)
  gen     single-turn replies, thinking off so usage.output counts only the reply
  multi   7-turn conversations; the skill is invoked on turn 1 only (drift test)
  judge   cross-family judge: key-point coverage, pairwise preference, register
  report  REPORT.md and SAMPLES.md in results/<tag>/

Run with `uv run bench.py <phase>`: the script header pulls tiktoken for visible-token counts.
Plain `python3 bench.py` works too, without the visible-token columns.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import shutil
import statistics as st
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

try:
    import tiktoken
    ENC = tiktoken.get_encoding("o200k_base")
except Exception:  # visible-token columns need tiktoken; `uv run bench.py` installs it from the script header
    ENC = None

ROOT = Path(__file__).resolve().parent
PROMPTS = json.loads((ROOT / "prompts.json").read_text())
CONVO = json.loads((ROOT / "conversation.json").read_text())

# pi model ids (provider/model). Use a judge from another model family than the generator.
GEN_MODEL = os.environ.get("BENCH_GEN_MODEL")
JUDGE_MODEL = os.environ.get("BENCH_JUDGE_MODEL")
WORKERS = int(os.environ.get("BENCH_WORKERS", "2"))

# filled in main() from --skill NAME=DIR
SKILLS: dict = {}
ARMS: list = []
PAIRS: list = []
FOCUS = ""


def configure(skill_names) -> None:
    """arms = base, terse, then each skill; pairs = focus vs every other arm, other skills vs terse."""
    global ARMS, PAIRS, FOCUS
    names = list(skill_names)
    FOCUS = names[0]
    ARMS = ["base", "terse", *names[1:], FOCUS]
    PAIRS = [(FOCUS, a) for a in ARMS if a != FOCUS] + [(s, "terse") for s in names[1:]]
    LINT["meta"] = r"\b(?:" + "|".join(re.escape(n) for n in names) + r")\b"
PI = ["pi", "-p", "--mode", "json", "--no-tools", "--no-context-files", "--no-extensions", "--no-mcp", "--no-skills"]
JUDGE_SYSTEM = "You are a careful, strict grader. Output exactly one JSON object and nothing else."

COV = """Grade one reply from a coding assistant against a list of key points.

QUESTION:
{q}

REPLY:
<<<
{reply}
>>>

KEY POINTS:
{points}

For each key point, score how well the reply conveys it:
1 = clearly conveyed. Any wording, notation, symbols, or terse fragments count if a competent developer would understand them.
0.5 = partly conveyed, or only implied.
0 = missing, or contradicted.
Judge meaning only. Do not reward or penalize style, tone, or length.

Then list factual errors: statements in the reply that are wrong or misleading. Omissions are not errors.

Output JSON: {{"scores": [one number per key point, in order], "errors": ["short description", ...]}}"""

PAIR = """A developer asked a coding assistant the question below. Compare two replies.

QUESTION:
{q}

REPLY A:
<<<
{a}
>>>

REPLY B:
<<<
{b}
>>>

Which reply serves the developer better? Weigh, in this order:
1. Correctness: wrong or misleading claims are the worst flaw.
2. Substance: covers what matters for this question. A missing key fact or a missing needed warning is a serious flaw.
3. Clarity: how fast the developer can read it, understand it, and act on it.
Length is not a virtue. When two replies are equally correct and complete, prefer the one that is faster to read. Ignore politeness.

Output JSON: {{"winner": "A" or "B" or "tie", "reason": "one sentence"}}"""

REG = """Classify the writing register of one reply from a coding assistant.

REPLY:
<<<
{reply}
>>>

register:
0 = ordinary assistant prose: full grammatical sentences, transitions, framing.
1 = mostly ordinary prose, somewhat trimmed.
2 = mostly compressed: fragments, key: value lines, symbols, little connective grammar.
3 = compressed throughout.

Also answer:
social: does it contain pleasantries, thanks, praise, or enthusiasm?
offer: does it offer further help or service, such as "let me know if", "want me to", "I can also", "happy to"? Asking the user for information needed to proceed is not an offer.
meta: does it mention its own style, mode, or format?

Output JSON: {{"register": 0, "social": false, "offer": false, "meta": false}}"""

LINT = {
    "social": r"\b(?:great question|good question|happy to help|glad to help|hope (?:this|that|it) helps|you're welcome|no problem|sure thing|certainly|absolutely|of course)\b",
    "offer": r"(?:let me know|feel free|if you(?:'d| would)? like|want me to|i can also|i'd be happy|happy to (?:help|dig|walk|take))",
    "hedge": r"\b(?:might|probably|perhaps|maybe|it seems|seems to|possibly)\b",
    "meta": r"$^",  # set in configure(): mentions of a skill's own name
}
FMT = {
    "headers": r"(?m)^#{1,6} ",
    "bold": r"\*\*[^*\n]+\*\*",
    "arrows": r"→",
    "tags": r"\[(?:verified|inferred|assumed|p=)",
}
# scope qualifiers: words that bound a claim's truth conditions. Hedge rules must not strip these.
QUAL = r"\b(?:usually|often|typically|generally|commonly|mostly|most|some|many|rarely|by default|in most cases|can|may|tends? to|depends?|unless|if)\b"

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1))
    tmp.replace(path)


def load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def iter_json(d: Path):
    if d.exists():
        for f in sorted(d.rglob("*.json")):
            yield json.loads(f.read_text())


def wrap(arm: str, prompt: str, first: bool = True) -> str:
    if not first or arm == "base":
        return prompt
    if arm == "terse":
        return "Answer concisely.\n\n" + prompt
    return f"/skill:{arm} {prompt}"


def run_pi(message: str, *, model: str, thinking: str, skill=None, system=None, session=None, timeout=420) -> dict:
    cmd = ["nice", "-n", "10", *PI, "--model", model, "--thinking", thinking]
    cmd += ["--session-dir", str(session[0]), "--session-id", session[1]] if session else ["--no-session"]
    if skill:
        cmd += ["--skill", str(skill)]
    if system:
        cmd += ["--system-prompt", system]
    cmd.append(message)
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd="/tmp", capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "err": f"timeout after {timeout}s", "secs": timeout}
    final, user_chars = None, None
    for line in p.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") != "message_end":
            continue
        m = ev.get("message") or {}
        if m.get("role") == "assistant":
            final = m
        elif m.get("role") == "user":
            c = m.get("content")
            user_chars = len(c) if isinstance(c, str) else sum(len(x.get("text", "")) for x in c or [])
    secs = round(time.time() - t0, 1)
    if final is None:
        return {"ok": False, "err": f"no assistant message, rc={p.returncode}: {p.stderr.strip()[-300:]}", "secs": secs}
    text = "".join(x.get("text", "") for x in final.get("content") or [] if x.get("type") == "text")
    return {
        "ok": final.get("stopReason") == "stop" and bool(text.strip()),
        "text": text,
        "usage": final.get("usage"),
        "stop": final.get("stopReason"),
        "err": final.get("errorMessage"),
        "model": final.get("model"),
        "user_chars": user_chars,
        "secs": secs,
    }


def call(retries: int = 2, **kw) -> dict:
    r: dict = {}
    for attempt in range(retries + 1):
        r = run_pi(**kw)
        if r["ok"]:
            break
        time.sleep(5 * (attempt + 1))
    return r


def pool(jobs, fn) -> None:
    jobs = list(jobs)
    log(f"{len(jobs)} jobs, {WORKERS} workers")

    def safe(job):
        try:
            fn(job)
        except Exception as e:  # keep the pool alive; the unfinished item reruns next time
            log(f"ERROR {job[:2]}: {e!r}")

    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(safe, jobs))


# ---------------------------------------------------------------- phases


def phase_gen(run: Path, samples: int, model: str) -> None:
    def jobs():
        for s in range(samples):
            for p in PROMPTS:
                for arm in ARMS:
                    path = run / "gen" / arm / f"{p['id']}__s{s}.json"
                    r = load(path)
                    if not (r and r.get("ok")):
                        yield path, arm, p, s

    def work(job):
        path, arm, p, s = job
        r = call(message=wrap(arm, p["prompt"]), model=model, thinking="off", skill=SKILLS.get(arm))
        save(path, {"arm": arm, "pid": p["id"], "sample": s, **r})
        out = (r.get("usage") or {}).get("output")
        status = "ok" if r["ok"] else "FAIL " + str(r.get("err"))[:120]
        log(f"gen   {arm:8} {p['id']:13} s{s}  {out} tok  {r.get('secs')}s  {status}")

    pool(jobs(), work)


def phase_multi(run: Path, convos: int, model: str) -> None:
    def jobs():
        for c in range(convos):
            for arm in ARMS:
                path = run / "multi" / arm / f"c{c}.json"
                r = load(path)
                if not (r and r.get("ok")):
                    yield path, arm, c

    def work(job):
        path, arm, c = job
        turns: list = []
        for attempt in range(3):
            sdir = run / "sessions" / f"{arm}-c{c}-a{attempt}"
            shutil.rmtree(sdir, ignore_errors=True)
            sid = str(uuid.uuid4())
            turns = []
            for k, q in enumerate(CONVO):
                r = run_pi(wrap(arm, q, first=k == 0), model=model, thinking="off",
                           skill=SKILLS.get(arm), session=(sdir, sid))
                turns.append({"turn": k, "q": q, **r})
                out = (r.get("usage") or {}).get("output")
                log(f"multi {arm:8} c{c} t{k}  {out} tok  {r.get('secs')}s  {'ok' if r['ok'] else 'FAIL'}")
                if not r["ok"]:
                    break
            if len(turns) == len(CONVO) and all(t["ok"] for t in turns):
                save(path, {"arm": arm, "convo": c, "ok": True, "turns": turns})
                return
            time.sleep(10)
        save(path, {"arm": arm, "convo": c, "ok": False, "turns": turns})

    pool(jobs(), work)


def judge_call(prompt: str, model: str, thinking: str):
    for attempt in range(3):
        r = run_pi(prompt, model=model, thinking=thinking, system=JUDGE_SYSTEM)
        if r["ok"]:
            m = re.search(r"\{.*\}", r["text"], re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except ValueError:
                    pass
        time.sleep(5 * (attempt + 1))
    return None


def phase_judge(run: Path, model: str) -> None:
    pmap = {p["id"]: p for p in PROMPTS}
    gens = {(g["arm"], g["pid"], g["sample"]): g for g in iter_json(run / "gen") if g.get("ok")}
    jobs = []
    for (arm, pid, s), g in gens.items():
        path = run / "judge" / "cov" / arm / f"{pid}__s{s}.json"
        if not path.exists():
            jobs.append(("cov", path, g))
    for a, b in PAIRS:
        for (arm, pid, s), g in gens.items():
            if arm == a and (b, pid, s) in gens:
                for order in ("ab", "ba"):
                    path = run / "judge" / "pair" / f"{a}_vs_{b}" / f"{pid}__s{s}__{order}.json"
                    if not path.exists():
                        jobs.append(("pair", path, (g, gens[(b, pid, s)], order)))
    for m in iter_json(run / "multi"):
        if m.get("ok"):
            for t in m["turns"]:
                path = run / "judge" / "reg" / m["arm"] / f"c{m['convo']}_t{t['turn']}.json"
                if not path.exists():
                    jobs.append(("reg", path, {**t, "arm": m["arm"], "convo": m["convo"]}))
    random.Random(0).shuffle(jobs)

    def work(job):
        kind, path, data = job
        if kind == "cov":
            p = pmap[data["pid"]]
            pts = "\n".join(f"{i + 1}. {x['t']}" for i, x in enumerate(p["points"]))
            j = judge_call(COV.format(q=p["prompt"], reply=data["text"], points=pts), model, "medium")
            sc = (j or {}).get("scores")
            ok = isinstance(sc, list) and len(sc) == len(p["points"]) and all(
                isinstance(x, (int, float)) and 0 <= x <= 1 for x in sc)
            rec = {"arm": data["arm"], "pid": data["pid"], "sample": data["sample"], "ok": ok, "judge": j}
        elif kind == "pair":
            ga, gb, order = data
            first, second = (ga, gb) if order == "ab" else (gb, ga)
            q = pmap[ga["pid"]]["prompt"]
            j = judge_call(PAIR.format(q=q, a=first["text"], b=second["text"]), model, "medium")
            w = str((j or {}).get("winner", "")).strip().lower().replace("reply", "").strip()
            winner = {"a": first["arm"], "b": second["arm"], "tie": "tie"}.get(w)
            rec = {"pair": [ga["arm"], gb["arm"]], "pid": ga["pid"], "sample": ga["sample"], "order": order,
                   "ok": winner is not None, "winner": winner, "judge": j}
        else:
            j = judge_call(REG.format(reply=data["text"]), model, "low")
            ok = bool(j) and isinstance(j.get("register"), (int, float))
            rec = {"arm": data["arm"], "convo": data["convo"], "turn": data["turn"], "ok": ok, "judge": j}
        if rec["ok"]:
            save(path, rec)
        log(f"judge {kind:4} {path.relative_to(run / 'judge')}  {'ok' if rec['ok'] else 'FAIL'}")

    pool(jobs, work)


# ---------------------------------------------------------------- report


def fmean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else None


def boot_ci(vals, n=4000, seed=1):
    rnd = random.Random(seed)
    means = sorted(st.mean(rnd.choices(vals, k=len(vals))) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def f0(x):
    return "-" if x is None else f"{x:.0f}"


def f1(x):
    return "-" if x is None else f"{x:.1f}"


def f2(x):
    return "-" if x is None else f"{x:.2f}"


def pct(x):
    return "-" if x is None else f"{100 * x:.0f}%"


def phase_report(run: Path) -> Path:
    pmap = {p["id"]: p for p in PROMPTS}
    pids = [p["id"] for p in PROMPTS]
    gens = {(g["arm"], g["pid"], g["sample"]): g for g in iter_json(run / "gen") if g.get("ok")}
    covs = {(c["arm"], c["pid"], c["sample"]): c["judge"] for c in iter_json(run / "judge" / "cov") if c.get("ok")}
    meta = load(run / "meta.json") or {}

    def out_tok(k):
        return gens[k]["usage"]["output"]

    def vis_tok(k):
        return len(ENC.encode(gens[k]["text"])) if ENC else None

    def n_err(k):
        return len(covs[k].get("errors") or []) if k in covs else None

    def prose(k):
        return re.sub(r"```.*?```", "", gens[k]["text"], flags=re.S)

    def in_tok(k):
        u = gens[k]["usage"]
        return u.get("input", 0) + u.get("cacheRead", 0) + u.get("cacheWrite", 0)

    def cov_frac(k, core_only):
        j = covs.get(k)
        if not j:
            return None
        pts = pmap[k[1]]["points"]
        sel = [float(s) for s, pt in zip(j["scores"], pts) if pt["core"] or not core_only]
        return sum(sel) / len(sel) if sel else None

    def keys(arm, pid=None):
        return [k for k in gens if k[0] == arm and (pid is None or k[1] == pid)]

    def per_prompt(arm, fn):
        return {pid: fmean([fn(k) for k in keys(arm, pid)]) for pid in pids}

    L = [f"# latent-bench report: {run.name}", "", f"focus arm: `{FOCUS}`", ""]
    L += [f"generated {datetime.now():%Y-%m-%d %H:%M}. gen model `{meta.get('gen_model')}` (thinking off), "
          f"judge `{meta.get('judge_model')}`. {len(PROMPTS)} prompts; replies per arm below.", ""]
    L += ["skill versions: " + ", ".join(f"{k} `{v[:12]}`" for k, v in (meta.get("skills") or {}).items()), ""]

    # per-arm summary
    cols = ["arm", "replies", "visible tok", "visible vs base", "billed tok", "billed vs base", "secs", "in tok/call",
            "core cov", "all cov", "errors/reply", "qualifiers/100w", "social", "offer", "hedge", "meta", "headers", "bold"]
    L += ["## Per arm", "", "| " + " | ".join(cols) + " |", "|---" * len(cols) + "|"]

    def total(arm, fn):
        vals = [v for v in per_prompt(arm, fn).values() if v]
        return sum(vals) if vals else None

    base_vis, base_out = total("base", vis_tok), total("base", out_tok)
    for arm in ARMS:
        ks = keys(arm)
        if not ks:
            continue
        av, ao = total(arm, vis_tok), total(arm, out_tok)
        words = sum(len(prose(k).split()) for k in ks)
        qual = 100 * sum(len(re.findall(QUAL, prose(k), re.I)) for k in ks) / words if words else None
        lint = {n: fmean([len(re.findall(rx, gens[k]["text"].lower())) for k in ks]) for n, rx in LINT.items()}
        fmt = {n: fmean([len(re.findall(rx, gens[k]["text"])) for k in ks]) for n, rx in FMT.items()}
        cells = [arm, len(ks), f0(fmean([vis_tok(k) for k in ks])), pct(av / base_vis if av and base_vis else None),
                 f0(fmean([out_tok(k) for k in ks])), pct(ao / base_out if ao and base_out else None),
                 f1(fmean([gens[k].get("secs") for k in ks])), f0(fmean([in_tok(k) for k in ks])),
                 pct(fmean([cov_frac(k, True) for k in ks])), pct(fmean([cov_frac(k, False) for k in ks])),
                 f2(fmean([n_err(k) for k in ks])), f2(qual), f2(lint["social"]), f2(lint["offer"]),
                 f2(lint["hedge"]), f2(lint["meta"]), f2(fmt["headers"]), f2(fmt["bold"])]
        L.append("| " + " | ".join(str(c) for c in cells) + " |")
    L += ["", "visible tok: o200k_base count of the reply text, a proxy tokenizer (needs tiktoken: `uv run bench.py`). "
          "billed tok: `usage.output` from the API. Billed exceeds visible by generation the API does not return, even "
          "with thinking off; it adds latency, so it is real compute, not rounding.", "",
          "core cov / all cov: share of key points the judge found conveyed (core points only / all points). "
          "errors/reply: judge-flagged wrong or misleading claims. qualifiers/100w: scope words such as usually, "
          "by default, can, depends, unless, in prose outside code fences. "
          "social, offer, hedge, meta, headers, bold: regex hits per reply.", ""]

    # latent vs each other arm, per-prompt paired, bootstrap CI over prompts
    L += [f"## {FOCUS} vs other arms (paired per prompt, 95% bootstrap CI over prompts)", "",
          f"| vs | core cov Δ | all cov Δ | errors/reply Δ | visible tok, {FOCUS} / other | billed tok, {FOCUS} / other |",
          "|---|---|---|---|---|---|"]
    metrics = {"core": lambda k: cov_frac(k, True), "all": lambda k: cov_frac(k, False), "err": n_err,
               "vis": vis_tok, "out": out_tok}
    lat = {m: per_prompt(FOCUS, fn) for m, fn in metrics.items()}
    for other in [a for a in ARMS if a != FOCUS]:
        oth = {m: per_prompt(other, fn) for m, fn in metrics.items()}
        diffs = {m: [lat[m][p] - oth[m][p] for p in pids if lat[m][p] is not None and oth[m][p] is not None]
                 for m in ("core", "all", "err")}
        ratios = {m: [math.log(lat[m][p] / oth[m][p]) for p in pids if lat[m][p] and oth[m][p]] for m in ("vis", "out")}
        cells = []
        for vals, kind in ((diffs["core"], "pp"), (diffs["all"], "pp"), (diffs["err"], "abs"),
                           (ratios["vis"], "ratio"), (ratios["out"], "ratio")):
            if len(vals) < 2:
                cells.append("-")
                continue
            lo, hi = boot_ci(vals)
            m = st.mean(vals)
            if kind == "pp":
                cells.append(f"{100 * m:+.1f} pp [{100 * lo:+.1f}, {100 * hi:+.1f}]")
            elif kind == "abs":
                cells.append(f"{m:+.2f} [{lo:+.2f}, {hi:+.2f}]")
            else:
                cells.append(f"{math.exp(m):.2f}x [{math.exp(lo):.2f}, {math.exp(hi):.2f}]")
        L.append(f"| {other} | " + " | ".join(cells) + " |")
    L += ["", "token ratios: geometric mean over prompts.", ""]

    # pairwise
    pairs = list(iter_json(run / "judge" / "pair"))
    if pairs:
        L += ["## Pairwise preference (judge sees both replies, both orders)", "",
              "| pair | first arm score | 95% CI | wins | ties | losses | judgments | order flips |",
              "|---|---|---|---|---|---|---|---|"]
        for a, b in PAIRS:
            recs = [r for r in pairs if r.get("ok") and r["pair"] == [a, b]]
            if not recs:
                continue
            w = sum(r["winner"] == a for r in recs)
            t = sum(r["winner"] == "tie" for r in recs)
            lo = len(recs) - w - t
            by, per_pid = {}, {}
            for r in recs:
                by.setdefault((r["pid"], r["sample"]), {})[r["order"]] = r["winner"]
                per_pid.setdefault(r["pid"], []).append(1.0 if r["winner"] == a else 0.5 if r["winner"] == "tie" else 0.0)
            both = [v for v in by.values() if len(v) == 2]
            flips = sum(v["ab"] != v["ba"] for v in both)
            vals = [st.mean(v) for v in per_pid.values()]
            ci = "[{:.2f}, {:.2f}]".format(*boot_ci(vals)) if len(vals) > 1 else "-"
            L.append(f"| {a} vs {b} | {(w + 0.5 * t) / len(recs):.2f} | {ci} | {w} | {t} | {lo} | {len(recs)} | {flips}/{len(both)} |")
        L += ["", "score = (wins + ties/2) / judgments for the first arm; CI bootstraps prompts. "
              "order flips = items where swapping A/B changed the verdict.", ""]

    # per prompt
    L += [f"## Per prompt: {'visible' if ENC else 'billed'} tokens · core coverage", "",
          "| prompt | category | " + " | ".join(ARMS) + " |", "|---|---|" + "---|" * len(ARMS)]
    for pid in pids:
        cells = []
        for arm in ARMS:
            o = per_prompt(arm, vis_tok if ENC else out_tok)[pid]
            c = per_prompt(arm, lambda k: cov_frac(k, True))[pid]
            cells.append(f"{f0(o)} · {pct(c)}")
        L.append(f"| {pid} | {pmap[pid]['cat']} | " + " | ".join(cells) + " |")
    L.append("")

    # multi-turn drift
    multis = [m for m in iter_json(run / "multi") if m.get("ok")]
    regs = {(r["arm"], r["convo"], r["turn"]): r["judge"] for r in iter_json(run / "judge" / "reg") if r.get("ok")}
    if multis:
        L += ["## Multi-turn drift (skill invoked on turn 1 only)", "",
              "| turn | question | " + " | ".join(f"{a} {'vis' if ENC else 'billed'} tok" for a in ARMS) + " | "
              + " | ".join(f"{a} reg" for a in ARMS) + " |",
              "|---|---|" + "---|" * (2 * len(ARMS))]
        for k, q in enumerate(CONVO):
            toks, rg = [], []
            for arm in ARMS:
                ms = [m for m in multis if m["arm"] == arm and len(m["turns"]) > k]
                toks.append(f0(fmean([len(ENC.encode(m["turns"][k]["text"])) if ENC else m["turns"][k]["usage"]["output"]
                                      for m in ms])))
                rg.append(f1(fmean([(regs.get((arm, m["convo"], k)) or {}).get("register") for m in ms])))
            L.append(f"| {k + 1} | {q[:48]}{'…' if len(q) > 48 else ''} | " + " | ".join(toks) + " | " + " | ".join(rg) + " |")
        L += ["", "reg = judge register score: 0 ordinary prose … 3 compressed throughout.", ""]
        L += ["| arm | conversations | visible tok / convo | billed tok / convo | social turns | offer turns | meta turns |",
              "|---|---|---|---|---|---|---|"]
        for arm in ARMS:
            ms = [m for m in multis if m["arm"] == arm]
            js = [regs.get((arm, m["convo"], t["turn"])) or {} for m in ms for t in m["turns"]]
            if js:
                vis = fmean([sum(len(ENC.encode(t["text"])) for t in m["turns"]) for m in ms]) if ENC else None
                out = fmean([sum(t["usage"]["output"] for t in m["turns"]) for m in ms])
                L.append(f"| {arm} | {len(ms)} | {f0(vis)} | {f0(out)} | "
                         + " | ".join(f"{sum(bool(j.get(f)) for j in js)}/{len(js)}" for f in ("social", "offer", "meta")) + " |")
        L.append("")

    # judge-flagged errors, for manual review
    errs = [(k, e) for k, j in sorted(covs.items()) for e in (j.get("errors") or [])]
    if errs:
        L += ["## Judge-flagged errors (verify by hand: the judge can be wrong)", ""]
        L += [f"- {k[0]} / {k[1]} / s{k[2]}: {e}" for k, e in errs]
        L.append("")

    report = run / "REPORT.md"
    report.write_text("\n".join(L))

    S = [f"# latent-bench samples: {run.name}", ""]
    for pid in pids:
        S += [f"## {pid} ({pmap[pid]['cat']})", "", "> " + pmap[pid]["prompt"].replace("\n", "\n> "), ""]
        for arm in ARMS:
            k = (arm, pid, 0)
            if k in gens:
                cv = cov_frac(k, True)
                S += [f"### {arm}: {f0(vis_tok(k))} visible / {out_tok(k)} billed tok, core {pct(cv)}", "", "~~~~text",
                      gens[k]["text"].strip(), "~~~~", ""]
    for m in sorted(multis, key=lambda m: (m["convo"], ARMS.index(m["arm"]))):
        if m["convo"] != 0:
            continue
        S += [f"## multi-turn: {m['arm']}", ""]
        for t in m["turns"]:
            S += [f"### turn {t['turn'] + 1}: {t['q']}", "", "~~~~text", t["text"].strip(), "~~~~", ""]
    (run / "SAMPLES.md").write_text("\n".join(S))
    return report


# ---------------------------------------------------------------- main


def sha(path: Path) -> str:
    return hashlib.sha256((path / "SKILL.md").read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["gen", "multi", "judge", "report", "all"])
    ap.add_argument("--tag", default="pilot", help="results/<tag>/; use a new tag after editing a skill")
    ap.add_argument("--skill", action="append", default=[], metavar="NAME=DIR",
                    help="skill arm: NAME is the /skill: name, DIR holds SKILL.md. Repeatable; the first is the focus "
                         "arm. Default: latent=skills/latent. Not needed for report.")
    ap.add_argument("--samples", type=int, default=1, help="replies per prompt and arm")
    ap.add_argument("--convos", type=int, default=1, help="multi-turn conversations per arm")
    ap.add_argument("--model", default=GEN_MODEL, help="generator, pi provider/model id (env BENCH_GEN_MODEL)")
    ap.add_argument("--judge-model", default=JUDGE_MODEL, help="judge, pi provider/model id (env BENCH_JUDGE_MODEL)")
    ap.add_argument("--only", help="comma-separated prompt ids (smoke tests)")
    ap.add_argument("--turns", type=int, help="limit multi-turn length (smoke tests)")
    a = ap.parse_args()

    global PROMPTS, CONVO
    if a.only:
        ids = a.only.split(",")
        unknown = set(ids) - {p["id"] for p in PROMPTS}
        if unknown:
            raise SystemExit(f"unknown prompt ids: {sorted(unknown)}")
        PROMPTS = [p for p in PROMPTS if p["id"] in ids]
    if a.turns:
        CONVO = CONVO[: a.turns]

    run = ROOT / "results" / a.tag
    meta = load(run / "meta.json")
    if a.phase == "report" and not a.skill:
        if meta is None:
            raise SystemExit(f"results/{a.tag} has no meta.json; nothing to report")
        focus = meta.get("focus") or next(iter(meta["skills"]))
        configure([focus, *(k for k in meta["skills"] if k != focus)])
        print(phase_report(run))
        return

    specs = a.skill or [f"latent={ROOT / 'skills' / 'latent'}"]
    for spec in specs:
        name, sep, d = spec.partition("=")
        if not sep or not (Path(d).expanduser() / "SKILL.md").is_file():
            raise SystemExit(f"--skill {spec!r}: expected NAME=DIR with DIR/SKILL.md")
        if name in ("base", "terse"):
            raise SystemExit(f"--skill name {name!r} is reserved")
        SKILLS[name] = Path(d).expanduser().resolve()
    configure(SKILLS)
    if not a.model or not a.judge_model:
        raise SystemExit("set --model and --judge-model (or BENCH_GEN_MODEL / BENCH_JUDGE_MODEL)")

    run.mkdir(parents=True, exist_ok=True)
    skills = {k: sha(v) for k, v in SKILLS.items()}
    if meta is None:
        meta = {"created": datetime.now().isoformat(timespec="seconds"), "gen_model": a.model,
                "judge_model": a.judge_model, "focus": FOCUS, "skills": skills}
        save(run / "meta.json", meta)
    elif a.phase in ("gen", "multi", "all") and (meta["skills"] != skills or meta["gen_model"] != a.model):
        raise SystemExit(f"results/{a.tag} was made with other skill versions or another model; use a new --tag")

    if a.phase in ("gen", "all"):
        phase_gen(run, a.samples, a.model)
    if a.phase in ("multi", "all"):
        phase_multi(run, a.convos, a.model)
    if a.phase in ("judge", "all"):
        phase_judge(run, a.judge_model)
    if a.phase in ("report", "all"):
        print(phase_report(run))


if __name__ == "__main__":
    main()
