# ArthaScan Impact Model
**The "Tax/Fee Alpha" Equation**

When presenting ArthaScan to the judges or analyzing its real-world viability, the core value proposition is built on mathematically proving wealth erosion. This model demonstrates exactly how our deterministic engine calculates the "10-Year Wealth Bleed" metric displayed in the app.

---

## 1. The Core Problem: The 1% Invisible Drain
The average retail investor often accidentally purchases **"Regular"** mutual fund plans instead of **"Direct"** plans via third-party brokers or bank managers. 
- **Average Regular Plan Expense Ratio (TER):** ~1.5%
- **Average Direct Plan Expense Ratio (TER):** ~0.5%
- **The Inefficiency:** A 1.0% annual management fee drag that compounds negatively over time.

Because mutual fund statements (like CAMS) are incredibly dense, users do not realize they are paying this 1% premium.

## 2. The Mathematical Impact (User Profile)
To standardize the impact for the hackathon pitch, we assume a standard middle-class retail investor profile.

- **Investment Strategy:** ₹10,000 monthly SIP (Systematic Investment Plan)
- **Time Horizon:** 10 Years
- **Total Principal Invested:** ₹12,00,000
- **Assumed Market Return:** 12% annualized (Historical NIFTY 50 average)

### The Math (Calculated deterministically in `metrics.py`)
If the user holds the **Regular Plan (1.5% TER)**, their effective net return drops to **10.5%**.
- *Future Value (10 Years @ 10.5%):* **₹20.6 Lakhs**

If ArthaScan intercepts this and advises a switch to the **Direct Plan (0.5% TER)**, their effective net return becomes **11.5%**.
- *Future Value (10 Years @ 11.5%):* **₹23.1 Lakhs**

## 3. The Pitch Metric
> **The Difference:** ₹23.1 Lakhs - ₹20.6 Lakhs = **₹2.5 Lakhs**

By simply uploading a PDF into Telegram, ArthaScan's deterministic engine identifies the `1.5% TER` tag, calculates the compounding drag against a `0.5%` index baseline, and instantly generates a `SWITCH` command. 

**ArthaScan finds the hidden 1% and returns ₹2.5 Lakhs directly to the user's retirement fund.** 

*(Note: This does not even factor in the additional lakhs saved by the engine catching and consolidating >60% overlapping duplicate funds, which further eliminates redundant management fees).*
