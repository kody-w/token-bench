---
name: double-paid
description: Find invoices that were paid more than once and the total overpaid, from an invoices CSV and a payments CSV.
---
# DoublePaid

Inputs: invoices CSV (invoice_id, customer_id, amount) and payments CSV (payment_id, invoice_id, amount).
1. Count payments per invoice_id.
2. An invoice with more than one payment was double-paid.
3. Overpaid for that invoice = (payments - 1) x the invoice amount from the invoices file.
4. Report the number of double-paid invoices and the total overpaid, rounded to the cent.

These rules are implemented in a bundled script. Run it instead of working them out:

    python3 .github/skills/double-paid/scripts/double_paid.py <invoices> <payments>

It prints the answer as JSON.
