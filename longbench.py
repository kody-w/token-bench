#!/usr/bin/env python3
"""longbench: play the same multi-turn conversation through several host x arm combinations ("lanes"), in
parallel, and record what every turn costs: input tokens, model calls, seconds, tools used, right or wrong.

Hosts:  cc = Claude Code (claude -p)   cp = GitHub Copilot CLI (copilot -p)   bs = a Brainstem's POST /chat
Arms:   skill            the task's rules as Agent Skills (SKILL.md, instructions only)
        skill_script     the same skills plus a bundled script that implements the rules
        agentpy          the same rules as RAPP agent.py files, served to the host as MCP tools
        agentpy_visible  agentpy with Claude Code's MCP tool search turned off (tools listed up front)
        brainstem_plain  Copilot CLI with the brainstem-mcp plugin, asked plainly
        brainstem        the same, with "Ask the brainstem:" in front of every question
Suffixes: +fresh = a new session for every question (context cleared);  #N = repeat number.

Usage: longbench.py tasks/long-session --lanes cc:skill,cc:agentpy,cp:agentpy,bs:agentpy [--turns N]
       [--bs-url URL --bs-tap FILE] [--session baseline.json] [--out DIR]
Env:   LB_CC_MODEL (haiku)  LB_CP_MODEL (claude-haiku-5.5)  LB_STOCK=1 (Copilot with an empty home: no user
       plugins, MCP servers or instructions)  LB_REAL=1 (Copilot exactly as installed)  BRAINSTEM_MCP_LAUNCH
       (the plugin's launch.py; default: the newest installed version)  LB_TMP (where sandboxes go)"""
import argparse, glob, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
COPILOT = os.environ.get("COPILOT_BIN") or shutil.which("copilot") or "copilot"
_plugins = sorted(glob.glob(os.path.expanduser("~/.claude/plugins/cache/brainstem-mcp/brainstem/*/launch.py")),
                  key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r"[./]", p)])
BS_PLUGIN = os.environ.get("BRAINSTEM_MCP_LAUNCH") or (_plugins[-1] if _plugins else "")
BS_PLUGIN_HOME = os.path.expanduser("~/.cache/brainstem-mcp")  # where the plugin keeps its venv; stock mode hides HOME
BS_PLUGIN_FIXED = os.environ.get("BS_PLUGIN_FIXED", BS_PLUGIN)  # a second plugin build to compare against
try: USER_MCPS = list(json.load(open(os.path.expanduser("~/.copilot/mcp-config.json")))["mcpServers"])
except Exception: USER_MCPS = []
MODELS = {"cc": os.environ.get("LB_CC_MODEL", "haiku"), "cp": os.environ.get("LB_CP_MODEL", "claude-haiku-5.5")}

WORDS = {w: str(i) for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
def norm(s):
    s = re.sub(r"\b(" + "|".join(WORDS) + r")\b", lambda m: WORDS[m.group(1)], s.lower())
    return re.sub(r"[,$\s]", "", s)
def numbers(ans):
    t = re.sub(r"\b(" + "|".join(WORDS) + r")\b", lambda m: WORDS[m.group(1)], ans.lower())
    return [float(x.replace(",", "")) for x in re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?", t)]
def graded(ans, expect):
    found = numbers(ans)
    return all(any(abs(f - float(e)) < 0.005 for f in found) for e in expect)

ARM_DIR = {"agentpy_visible": "agentpy"}  # same files as another arm, different host setting

def sandbox(task, arm):
    sb = tempfile.mkdtemp(prefix=f"lb-{arm}-", dir=os.environ.get("LB_TMP"))
    shutil.copytree(os.path.join(task, "arms", ARM_DIR.get(arm, arm)), sb, dirs_exist_ok=True)
    shutil.copytree(os.path.join(task, "fixtures"), os.path.join(sb, "data"))
    return sb

def mcp_cfg(sb, host):
    """The agent.py files served as MCP tools. Claude Code wants type "stdio"; Copilot CLI wants "local" plus a tools filter."""
    server = {"command": sys.executable, "args": [os.path.join(HERE, "agent_host.py"), sb]}
    server.update({"type": "stdio"} if host == "cc" else {"type": "local", "tools": ["*"]})
    return {"mcpServers": {"agentpy": server}}

def cc_turn(state, prompt, first):
    sb, arm = state["sb"], state["arm"]
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", MODELS["cc"], "--dangerously-skip-permissions"]
    if arm != "real":  # "real" = Claude Code exactly as its owner set it up: user settings, plugins, memory, MCP servers
        cmd += ["--setting-sources", "project", "--strict-mcp-config"]
    if ARM_DIR.get(arm, arm) == "agentpy":  # every arm built from the agent.py files gets them as tools
        cfg = os.path.join(sb, ".lb-mcp.json"); json.dump(mcp_cfg(sb, "cc"), open(cfg, "w")); cmd += ["--mcp-config", cfg]
    if not first: cmd += ["--resume", state["sid"]]
    env = dict(os.environ, ENABLE_TOOL_SEARCH="false") if arm == "agentpy_visible" else None
    p = subprocess.run(cmd, cwd=sb, capture_output=True, text=True, timeout=900, env=env)
    calls, seen, ans, out_tok, cost, tools = [], set(), "", 0, 0.0, []
    for line in p.stdout.splitlines():
        try: ev = json.loads(line)
        except ValueError: continue
        if ev.get("type") == "assistant":
            m = ev["message"]
            tools += [b.get("name") for b in m.get("content", []) if b.get("type") == "tool_use"]
            if m.get("id") in seen: continue
            seen.add(m.get("id")); u = m.get("usage", {})
            calls.append(u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0))
        elif ev.get("type") == "result":
            state["sid"] = ev.get("session_id", state.get("sid")); ans = ev.get("result") or ""
            out_tok = ev.get("usage", {}).get("output_tokens", 0); cost = ev.get("total_cost_usd", 0)
    return {"answer": ans, "calls": len(calls), "context_per_call": calls, "input_tokens": sum(calls), "output_tokens": out_tok, "cost_usd": cost,
            "tools": tools, "error": None if ans else p.stderr[-300:]}

_GH = None
def cp_env(sb):
    """LB_STOCK=1: run Copilot as a fresh install would (empty home, so no user plugins, MCP servers or
    instructions). Sign-in comes from the GitHub CLI's token, passed only in this child's environment."""
    global _GH
    if os.environ.get("LB_STOCK") != "1": return None
    if _GH is None: _GH = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    home = os.path.join(sb, ".home"); os.makedirs(home, exist_ok=True)
    return dict(os.environ, HOME=home, GH_TOKEN=_GH)

def cp_turn(state, prompt, first):
    sb, arm = state["sb"], state["arm"]
    uf = os.path.join(sb, f".usage-{state['n']}.json")
    cmd = [COPILOT, "-p", prompt, "--model", MODELS["cp"], "--allow-all", "--no-custom-instructions", "--disable-builtin-mcps",
           "--usage-output-file", uf, "--output-format", "json"]
    if ARM_DIR.get(arm, arm) == "agentpy": cmd += ["--additional-mcp-config", json.dumps(mcp_cfg(sb, "cp"))]
    if arm in ("brainstem", "brainstem_fixed", "brainstem_plain"):  # plain = shipped plugin, no hint  # Copilot hands the work to a brainstem through the brainstem MCP plugin
        cmd += ["--additional-mcp-config", json.dumps({"mcpServers": {"brainstem": {"type": "local", "command": "python3",
                "args": [BS_PLUGIN_FIXED if arm == "brainstem_fixed" else BS_PLUGIN], "tools": ["*"],
                "env": {"BRAINSTEM_URL": state["url"], "BRAINSTEM_MCP_HOME": BS_PLUGIN_HOME}}}})]
    env = cp_env(sb)
    if env is None and os.environ.get("LB_REAL") != "1":  # LB_REAL=1: the install exactly as its owner uses it
        for name in USER_MCPS: cmd += ["--disable-mcp-server", name]
    if not first and state.get("sid"): cmd += [f"--resume={state['sid']}"]
    before = os.path.getsize(state["tap"]) if arm.startswith("brainstem") and os.path.exists(state["tap"]) else 0
    p = subprocess.run(cmd, cwd=sb, capture_output=True, text=True, timeout=900, env=env)
    bs_in = bs_calls = 0
    if arm.startswith("brainstem") and os.path.exists(state["tap"]):
        with open(state["tap"]) as f:
            f.seek(before); us = [json.loads(l)["usage"] for l in f if l.strip()]
        bs_in, bs_calls = sum(u.get("prompt_tokens", 0) for u in us), len(us)
    ans, tools = "", []
    for line in p.stdout.splitlines():
        try: ev = json.loads(line)
        except ValueError: continue
        if ev.get("type") == "assistant.message":
            tools += [t.get("name") for t in ev["data"].get("toolRequests", [])]
            if ev["data"].get("content"): ans = ev["data"]["content"]
        if ev.get("type") == "result": state["sid"] = ev.get("sessionId")
    try:
        u = json.load(open(uf)); mm = next(iter(u["modelMetrics"].values()))
        cur = {"start": u.get("sessionStartTime"), "calls": mm["requests"]["count"], "in": mm["usage"]["inputTokens"], "out": mm["usage"]["outputTokens"]}
        prev = state.get("cp_prev") if not first else None
        if prev and prev["start"] != cur["start"]: raise RuntimeError("copilot session changed between turns")
        prev = prev or {"calls": 0, "in": 0, "out": 0}
        state["cp_prev"] = cur
        host_in, host_calls, host_out = cur["in"] - prev["in"], cur["calls"] - prev["calls"], cur["out"] - prev["out"]
        if arm.startswith("brainstem") and bs_calls == 0: raise RuntimeError("not routed: Copilot never called the brainstem")
        return {"answer": ans, "calls": host_calls + bs_calls, "context_per_call": [u.get("lastCallInputTokens", 0)], "model": u.get("currentModel"),
                "host_input_tokens": host_in, "brainstem_input_tokens": bs_in, "tools": tools,
                "input_tokens": host_in + bs_in, "output_tokens": host_out, "cost_usd": None, "error": None if ans else p.stderr[-300:]}
    except Exception as e:
        return {"answer": ans, "calls": 0, "failed": True, "context_per_call": [], "input_tokens": 0, "output_tokens": 0, "cost_usd": None, "error": f"{e}: {p.stderr[-300:]}"}

def bs_turn(state, prompt, first):
    # Mirrors the brainstem web UI: history = plain user/assistant text, capped at 40 messages / 60k characters.
    hist = state.setdefault("history", [])[-40:]
    while len(hist) > 1 and sum(len(m["content"]) for m in hist) > 60000: hist = hist[1:]
    before = os.path.getsize(state["tap"]) if os.path.exists(state["tap"]) else 0
    body = json.dumps({"user_input": prompt, "conversation_history": hist, "session_id": state.setdefault("sid", f"lb-{time.time()}")}).encode()
    req = urllib.request.Request(state["url"] + "/chat", body, {"content-type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=900)); ans = d.get("response", "")
    state["history"] += [{"role": "user", "content": prompt}, {"role": "assistant", "content": ans}]
    with open(state["tap"]) as f: f.seek(before); us = [json.loads(l)["usage"] for l in f if l.strip()]
    calls = [u.get("prompt_tokens", 0) for u in us]
    if not calls: raise RuntimeError("tap saw no model calls")
    return {"answer": ans, "calls": len(calls), "context_per_call": calls, "input_tokens": sum(calls), "model": d.get("model"),
            "output_tokens": sum(u.get("completion_tokens", 0) for u in us), "cost_usd": None, "error": None}

TURN = {"cc": cc_turn, "cp": cp_turn, "bs": bs_turn}

def run_lane(lane, task, session, args):
    host, arm = lane.split("#")[0].split(":")  # "#2" marks a repeat run of the same lane
    fresh = arm.endswith("+fresh")  # clear the context every turn: a new session per question
    arm = arm.replace("+fresh", "")
    state = {"arm": arm, "n": 0}
    state.update(url=args.bs_url, tap=args.bs_tap)
    if host == "bs":
        d = os.path.join(task, "fixtures")
    else:
        state["sb"] = sandbox(task, arm); d = os.path.join(state["sb"], "data")
    rows = []
    for i, t in enumerate(session["turns"][:args.turns]):
        state["n"] = i; prompt = t["prompt"].replace("{d}", d); t0 = time.time()
        if arm == "brainstem": prompt = "Ask the brainstem: " + prompt  # how a person with the plugin would ask
        if fresh and host == "bs": state["history"] = []
        try: r = TURN[host](state, prompt, i == 0 or fresh)
        except Exception as e: r = {"failed": True, "answer": "", "calls": 0, "context_per_call": [], "input_tokens": 0, "output_tokens": 0, "cost_usd": None, "error": str(e)}
        r.setdefault("failed", bool(r.get("error")))
        r.update(lane=lane, turn=i + 1, ok=graded(r["answer"], t["expect"]), wall_s=round(time.time() - t0, 1), answer=r["answer"][:300])
        rows.append(r)
        if args.out:  # save after every turn, so a stopped run keeps what it measured
            os.makedirs(args.out, exist_ok=True)
            json.dump(rows, open(os.path.join(args.out, f"partial-{lane.replace(':', '_')}.json"), "w"), indent=1)
        print(f"  {lane:<16} turn {i + 1:>2}  {'right' if r['ok'] else 'WRONG'}  calls={r['calls']}  in={r['input_tokens']:,}  peak={max(r['context_per_call'] or [0]):,}  secs={r['wall_s']}" + (f"  ERR {r['error'][:80]}" if r["error"] else ""), flush=True)
    if "sb" in state: shutil.rmtree(state["sb"], ignore_errors=True)
    return rows

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("task"); ap.add_argument("--lanes", required=True)
    ap.add_argument("--turns", type=int, default=99); ap.add_argument("--bs-url", default="http://127.0.0.1:7098")
    ap.add_argument("--bs-tap", default=os.path.join(HERE, "tap", "bs.jsonl")); ap.add_argument("--out"); ap.add_argument("--session", default="session.json")
    a = ap.parse_args(); task = os.path.abspath(a.task); session = json.load(open(os.path.join(task, a.session)))
    lanes = a.lanes.split(",")
    print(f"longbench: {len(lanes)} lanes x {min(a.turns, len(session['turns']))} turns, all lanes at once", flush=True)
    with ThreadPoolExecutor(len(lanes)) as ex: res = list(ex.map(lambda l: run_lane(l, task, session, a), lanes))
    od = a.out or os.path.join(task, "results", time.strftime("%Y%m%d-%H%M%S")); os.makedirs(od, exist_ok=True)
    json.dump({"lanes": lanes, "models": MODELS, "rows": [r for rs in res for r in rs]}, open(os.path.join(od, "long.json"), "w"), indent=1)
    for rs in res:
        if rs: print(f"{rs[0]['lane']:<16} right {sum(r['ok'] for r in rs)}/{len(rs)}  calls {sum(r['calls'] for r in rs)}  input {sum(r['input_tokens'] for r in rs):,}  last-turn peak {max(rs[-1]['context_per_call'] or [0]):,}")
    print("out:", od)

if __name__ == "__main__": main()
