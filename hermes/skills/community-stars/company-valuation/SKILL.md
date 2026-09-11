---
name: company-valuation
description: DCF, relative, and sum-of-parts valuation methods with sensitivity analysis. Use when user asks to value a company, calculate DCF, perform comparable analysis, or estimate company worth.
---

# Company Valuation

Value a company using DCF (Discounted Cash Flow), relative valuation (comps/multiples), and sum-of-parts methods.

## Valuation Methods

### 1. Discounted Cash Flow (DCF)

**Process:**
1. Project free cash flows for 5-7 years
2. Calculate terminal value (Gordon Growth or Exit Multiple)
3. Discount to present value using WACC
4. Add net cash / subtract net debt

**Key Inputs:**
- Revenue growth rate(s)
- Operating margins (EBIT margin)
- Tax rate, D&A, CapEx, change in working capital
- WACC (cost of equity × equity weight + after-tax cost of debt × debt weight)
- Terminal growth rate (typically 2-3%)
- Shares outstanding

**Sensitivity Table:** Show how valuation changes with different growth/WACC assumptions.

### 2. Relative Valuation (Comps)

**Process:**
1. Find comparable public companies
2. Calculate their multiples: P/E, EV/Revenue, EV/EBITDA, P/S, P/B
3. Apply median multiples to target company's financials
4. Adjust for growth, margins, and risk differences

**Standard Multiples:**
| Multiple | When to Use |
|----------|-------------|
| P/E | Profitable, stable growth |
| EV/EBITDA | Capital-intensive, varying D&A |
| EV/Revenue | Pre-profit, high-growth |
| P/S | SaaS, subscription businesses |

### 3. Sum-of-the-Parts

Break the company into business segments, value each separately, then add them up. Useful for conglomerates or companies with a valuable subsidiary.

### 4. Precedent Transactions
Look at what acquirers paid for similar companies (control premium).

## Output Format

Present all three methods with:
1. **Valuation range**: Bull / Base / Bear case
2. **Key assumptions**: Explicitly stated with justification
3. **Sensitivity analysis**: How assumptions affect the result
4. **Recommended valuation**: Method with highest confidence
5. **Risk factors**: What could materially change the valuation
