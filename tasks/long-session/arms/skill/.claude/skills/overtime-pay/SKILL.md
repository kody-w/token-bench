---
name: overtime-pay
description: Calculate an hourly employee's gross pay for a week under the overtime policy.
---
# OvertimePay

Inputs: timesheet CSV (employee, week, date, weekday, hours, holiday) and roster CSV (employee, hourly_rate).
Use only the employee's shifts for the week, in date order.
1. Any shift longer than 6 hours has an unpaid 30-minute break: subtract 0.5 hours.
2. Holiday shifts (holiday = yes) pay 2.5x for all hours and do not count toward weekly hours. A holiday on a Sunday pays the holiday rate.
3. Sunday shifts pay 2x for all hours and do not count toward weekly hours.
4. All other hours accumulate in order across the week: hours up to 40 pay 1x, hours from 40 to 60 pay 1.5x, hours beyond 60 pay 2x. Apply in 15-minute increments.
5. Gross pay = sum of hours x hourly_rate x multiplier. Do not round each shift; round only the total to the cent.
