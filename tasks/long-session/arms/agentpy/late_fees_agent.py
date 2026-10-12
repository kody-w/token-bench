import csv, json, math, statistics

try:
    from agents.basic_agent import BasicAgent
except ImportError:
    class BasicAgent:
        def __init__(self, name=None, metadata=None): self.name, self.metadata = name, metadata


def late_fees(invoices, customers, as_of):
    tier = {r["customer_id"]: r["tier"] for r in csv.DictReader(open(customers))}
    y, m, d = map(int, as_of.split("-"))
    import datetime as dt
    asof = dt.date(y, m, d)
    total, n = 0.0, 0
    for r in csv.DictReader(open(invoices)):
        if r["status"] != "open":
            continue
        due = dt.date(*map(int, r["due_date"].split("-")))
        late = (asof - due).days
        if late <= 0:
            continue
        if tier.get(r["customer_id"]) == "gold" and late < 15:
            continue
        amount = float(r["amount"])
        fee = amount * 0.015 * math.ceil(late / 30)
        fee = min(max(fee, 25.0), amount * 0.10)
        total += fee
        n += 1
    return {"as_of": as_of, "invoices_charged": n, "total_fees": round(total, 2)}


class LateFeesAgent(BasicAgent):
    def __init__(self):
        self.name = 'LateFees'
        self.metadata = {"name": "LateFees", "description": "Calculate late fees on open invoices as of a date, under the collections policy.", "parameters": {"type": "object", "properties": {"invoices": {"type": "string", "description": "Path to open invoices CSV"}, "customers": {"type": "string", "description": "Path to customers CSV"}, "as_of": {"type": "string", "description": "Date YYYY-MM-DD"}}, "required": ["invoices", "customers", "as_of"]}}
        super().__init__(name=self.name, metadata=self.metadata)

    def perform(self, **kwargs):
        return json.dumps(late_fees(**kwargs))
