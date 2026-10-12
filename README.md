# token-bench

Measure what an AI host spends to answer the same questions: input tokens, model calls, seconds and
right answers, turn by turn, for Claude Code, GitHub Copilot CLI and a [RAPP Brainstem](https://github.com/kody-w/rapp-installer).

The white paper built from these runs is **[The Context Tax](https://kody-w.github.io/token-bench/)**.

## What it runs

One conversation of business questions, played through several **lanes** at once. A lane is a host plus
a way of packaging the rules the host needs:

| Lane | What the host gets |
|---|---|
| `cc:skill`, `cp:skill` | The rules as Agent Skills (`SKILL.md`, instructions only) |
| `cc:skill_script`, `cp:skill_script` | The same skills plus a bundled script that implements the rules |
| `cc:agentpy`, `cp:agentpy` | The same rules as RAPP `agent.py` files, served as MCP tools |
| `bs:agentpy` | The same `agent.py` files loaded in a Brainstem, called with `POST /chat` |
| `cp:brainstem_plain` | Copilot CLI with the [brainstem-mcp](https://github.com/kody-w/brainstem-mcp) plugin |

Add `+fresh` to start a new session for every question (context cleared), and `#2`, `#3` for repeats.

The task in `tasks/long-session` has five capabilities with real rules: tiered sales commission with
clawbacks, overtime pay, reorder points, late fees and double-paid invoices. All three packagings are
generated from one implementation (`caps.py`), so every lane carries exactly the same logic. Answers are
graded against the exact numbers, to the cent.

## Run it

You need Python 3.10+, and whichever hosts you want to compare: `claude`, `copilot`, a Brainstem.

```bash
git clone https://github.com/kody-w/token-bench && cd token-bench

# 1. Each host's cost before any work: one trivial question
python3 longbench.py tasks/long-session --session baseline.json --lanes cc:skill,cp:skill

# 2. A Brainstem: start a measured copy of your installed one (your install is only read)
python3 start_brainstem.py            # leave it running; it prints the URL and token log path

# 3. The 15-question conversation, every lane at once
python3 longbench.py tasks/long-session --bs-tap tap/bs.jsonl \
  --lanes bs:agentpy,cc:skill,cc:skill_script,cc:agentpy,cp:skill,cp:skill_script,cp:agentpy

# 4. Combine repeats into medians
python3 longsummary.py summary.json tasks/long-session/results/*
```

Settings: `LB_CC_MODEL` and `LB_CP_MODEL` pick the model (default Claude Haiku 5.5 on both).
`LB_STOCK=1` runs Copilot from an empty home folder, so your own plugins, MCP servers and instructions
stay out of the measurement; `LB_REAL=1` measures Copilot exactly as you have it set up.

## How tokens are counted

- **Claude Code:** the `usage` of every model call in `claude -p --output-format stream-json`.
- **Copilot CLI:** `--usage-output-file`. It holds a running total for the whole session, so each turn
  is the difference from the previous one.
- **Brainstem:** `/chat` does not report usage, so `start_brainstem.py` loads `tap/sitecustomize.py`
  into the Brainstem's Python. The tap records the `usage` of each model response to a file and changes
  nothing else.

Input tokens are everything sent to the model on each call, cached or not. Caching makes repeated
context cheaper per token; it does not make it smaller.

## Your own task

Copy `tasks/long-session`, change `caps.py` (your functions and the rules in plain words), run
`python3 build.py` to generate the skills, the scripts, the `agent.py` files and `session.json`, and
point `longbench.py` at the folder.

## Results

`results/2026-10-11` holds every run behind the white paper, with a `summary.json` of medians. Runs
that were invalid because of a bug in this harness are kept in `results/2026-10-11/invalid` with the
reason, and are not counted.

## License

MIT
