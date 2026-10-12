---
name: reorder
description: Decide whether a SKU needs reordering and how many units to order, under the replenishment policy.
---
# Reorder

Inputs: demand CSV (sku, date, units, in date order) and inventory CSV (sku, on_hand, on_order, lead_time_days, moq, case_pack).
1. Use the SKU's last 28 demand rows. avg = mean units per day; sd = population standard deviation.
2. Reorder point = avg x lead_time_days + 1.65 x sd x sqrt(lead_time_days).
3. Position = on_hand + on_order. If position is above the reorder point, do not reorder (order 0).
4. Otherwise target = reorder point + 14 days of avg demand. Need = max(target - position, moq).
5. Round need UP to a whole number of case packs. Report reorder yes/no and the order quantity.
