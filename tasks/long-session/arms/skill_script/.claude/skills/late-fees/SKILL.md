---
name: late-fees
description: Calculate late fees on open invoices as of a date, under the collections policy.
---
# LateFees

Inputs: invoices CSV (invoice_id, customer_id, amount, due_date, status) and customers CSV (customer_id, tier).
Only invoices with status = open that are past due as of the date count.
1. Days late = as_of - due_date. Not late (0 or fewer days) = no fee.
2. Gold-tier customers are not charged when fewer than 15 days late.
3. Fee = amount x 1.5% for every started 30-day period late (1-30 days = 1 period, 31-60 = 2, ...).
4. Each fee is at least 25 dollars and at most 10% of the invoice amount. When 10% of the amount is below 25 dollars, the fee is 10% of the amount.
5. Add the exact fees without rounding each one, then round only the total to the cent. Report how many invoices were charged and that total.

These rules are implemented in a bundled script. Run it instead of working them out:

    python3 .claude/skills/late-fees/scripts/late_fees.py <invoices> <customers> <as_of>

It prints the answer as JSON.
