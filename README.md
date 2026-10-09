# latent-bench

A small, reusable benchmark for **response-style skills**: prompt add-ons that change how a coding assistant writes, such as [caveman](https://github.com/JuliusBrussee/caveman) ("talk like caveman, save tokens"). It runs each style through the real [pi](https://github.com/badlogic/pi-mono) CLI and measures what actually changes: length in visible and billed tokens, latency, key-point coverage, factual errors, pairwise preference, and whether the style survives a multi-turn conversation.

This repo also documents one experiment that **did not work**: `latent`, a skill meant to make the model write "model to model", in pure signal with no human-facing filler. The write-up is kept as a worked example of what the bench can catch.

## TL;DR

`latent` did what it said on the style axis and failed on the axes that would justify using it:

- **Style: worked.** No social filler, no closing offers, no headers, almost no bold, and it held that register for 7 turns after a single invocation, better than caveman.
- **Cost: no saving.** Visible tokens 0.97x of a plain reply, billed tokens 1.01x, about 9% slower. It shortens long answers about 30% but pads short ones with adjacent facts.
- **Accuracy: worse, likely.** More judge-flagged errors (0.90 vs 0.70 per reply, not significant at n=15), and the flagged errors skew toward overgeneralization: the skill strips hedges, and scope words like "usually" or "by default" go with them.
- **vs the trivial control:** prefixing `Answer concisely.` gave 38% fewer visible tokens than plain at a small coverage cost. latent was preferred over it only 52% of the time.

The cheap control is the bar. A style skill that can't beat "Answer concisely." is not worth 4.6K tokens of context on every call.

## Results (pilot)

Generator `claude-opus-5-5`, thinking off. Judge `gpt-6.1-sol`, a different model family than the generator. 15 prompts x 2 samples per arm, plus a 7-turn conversation x 2 per arm. Full tables, per-prompt numbers and every flagged error: [`results/pilot/REPORT.md`](results/pilot/REPORT.md). Replies side by side: [`results/pilot/SAMPLES.md`](results/pilot/SAMPLES.md).

| arm | visible tok | billed tok | secs | core coverage | all coverage | errors/reply | headers | bold |
|---|---|---|---|---|---|---|---|---|
| base | 432 | 739 | 8.8 | 98% | 96% | 0.70 | 3.00 | 6.93 |
| terse | 267 | 454 | 6.1 | 95% | 92% | 0.57 | 0.07 | 6.70 |
| caveman | 373 | 653 | 8.3 | 98% | 94% | 0.90 | 0.50 | 4.77 |
| latent | 370 | 709 | 9.6 | 98% | 96% | 0.90 | 0.00 | 0.33 |

Per-reply means. Arms: `base` is the prompt as-is, `terse` is `Answer concisely.` + prompt, the others invoke the skill.

Paired per prompt, latent vs each arm, 95% bootstrap CI over prompts:

| vs | all coverage Δ | errors/reply Δ | visible tok ratio | billed tok ratio | judge prefers latent |
|---|---|---|---|---|---|
| base | -0.1 pp [-2.8, +2.8] | +0.20 [-0.27, +0.67] | 0.97x [0.84, 1.14] | 1.01x [0.91, 1.13] | 62% [43, 80] |
| terse | +4.2 pp [+1.2, +7.5] | +0.33 [-0.13, +0.80] | 1.57x [1.33, 2.02] | 1.62x [1.45, 1.82] | 52% [33, 68] |
| caveman | +1.7 pp [-1.0, +4.5] | +0.00 [-0.47, +0.50] | 1.10x [0.96, 1.34] | 1.18x [1.02, 1.40] | 53% [33, 72] |

Multi-turn, skill invoked on turn 1 only. Judge register score, 0 = ordinary prose, 3 = compressed throughout:

| turns 2-7 | base | terse | caveman | latent |
|---|---|---|---|---|
| register | 0-1 | 0-1 | 1.5-2.0 | 2.0-3.0 |
| closing offers ("let me know...") | 4/14 turns | 3/14 | 1/14 | 0/14 |

## What we learned

These generalize beyond latent, and they're the reason to reuse the bench.

1. **Include a one-line control.** `Answer concisely.` costs nothing and beat every skill on length. Without it, any skill looks good against an unconstrained baseline.
2. **Plain replies already have little filler.** Base had 0.13 social phrases and no closing offers per single reply. On a modern model, a "drop the fluff" skill mostly removes markdown (headers, bold), not words.
3. **Saved carrier gets spent on content.** latent cut long answers (1009 → 700 tokens) but grew short ones (`default postgres port?` 18 → 39; `undo last commit` 168 → 293) by adding adjacent facts, despite a "stay on the question" rule. Net: zero.
4. **Billed tokens ≠ visible tokens.** Even with thinking off, the API bills more output than the reply text needs: about +64 tokens per reply for base and +140 for latent, measured by having the model copy its own reply verbatim and diffing the two bills. Those hidden tokens add latency at about the same rate as visible ones (regression over 120 calls), so they are real compute, not rounding. Report both.
5. **Symbols are not cheaper.** `→ ∴ ∵ ≈ ≠ ✓ ✗ Δ` save 0.1-1.0 tokens each vs the word they replace. Pick them for readability, not cost.
6. **"No hedging" eats scope qualifiers.** latent used 1.11 qualifiers per 100 words (usually, by default, can, unless, if) vs 2.13 for base, and its flagged errors were mostly overgeneralizations: "`--hard` deletes any uncommitted work" (untracked files survive), "at most once, no matter how many retries" (not after the idempotency key expires), "`CASCADE`: tables only, keep everything else" (it drops dependent views and constraints). Part of the qualifier gap is `→` standing in for "if", so this is a lead, not proof. A fix to test: "Hedge ≠ scope. Drop words that signal doubt (might, probably); keep words that bound where a claim holds (usually, by default, for tracked files)."
7. **Skill size is a per-call tax.** latent's skill text is about 4.6K input tokens on every call, caveman's about 1.9K. If the skill saves no output, it is a net loss.

## Reusing the bench

Requirements: [`pi`](https://github.com/badlogic/pi-mono) on `PATH` with at least one model configured, Python 3.9+, and [`uv`](https://docs.astral.sh/uv/) (optional, pulls `tiktoken` for the visible-token columns).

```bash
export BENCH_GEN_MODEL=anthropic/claude-sonnet-4-5   # any pi provider/model id
export BENCH_JUDGE_MODEL=openai/gpt-5                # pick a different model family than the generator

# focus arm first; every --skill becomes an arm next to base and terse
uv run bench.py all --tag mystyle-v1 --samples 2 --convos 2 \
  --skill mystyle=path/to/mystyle \
  --skill caveman=path/to/caveman

# smoke test first: two prompts, two turns
uv run bench.py all --tag smoke --only pg-port,git-undo --turns 2 --skill mystyle=path/to/mystyle

# rebuild the report from saved results
uv run bench.py report --tag mystyle-v1
```

Each `--skill NAME=DIR` needs `DIR/SKILL.md`; the skill is invoked as `/skill:NAME <prompt>`. With no `--skill`, the bench runs `latent` from [`skills/latent`](skills/latent/SKILL.md).

Phases: `gen` (single-turn replies), `multi` (7-turn conversations), `judge` (coverage, pairwise, register), `report`, or `all`. Every phase resumes: finished items are skipped, so an interrupted run continues where it stopped. A tag is locked to the skill hashes and generator it was created with; after editing a skill, use a new `--tag`.

Plain `python3 bench.py` also works, without the visible-token columns. Concurrency is 2 workers (`BENCH_WORKERS`).

To test your own prompts, edit [`prompts.json`](prompts.json) (each prompt has an id, a category, and key points, each marked core or not) and [`conversation.json`](conversation.json) (the multi-turn questions).

## Method

- **Isolation.** Every call is `pi -p --no-tools --no-context-files --no-extensions --no-mcp --no-skills`, run from `/tmp`, with only the arm's skill loaded. Thinking is off so output tokens count only the reply.
- **Prompts.** 15 developer questions across categories that stress a style skill differently: concept, shorthand debugging, error triage, decisions, procedures, destructive ops, security, code review, performance, creative naming, a trivial lookup, brainstorming, a plain-wording request. Each has 3-6 key points written before any reply was seen.
- **Coverage.** The judge scores each key point 1 / 0.5 / 0 and lists factual errors, told to judge meaning only, so symbols and fragments count when a developer would understand them.
- **Preference.** The judge sees two replies and ranks correctness > substance > clarity. Every pair is judged in both orders; order flips are reported (3-9 of 30 per pair here).
- **Drift.** A 7-turn conversation invokes the skill on turn 1 only and includes a topic change and a "thanks!" turn that invites filler. The judge scores the register of each turn.
- **Statistics.** Per-prompt paired differences, 95% bootstrap CI over prompts. Token ratios are geometric means.
- **Visible tokens** use `o200k_base` as a proxy tokenizer. The ratio to the generator's own tokenizer was about the same for base and latent (1.55 vs 1.53), so cross-arm ratios hold.

## Limitations

- One generator, one judge, 15 prompts. Effects under about 5 points of coverage or 0.5 errors per reply are below the noise floor.
- The judge flags errors it believes are wrong; some flags are themselves debatable. `REPORT.md` lists every flag for hand review.
- Models were reached through a private proxy that reports zero cost, so cost is shown in tokens, not dollars.
- Multi-turn session transcripts are not published (`results/*/sessions/` is git-ignored); the per-turn replies are in `results/pilot/multi/`.

## Files

```
bench.py            the harness (single file, stdlib + optional tiktoken)
prompts.json        15 prompts with judge key points
conversation.json   7-turn drift conversation
skills/latent/      the skill under test (the version measured: SKILL.md sha256 c487577d5e1e...)
results/pilot/      raw replies (gen/, multi/), judge verdicts (judge/), REPORT.md, SAMPLES.md
```

caveman is not vendored. The pilot used `skills/caveman/SKILL.md` from [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman), sha256 `5e30bb56afbd...`.

## License

MIT
