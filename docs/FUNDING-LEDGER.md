# Funding ledger

Every donation received and every expense paid from project funds is recorded
here. The tables are empty because no funds have been received yet. An entry is
added when a payout clears, not when a pledge is made.

Related: [Support and funding](SUPPORT-AND-FUNDING.md),
[Support](../SUPPORT.md).

## Policy

- Amounts are reported in the currency received and the currency spent.
- Payment-processor fees are listed separately, so gross and net are both
  visible.
- Donor identities are never published without permission. Recurring sponsors
  are named only if they ask to be.
- Hardware bought with project funds belongs to the project and is listed with
  its purchase date and purpose.
- A negative balance is published as clearly as a positive one. Money is not
  moved between categories to hide a shortfall.

## Income

| Date | Channel | Gross | Fees | Net | Note |
| --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | No funds received yet |

## Expenses

| Date | Item | Amount | Paid from | Purpose |
| --- | --- | --- | --- | --- |
| — | — | — | — | — |

## Balance

| Date | Balance | Note |
| --- | --- | --- |
| — | 0.00 | Opening balance |

## How to update this file

1. Add the payout or purchase as one row. Do not combine several transactions.
2. Put the processor fee in its own column entry, not inside the net amount.
3. Keep the balance table in step with the two tables above; the newest row
   goes at the bottom.
4. Commit the change with `docs(funding): record <month>` so the history of the
   ledger is auditable in the same way as the rest of the repository.
