import csv, json, math, statistics

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


if __name__ == '__main__':
    import sys
    print(json.dumps(reorder(*sys.argv[1:])))
