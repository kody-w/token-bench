import csv, json, math, statistics

try:
    from agents.basic_agent import BasicAgent
except ImportError:
    class BasicAgent:
        def __init__(self, name=None, metadata=None): self.name, self.metadata = name, metadata


def reorder(demand, inventory, sku):
    inv = {r["sku"]: r for r in csv.DictReader(open(inventory))}[sku]
    days = [float(r["units"]) for r in csv.DictReader(open(demand)) if r["sku"] == sku][-28:]
    avg, sd = sum(days) / len(days), statistics.pstdev(days)
    lead = int(inv["lead_time_days"])
    rop = avg * lead + 1.65 * sd * math.sqrt(lead)
    position = int(inv["on_hand"]) + int(inv["on_order"])
    if position > rop:
        return {"sku": sku, "reorder": False, "order_qty": 0}
    target = rop + avg * 14
    need = max(target - position, int(inv["moq"]))
    pack = int(inv["case_pack"])
    return {"sku": sku, "reorder": True, "order_qty": int(math.ceil(need / pack) * pack)}


class ReorderAgent(BasicAgent):
    def __init__(self):
        self.name = 'Reorder'
        self.metadata = {"name": "Reorder", "description": "Decide whether a SKU needs reordering and how many units to order, under the replenishment policy.", "parameters": {"type": "object", "properties": {"demand": {"type": "string", "description": "Path to daily demand CSV"}, "inventory": {"type": "string", "description": "Path to inventory CSV"}, "sku": {"type": "string", "description": "SKU id"}}, "required": ["demand", "inventory", "sku"]}}
        super().__init__(name=self.name, metadata=self.metadata)

    def perform(self, **kwargs):
        return json.dumps(reorder(**kwargs))
