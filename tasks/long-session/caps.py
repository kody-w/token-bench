"""Five rules-heavy business capabilities. ONE implementation is the source of truth:
the SKILL.md rules, the bundled scripts and the agent.py files are all generated from here,
so every arm carries exactly the same logic."""
import csv, json, math, random, statistics


def double_paid(invoices, payments):
    amt = {r["invoice_id"]: float(r["amount"]) for r in csv.DictReader(open(invoices))}
    c = {}
    for r in csv.DictReader(open(payments)):
        c[r["invoice_id"]] = c.get(r["invoice_id"], 0) + 1
    hits = {k: v for k, v in c.items() if v > 1}
    return {"count": len(hits), "total": round(sum((v - 1) * amt[k] for k, v in hits.items()), 2)}


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


def overtime_pay(timesheet, roster, employee, week):
    rate = {r["employee"]: float(r["hourly_rate"]) for r in csv.DictReader(open(roster))}[employee]
    shifts = [r for r in csv.DictReader(open(timesheet)) if r["employee"] == employee and r["week"] == week]
    pay, regular_so_far = 0.0, 0.0
    for s in sorted(shifts, key=lambda s: s["date"]):
        hours = float(s["hours"])
        if hours > 6:
            hours -= 0.5
        if s["holiday"] == "yes":
            pay += hours * rate * 2.5
            continue
        if s["weekday"] == "Sun":
            pay += hours * rate * 2.0
            continue
        for _ in range(int(round(hours * 4))):
            q = 0.25
            mult = 1.0 if regular_so_far < 40 else (1.5 if regular_so_far < 60 else 2.0)
            pay += q * rate * mult
            regular_so_far += q
    return {"employee": employee, "week": week, "gross_pay": round(pay, 2)}


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


CAPS = {
    "double_paid": {
        "fn": double_paid, "agent": "DoublePaid",
        "description": "Find invoices that were paid more than once and the total overpaid, from an invoices CSV and a payments CSV.",
        "params": {"invoices": "Path to invoices CSV", "payments": "Path to payments CSV"},
        "rules": """Inputs: invoices CSV (invoice_id, customer_id, amount) and payments CSV (payment_id, invoice_id, amount).
1. Count payments per invoice_id.
2. An invoice with more than one payment was double-paid.
3. Overpaid for that invoice = (payments - 1) x the invoice amount from the invoices file.
4. Report the number of double-paid invoices and the total overpaid, rounded to the cent.""",
    },
    "commission": {
        "fn": commission, "agent": "Commission",
        "description": "Calculate a sales rep's commission for a quarter under the company commission plan.",
        "params": {"sales": "Path to sales CSV", "rep": "Rep name", "quarter": "Quarter like 2026-Q2"},
        "rules": """Inputs: sales CSV (date, rep, quarter, customer, type, amount, discount_pct, new_logo, paid_commission).
Use only rows for the rep and quarter. Process rows in date order; rows with the same date keep their order in the file.
1. Tiered rate on the rep's cumulative booked amount in the quarter: 5% on the first 50,000 dollars, 8% from 50,000 dollars to 150,000 dollars, 12% above 150,000 dollars. A deal that crosses a tier boundary is split across tiers.
2. A deal with discount_pct above 20 earns half of its tiered commission.
3. New-logo bonus: 500 dollars for a deal with new_logo = yes, at most once per customer.
4. Refund rows (type = refund) claw back their paid_commission value. Refunds do not reduce booked amount.
5. Quarterly commission is never below 0 dollars and is capped at 40,000 dollars. Do not round individual deals; round only the final amount to the cent.""",
    },
    "overtime_pay": {
        "fn": overtime_pay, "agent": "OvertimePay",
        "description": "Calculate an hourly employee's gross pay for a week under the overtime policy.",
        "params": {"timesheet": "Path to timesheet CSV", "roster": "Path to roster CSV", "employee": "Employee name", "week": "Week like 2026-W14"},
        "rules": """Inputs: timesheet CSV (employee, week, date, weekday, hours, holiday) and roster CSV (employee, hourly_rate).
Use only the employee's shifts for the week, in date order.
1. Any shift longer than 6 hours has an unpaid 30-minute break: subtract 0.5 hours.
2. Holiday shifts (holiday = yes) pay 2.5x for all hours and do not count toward weekly hours. A holiday on a Sunday pays the holiday rate.
3. Sunday shifts pay 2x for all hours and do not count toward weekly hours.
4. All other hours accumulate in order across the week: hours up to 40 pay 1x, hours from 40 to 60 pay 1.5x, hours beyond 60 pay 2x. Apply in 15-minute increments.
5. Gross pay = sum of hours x hourly_rate x multiplier. Do not round each shift; round only the total to the cent.""",
    },
    "reorder": {
        "fn": reorder, "agent": "Reorder",
        "description": "Decide whether a SKU needs reordering and how many units to order, under the replenishment policy.",
        "params": {"demand": "Path to daily demand CSV", "inventory": "Path to inventory CSV", "sku": "SKU id"},
        "rules": """Inputs: demand CSV (sku, date, units, in date order) and inventory CSV (sku, on_hand, on_order, lead_time_days, moq, case_pack).
1. Use the SKU's last 28 demand rows. avg = mean units per day; sd = population standard deviation.
2. Reorder point = avg x lead_time_days + 1.65 x sd x sqrt(lead_time_days).
3. Position = on_hand + on_order. If position is above the reorder point, do not reorder (order 0).
4. Otherwise target = reorder point + 14 days of avg demand. Need = max(target - position, moq).
5. Round need UP to a whole number of case packs. Report reorder yes/no and the order quantity.""",
    },
    "late_fees": {
        "fn": late_fees, "agent": "LateFees",
        "description": "Calculate late fees on open invoices as of a date, under the collections policy.",
        "params": {"invoices": "Path to open invoices CSV", "customers": "Path to customers CSV", "as_of": "Date YYYY-MM-DD"},
        "rules": """Inputs: invoices CSV (invoice_id, customer_id, amount, due_date, status) and customers CSV (customer_id, tier).
Only invoices with status = open that are past due as of the date count.
1. Days late = as_of - due_date. Not late (0 or fewer days) = no fee.
2. Gold-tier customers are not charged when fewer than 15 days late.
3. Fee = amount x 1.5% for every started 30-day period late (1-30 days = 1 period, 31-60 = 2, ...).
4. Each fee is at least 25 dollars and at most 10% of the invoice amount. When 10% of the amount is below 25 dollars, the fee is 10% of the amount.
5. Add the exact fees without rounding each one, then round only the total to the cent. Report how many invoices were charged and that total.""",
    },
}


def gen_fixtures(out, seed=7):
    """Synthetic data only. Fixed seed so every arm sees identical files."""
    import os
    random.seed(seed)
    os.makedirs(out, exist_ok=True)
    W = lambda name, hdr, rows: csv.writer(open(os.path.join(out, name), "w", newline="")).writerows([hdr] + rows)
    inv = [(f"INV-{i:06d}", f"CUST-{random.randint(1, 800):04d}", round(random.uniform(50, 9000), 2)) for i in range(1, 20001)]
    pays = [(f"PAY-{i:07d}", r[0], r[2]) for i, r in enumerate(inv, 1)]
    for j, r in enumerate(random.sample(inv, 9)):
        pays.append((f"PAY-{30000 + j}", r[0], r[2]))
    random.shuffle(pays)
    W("invoices.csv", ["invoice_id", "customer_id", "amount"], inv)
    W("payments.csv", ["payment_id", "invoice_id", "amount"], pays)
    reps = ["Avery", "Blake", "Casey", "Devon", "Emery", "Finley"]
    sales = []
    for q, months in (("2026-Q1", (1, 2, 3)), ("2026-Q2", (4, 5, 6))):
        for rep in reps:
            for k in range(random.randint(14, 24)):
                cust = f"ACME-{random.randint(1, 40):03d}"
                date = f"2026-{random.choice(months):02d}-{random.randint(1, 28):02d}"
                if random.random() < 0.08:
                    sales.append([date, rep, q, cust, "refund", 0, 0, "no", round(random.uniform(200, 3000), 2)])
                else:
                    sales.append([date, rep, q, cust, "deal", round(random.uniform(2000, 30000), 2),
                                  random.choice([0, 5, 10, 15, 22, 25, 30]), random.choice(["yes", "no", "no"]), 0])
    W("sales.csv", ["date", "rep", "quarter", "customer", "type", "amount", "discount_pct", "new_logo", "paid_commission"], sales)
    staff = ["Rivera", "Okafor", "Lindqvist", "Tanaka", "Moreau"]
    W("roster.csv", ["employee", "hourly_rate"], [[e, round(random.uniform(18, 45), 2)] for e in staff])
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    ts = []
    for wk in range(10, 16):
        for e in staff:
            for di, dname in enumerate(days):
                if random.random() < 0.82:
                    ts.append([e, f"2026-W{wk}", f"2026-W{wk}-{di + 1}", dname, random.choice([4, 6.5, 8, 9.5, 10, 11, 12]),
                               "yes" if random.random() < 0.05 else "no"])
    W("timesheet.csv", ["employee", "week", "date", "weekday", "hours", "holiday"], ts)
    skus = [f"SKU-{i:04d}" for i in range(1, 41)]
    W("demand.csv", ["sku", "date", "units"], [[s, f"d{d:03d}", max(0, int(random.gauss(40 + i * 3, 12)))] for i, s in enumerate(skus) for d in range(1, 61)])
    W("inventory.csv", ["sku", "on_hand", "on_order", "lead_time_days", "moq", "case_pack"],
      [[s, random.randint(50, 1400), random.choice([0, 0, 120, 300]), random.choice([3, 5, 7, 10, 14]), random.choice([100, 200, 500]), random.choice([6, 12, 24, 48])] for s in skus])
    W("customers.csv", ["customer_id", "tier"], [[f"CUST-{i:04d}", random.choice(["gold", "silver", "standard", "standard"])] for i in range(1, 801)])
    oi = []
    for i in range(1, 3001):
        oi.append([f"OI-{i:05d}", f"CUST-{random.randint(1, 800):04d}", round(random.uniform(80, 12000), 2),
                   f"2026-{random.randint(5, 9):02d}-{random.randint(1, 28):02d}", random.choice(["open", "open", "paid"])])
    W("open_invoices.csv", ["invoice_id", "customer_id", "amount", "due_date", "status"], oi)
