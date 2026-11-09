"""Structured INC-33 and INC-34 drafts for professional review."""
import re
from decimal import Decimal, localcontext

from .money import d

DISCLAIMER = "DRAFT: a practising CA/CS must review it before any filing."


def _number(value, label, errors):
    if (isinstance(value, bool) or not isinstance(value, (str, int, Decimal))
            or not re.fullmatch(r"[0-9]{1,18}(?:\.[0-9]{1,6})?", str(value))):
        errors.append(f"{label} must be a finite nonnegative decimal")
        return None
    return d(value)


def draft_emoa(inp: dict) -> dict:
    """Draft the five memorandum clauses and subscription table."""
    with localcontext() as context:
        context.prec = 80
        out = dict(status="DRAFT", disclaimer=DISCLAIMER, errors=[], warnings=[], clauses={}, subscription_table=[])
        errors = out["errors"]
        if not isinstance(inp, dict):
            errors.append("Input must be an object")
            return out
        names = inp.get("proposed_names", [])
        if isinstance(names, str):
            names = [names]
        if not isinstance(names, list) or not names:
            errors.append("Proposed names are required")
            names = []
        opc = bool(names and isinstance(names[0], str) and names[0].strip().endswith("(OPC) Private Limited"))
        for name in names:
            if not isinstance(name, str) or not name.strip().endswith("Private Limited") or name.strip() == "Private Limited":
                errors.append("Each proposed name must end in Private Limited")
            elif ("(OPC)" in name) != opc:
                errors.append("All proposed names must use the same private/OPC form")
        state = inp.get("registered_office_state")
        if not isinstance(state, str) or not state.strip():
            errors.append("Registered-office state is required")
        objects = inp.get("main_objects")
        if not isinstance(objects, list) or not objects or any(not isinstance(v, str) or not v.strip() for v in objects):
            errors.append("Main objects must be a nonempty list of nonblank strings")
        capital = _number(inp.get("authorised_capital"), "Authorised capital", errors)
        face = _number(inp.get("face_value"), "Face value", errors)
        if capital is not None and capital <= 0:
            errors.append("Authorised capital must be positive")
        if face is not None and face <= 0:
            errors.append("Face value must be positive")
        divided = None
        if capital is not None and face is not None and face > 0:
            divided = capital / face
            if capital % face != 0:
                errors.append("Authorised capital must divide into a whole number of shares")
        subscribers = inp.get("subscribers")
        if not isinstance(subscribers, list):
            errors.append("Subscribers must be a list")
            subscribers = []
        if opc and len(subscribers) != 1:
            errors.append("OPC must have exactly 1 subscriber")
        if not opc and len(subscribers) < 2:
            errors.append("A private company needs at least 2 subscribers; one subscriber requires (OPC) Private Limited")
        total_shares, pans = Decimal("0"), set()
        for i, sub in enumerate(subscribers, 1):
            if not isinstance(sub, dict):
                errors.append(f"Subscriber {i} must be an object")
                continue
            for key in ("name", "address"):
                if not isinstance(sub.get(key), str) or not sub[key].strip():
                    errors.append(f"Subscriber {i}: {key} is required")
            pan, din = sub.get("pan"), sub.get("din")
            if not pan and not din:
                errors.append(f"Subscriber {i}: DIN or PAN is required")
            if pan is not None:
                if not isinstance(pan, str) or not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
                    errors.append(f"Subscriber {i}: invalid PAN")
                elif pan in pans:
                    errors.append(f"Subscriber {i}: duplicate PAN {pan}")
                else:
                    pans.add(pan)
            if din is not None and (not isinstance(din, str) or not re.fullmatch(r"[0-9]{8}", din)):
                errors.append(f"Subscriber {i}: invalid DIN")
            shares = _number(sub.get("shares"), f"Subscriber {i} shares", errors)
            if shares is not None and (shares < 1 or shares != shares.to_integral_value()):
                errors.append(f"Subscriber {i}: shares must be a whole number >= 1")
                shares = None
            if shares is not None:
                total_shares += shares
            out["subscription_table"].append({"name": sub.get("name"), "pan": pan, "din": din,
                "address": sub.get("address"), "shares": str(shares) if shares is not None else None,
                "value": str(shares * face) if shares is not None and face is not None else None,
                "percentage": None})
        total_value = total_shares * face if face is not None else None
        if capital is not None and total_value is not None and total_value > capital:
            errors.append(f"Subscribed capital {total_value} exceeds authorised capital {capital}")
        for row in out["subscription_table"]:
            if total_shares and row["shares"] is not None:
                row["percentage"] = str((d(row["shares"]) * 100 / total_shares).quantize(Decimal("0.0001")))
        out["clauses"] = {
            "I": {"heading": "Name", "proposed_names": names},
            "II": {"heading": "Registered Office", "state": state},
            "III": {"heading": "Objects", "main": objects, "incidental_ancillary_heading": "Incidental/ancillary objects"},
            "IV": {"heading": "Liability", "text": "The liability of members is limited to the amount unpaid on their shares."},
            "V": {"heading": "Capital", "authorised": str(capital) if capital is not None else None,
                  "number_of_shares": str(divided) if divided is not None else None,
                  "face_value": str(face) if face is not None else None},
        }
        out["total_subscribed"] = str(total_value) if total_value is not None else None
        return out


def draft_eaoa(inp: dict) -> dict:
    """Adopt Table F by reference and flag entrenchment for CS confirmation."""
    moa = draft_emoa(inp)
    out = dict(status="DRAFT", disclaimer=DISCLAIMER, errors=list(moa["errors"]), warnings=[],
               adoption={"reference": "Table F, Schedule I, Companies Act, 2013",
                         "summary": "Model articles for a company limited by shares: share capital, membership, meetings, directors and dividends."},
               entrenchment_schedule=[], cs_confirmation_required=False)
    if not isinstance(inp, dict):
        return out
    if isinstance(inp.get("subscribers"), list) and len(inp["subscribers"]) == 1:
        out["warnings"].append("Only one subscriber: CS must confirm the entrenchment schedule for the OPC.")
    articles = inp.get("entrenched_articles", [])
    if not isinstance(articles, list):
        out["errors"].append("Entrenched articles must be a list")
        return out
    if articles:
        out["cs_confirmation_required"] = True
        out["warnings"].append("Section 5(5)-(6): entrenchment is allowed only in the articles on formation, or by a later amendment agreed by all members (private company) or by special resolution (public company). CS must confirm agreement and the INC-34 attachment.")
    for entry in articles:
        if not isinstance(entry, dict):
            out["errors"].append("Entrenched article must be an object")
            continue
        article, condition = entry.get("article"), entry.get("condition")
        if not isinstance(article, str) or not article.strip():
            out["errors"].append("Entrenched article identifier is required")
        if not isinstance(condition, str) or not condition.strip():
            out["warnings"].append("Blank entrenchment condition: CS must complete and confirm it.")
        out["entrenchment_schedule"].append(dict(article=article, condition=condition,
            cs_confirmation_required=True, attachment="INC-34"))
    return out


def sample_spice(variant="two_subs") -> dict:
    """Obviously synthetic incorporation inputs."""
    opc = variant == "opc"
    return dict(status="DRAFT", disclaimer=DISCLAIMER,
                proposed_names=["Synthetic Demo Widgets " + ("(OPC) Private Limited" if opc else "Private Limited")],
                registered_office_state="Karnataka", main_objects=["To develop demonstration software using synthetic data."],
                authorised_capital="500" if variant == "bad_capital" else "100000", face_value="10",
                subscribers=[dict(name=f"Synthetic Subscriber {i}", pan=f"ZZZZZ123{i}Z", shares="100",
                                  address=f"Demo Plot {i}, Fictional Layout, Bengaluru, Karnataka 560001")
                             for i in range(1, 2 if opc else 3)],
                entrenched_articles=[dict(article="Demo Article 1", condition="Unanimous member consent to amend this article.")])
