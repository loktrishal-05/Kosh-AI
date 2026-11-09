"""Synthetic cloud and Tally servers; no installed bridge package needed."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import logging
import os
from pathlib import Path
import threading
import urllib.error

import pytest

from taxsetu_engine.gst import gstin_check_char


PATH = Path(__file__).resolve().parents[2] / "apps" / "tally-bridge" / "tally_bridge.py"
spec = importlib.util.spec_from_file_location("tally_bridge", PATH)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
COMPANY = "Synthetic Example Books"
XML = ("<ENVELOPE><HEADER><TALLYREQUEST>Import</TALLYREQUEST></HEADER><BODY><IMPORTDATA>"
       "<REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME><STATICVARIABLES>"
       f"<SVCURRENTCOMPANY>{COMPANY}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>"
       '<REQUESTDATA><TALLYMESSAGE><VOUCHER VCHTYPE="Journal" ACTION="Create">'
       "</VOUCHER></TALLYMESSAGE></REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>")
SUCCESS = "<RESPONSE><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS><EXCEPTIONS>0</EXCEPTIONS></RESPONSE>"
GSTIN14 = "29ZZZZZ1234Z1Z"
GSTIN = GSTIN14 + gstin_check_char(GSTIN14)


def item(config, xml=XML, item_id="synthetic-1"):
    digest = hashlib.sha256(xml.encode("utf-8")).hexdigest()
    return {"id": item_id, "kind": "voucher", "xml": xml, "sha256": digest,
            "sig": hmac.new(config["signing_key"].encode(), digest.encode(), hashlib.sha256).hexdigest()}


@pytest.fixture
def servers(tmp_path):
    data = {"items": [], "acks": [], "imports": [], "exports": [], "ledgers": [], "pairs": [],
            "reply": SUCCESS, "ack_fail": False, "auth": [], "content_type": []}

    class Tally(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            data["content_type"].append(self.headers["Content-Type"])
            if b"<TALLYREQUEST>Export</TALLYREQUEST>" in body:
                data["exports"].append(body)
                if b"<ID>List of Accounts</ID>" in body:
                    raw = (f'<ENVELOPE><LEDGER NAME="Synthetic Ledger"><PARENT>Sundry Creditors</PARENT>'
                           f'<PARTYGSTIN>{GSTIN}</PARTYGSTIN></LEDGER></ENVELOPE>')
                else:
                    raw = f'<ENVELOPE><COMPANY NAME="{COMPANY}"/></ENVELOPE>'
            else:
                data["imports"].append(body)
                raw = data["reply"]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(raw.encode())

    class Cloud(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            assert self.path == "/api/v1/tally/bridge/pending"
            data["auth"].append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"items": data["items"]}).encode())

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            data["auth"].append(self.headers.get("Authorization"))
            if self.path.endswith("/ack") and data["ack_fail"]:
                self.send_response(503)
                self.end_headers()
                return
            if self.path.endswith("/ack"):
                data["acks"].append(payload)
                reply = {}
            elif self.path.endswith("/ledgers"):
                data["ledgers"].append(payload)
                reply = {}
            else:
                assert self.path == "/api/v1/tally/bridge/pair"
                data["pairs"].append(payload)
                reply = {k: config[k] for k in ("bridge_token", "signing_key", "company")}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(reply).encode())

    tally = ThreadingHTTPServer(("127.0.0.1", 0), Tally)
    cloud = ThreadingHTTPServer(("127.0.0.1", 0), Cloud)
    config = {"tally_url": f"http://127.0.0.1:{tally.server_port}",
              "api_base": f"http://127.0.0.1:{cloud.server_port}", "bridge_token": "synthetic-secret-token",
              "signing_key": "synthetic-signing-secret", "company": COMPANY, "dry_run": False, "poll_seconds": 15}
    threads = [threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
               for s in (tally, cloud)]
    for thread in threads:
        thread.start()
    data.update(config=config, state=tmp_path / "posted.json", config_path=tmp_path / "config.json",
                log=logging.getLogger("bridge-test"), tally=tally)
    try:
        yield data
    finally:
        for server in (tally, cloud):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=1)


def run(data, dry_run=False):
    bridge.cycle(data["config"], data["state"], data["log"], dry_run)


def test_good_item(servers):
    s = servers
    s["items"] = [item(s["config"])]
    run(s)
    assert s["imports"] == [XML.encode()]
    assert s["acks"] == [{"id": "synthetic-1", "ok": True, "created": 1, "altered": 0,
                          "errors": [], "response": SUCCESS}]
    assert s["auth"] == ["Bearer synthetic-secret-token"] * 2
    assert s["content_type"] == ["text/xml; charset=utf-8"]
    assert json.loads(s["state"].read_text()) == {"synthetic-1": {"acked": True}}


@pytest.mark.parametrize("change,reason", [
    ("tamper", "SHA-256"), ("signature", "signature"), ("company", "company"),
    ("delete", "Create or Alter"), ("doctype", "Malformed"), ("entity", "Malformed"),
    ("execute", "Import"), ("cancel", "Create or Alter"), ("vchtype", "VCHTYPE"),
    ("report", "Vouchers"), ("malformed", "Malformed"), ("company_duplicate", "company"),
])
def test_refused_item_does_not_stop_next(servers, change, reason):
    s = servers
    xml = XML
    if change == "company":
        xml = xml.replace(COMPANY, "Other Synthetic Books")
    elif change in ("delete", "cancel"):
        xml = xml.replace('ACTION="Create"', f'ACTION="{change.title()}"')
    elif change == "doctype":
        xml = '<!DOCTYPE ENVELOPE [<!ENTITY x "unsafe">]>' + xml
    elif change == "entity":
        xml = '<!ENTITY x "unsafe">' + xml
    elif change == "execute":
        xml = xml.replace(">Import<", ">Execute<")
    elif change == "vchtype":
        xml = xml.replace('VCHTYPE="Journal"', "")
    elif change == "report":
        xml = xml.replace("Vouchers", "Day Book")
    elif change == "malformed":
        xml = xml[:-1]
    elif change == "company_duplicate":
        xml = xml.replace("</STATICVARIABLES>", "<SVCURRENTCOMPANY>Other Books</SVCURRENTCOMPANY></STATICVARIABLES>")
    bad = item(s["config"], xml)
    if change == "tamper":
        bad["xml"] += " "
    elif change == "signature":
        bad["sig"] = "0" * 64
    s["items"] = [bad, item(s["config"], item_id="synthetic-2")]
    run(s)
    assert len(s["imports"]) == 1
    assert s["acks"][0]["ok"] is False
    assert reason.lower() in s["acks"][0]["errors"][0].lower()
    assert s["acks"][1]["ok"] is True


def test_lineerror(servers):
    s = servers
    s["reply"] = SUCCESS.replace("<ERRORS>0", "<ERRORS>1").replace(
        "</RESPONSE>", "<LINEERROR>Synthetic ledger missing</LINEERROR></RESPONSE>")
    s["items"] = [item(s["config"])]
    run(s)
    assert s["acks"][0]["ok"] is False
    assert s["acks"][0]["errors"] == ["Synthetic ledger missing"]


@pytest.mark.parametrize("config_flag", [False, True])
def test_dry_run(servers, config_flag):
    s = servers
    s["config"]["dry_run"] = config_flag
    s["items"] = [item(s["config"])]
    run(s, dry_run=not config_flag)
    assert s["imports"] == []
    assert s["acks"][0]["ok"] is True
    assert s["acks"][0]["response"] == "dry-run"


def test_ack_retry_without_reposting_even_when_pending_empty(servers):
    s = servers
    s["items"] = [item(s["config"])]
    s["ack_fail"] = True
    with pytest.raises(OSError):
        run(s)
    s["ack_fail"] = False
    s["items"] = []
    run(s)
    s["items"] = [item(s["config"])]
    run(s)
    assert len(s["imports"]) == len(s["acks"]) == 1
    assert s["acks"][0]["ok"] is True


def test_crash_after_tally_post_never_reposts(servers, monkeypatch):
    s = servers
    s["items"] = [item(s["config"])]
    original = bridge.request

    def crash(url, *args, **kwargs):
        result = original(url, *args, **kwargs)
        if url == s["config"]["tally_url"]:
            raise KeyboardInterrupt
        return result

    monkeypatch.setattr(bridge, "request", crash)
    with pytest.raises(KeyboardInterrupt):
        run(s)
    monkeypatch.setattr(bridge, "request", original)
    run(s)
    assert len(s["imports"]) == 1
    assert s["acks"][0]["ok"] is False
    assert "uncertain" in s["acks"][0]["errors"][0]


def test_selftest_down(servers, caplog):
    servers["tally"].shutdown()
    servers["tally"].server_close()
    assert bridge.selftest(servers["config"], servers["log"]) is False
    assert "FAIL" in caplog.text and "port 9000" in caplog.text and "Advanced Configuration" in caplog.text


def test_selftest_syncs_ledgers(servers):
    assert bridge.selftest(servers["config"], servers["log"]) is True
    assert servers["ledgers"] == [{"ledgers": [{"name": "Synthetic Ledger", "parent": "Sundry Creditors", "gstin": GSTIN}]}]
    assert b"<ID>List of Accounts</ID>" in servers["exports"][1] and b"<ACCOUNTTYPE>Ledgers</ACCOUNTTYPE>" in servers["exports"][1]


def test_redaction(servers, tmp_path, capsys):
    config = servers["config"]
    path = tmp_path / "bridge.log"
    log = bridge.setup_log(path, config)
    try:
        try:
            raise ValueError(config["signing_key"])
        except ValueError:
            log.exception("config=%s", config)
        for output in (path.read_text(encoding="utf-8"), capsys.readouterr().err):
            assert config["bridge_token"] not in output
            assert config["signing_key"] not in output
            assert "[REDACTED]" in output
    finally:
        for handler in log.handlers[:]:
            handler.close()
            log.removeHandler(handler)


def test_pair_and_private_config(servers, capsys):
    s = servers
    assert bridge.main(["pair", "--config", str(s["config_path"]), "--api", s["config"]["api_base"],
                        "--code", "synthetic-code"]) == 0
    config = bridge.load_config(s["config_path"])
    assert config == {**s["config"], "tally_url": "http://127.0.0.1:9000"}
    assert s["pairs"][0]["code"] == "synthetic-code"
    assert s["pairs"][0]["host"]
    output = capsys.readouterr().out
    assert config["bridge_token"] not in output and config["signing_key"] not in output
    if os.name != "nt":
        assert s["config_path"].stat().st_mode & 0o777 == 0o600
    assert bridge.main(["pair", "--config", str(s["config_path"]), "--api", config["api_base"], "--code", "again"]) == 1


@pytest.mark.parametrize("raw", ["not XML", "<RESPONSE><CREATED>oops</CREATED></RESPONSE>",
                                 '<!DOCTYPE RESPONSE><RESPONSE/>', "<RESPONSE/>"])
def test_bad_reply_is_structured(raw):
    result = bridge.parse_reply(raw)
    assert result["ok"] is False and result["errors"]


def test_failure_envelope():
    raw = ("<ENVELOPE><HEADER><STATUS>0</STATUS></HEADER><BODY><DATA><STATUS.LIST>"
           "<STATUS><CODE>123</CODE><DESC>Synthetic company unavailable</DESC></STATUS>"
           "</STATUS.LIST></DATA></BODY></ENVELOPE>")
    assert bridge.parse_reply(raw) == {"ok": False, "created": 0, "altered": 0,
                                      "errors": ["123: Synthetic company unavailable"]}


def test_size_and_utf16_doctype(servers):
    config = servers["config"]
    assert "2 MB" in bridge.verify_item(item(config, "x" * (bridge.MAX_XML + 1)), config)
    utf16 = ('<!DOCTYPE ENVELOPE [<!ENTITY x "unsafe">]>' + XML).encode("utf-16").decode("latin-1")
    assert bridge.verify_item(item(config, utf16), config)


def test_corrupt_journal_fails_closed(servers):
    s = servers
    s["items"] = [item(s["config"])]
    s["state"].write_text("broken", encoding="utf-8")
    with pytest.raises(ValueError):
        run(s)
    assert not s["imports"]


def test_concurrent_bridge_lock(tmp_path):
    path = tmp_path / "bridge.lock"
    lock = bridge.lock_file(path)
    try:
        with pytest.raises(OSError):
            bridge.lock_file(path)
    finally:
        lock.close()


def test_run_sync_every_twenty_cycles_and_ctrl_c(servers, monkeypatch):
    s = servers
    bridge.save_json(s["config_path"], s["config"])
    calls = []
    delays = []
    monkeypatch.setattr(bridge, "cycle", lambda *args: calls.append(True))

    def sleep(delay):
        delays.append(delay)
        if len(delays) == 20:
            raise KeyboardInterrupt

    monkeypatch.setattr(bridge.time, "sleep", sleep)
    assert bridge.main(["run", "--config", str(s["config_path"])]) == 0
    assert len(calls) == 20 and len(s["ledgers"]) == 1


def test_network_backoff(servers, monkeypatch):
    s = servers
    bridge.save_json(s["config_path"], s["config"])
    delays = []

    def fail(*args):
        raise urllib.error.URLError("synthetic failure")

    def sleep(delay):
        delays.append(delay)
        if len(delays) == 8:
            raise KeyboardInterrupt

    monkeypatch.setattr(bridge, "cycle", fail)
    monkeypatch.setattr(bridge.time, "sleep", sleep)
    assert bridge.main(["--config", str(s["config_path"]), "run"]) == 0
    assert delays == [15, 30, 60, 120, 240, 300, 300, 300]


def test_classic_import_data_envelope_is_accepted_and_empty_import_is_not_success():
    """Our engine's envelope says 'Import Data'; a reply that created nothing must not be reported as posted."""
    import importlib.util  # noqa: F401  (module already loaded as `bridge` above)
    ok = bridge.parse_reply("<RESPONSE><CREATED>2</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS></RESPONSE>")      # no EXCEPTIONS tag (older Tally)
    assert ok["ok"] and ok["created"] == 2
    nothing = bridge.parse_reply("<RESPONSE><CREATED>0</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS><EXCEPTIONS>0</EXCEPTIONS></RESPONSE>")
    assert not nothing["ok"] and "created nothing" in nothing["errors"][0]
    wrapped = bridge.parse_reply("<ENVELOPE><BODY><DATA><IMPORTRESULT><CREATED>1</CREATED><ALTERED>0</ALTERED><ERRORS>0</ERRORS></IMPORTRESULT></DATA></BODY></ENVELOPE>")
    assert wrapped["ok"] and wrapped["created"] == 1


def test_documented_success_envelope_without_counters_is_ok_and_lineerror_still_fails():
    assert bridge.parse_reply("<ENVELOPE><HEADER><VERSION>1</VERSION><STATUS>1</STATUS></HEADER><BODY><DATA/></BODY></ENVELOPE>")["ok"]
    bad = bridge.parse_reply("<ENVELOPE><HEADER><STATUS>1</STATUS></HEADER><BODY><DATA><LINEERROR>No such ledger</LINEERROR></DATA></BODY></ENVELOPE>")
    assert not bad["ok"] and bad["errors"] == ["No such ledger"]


def test_bridge_reads_a_reply_with_the_illegal_character_reference_real_tally_emits():
    from pathlib import Path
    xml = (Path(__file__).resolve().parents[1] / "fixtures" / "tallyprime_7_2_ledger_export.xml").read_text(encoding="utf-8")
    assert "&#4;" in xml
    root = bridge.safe_xml(xml)
    assert [e.get("NAME") for e in root.findall(".//LEDGER")] == ["Cash"]
    with pytest.raises(ValueError):
        bridge.safe_xml('<!DOCTYPE x [<!ENTITY a "b">]><ENVELOPE/>')
