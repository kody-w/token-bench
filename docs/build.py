#!/usr/bin/env python3
"""Build the white paper (docs/index.html) from results/<date>/summary.json, so every number and every chart
comes from the measured runs. Usage: python3 docs/build.py [results/2026-10-11]"""
import html, json, os, sys
from string import Template

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results", "2026-10-11")
S = json.load(open(os.path.join(RES, "summary.json")))
X = json.load(open(os.path.join(RES, "extras.json")))  # values measured outside longbench (stated in the paper)


def g(key, field="tokens_per_turn"):
    return (S.get(key) or {}).get(field)


def k(n):  # 12,345 -> "12.3k"; 1,234,567 -> "1.23M"
    if n is None: return "n/a"
    return f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.1f}k" if n >= 1e4 else f"{n / 1e3:.1f}k" if n >= 1e3 else f"{n:.0f}"


def num(n): return "n/a" if n is None else f"{n:,.0f}"
def ratio(a, b): return f"{a / b:.1f}" if a and b else "n/a"
def right(key): s = S.get(key) or {}; return f"{s.get('right', 0)} of {s.get('turns', 0)}"


HOST = {"bs": "Brainstem", "cc": "Claude Code", "cp": "Copilot CLI"}


def hbars(rows, unit="tokens", note=""):
    """rows: (label, value, host, hatched). Horizontal bars, one scale, direct labels."""
    rows = [r for r in rows if r[1] is not None]
    if not rows: return ""
    vmax = max(r[1] for r in rows); W, lw, vw, rh = 720, 250, 92, 34
    bw = W - lw - vw; H = rh * len(rows) + 8
    out = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(note)}">']
    for i, (label, v, host, hatch) in enumerate(rows):
        y = 4 + i * rh; w = max(2, bw * v / vmax)
        fill = f"url(#hatch-{host})" if hatch else f"var(--{host})"
        out.append(f'<g class="mark"><title>{html.escape(label)}: {num(v)} {unit}</title>'
                   f'<text x="{lw - 10}" y="{y + rh / 2 + 5}" text-anchor="end" class="lab">{html.escape(label)}</text>'
                   f'<rect x="{lw}" y="{y + 6}" width="{w:.1f}" height="{rh - 12}" rx="4" fill="{fill}" stroke="var(--{host})" stroke-width="{1.5 if hatch else 0}"/>'
                   f'<text x="{lw + w + 8:.1f}" y="{y + rh / 2 + 5}" class="val">{k(v) if unit == "tokens" else f"{v:.1f} s"}</text></g>')
    out.append("</svg>")
    return "".join(out)


def lines(series, turns, ylabel="tokens per question"):
    """series: (label, host, [values per turn]). One y scale from zero, direct end labels, recessive grid."""
    W, H, l, r, t, b = 720, 300, 64, 150, 14, 34
    vmax = max(max(v for v in s[2] if v is not None) for s in series) * 1.08
    X0 = lambda i: l + (W - l - r) * (i - 1) / (turns - 1)
    Y0 = lambda v: t + (H - t - b) * (1 - v / vmax)
    out = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(ylabel)} by question number">']
    step = 10000 if vmax > 40000 else 2000
    for gv in range(0, int(vmax) + 1, step):
        out.append(f'<line x1="{l}" x2="{W - r}" y1="{Y0(gv):.1f}" y2="{Y0(gv):.1f}" class="grid"/>'
                   f'<text x="{l - 8}" y="{Y0(gv) + 4:.1f}" text-anchor="end" class="axis">{k(gv) if gv else 0}</text>')
    for i in range(1, turns + 1):
        if i in (1, 5, 10, 15) or turns <= 5:
            out.append(f'<text x="{X0(i):.1f}" y="{H - 10}" text-anchor="middle" class="axis">{i}</text>')
    out.append(f'<text x="{(l + W - r) / 2:.0f}" y="{H}" text-anchor="middle" class="axis">question number</text>')
    for label, host, vals in series:
        pts = [(X0(i + 1), Y0(v)) for i, v in enumerate(vals) if v is not None]
        out.append(f'<polyline fill="none" stroke="var(--{host})" stroke-width="2" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"/>')
        for i, (x, y) in enumerate(pts):
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="var(--{host})" stroke="var(--bg)" stroke-width="2">'
                       f'<title>{html.escape(label)}, question {i + 1}: {num(vals[i])} tokens</title></circle>')
        x, y = pts[-1]
        out.append(f'<text x="{x + 10:.1f}" y="{y + 4:.1f}" class="lab">{html.escape(label)}</text>')
    out.append("</svg>")
    return "".join(out)


def table(head, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def per_turn(key): return [p["tokens"] for p in (S.get(key) or {}).get("per_turn", [])]


bs5 = sum(per_turn("long/brainstem")[:5]) if per_turn("long/brainstem") else None
SKILL_ONLY = ("long/claude-code/skill", "fresh/claude-code/skill", "long/copilot-stock/skill", "fresh/copilot-stock/skill")
code_ran = code_ok = 0  # answers where agent code demonstrably ran: an agent.py tool call, a routed Brainstem turn, or Brainstem /chat
for f in __import__("glob").glob(os.path.join(RES, "runs", "**", "*.json"), recursive=True):
    for r in json.load(open(f)):
        used = any(str(t).startswith(("mcp__agentpy", "agentpy-")) for t in (r.get("tools") or [])) or bool(r.get("brainstem_input_tokens")) or r["lane"].startswith("bs:")
        if used and not r.get("failed"): code_ran += 1; code_ok += bool(r["ok"])
_cpt = [r for r in json.load(open(os.path.join(RES, "runs", "timing", "copilot-stock-agentpy.json")))] if os.path.exists(os.path.join(RES, "runs", "timing", "copilot-stock-agentpy.json")) else []
_apf = json.load(open(os.path.join(RES, "runs", "fresh", "claude-code", "agentpy.json")))
cc_apf_wrong = sum(1 for r in _apf if not r["ok"] and not any(str(t).startswith("mcp__agentpy") for t in (r.get("tools") or [])))
V = dict(
    b_bs=num(g("base/brainstem")), b_cc=num(g("base/claude-code")), b_cp=num(g("base/copilot-stock")),
    b_cc_listed=num(g("base/claude-code-agentpy-listed")), b_cc_real=num(g("base/claude-code-real")),
    b_cp_real=num(g("base/copilot-real")), b_bs_real=num(g("base/brainstem-global")),
    r_cc_bs=ratio(g("base/claude-code"), g("base/brainstem")), r_cp_bs=ratio(g("base/copilot-stock"), g("base/brainstem")),
    l_bs=k(g("long/brainstem", "tokens_per_run")), l_cc_ss=k(g("long/claude-code/skill_script", "tokens_per_run")),
    l_cc_ap=k(g("long/claude-code/agentpy", "tokens_per_run")), l_cc_sk=k(g("long/claude-code/skill", "tokens_per_run")),
    l_cc_al=k(g("long/claude-code/agentpy_listed", "tokens_per_run")),
    r_long=ratio(g("long/claude-code/skill_script", "tokens_per_run"), g("long/brainstem", "tokens_per_run")),
    c_ap=k(g("long/copilot-stock/agentpy", "tokens_per_run")), c_ss=k(g("long/copilot-stock/skill_script", "tokens_per_run")),
    c_sk=k(g("long/copilot-stock/skill", "tokens_per_run")), bs5=k(bs5),
    r_cp5=ratio(g("long/copilot-stock/agentpy", "tokens_per_run"), bs5),
    co_ap=k(g("long/copilot-own/agentpy", "tokens_per_run")), co_s=f'{g("long/copilot-own/agentpy", "secs_per_turn") or 0:.0f}',
    cs_s=f'{g("long/copilot-stock/agentpy", "secs_per_turn") or 0:.0f}',
    f_bs=k(g("fresh/brainstem", "tokens_per_run")),
    right_bs=right("long/brainstem"), right_cc_ss=right("long/claude-code/skill_script"), right_cc_sk=right("long/claude-code/skill"),
    right_cp_sk=right("long/copilot-stock/skill"), right_cp_skf=right("fresh/copilot-stock/skill"), right_cc_skf=right("fresh/claude-code/skill"),
    right_cc_apf=right("fresh/claude-code/agentpy"),
    tool_cc_ap=(S.get("long/claude-code/agentpy") or {}).get("agent_tool_turns"), tool_cc_apf=(S.get("fresh/claude-code/agentpy") or {}).get("agent_tool_turns"),
    tool_cc_al=(S.get("long/claude-code/agentpy_listed") or {}).get("agent_tool_turns"),
    g_chat=k(g("global/chat")), g_plug=k(g("global/copilot-stock+plugin-0.2.1")),
    r_bridge=ratio(g("global/copilot-stock+plugin-0.2.1"), g("global/chat")),
    rt_020=(S.get("bridge/copilot-stock+plugin-0.2.0") or {}).get("routed_turns"),
    rt_021=(S.get("bridge/copilot-stock+plugin-0.2.1") or {}).get("routed_turns"),
    rt_g021=(S.get("global/copilot-stock+plugin-0.2.1") or {}).get("routed_turns"),
    rt_own=(S.get("global/copilot-own+plugin-0.2.1") or {}).get("routed_turns"),
    right_020=right("bridge/copilot-stock+plugin-0.2.0"), right_021=right("bridge/copilot-stock+plugin-0.2.1"),
    right_own=right("global/copilot-own+plugin-0.2.1"),
    t_bs=f'{g("timing/brainstem", "secs_per_turn") or 0:.1f}', t_cc=f'{g("timing/claude-code-skill_script", "secs_per_turn") or 0:.1f}',
    t_cp=f'{g("timing/copilot-stock-agentpy", "secs_per_turn") or 0:.1f}', t_ccal=f'{g("timing/claude-code-agentpy_listed", "secs_per_turn") or 0:.1f}',
    t_cp_own=f'{g("timing/copilot-own-agentpy", "secs_per_turn") or 0:.0f}', t_cp_own_tok=k(g("timing/copilot-own-agentpy", "tokens_per_run")),
    r_cp_own_tok=ratio(g("timing/copilot-own-agentpy", "tokens_per_run"), g("timing/copilot-stock-agentpy", "tokens_per_run")),
    t_bs_tok=k(g("timing/brainstem", "tokens_per_run")), t_cp_tok=k(g("timing/copilot-stock-agentpy", "tokens_per_run")),
    t_ccal_tok=k(g("timing/claude-code-agentpy_listed", "tokens_per_run")),
    sess_calls=num(X["session"]["calls"]), sess_tokens=k(X["session"]["tokens"]), sess_avg=k(X["session"]["avg"]),
    code_ran=num(code_ran), code_ok=num(code_ok), cc_apf_wrong=cc_apf_wrong,
    s_total=sum((S.get(c) or {}).get("turns", 0) for c in SKILL_ONLY), s_wrong=sum((S.get(c) or {}).get("turns", 0) - (S.get(c) or {}).get("right", 0) for c in SKILL_ONLY),
    long_right_min=min((S.get(c) or {}).get("right", 45) for c in ("long/brainstem", "long/claude-code/skill_script", "long/claude-code/agentpy", "long/claude-code/skill")),
    cp_tool_used=sum(any(str(t).startswith("agentpy-") for t in (r.get("tools") or [])) for r in _cpt), cp_tool_turns=len(_cpt),
    glue_bs=X["glue"]["bs"], glue_cc=X["glue"]["cc"], glue_cp=X["glue"]["cp"], flags_cc=X["flags"]["cc"], flags_cp=X["flags"]["cp"],
)

CHART_BASE = hbars([
    ("Brainstem, five agents", g("base/brainstem"), "bs", False),
    ("Brainstem, as used (22 agents)", g("base/brainstem-global"), "bs", True),
    ("Claude Code, fresh setup", g("base/claude-code"), "cc", False),
    ("Claude Code, as used", g("base/claude-code-real"), "cc", True),
    ("Copilot CLI, fresh install", g("base/copilot-stock"), "cp", False),
    ("Copilot CLI, as used", g("base/copilot-real"), "cp", True),
], note="Input tokens for one trivial question, per host")
CHART_LONG = hbars([
    ("Brainstem, /chat", g("long/brainstem", "tokens_per_run"), "bs", False),
    ("Claude Code, skill + script", g("long/claude-code/skill_script", "tokens_per_run"), "cc", False),
    ("Claude Code, agent.py tools", g("long/claude-code/agentpy", "tokens_per_run"), "cc", False),
    ("Claude Code, skill", g("long/claude-code/skill", "tokens_per_run"), "cc", False),
], note="Total input tokens for the same 15 questions")
CHART_TURNS = lines([
    ("Claude Code", "cc", per_turn("long/claude-code/skill_script")),
    ("Brainstem", "bs", per_turn("long/brainstem")),
], 15)
CHART_TIME = hbars([
    ("Brainstem, /chat", g("timing/brainstem", "secs_per_turn"), "bs", False),
    ("Copilot CLI, agent.py", g("timing/copilot-stock-agentpy", "secs_per_turn"), "cp", False),
    ("Claude Code, skill + script", g("timing/claude-code-skill_script", "secs_per_turn"), "cc", False),
    ("Claude Code, agent.py listed", g("timing/claude-code-agentpy_listed", "secs_per_turn"), "cc", False),
    ("Copilot CLI as used, agent.py", g("timing/copilot-own-agentpy", "secs_per_turn"), "cp", True),
], unit="seconds", note="Median seconds per answer")
CHART_BRIDGE = hbars([
    ("Brainstem, /chat", g("global/chat"), "bs", False),
    ("Copilot CLI + plugin, when it routed", g("global/copilot-stock+plugin-0.2.1"), "cp", False),
], note="Input tokens per answer from the same Brainstem")


def row(key, label):
    s = S.get(key) or {}
    tools = s.get("agent_tool_turns")
    return [label, k(s.get("tokens_per_run")), f"{s.get('right', 0)} of {s.get('turns', 0)}",
            f"{s.get('secs_per_turn') or 0:.1f} s", "" if tools is None else f"{tools} of {s.get('turns', 0)}"]


T_PACK = table(["Setup", "Tokens, whole chat", "Right", "Seconds / answer*", "Agent tool used"], [
    row("long/brainstem", "Brainstem, /chat (15 questions)"),
    row("fresh/brainstem", "Brainstem, new chat per question"),
    row("long/claude-code/skill_script", "Claude Code, skill + script"),
    row("fresh/claude-code/skill_script", "&nbsp;&nbsp;new chat per question"),
    row("long/claude-code/agentpy", "Claude Code, agent.py tools"),
    row("fresh/claude-code/agentpy", "&nbsp;&nbsp;new chat per question"),
    row("long/claude-code/agentpy_listed", "Claude Code, agent.py listed up front"),
    row("fresh/claude-code/agentpy_listed", "&nbsp;&nbsp;new chat per question"),
    row("long/claude-code/skill", "Claude Code, skill (instructions only)"),
    row("fresh/claude-code/skill", "&nbsp;&nbsp;new chat per question"),
    row("long/copilot-stock/agentpy", "Copilot CLI, agent.py tools (5 questions)"),
    row("fresh/copilot-stock/agentpy", "&nbsp;&nbsp;new chat per question"),
    row("long/copilot-stock/skill_script", "Copilot CLI, skill + script"),
    row("long/copilot-stock/skill", "Copilot CLI, skill (instructions only)"),
    row("long/copilot-own/agentpy", "Copilot CLI as used, agent.py tools"),
], "num")
T_BRIDGE = table(["Path to the same agents", "Copilot called the Brainstem", "Right"], [
    ["Copilot CLI (fresh install) + brainstem-mcp 0.2.0", f"{V['rt_020']} of 15", V["right_020"]],
    ["Copilot CLI (fresh install) + brainstem-mcp 0.2.1", f"{V['rt_021']} of 15", V["right_021"]],
    ["Same, against the author's own Brainstem", f"{V['rt_g021']} of 15", right("global/copilot-stock+plugin-0.2.1")],
    ["Copilot CLI as the author uses it + 0.2.1", f"{V['rt_own']} of 10", V["right_own"]],
    ["The Brainstem's /chat, called directly", "every question",
     right("global/chat") + (f" ({S['global/chat']['failed']} upstream error, no answer)" if (S.get("global/chat") or {}).get("failed") else "")],
], "num")
T_LEDGER = table(["Host", "What broke or surprised us", "Error shown?", "Whose fault"], [[html.escape(c) for c in r] for r in X["ledger"]])

PAGE = Template(open(os.path.join(ROOT, "docs", "template.html")).read())
open(os.path.join(ROOT, "docs", "index.html"), "w").write(PAGE.substitute(
    V, CHART_BASE=CHART_BASE, CHART_LONG=CHART_LONG, CHART_TURNS=CHART_TURNS, CHART_TIME=CHART_TIME,
    CHART_BRIDGE=CHART_BRIDGE, T_PACK=T_PACK, T_BRIDGE=T_BRIDGE, T_LEDGER=T_LEDGER))
print("wrote docs/index.html")
