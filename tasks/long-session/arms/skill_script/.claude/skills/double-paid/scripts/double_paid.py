import csv, json, math, statistics

def double_paid(invoices, payments):
    amt = {r["invoice_id"]: float(r["amount"]) for r in csv.DictReader(open(invoices))}
    c = {}
    for r in csv.DictReader(open(payments)):
        c[r["invoice_id"]] = c.get(r["invoice_id"], 0) + 1
    hits = {k: v for k, v in c.items() if v > 1}
    return {"count": len(hits), "total": round(sum((v - 1) * amt[k] for k, v in hits.items()), 2)}


if __name__ == '__main__':
    import sys
    print(json.dumps(double_paid(*sys.argv[1:])))
