"""Local Tally transport for human-approved drafts. Python 3.10+, stdlib only."""
import argparse
import csv
import hashlib
import hmac
import io
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape


MAX_XML = 2 * 1024 * 1024
DEFAULT_CONFIG = Path.home() / ".taxsetu-bridge.json"
NETWORK_ERRORS = (OSError, urllib.error.URLError)
CLOUD_TIMEOUT, TALLY_TIMEOUT = 60, 600      # a 500-voucher import took 22 s to create and 43 s to re-send on a fast PC; a slow accounts PC needs headroom


def private_file(path):
    """Restrict local secrets to the current account where supported."""
    if os.name == "nt":
        try:
            identity = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True, stderr=subprocess.PIPE)
            sid = next(csv.reader(io.StringIO(identity.strip())))[1]
            subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
                           check=True, capture_output=True)
        except (OSError, subprocess.SubprocessError, IndexError, StopIteration):
            warnings.warn("Windows could not restrict file permissions; keep bridge files in a private user folder.")
    else:
        os.chmod(path, 0o600)


def save_json(path, value):
    """Replace atomically, flushing before any external side effect."""
    path = Path(path)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        private_file(name)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = None
            json.dump(value, stream, ensure_ascii=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if fd is not None:
            os.close(fd)
        if os.path.exists(name):
            os.unlink(name)


class Redact(logging.Filter):
    def __init__(self, config):
        super().__init__()
        self.secrets = [config.get(k) for k in ("bridge_token", "signing_key") if config.get(k)]

    def filter(self, record):
        message = record.getMessage()
        for secret in self.secrets:
            message = message.replace(secret, "[REDACTED]")
        record.msg, record.args = message, ()
        record.exc_info, record.exc_text = None, None
        return True


def setup_log(path, config):
    logger = logging.getLogger("tally-bridge")
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in (logging.StreamHandler(), RotatingFileHandler(path, maxBytes=1024 * 1024, backupCount=1,
                                                               encoding="utf-8")):
        handler.addFilter(Redact(config))
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    private_file(path)
    return logger


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, data=None, token="", xml=False):
    headers = {"Content-Type": "text/xml; charset=utf-8" if xml else "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = data if xml or data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers)
    # No redirects or environment proxies for the local Tally connection.
    handlers = [NoRedirect()]
    if xml:
        handlers.append(urllib.request.ProxyHandler({}))
    with urllib.request.build_opener(*handlers).open(req, timeout=TALLY_TIMEOUT if xml else CLOUD_TIMEOUT) as response:
        raw = response.read(MAX_XML + 1)
    if len(raw) > MAX_XML:
        raise ValueError("Response exceeds 2 MB")
    return raw.decode("utf-8", errors="replace") if xml else (json.loads(raw) if raw else {})


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    config = {"tally_url": "http://127.0.0.1:9000", "poll_seconds": 15, "dry_run": False, **config}
    for key in ("api_base", "bridge_token", "signing_key", "company", "tally_url"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError("Missing configuration field: " + key)
    for key in ("api_base", "tally_url"):
        url = urllib.parse.urlsplit(config[key])
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Invalid URL in " + key)
    seconds = config["poll_seconds"]
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("poll_seconds must be positive")
    if not isinstance(config["dry_run"], bool):
        raise ValueError("dry_run must be true or false")
    return config


_XML_REF = re.compile(r"&#(x[0-9a-fA-F]+|[0-9]+);")


def _drop_illegal_refs(text):
    """Real TallyPrime writes character references such as &#4; that XML 1.0 forbids; a strict parser rejects the whole reply. Drop only those."""
    def keep(m):
        ref = m.group(1)
        code = int(ref[1:], 16) if ref[0] == "x" else int(ref)
        ok = code in (9, 10, 13) or 0x20 <= code <= 0xD7FF or 0xE000 <= code <= 0xFFFD or 0x10000 <= code <= 0x10FFFF
        return m.group(0) if ok else ""
    return _XML_REF.sub(keep, text)


IMPORT_REQUESTS = ("import", "import data")      # the classic envelope says "Import Data"; the newer HEADER style says "Import"


def safe_xml(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_XML:
        raise ValueError("XML exceeds 2 MB or is not text")
    if "\x00" in text or re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I):
        raise ValueError("DOCTYPE and ENTITY are forbidden")
    root = ET.fromstring(_drop_illegal_refs(text))
    for element in root.iter():
        element.tag = element.tag.upper()
        element.attrib = {key.upper(): value for key, value in element.attrib.items()}
    return root


def verify_item(item, config):
    """Return a refusal reason; document contents never become instructions."""
    try:
        xml = item.get("xml")
        if not isinstance(xml, str) or len(xml.encode("utf-8")) > MAX_XML:
            return "XML exceeds 2 MB or is not text"
        digest = hashlib.sha256(xml.encode("utf-8")).hexdigest()
        if item.get("sha256") != digest:
            return "XML SHA-256 mismatch"
        signature = hmac.new(config["signing_key"].encode("utf-8"), digest.encode("ascii"), hashlib.sha256).hexdigest()
        if not isinstance(item.get("sig"), str) or not hmac.compare_digest(signature, item["sig"]):
            return "Invalid signature"
        root = safe_xml(xml)
        requests = root.findall(".//TALLYREQUEST")
        if root.tag != "ENVELOPE" or root.findtext("HEADER/TALLYREQUEST", "").strip().lower() not in IMPORT_REQUESTS:
            return "Only an ENVELOPE Import request is allowed"
        if any((e.text or "").strip().lower() not in IMPORT_REQUESTS for e in requests):
            return "Delete, Cancel, Execute and other requests are forbidden"
        reports = root.findall(".//REPORTNAME") + root.findall("HEADER/ID")
        if not reports or any((e.text or "").strip().lower() not in ("vouchers", "all masters") for e in reports):
            return "Only Vouchers or All Masters may be imported"
        for element in root.iter():
            action = element.attrib.get("ACTION")
            if (action is not None and action.strip().lower() not in ("create", "alter")) or (
                    element.tag == "ACTION" and (element.text or "").strip().lower() not in ("create", "alter")):
                return "Only Create or Alter actions are allowed"
            if element.tag == "VOUCHER" and not element.get("VCHTYPE", "").strip():
                return "Every VOUCHER needs VCHTYPE"
        companies = root.findall(".//SVCURRENTCOMPANY")
        scoped = (root.findall("BODY/IMPORTDATA/REQUESTDESC/STATICVARIABLES/SVCURRENTCOMPANY") +
                  root.findall("BODY/DESC/STATICVARIABLES/SVCURRENTCOMPANY"))
        if not scoped or any(e.text != config["company"] for e in companies):
            return "SVCURRENTCOMPANY must match the paired company"
    except (ValueError, TypeError, AttributeError, ET.ParseError, UnicodeError):
        return "Malformed XML or item"
    return ""


def parse_reply(raw):
    """Read import counters or Tally's failure envelope."""
    result = {"ok": False, "created": 0, "altered": 0, "errors": []}
    try:
        root = safe_xml(raw)
        lines = [(e.text or "").strip() for e in root.findall(".//LINEERROR") if (e.text or "").strip()]
        if root.findtext("HEADER/STATUS", "").strip() == "0":
            for status in root.findall("BODY/DATA/STATUS.LIST/STATUS"):
                lines.append(": ".join(s for s in (status.findtext("CODE", ""), status.findtext("DESC", "")) if s))
            result["errors"] = lines or ["Tally rejected the import"]
            return result
        response = root if root.tag in ("RESPONSE", "IMPORTRESULT") else root.find(".//RESPONSE")
        if response is None:
            response = root.find(".//IMPORTRESULT")
        if response is None and root.findtext("HEADER/STATUS", "").strip() == "1" and not lines:
            result["ok"] = True          # Tally's documented success envelope carries no counters; a false failure would invite a duplicate re-send
            return result
        if response is None:
            result["errors"] = lines or ["Tally returned no import counters"]
            return result
        counters = {}
        for key in ("CREATED", "ALTERED", "ERRORS", "EXCEPTIONS"):
            value = response.findtext(key)
            if value is None and key == "EXCEPTIONS":
                value = "0"                                  # older Tally versions do not send it
            if value is None or not value.strip().isascii() or not value.strip().isdigit():
                raise ValueError("Invalid import counter")
            counters[key] = int(value)
        result.update(created=counters["CREATED"], altered=counters["ALTERED"])
        if counters["ERRORS"] or counters["EXCEPTIONS"]:
            lines = lines or [f"Tally reported {counters['ERRORS']} errors and {counters['EXCEPTIONS']} exceptions"]
        if not lines and counters["CREATED"] + counters["ALTERED"] == 0:
            lines = ["Tally accepted the request but created nothing (already entered?); check the books before retrying"]
        result.update(ok=not lines, errors=lines)
    except (ValueError, TypeError, ET.ParseError, UnicodeError):
        result["errors"] = ["Malformed Tally reply"]
    return result


def export_xml(collection, company=""):
    return ("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>"
            f"<TYPE>Collection</TYPE><ID>{collection}</ID></HEADER><BODY><DESC><STATICVARIABLES>"
            f"<SVCURRENTCOMPANY>{escape(company)}</SVCURRENTCOMPANY></STATICVARIABLES>"
            "<FETCHLIST><FETCH>Name</FETCH><FETCH>Parent</FETCH><FETCH>PartyGSTIN</FETCH></FETCHLIST>"
            "</DESC></BODY></ENVELOPE>").encode("utf-8")


def ledgers_xml(company):
    return ("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>List of Accounts</ID></HEADER>"
            f"<BODY><DESC><STATICVARIABLES><SVCURRENTCOMPANY>{escape(company)}</SVCURRENTCOMPANY>"
            "<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT><ACCOUNTTYPE>Ledgers</ACCOUNTTYPE></STATICVARIABLES></DESC></BODY></ENVELOPE>").encode("utf-8")


def sync_ledgers(config, log):
    try:
        root = safe_xml(request(config["tally_url"], ledgers_xml(config["company"]), xml=True))
        if root.findtext("HEADER/STATUS", "").strip() == "0":
            raise ValueError("Ledger export failed")
        ledgers = [{"name": e.get("NAME") or e.findtext("NAME", ""), "parent": e.findtext("PARENT", ""),
                    "gstin": e.findtext("PARTYGSTIN", "") or e.findtext("GSTIN", "")}
                   for e in root.findall(".//LEDGER")]
        request(config["api_base"].rstrip("/") + "/api/v1/tally/bridge/ledgers", {"ledgers": ledgers}, config["bridge_token"])
        log.info("Ledger list synced")
    except (OSError, ValueError, ET.ParseError, urllib.error.URLError):
        log.warning("Ledger sync failed; will try again later")


def selftest(config, log):
    try:
        root = safe_xml(request(config["tally_url"], export_xml("List of Companies"), xml=True))
        companies = root.findall(".//COMPANY")
        if root.findtext("HEADER/STATUS", "").strip() == "0" or not companies:
            log.error("FAIL: Tally replied but no company list was available. Keep the paired company open in TallyPrime.")
            return False
        names = [e.get("NAME") or e.findtext("NAME", "") for e in companies]
        if config["company"] not in names:
            log.error("FAIL: Open the paired company in TallyPrime, then run selftest again.")
            return False
    except (OSError, ValueError, ET.ParseError, urllib.error.URLError):
        log.error("FAIL: Tally is not listening or returned an unreadable reply. Open TallyPrime, press F1, Settings, "
                  "Advanced Configuration, enable the HTTP server on port 9000; check tally_url and keep the company open.")
        return False
    log.info("PASS: Tally is reachable and the paired company is open.")
    sync_ledgers(config, log)
    return True


def cycle(config, state_path, log, dry_run=False):
    """Poll once; preserve outcomes until the cloud accepts each acknowledgement."""
    state_path = Path(state_path)
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    if not isinstance(state, dict) or any(not isinstance(v, dict) for v in state.values()):
        raise ValueError("Invalid journal; restore it before posting")
    base = config["api_base"].rstrip("/") + "/api/v1/tally/bridge/"
    network_failed = False
    # Retry saved acknowledgements even if an item disappears from pending.
    for saved_id, record in state.items():
        if not record.get("acked"):
            try:
                request(base + "ack", record["ack"], config["bridge_token"])
                state[saved_id] = {"acked": True}
                save_json(state_path, state)
            except (OSError, urllib.error.URLError, ValueError):
                network_failed = True
                log.warning("Acknowledgement failed; saved for next cycle")
    pending = request(base + "pending", token=config["bridge_token"])
    if not isinstance(pending, dict) or not isinstance(pending.get("items"), list):
        raise ValueError("Invalid pending response")
    for item in pending["items"]:
        item_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(item_id, str) or not item_id:
            log.warning("Skipped malformed item without a valid id")
            continue
        if item_id in state:
            continue
        reason = verify_item(item, config)
        ack = {"id": item_id, "ok": False, "created": 0, "altered": 0, "errors": [], "response": ""}
        if reason:
            ack["errors"] = [reason]
            log.warning("Item refused by local validation")
        elif dry_run or config["dry_run"]:
            ack.update(ok=True, response="dry-run")
            log.info("Item verified: dry-run")
        else:
            # Persist intent first: a lost reply or crash must never cause a second import.
            ack["errors"] = ["Import outcome uncertain; check Tally manually before creating a new approved item"]
            state[item_id] = {"ack": ack, "acked": False}
            save_json(state_path, state)
            try:
                raw = request(config["tally_url"], item["xml"].encode("utf-8"), xml=True)
                ack = {"id": item_id, **parse_reply(raw), "response": raw[:2000]}
            except NETWORK_ERRORS:
                network_failed = True
                log.error("Tally connection failed; outcome uncertain, manual reconciliation required")
            except ValueError:
                log.error("Tally response unreadable; outcome uncertain, manual reconciliation required")
        state[item_id] = {"ack": ack, "acked": False}
        save_json(state_path, state)
        try:
            request(base + "ack", ack, config["bridge_token"])
            state[item_id] = {"acked": True}
            save_json(state_path, state)
            log.info("Item acknowledgement accepted")
        except (OSError, urllib.error.URLError, ValueError):
            network_failed = True
            log.warning("Acknowledgement failed; saved for next cycle")
    if network_failed:
        raise OSError("Network operation failed")


def lock_file(path):
    """Prevent two local processes posting the same queue concurrently."""
    stream = open(path, "a+b")
    try:
        private_file(path)
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        stream.close()
        raise
    return stream


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("pair", "selftest", "once", "run"):
        sub = commands.add_parser(command)
        sub.add_argument("--config", type=Path, default=argparse.SUPPRESS)
        sub.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
        if command == "pair":
            sub.add_argument("--api", required=True)
            sub.add_argument("--code", required=True)
    args = parser.parse_args(argv)
    log = logging.getLogger("tally-bridge")
    lock = None
    try:
        lock = lock_file(str(args.config) + ".lock")
        if args.command == "pair":
            if args.config.exists() or Path(str(args.config) + ".posted.json").exists():
                print("FAIL: Already paired. Use a different --config path to pair another bridge.")
                return 1
            paired = request(args.api.rstrip("/") + "/api/v1/tally/bridge/pair",
                             {"code": args.code, "host": socket.gethostname()})
            config = {"api_base": args.api, "bridge_token": paired["bridge_token"], "signing_key": paired["signing_key"],
                      "company": paired["company"], "tally_url": "http://127.0.0.1:9000", "poll_seconds": 15, "dry_run": False}
            if any(not isinstance(config[k], str) or not config[k].strip() for k in ("bridge_token", "signing_key", "company")):
                raise ValueError("Invalid pairing response")
            save_json(args.config, config)
            print("Paired. Keep the company open in TallyPrime, then run selftest.")
            return 0
        config = load_config(args.config)
        log = setup_log(str(args.config) + ".log", config)
        if args.command == "selftest":
            return 0 if selftest(config, log) else 1
        cycles, backoff = 0, config["poll_seconds"]
        while True:
            failed = False
            try:
                cycle(config, str(args.config) + ".posted.json", log, args.dry_run)
                backoff = config["poll_seconds"]
            except NETWORK_ERRORS:
                failed = True
                log.warning("Network unavailable; check the internet and Tally HTTP server")
            cycles += 1
            if cycles % 20 == 0:
                sync_ledgers(config, log)
            if args.command == "once":
                return 1 if failed else 0
            delay = min(backoff, 300) if failed else config["poll_seconds"]
            time.sleep(delay)
            if failed:
                backoff = min(backoff * 2, 300)
    except KeyboardInterrupt:
        print("Bridge stopped. Saved acknowledgements will resume next time.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
        # Never print exception text: it can contain credentials or untrusted XML.
        print("FAIL: Cannot start or continue. Check pairing, configuration, permissions, and the journal. "
              "Close any other bridge using this config. Do not delete the journal to retry an import.")
        return 1
    finally:
        if lock is not None:
            lock.close()


if __name__ == "__main__":
    raise SystemExit(main())
