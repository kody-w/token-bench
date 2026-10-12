---
name: commission
description: Calculate a sales rep's commission for a quarter under the company commission plan.
---
# Commission

Inputs: sales CSV (date, rep, quarter, customer, type, amount, discount_pct, new_logo, paid_commission).
Use only rows for the rep and quarter. Process rows in date order; rows with the same date keep their order in the file.
1. Tiered rate on the rep's cumulative booked amount in the quarter: 5% on the first 50,000 dollars, 8% from 50,000 dollars to 150,000 dollars, 12% above 150,000 dollars. A deal that crosses a tier boundary is split across tiers.
2. A deal with discount_pct above 20 earns half of its tiered commission.
3. New-logo bonus: 500 dollars for a deal with new_logo = yes, at most once per customer.
4. Refund rows (type = refund) claw back their paid_commission value. Refunds do not reduce booked amount.
5. Quarterly commission is never below 0 dollars and is capped at 40,000 dollars. Do not round individual deals; round only the final amount to the cent.

These rules are implemented in a bundled script. Run it instead of working them out:

    python3 .claude/skills/commission/scripts/commission.py <sales> <rep> <quarter>

It prints the answer as JSON.
