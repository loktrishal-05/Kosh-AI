-- Phase 0b: durable HITL drafts + audit-log detail. Same RLS discipline as 0001 (FORCE + non-bypass app role).

CREATE TABLE hitl_drafts (
  draft_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants,
  kind TEXT NOT NULL,
  payload JSONB NOT NULL,
  payload_sha256 CHAR(64) NOT NULL,
  status TEXT NOT NULL DEFAULT 'DRAFT_STAGED' CHECK (status IN ('DRAFT_STAGED','FILED_VERIFIED')),
  otp_hash CHAR(64),
  otp_expires DOUBLE PRECISION NOT NULL DEFAULT 0,   -- epoch seconds, compared with the app clock
  ack JSONB NOT NULL DEFAULT '{}',
  version INT NOT NULL DEFAULT 0,                    -- optimistic lock: stops two concurrent authorize() calls spending one OTP
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE hitl_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE hitl_drafts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON hitl_drafts
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
GRANT SELECT, INSERT, UPDATE ON hitl_drafts TO taxsetu_app;   -- no DELETE: drafts are evidence

-- The audit log records more than the four portal actions (OTP issued, filing rejected, edits, recon runs).
ALTER TABLE hitl_approvals_and_audit_log DROP CONSTRAINT hitl_approvals_and_audit_log_action_type_check;
ALTER TABLE hitl_approvals_and_audit_log ADD CONSTRAINT hitl_audit_action_type_check CHECK (action_type IN
  ('RETSAVE','RETFILE_HITL','ITR_SUBMIT_HITL','IMS_ACTION','OTP_ISSUED','FILING_REJECTED','DRAFT_EDITED','RECON_COMPLETED'));
-- Canonical JSON the hash was computed over, so verification re-hashes exactly what was signed. seq gives a gap-free-per-insert order.
ALTER TABLE hitl_approvals_and_audit_log ADD COLUMN body_json TEXT;
ALTER TABLE hitl_approvals_and_audit_log ADD COLUMN seq BIGINT GENERATED ALWAYS AS IDENTITY;
CREATE INDEX hitl_audit_tenant_seq ON hitl_approvals_and_audit_log (tenant_id, seq);
