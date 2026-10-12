import csv, json, math, statistics

try:
    from agents.basic_agent import BasicAgent
except ImportError:
    class BasicAgent:
        def __init__(self, name=None, metadata=None): self.name, self.metadata = name, metadata


def double_paid(invoices, payments):
    amt = {r["invoice_id"]: float(r["amount"]) for r in csv.DictReader(open(invoices))}
    c = {}
    for r in csv.DictReader(open(payments)):
        c[r["invoice_id"]] = c.get(r["invoice_id"], 0) + 1
    hits = {k: v for k, v in c.items() if v > 1}
    return {"count": len(hits), "total": round(sum((v - 1) * amt[k] for k, v in hits.items()), 2)}


class DoublePaidAgent(BasicAgent):
    def __init__(self):
        self.name = 'DoublePaid'
        self.metadata = {"name": "DoublePaid", "description": "Find invoices that were paid more than once and the total overpaid, from an invoices CSV and a payments CSV.", "parameters": {"type": "object", "properties": {"invoices": {"type": "string", "description": "Path to invoices CSV"}, "payments": {"type": "string", "description": "Path to payments CSV"}}, "required": ["invoices", "payments"]}}
        super().__init__(name=self.name, metadata=self.metadata)

    def perform(self, **kwargs):
        return json.dumps(double_paid(**kwargs))
