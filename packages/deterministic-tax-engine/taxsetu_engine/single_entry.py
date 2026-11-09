"""Cash-book conversion to double-entry drafts. No posting or I/O."""
import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .money import d, r2
from .se_rules import ASSETS, LIABILITIES, ADJUSTMENTS, CAPITAL, INCOME, classify, valid_head
from .tally_models import LedgerSpec, Line, VoucherDraft

ZERO = Decimal("0.00")


def _amount(value, signed=False):
    try:
        amount = d(("" if value is None else str(value)).replace(",", "").strip() or "0")      # blank cell = zero
        return r2(amount) if amount.is_finite() and (signed or amount >= 0) else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _date(value):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%y", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _money(value):
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, dict):
        return {k: _money(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_money(v) for v in value]
    return value


def convert(book: dict) -> dict:
    """Return balanced journals, statements and independent net-worth checks."""
    errors, warnings, questions, journal = [], [], [], []
    result = {"entity_type": "", "name": "", "period": {"start": "", "end": ""}, "journal": journal,
              "trial_balance": {"rows": [], "total_debit": ZERO, "total_credit": ZERO, "balanced": True},
              "ledgers": {}, "statements": {}, "crosscheck": {},
              "counts": {"entries": 0, "classified": 0, "needs_review": 0, "excluded": 0},
              "questions": questions, "warnings": warnings, "errors": errors}
    if not isinstance(book, dict):
        errors.append("Book must be an object.")
        return _money(result)
    entity = book.get("entity_type")
    if not isinstance(entity, str) or entity not in CAPITAL:
        errors.append("Unknown entity_type; use business, individual or nonprofit.")
        return _money(result)
    start, end = _date(book.get("period_start")), _date(book.get("period_end"))
    result.update(entity_type=entity, name=str(book.get("name") or ""), period={"start": start or "", "end": end or ""})
    if not start or not end or start > end:
        errors.append("Invalid period_start/period_end.")
        return _money(result)
    capital = CAPITAL[entity]
    counts = result["counts"]
    def mapping(value, label):
        if value is None:
            return {}
        if not isinstance(value, dict):
            errors.append(label + " must be an object.")
            return {}
        return value
    def amount(value, label):
        parsed = _amount(value)
        if parsed is None:
            errors.append(label + ": invalid non-negative amount.")
            return ZERO
        return parsed
    opening_raw = mapping(book.get("opening"), "opening")
    closing_raw = mapping(book.get("closing"), "closing")
    opening, closing = {}, {}
    for raw, target, label in ((opening_raw, opening, "opening"), (closing_raw, closing, "closing")):
        for key in sorted(ASSETS.keys() | LIABILITIES.keys() | {"discount_allowed", "discount_received", "bad_debts", "sales_returns", "purchase_returns"}):
            if key in ADJUSTMENTS:
                heads = mapping(raw.get(key), label + "." + key)
                target[key] = {}
                for head in sorted(heads, key=str):
                    if not valid_head(head):
                        errors.append(label + "." + key + ": invalid head " + str(head))
                        continue
                    target[key][head] = amount(heads[head], label + "." + key + "." + head)
            else:
                target[key] = amount(raw.get(key, "0"), label + "." + key)
    def total(values, key):
        return sum(values[key].values(), ZERO) if key in ADJUSTMENTS else values[key]
    opening_assets = {ledger: total(opening, key) for key, ledger in ASSETS.items()}
    opening_liabilities = {ledger: total(opening, key) for key, ledger in LIABILITIES.items()}
    opening_capital = sum(opening_assets.values(), ZERO) - sum(opening_liabilities.values(), ZERO)
    if opening_raw.get("capital") is not None:
        supplied = _amount(opening_raw["capital"], signed=True)
        if supplied is None:
            errors.append("opening.capital: invalid amount.")
            supplied = ZERO
        if supplied != opening_capital:
            warnings.append(f"Opening capital supplied {supplied:.2f} differs from statement of affairs {opening_capital:.2f}; using the balancing figure.")
    balances, totals = {}, {}
    income_heads, expense_heads = set(), set()
    def post(when, narration, source, lines, flags=(), confidence=1, category=""):
        clean = []
        for ledger, value in lines:
            if not value:
                continue
            clean.append({"ledger": ledger, "amount": abs(value), "side": "Dr" if value > 0 else "Cr"})
            balances[ledger] = balances.get(ledger, ZERO) + value
            dr, cr = totals.setdefault(ledger, [ZERO, ZERO])
            totals[ledger] = [dr + max(value, ZERO), cr + max(-value, ZERO)]
        if clean:
            item = {"date": when, "narration": narration, "source": source, "lines": clean,
                    "flags": list(flags), "confidence": confidence}
            if category:
                item["category"] = category
            journal.append(item)
    post(start, "Opening statement of affairs", "opening",
         list(opening_assets.items()) + [(k, -v) for k, v in opening_liabilities.items()] + [(capital, -opening_capital)])
    entries = book.get("entries", [])
    if not isinstance(entries, list):
        errors.append("entries must be a list.")
        entries = []
    counts["entries"] = len(entries)
    validated = []
    for number, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            errors.append(f"Entry {number}: must be an object.")
            counts["excluded"] += 1
            continue
        receipt, payment = _amount(entry.get("receipt") or "0"), _amount(entry.get("payment") or "0")      # a blank spreadsheet cell means zero
        when, mode = _date(entry.get("date")), str(entry.get("mode", "cash")).lower()
        if receipt is None or payment is None or bool(receipt) == bool(payment) or not when or mode not in {"cash", "bank"}:
            errors.append(f"Entry {number}: invalid date, mode or receipt/payment (exactly one must be positive).")
            counts["excluded"] += 1
            continue
        if not start <= when <= end:
            warnings.append(f"Entry {number}: date outside the period; excluded.")
            counts["excluded"] += 1
            continue
        category, ledger, confidence, reason = classify(entry, entity, bool(receipt))
        flags = ["NEEDS_REVIEW"] if reason else []
        if reason:
            questions.append(f"Entry {number}: {reason}")
            counts["needs_review"] += 1
        counts["classified"] += 1
        validated.append({"number": number, "entry": entry, "date": when, "mode": mode.title(), "incoming": bool(receipt),
                          "amount": receipt or payment, "category": category, "ledger": ledger,
                          "confidence": confidence, "flags": flags})
    # Direct arithmetic uses validated cash-book rows, never journal lines or ledger balances.
    direct = {**opening_assets, **{k: -v for k, v in opening_liabilities.items()}}
    movements = {}
    receipts, payments = {}, {}
    introduced = corpus = drawings = ZERO
    ignored = set()
    for i, row in enumerate(validated):
        if i in ignored:
            continue
        category, ledger, value = row["category"], row["ledger"], row["amount"]
        incoming, mode = row["incoming"], row["mode"]
        signed = value if incoming else -value
        counter = -signed
        if category == "contra":
            ledger = "Bank" if mode == "Cash" else "Cash"
            twin = next((j for j in range(i + 1, len(validated)) if j not in ignored and
                         validated[j]["category"] == "contra" and validated[j]["date"] == row["date"] and
                         validated[j]["amount"] == value and validated[j]["mode"] != mode and
                         validated[j]["incoming"] != incoming), None)
            if twin is not None:
                ignored.add(twin)
            else:
                warnings.append(f"Entry {row['number']}: unmatched contra; posted once with both cash/bank sides.")
            direct[ledger] += counter
        else:
            movements[category] = movements.get(category, ZERO) + value
            cash_heads = receipts if incoming else payments
            cash_heads[ledger] = cash_heads.get(ledger, ZERO) + value
            if ledger in direct:
                direct[ledger] += counter
            if category == "capital_introduced":
                introduced += value
            elif category == "corpus_donation":
                corpus += value
            elif category == "drawings":
                drawings += value
            elif category == "asset_sale":
                warnings.append(f"Entry {row['number']}: asset sale treated at cost; what is the profit/loss on sale?")
            elif ledger not in set(ASSETS.values()) | set(LIABILITIES.values()) | {capital, "Drawings", "Purchases", "Sales"}:
                (income_heads if incoming else expense_heads).add(ledger)
        direct[mode] += signed
        post(row["date"], str(row["entry"].get("description") or ""), "cash_book", [(ledger, counter), (mode, signed)],
             row["flags"], row["confidence"], category)
    if entity == "business":
        for key, movement, question in (("debtors", "debtor_receipt", "What do customers still owe you at the end of the period?"),
                                        ("creditors", "creditor_payment", "What do you still owe suppliers at the end of the period?")):
            if key not in closing_raw:
                closing[key] = opening[key]
                if opening[key] or movements.get(movement, ZERO):
                    questions.append(question)
                    warnings.append("Missing closing " + key + "; assumed equal to opening.")
        credit_sales = closing["debtors"] + movements.get("debtor_receipt", ZERO) + sum(closing[k] for k in ("discount_allowed", "bad_debts", "sales_returns")) - opening["debtors"]
        credit_purchases = closing["creditors"] + movements.get("creditor_payment", ZERO) + closing["discount_received"] + closing["purchase_returns"] - opening["creditors"]
        for label, value, debit, credit in (("credit sales", credit_sales, "Debtors", "Sales"), ("credit purchases", credit_purchases, "Purchases", "Creditors")):
            if value < 0:
                questions.append("ERROR: inconsistent figures produce negative " + label + "; please correct the opening/closing balances.")
            else:
                post(end, "Derived " + label, "derived", [(debit, value), (credit, -value)])
        for key, debit, credit in (("discount_allowed", "Discount Allowed", "Debtors"), ("bad_debts", "Bad Debts", "Debtors"),
                                   ("discount_received", "Creditors", "Discount Received"), ("sales_returns", "Sales Returns", "Debtors"),
                                   ("purchase_returns", "Creditors", "Purchase Returns")):
            post(end, key.replace("_", " "), "derived", [(debit, closing[key]), (credit, -closing[key])])
        expense_heads |= {"Discount Allowed", "Bad Debts"}
        income_heads.add("Discount Received")
        direct["Debtors"], direct["Creditors"] = closing["debtors"], -closing["creditors"]
        if "stock" not in closing_raw:
            questions.append("What is the value of unsold stock at the end of the period?")
            warnings.append("Missing closing stock treated as 0; gross profit is unreliable.")
        direct["Stock-in-Trade"] = closing["stock"]
    else:
        for key in ("debtors", "creditors", "stock"):
            if key in closing_raw:
                direct[(ASSETS | LIABILITIES)[key]] = closing[key] * (-1 if key == "creditors" else 1)
    for key in ADJUSTMENTS:
        aggregate = (ASSETS | LIABILITIES)[key]
        asset = key in ASSETS
        for values, reverse in ((opening, True), (closing, False)):
            for head, value in sorted(values[key].items()):
                (expense_heads if key in {"outstanding_expenses", "prepaid_expenses"} else income_heads).add(head)
                sign = (1 if asset else -1) * (-1 if reverse else 1)
                post(end, ("Reverse opening " if reverse else "Closing ") + key + ": " + head, "adjustment",
                     [(aggregate, value * sign), (head, -value * sign)])
        direct[aggregate] = total(closing, key) * (1 if asset else -1)
    depreciation = ZERO
    if closing_raw.get("depreciation") is not None:
        depreciation = amount(closing_raw["depreciation"], "closing.depreciation")
    elif closing_raw.get("depreciation_rate") is not None:
        rate = amount(closing_raw["depreciation_rate"], "closing.depreciation_rate")
        try:
            depreciation = r2((opening["fixed_assets"] + movements.get("asset_purchase", ZERO)) * rate / 100)
        except InvalidOperation:
            errors.append("Invalid depreciation calculation.")
        warnings.append("additions depreciated for a full year")
    post(end, "Depreciation", "adjustment", [("Depreciation", depreciation), ("Fixed Assets", -depreciation)])
    expense_heads.add("Depreciation")
    direct["Fixed Assets"] -= depreciation
    rows = [{"ledger": ledger, "debit": max(value, ZERO), "credit": max(-value, ZERO)} for ledger, value in sorted(balances.items()) if value]
    debit, credit = sum((r["debit"] for r in rows), ZERO), sum((r["credit"] for r in rows), ZERO)
    result["trial_balance"] = {"rows": rows, "total_debit": debit, "total_credit": credit, "balanced": debit == credit}
    expenses = {h: balances[h] for h in sorted(expense_heads) if balances.get(h)}
    incomes = {h: -balances[h] for h in sorted(income_heads) if balances.get(h)}
    total_expenses, total_income = sum(expenses.values(), ZERO), sum(incomes.values(), ZERO)
    statements = result["statements"]
    gross = ZERO
    if entity == "business":
        sales, purchases = -balances.get("Sales", ZERO), balances.get("Purchases", ZERO)
        sales_returns, purchase_returns = balances.get("Sales Returns", ZERO), -balances.get("Purchase Returns", ZERO)
        net_sales, net_purchases = sales - sales_returns, purchases - purchase_returns
        cost = opening["stock"] + net_purchases - closing["stock"]
        gross = net_sales - cost
        statements["trading"] = {"sales": sales, "sales_returns": sales_returns, "net_sales": net_sales,
                                 "opening_stock": opening["stock"], "purchases": purchases, "purchase_returns": purchase_returns,
                                 "net_purchases": net_purchases, "closing_stock": closing["stock"], "cost_of_goods_sold": cost, "gross_profit": gross}
        statements["profit_loss"] = {"gross_profit": gross, "other_income": incomes, "expenses": expenses,
                                     "total_other_income": total_income, "total_expenses": total_expenses, "net_profit": gross + total_income - total_expenses}
        post(end, "Opening stock to trading", "closing", [("Trading A/c", opening["stock"]), ("Stock-in-Trade", -opening["stock"])])
        post(end, "Closing stock", "closing", [("Stock-in-Trade", closing["stock"]), ("Trading A/c", -closing["stock"])])
        for head in ("Sales", "Sales Returns", "Purchases", "Purchase Returns"):
            value = balances.get(head, ZERO)
            post(end, "Close " + head, "closing", [(head, -value), ("Trading A/c", value)])
        value = balances.get("Trading A/c", ZERO)
        post(end, "Gross profit/loss", "closing", [("Trading A/c", -value), ("Profit & Loss A/c", value)])
    profit = gross + total_income - total_expenses
    summary_head = "Profit & Loss A/c" if entity == "business" else "Income & Expenditure A/c"
    for head in sorted(expense_heads | income_heads):
        value = balances.get(head, ZERO)
        post(end, "Close " + head, "closing", [(head, -value), (summary_head, value)])
    value = balances.get(summary_head, ZERO)
    post(end, "Transfer profit/surplus/savings", "closing", [(summary_head, -value), (capital, value)])
    if entity == "business":
        post(end, "Transfer drawings", "closing", [(capital, drawings), ("Drawings", -drawings)])
    assets = {h: balances[h] for h in ASSETS.values() if balances.get(h)}
    liabilities = {h: -balances[h] for h in LIABILITIES.values() if balances.get(h)}
    closing_capital = -balances.get(capital, ZERO)
    asset_total, liability_total = sum(assets.values(), ZERO), sum(liabilities.values(), ZERO)
    sheet = {"assets": assets, "liabilities": liabilities, "total_assets": asset_total,
             "total_liabilities_and_capital": liability_total + closing_capital, "balanced": asset_total == liability_total + closing_capital}
    if entity == "business":
        sheet["capital"] = {"opening": opening_capital, "introduced": introduced, "net_profit": profit, "drawings": drawings, "closing": closing_capital}
    elif entity == "nonprofit":
        sheet["capital_fund"] = {"opening": opening_capital, "surplus": profit, "corpus": corpus, "closing": closing_capital}
        cash_open = {k: opening[k] for k in ("cash", "bank")}
        cash_close = {k: direct[k.title()] for k in ("cash", "bank")}
        rp_receipts = sum(cash_open.values(), ZERO) + sum(receipts.values(), ZERO)
        rp_payments = sum(payments.values(), ZERO) + sum(cash_close.values(), ZERO)
        statements["receipts_payments"] = {"opening": cash_open, "receipts": dict(sorted(receipts.items())), "payments": dict(sorted(payments.items())),
                                           "closing": cash_close, "total_receipts": rp_receipts, "total_payments": rp_payments, "balanced": rp_receipts == rp_payments}
        statements["income_expenditure"] = {"income": incomes, "expenditure": expenses, "total_income": total_income, "total_expenditure": total_expenses, "surplus": profit}
    else:
        sheet["capital"] = {"ledger": "Net Worth", "opening": opening_capital, "savings": profit, "closing": closing_capital}
        statements["income_expense"] = {"income": incomes, "expenses": expenses, "total_income": total_income, "total_expenses": total_expenses, "savings": profit}
        gain = ZERO
        if closing_raw.get("investments_market_value") is not None:
            gain = amount(closing_raw["investments_market_value"], "closing.investments_market_value") - assets.get("Investments", ZERO)
        market_assets = dict(assets)
        if gain or "Investments" in assets:
            market_assets["Investments"] = assets.get("Investments", ZERO) + gain
        statements["net_worth"] = {
            "opening": {"assets": opening_assets, "liabilities": opening_liabilities, "net_worth": opening_capital},
            "closing_at_cost": {"assets": assets, "liabilities": liabilities, "net_worth": closing_capital},
            "closing_at_market": {"assets": market_assets, "liabilities": liabilities, "net_worth": closing_capital + gain, "unrealised_gain": gain}}
    statements["balance_sheet"] = sheet
    direct_net = sum(direct.values(), ZERO)
    direct_profit = direct_net - opening_capital - introduced - corpus + drawings
    result["crosscheck"] = {"method": "statement_of_affairs", "closing_net_worth_direct": direct_net,
                            "closing_net_worth_from_books": closing_capital, "profit_by_books": profit,
                            "profit_by_net_worth_change": direct_profit, "agrees": direct_net == closing_capital and direct_profit == profit}
    result["ledgers"] = {h: {"debit": totals[h][0], "credit": totals[h][1], "balance": abs(value), "side": "Dr" if value > 0 else "Cr" if value < 0 else ""}
                         for h, value in sorted(balances.items())}
    priority = {"opening": 0, "cash_book": 1, "derived": 2, "adjustment": 3, "closing": 4}
    journal.sort(key=lambda item: (item["date"], priority[item["source"]]))
    return _money(result)


def parse_cash_book_csv(text: str) -> dict:
    """Find a header, skip junk/totals, return dated entry strings."""
    result = {"entries": [], "errors": [], "skipped": 0}
    if not isinstance(text, str):
        result["errors"].append("CSV must be text.")
        return result
    aliases = {"date": {"date"}, "description": {"description", "particulars", "narration", "details"},
               "receipt": {"receipt", "in", "received", "credit", "deposit"}, "payment": {"payment", "out", "paid", "debit", "withdrawal"},
               "mode": {"mode", "type", "cash/bank"}, "party": {"party", "name"}, "hint": {"hint"}, "amount": {"amount", "signed amount"}}
    header = None
    try:
        for number, row in enumerate(csv.reader(io.StringIO(text.lstrip("\ufeff"))), 1):
            labels = [s.strip().lower() for s in row]
            if header is None:
                found = {key: i for key, names in aliases.items() for i, label in enumerate(labels) if label.rstrip("s") in names or label in names}
                if "date" in found and "description" in found and ("amount" in found or "receipt" in found or "payment" in found):
                    header = found
                else:
                    result["skipped"] += 1
                continue
            if not any(labels) or any(s.startswith(("total", "grand total", "closing balance")) for s in labels):
                result["skipped"] += 1
                continue
            entry = {key: row[i].strip() if i < len(row) else "" for key, i in header.items()}
            when = _date(entry.get("date"))
            if not when:
                result["errors"].append(f"CSV row {number}: invalid date.")
                result["skipped"] += 1
                continue
            entry["date"] = when
            entry["mode"] = entry.get("mode") or "cash"
            if "amount" in entry:
                signed = entry.pop("amount")
                value = _amount(signed[1:] if signed.startswith(("-", "+")) else signed)
                if value is None or not value:
                    result["errors"].append(f"CSV row {number}: invalid amount.")
                    result["skipped"] += 1
                    continue
                entry["payment" if signed.startswith("-") else "receipt"] = format(value, ".2f")
            for key in ("receipt", "payment"):
                entry[key] = entry.get(key) or "0"
            a, b = _amount(entry["receipt"]), _amount(entry["payment"])
            if a is None or b is None or bool(a) == bool(b):
                result["errors"].append(f"CSV row {number}: invalid receipt/payment.")
                result["skipped"] += 1
                continue
            result["entries"].append(entry)
    except csv.Error as exc:
        result["errors"].append("Invalid CSV: " + str(exc))
    if header is None:
        result["errors"].append("Cash-book header not found.")
    return result


def to_tally(result: dict) -> dict:
    """Build draft masters/vouchers only; omit closing transfers."""
    output = {"ledgers": [], "vouchers": []}
    if not isinstance(result, dict) or not isinstance(result.get("journal"), list):
        return output
    groups = {"Cash": "Cash-in-Hand", "Bank": "Bank Accounts", "Debtors": "Sundry Debtors", "Creditors": "Sundry Creditors",
              "Stock-in-Trade": "Current Assets",   # verified on real TallyPrime 7.2: a ledger under Stock-in-Hand cannot be used in an ordinary voucher "Fixed Assets": "Fixed Assets", "Investments": "Investments",
              "Prepaid Expenses": "Current Assets", "Accrued Income": "Current Assets", "Loans": "Loans (Liability)",
              "Outstanding Expenses": "Current Liabilities", "Income Received in Advance": "Current Liabilities",
              **{h: "Capital Account" for h in ("Capital", "Drawings", "Net Worth", "Capital Fund")},
              "Sales": "Sales Accounts", "Sales Returns": "Sales Accounts", "Purchases": "Purchase Accounts", "Purchase Returns": "Purchase Accounts"}
    incomes = set(INCOME.values()) | {"Discount Received"}
    for item in result["journal"]:
        if not isinstance(item, dict) or item.get("source") not in {"opening", "cash_book", "derived", "adjustment"}:
            continue
        try:
            lines = tuple(Line(l["ledger"], d(l["amount"]), l["side"]) for l in item["lines"])
            if any(not isinstance(l.ledger, str) or not l.ledger or not l.amount.is_finite() or l.amount <= 0 or l.side not in {"Dr", "Cr"} for l in lines):
                continue
            money = [l for l in lines if l.ledger in {"Cash", "Bank"}]
            vtype = "Journal"
            if item["source"] == "cash_book" and len(money) == 2:
                vtype = "Contra"
            elif item["source"] == "cash_book" and len(money) == 1:
                vtype = "Receipt" if money[0].side == "Dr" else "Payment"
                lines = tuple(l for l in lines if l not in money) + tuple(money)
            voucher = VoucherDraft(vtype, date.fromisoformat(item["date"]), lines, narration=str(item.get("narration", "")),
                                   party=lines[0].ledger if vtype in {"Receipt", "Payment"} else "",
                                   confidence=d(item.get("confidence", 1)), flags=tuple(item.get("flags", ())))
            if voucher.balanced():
                output["vouchers"].append(voucher)
        except (KeyError, TypeError, ValueError, InvalidOperation, AttributeError):
            continue
    for section, key in (("profit_loss", "other_income"), ("income_expenditure", "income"), ("income_expense", "income")):
        statements = result.get("statements", {})
        if isinstance(statements, dict) and isinstance(statements.get(section), dict):
            incomes.update(statements[section].get(key, {}))
    names = {l.ledger for v in output["vouchers"] for l in v.lines}
    output["ledgers"] = [LedgerSpec(h, groups.get(h, "Indirect Incomes" if h in incomes else "Indirect Expenses")) for h in sorted(names)]
    return output
