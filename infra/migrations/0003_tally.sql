-- Phase 8: Tally autopilot. Same RLS discipline as 0001/0002 (FORCE + non-bypass app role).

-- Approved-bytes outbox: the bridge on the customer PC only ever sees rows a human approved.
CREATE TABLE tally_outbox (
  batch_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants,
  kind TEXT NOT NULL CHECK (kind IN ('vouchers','masters')),
  company TEXT NOT NULL,
  xml TEXT NOT NULL,
  sha256 CHAR(64) NOT NULL,
  summary JSONB NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL'
    CHECK (status IN ('PENDING_APPROVAL','APPROVED','REJECTED','POSTED','FAILED')),
  approved_by TEXT,
  ack JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX tally_outbox_tenant_status ON tally_outbox (tenant_id, status, created_at);

-- Learned "who is this" memory: normalised counterparty -> ledger.
CREATE TABLE tally_aliases (
  tenant_id UUID NOT NULL REFERENCES tenants,
  alias TEXT NOT NULL,
  ledger TEXT NOT NULL,
  PRIMARY KEY (tenant_id, alias)
);

CREATE TABLE tally_bridges (
  bridge_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants,
  company TEXT NOT NULL,
  host TEXT,
  paired BOOLEAN NOT NULL DEFAULT FALSE,
  revoked BOOLEAN NOT NULL DEFAULT FALSE,
  last_seen TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ledger list last synced up from the customer's Tally by the bridge.
CREATE TABLE tally_ledgers (
  tenant_id UUID NOT NULL REFERENCES tenants,
  name TEXT NOT NULL,
  parent TEXT NOT NULL DEFAULT '',
  gstin TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (tenant_id, name)
);

DO $$ DECLARE t TEXT; BEGIN
  FOREACH t IN ARRAY ARRAY['tally_outbox','tally_aliases','tally_bridges','tally_ledgers'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format($p$CREATE POLICY tenant_isolation ON %I
      USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)$p$, t);
  END LOOP;
END $$;

GRANT SELECT, INSERT, UPDATE ON tally_outbox, tally_bridges TO taxsetu_app;     -- no DELETE: evidence
GRANT SELECT, INSERT, UPDATE, DELETE ON tally_aliases, tally_ledgers TO taxsetu_app;

ALTER TABLE hitl_approvals_and_audit_log DROP CONSTRAINT hitl_audit_action_type_check;
ALTER TABLE hitl_approvals_and_audit_log ADD CONSTRAINT hitl_audit_action_type_check CHECK (action_type IN
  ('RETSAVE','RETFILE_HITL','ITR_SUBMIT_HITL','IMS_ACTION','OTP_ISSUED','FILING_REJECTED','DRAFT_EDITED','RECON_COMPLETED',
   'TALLY_BATCH_STAGED','TALLY_BATCH_APPROVED','TALLY_BATCH_REJECTED','TALLY_BATCH_POSTED','TALLY_BATCH_FAILED',
   'BRIDGE_PAIRED','BRIDGE_REVOKED','ALIAS_LEARNED'));
