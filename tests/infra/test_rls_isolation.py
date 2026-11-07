"""Phase 0 gate. Static checks always run; the live cross-tenant test needs Postgres (DATABASE_URL + psycopg) and skips otherwise."""
import os
import re
from pathlib import Path

import pytest

SQL = (Path(__file__).parents[2] / "infra" / "migrations" / "0001_core.sql").read_text(encoding="utf-8")
TENANT_TABLES = ["tenants", "gst_registrations", "invoices_inward_outward", "eway_bills_and_detentions",
                 "direct_tax_and_employee_records", "corporate_and_labour_registers", "hitl_approvals_and_audit_log"]


def test_every_table_has_rls_enabled_forced_and_a_policy():
    created = re.findall(r"CREATE TABLE (\w+)", SQL)
    assert set(created) == set(TENANT_TABLES)                 # no table escapes the check
    for t in created:
        if t in ("tenants", "hitl_approvals_and_audit_log"):  # written out explicitly
            assert f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY" in SQL and f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY" in SQL
        else:                                                 # applied via the loop over this array
            assert f"'{t}'" in SQL.split("FOREACH t IN ARRAY ARRAY[")[1].split("]")[0]
    assert "FORCE ROW LEVEL SECURITY" in SQL and "%I FORCE" in SQL
    assert SQL.count("current_setting('app.tenant_id', true)") >= 6


def test_audit_table_is_append_only_by_grant_and_policy():
    assert "GRANT SELECT, INSERT ON hitl_approvals_and_audit_log" in SQL
    audit = SQL.split("ALTER TABLE hitl_approvals_and_audit_log ENABLE")[1]
    assert "FOR UPDATE" not in audit and "FOR DELETE" not in audit and "FOR ALL" not in audit


def test_app_role_cannot_bypass_rls():
    assert "NOSUPERUSER NOBYPASSRLS" in SQL


URL = os.environ.get("DATABASE_URL_APP", "postgresql://taxsetu_app:taxsetu_app@localhost:5432/taxsetu")


@pytest.fixture
def conn():
    psycopg = pytest.importorskip("psycopg", reason="psycopg not installed")
    try:
        c = psycopg.connect(URL, connect_timeout=2, autocommit=False)
    except Exception as e:
        pytest.skip(f"no live Postgres: {type(e).__name__}")
    yield c
    c.rollback()
    c.close()


def _as(conn, tenant):
    conn.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant or "",))


def test_live_cross_tenant_isolation(conn):
    a, b = "00000000-0000-0000-0000-00000000000a", "00000000-0000-0000-0000-00000000000b"
    for t in (a, b):
        _as(conn, t)
        conn.execute("INSERT INTO tenants(tenant_id, legal_name, entity_type) VALUES (%s,%s,'PROPRIETORSHIP')", (t, f"T{t[-1]}"))
        conn.execute("INSERT INTO invoices_inward_outward(tenant_id,direction,invoice_no,invoice_date,taxable_value,dedup_hash)"
                     " VALUES (%s,'INWARD','INV1','2026-11-01',100,%s)", (t, t[-1] * 64))
    _as(conn, a)
    assert [r[0] for r in conn.execute("SELECT tenant_id::text FROM invoices_inward_outward")] == [a]
    assert conn.execute("SELECT count(*) FROM tenants").fetchone()[0] == 1
    _as(conn, None)
    assert conn.execute("SELECT count(*) FROM invoices_inward_outward").fetchone()[0] == 0   # no context -> no rows
    _as(conn, a)
    with pytest.raises(Exception, match="row-level security"):                                # cannot write into B's tenant
        conn.execute("INSERT INTO invoices_inward_outward(tenant_id,direction,invoice_no,invoice_date,taxable_value,dedup_hash)"
                     " VALUES (%s,'INWARD','X','2026-11-01',1,%s)", (b, "c" * 64))
