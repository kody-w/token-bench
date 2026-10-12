import csv, json, math, statistics

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


if __name__ == '__main__':
    import sys
    print(json.dumps(late_fees(*sys.argv[1:])))
