"""Build the long-session task from caps.py: fixtures, three arms, and a 15-turn session with answers."""
import inspect, json, os, random, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import caps

FX = os.path.join(HERE, "fixtures")
caps.gen_fixtures(FX)
for arm in ("skill", "skill_script", "agentpy"):
    shutil.rmtree(os.path.join(HERE, "arms", arm), ignore_errors=True)
    os.makedirs(os.path.join(HERE, "arms", arm))

HEADER = "import csv, json, math, statistics\n\n"
for key, c in caps.CAPS.items():
    src = inspect.getsource(c["fn"])
    slug = key.replace("_", "-")
    fm = f"---\nname: {slug}\ndescription: {c['description']}\n---\n# {c['agent']}\n\n"
    # Skill, instructions only. Mirrored into .github/skills so Copilot CLI finds it too.
    for root in (".claude", ".github"):
        d = os.path.join(HERE, "arms", "skill", root, "skills", slug); os.makedirs(d)
        open(os.path.join(d, "SKILL.md"), "w").write(fm + c["rules"] + "\n")
    # Skill + bundled script: same rules, plus a script that implements them.
    script = HEADER + src + f"\n\nif __name__ == '__main__':\n    import sys\n    print(json.dumps({c['fn'].__name__}(*sys.argv[1:])))\n"
    args = " ".join(f"<{p}>" for p in c["params"])
    for root in (".claude", ".github"):
        d = os.path.join(HERE, "arms", "skill_script", root, "skills", slug); os.makedirs(os.path.join(d, "scripts"))
        open(os.path.join(d, "scripts", f"{key}.py"), "w").write(script)
        open(os.path.join(d, "SKILL.md"), "w").write(fm + c["rules"] + f"\n\nThese rules are implemented in a bundled script. Run it instead of working them out:\n\n    python3 {root}/skills/{slug}/scripts/{key}.py {args}\n\nIt prints the answer as JSON.\n")
    # agent.py: same function, wrapped in the RAPP single-file agent shape.
    props = {p: {"type": "string", "description": d} for p, d in c["params"].items()}
    meta = {"name": c["agent"], "description": c["description"], "parameters": {"type": "object", "properties": props, "required": list(props)}}
    agent = (HEADER + "try:\n    from agents.basic_agent import BasicAgent\nexcept ImportError:\n    class BasicAgent:\n"
             "        def __init__(self, name=None, metadata=None): self.name, self.metadata = name, metadata\n\n\n"
             + src + f"\n\nclass {c['agent']}Agent(BasicAgent):\n    def __init__(self):\n        self.name = {c['agent']!r}\n"
             f"        self.metadata = {json.dumps(meta)}\n        super().__init__(name=self.name, metadata=self.metadata)\n\n"
             f"    def perform(self, **kwargs):\n        return json.dumps({c['fn'].__name__}(**kwargs))\n")
    open(os.path.join(HERE, "arms", "agentpy", f"{key}_agent.py"), "w").write(agent)

# The 15-turn session: plain business questions, no tool or skill names. {d} = the folder holding the files.
random.seed(11)
F = lambda n: os.path.join(FX, n)
turns = []
def add(prompt, fn, kwargs, nums):
    out = fn(**kwargs); turns.append({"prompt": prompt + " Answer in one short sentence with the numbers.", "expect": [str(out[k]) for k in nums], "truth": out})
add("Check {d}/invoices.csv against {d}/payments.csv: how many invoices got paid twice and how much did we overpay in total?", caps.double_paid, {"invoices": F("invoices.csv"), "payments": F("payments.csv")}, ["count", "total"])
for rep, q in (("Avery", "2026-Q1"), ("Casey", "2026-Q2"), ("Emery", "2026-Q1"), ("Blake", "2026-Q2")):
    add(f"Using {{d}}/sales.csv, what commission does {rep} earn for {q}?", caps.commission, {"sales": F("sales.csv"), "rep": rep, "quarter": q}, ["commission"])
for emp, wk in (("Rivera", "2026-W12"), ("Tanaka", "2026-W14"), ("Okafor", "2026-W11")):
    add(f"Using {{d}}/timesheet.csv and {{d}}/roster.csv, what is {emp}'s gross pay for {wk}?", caps.overtime_pay, {"timesheet": F("timesheet.csv"), "roster": F("roster.csv"), "employee": emp, "week": wk}, ["gross_pay"])
need = [s for s in (f"SKU-{i:04d}" for i in range(1, 41)) if caps.reorder(F("demand.csv"), F("inventory.csv"), s)["reorder"]]
for sku in need[:3]:
    add(f"Using {{d}}/demand.csv and {{d}}/inventory.csv, does {sku} need a reorder, and how many units should we order?", caps.reorder, {"demand": F("demand.csv"), "inventory": F("inventory.csv"), "sku": sku}, ["order_qty"])
for day in ("2026-09-30", "2026-10-11"):
    add(f"Using {{d}}/open_invoices.csv and {{d}}/customers.csv, what late fees do we charge as of {day}?", caps.late_fees, {"invoices": F("open_invoices.csv"), "customers": F("customers.csv"), "as_of": day}, ["invoices_charged", "total_fees"])
add("Recheck {d}/invoices.csv against {d}/payments.csv for double payments: count and total overpaid?", caps.double_paid, {"invoices": F("invoices.csv"), "payments": F("payments.csv")}, ["count", "total"])
add("Using {d}/sales.csv, what commission does Devon earn for 2026-Q2?", caps.commission, {"sales": F("sales.csv"), "rep": "Devon", "quarter": "2026-Q2"}, ["commission"])
first, rest = turns[0], turns[1:]; random.shuffle(rest); turns = [first] + rest
json.dump({"model": "haiku", "turns": turns}, open(os.path.join(HERE, "session.json"), "w"), indent=1)
print(len(turns), "turns"); [print(" ", t["expect"], t["prompt"][:70]) for t in turns]
