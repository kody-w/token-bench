import csv, json, math, statistics

try:
    from agents.basic_agent import BasicAgent
except ImportError:
    class BasicAgent:
        def __init__(self, name=None, metadata=None): self.name, self.metadata = name, metadata


def commission(sales, rep, quarter):
    rows = [r for r in csv.DictReader(open(sales)) if r["rep"] == rep and r["quarter"] == quarter]
    seen, total, booked = set(), 0.0, 0.0
    tiers = [(50000, 0.05), (150000, 0.08), (float("inf"), 0.12)]
    for r in sorted(rows, key=lambda r: r["date"]):
        amount = float(r["amount"])
        if r["type"] == "refund":
            total -= float(r["paid_commission"])
            continue
        disc = float(r["discount_pct"])
        pay = 0.0
        remaining, start = amount, booked
        for cap, rate in tiers:
            if start >= cap or remaining <= 0:
                continue
            take = min(remaining, cap - start)
            pay += take * rate
            remaining -= take
            start += take
        booked += amount
        if disc > 20:
            pay /= 2
        if r["new_logo"] == "yes" and r["customer"] not in seen:
            pay += 500
            seen.add(r["customer"])
        total += pay
    return {"rep": rep, "quarter": quarter, "commission": round(min(max(total, 0.0), 40000.0), 2)}


class CommissionAgent(BasicAgent):
    def __init__(self):
        self.name = 'Commission'
        self.metadata = {"name": "Commission", "description": "Calculate a sales rep's commission for a quarter under the company commission plan.", "parameters": {"type": "object", "properties": {"sales": {"type": "string", "description": "Path to sales CSV"}, "rep": {"type": "string", "description": "Rep name"}, "quarter": {"type": "string", "description": "Quarter like 2026-Q2"}}, "required": ["sales", "rep", "quarter"]}}
        super().__init__(name=self.name, metadata=self.metadata)

    def perform(self, **kwargs):
        return json.dumps(commission(**kwargs))
