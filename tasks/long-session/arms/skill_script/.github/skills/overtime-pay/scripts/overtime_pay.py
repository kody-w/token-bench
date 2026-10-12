import csv, json, math, statistics

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


if __name__ == '__main__':
    import sys
    print(json.dumps(overtime_pay(*sys.argv[1:])))
