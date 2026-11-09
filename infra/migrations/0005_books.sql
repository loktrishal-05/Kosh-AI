-- Phase 9: single-entry books kept over time. Same RLS discipline as every other tenant table (FORCE + non-bypass app role).
-- Entries are never deleted: a correction voids the old line (with a reason) and adds a new one, so the history stays as evidence.

CREATE TABLE se_books (
  book_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants,
  name TEXT NOT NULL,
  entity_type TEXT NOT NULL CHECK (entity_type IN ('business','individual','nonprofit')),
  period_start DATE NOT NULL,
  period_end DATE NOT NULL CHECK (period_end >= period_start),
  opening JSONB NOT NULL DEFAULT '{}',
  closing JSONB NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
  closed_report JSONB,
  rolled_from UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE se_entries (
  entry_id UUID PRIMARY KEY,
  book_id UUID NOT NULL REFERENCES se_books,
  tenant_id UUID NOT NULL REFERENCES tenants,
  seq BIGINT GENERATED ALWAYS AS IDENTITY,
  entry_date DATE NOT NULL,
  description TEXT NOT NULL,
  receipt NUMERIC(15,2) NOT NULL DEFAULT 0 CHECK (receipt >= 0),
  payment NUMERIC(15,2) NOT NULL DEFAULT 0 CHECK (payment >= 0),
  mode TEXT NOT NULL DEFAULT 'cash' CHECK (mode IN ('cash','bank')),
  party TEXT NOT NULL DEFAULT '',
  hint TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','VOID')),
  void_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((receipt > 0) <> (payment > 0))
);
CREATE INDEX se_entries_book_seq ON se_entries (book_id, seq);

DO $$ DECLARE t TEXT; BEGIN
  FOREACH t IN ARRAY ARRAY['se_books','se_entries'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format($p$CREATE POLICY tenant_isolation ON %I
      USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)$p$, t);
  END LOOP;
END $$;

GRANT SELECT, INSERT, UPDATE ON se_books, se_entries TO taxsetu_app;      -- no DELETE: books and their entries are evidence

ALTER TABLE hitl_approvals_and_audit_log DROP CONSTRAINT hitl_audit_action_type_check;
ALTER TABLE hitl_approvals_and_audit_log ADD CONSTRAINT hitl_audit_action_type_check CHECK (action_type IN
  ('RETSAVE','RETFILE_HITL','ITR_SUBMIT_HITL','IMS_ACTION','OTP_ISSUED','FILING_REJECTED','DRAFT_EDITED','RECON_COMPLETED',
   'TALLY_BATCH_STAGED','TALLY_BATCH_APPROVED','TALLY_BATCH_REJECTED','TALLY_BATCH_POSTED','TALLY_BATCH_FAILED',
   'BRIDGE_PAIRED','BRIDGE_REVOKED','ALIAS_LEARNED','TENANT_CREATED',
   'BOOK_CREATED','BOOK_SETUP_CHANGED','BOOK_ENTRIES_ADDED','BOOK_ENTRY_VOIDED','BOOK_CLOSED','BOOK_ROLLED_OVER','BOOK_TALLY_STAGED'));
