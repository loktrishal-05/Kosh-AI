-- TaxSetu AI core schema (report s3.3). Every tenant table is RLS-protected and FORCEd (applies to the table owner too).
-- The API connects as taxsetu_app (no BYPASSRLS) and sets: SET app.tenant_id = '<uuid>' per transaction/connection.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'taxsetu_app') THEN
    CREATE ROLE taxsetu_app LOGIN PASSWORD 'taxsetu_app' NOSUPERUSER NOBYPASSRLS;
  END IF;
END $$;

CREATE TABLE tenants (
  tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  legal_name TEXT NOT NULL,
  entity_type TEXT NOT NULL CHECK (entity_type IN ('PROPRIETORSHIP','PARTNERSHIP','LLP','PVT_LTD','OPC')),
  pan_encrypted BYTEA, tan_encrypted BYTEA, cin TEXT,
  primary_whatsapp_e164 TEXT, preferred_locale TEXT DEFAULT 'en',
  assigned_ca_id UUID, qrmp_opted BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE gst_registrations (
  gstin_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants,
  gstin CHAR(15) NOT NULL UNIQUE, state_code CHAR(2) NOT NULL,
  filing_frequency TEXT NOT NULL CHECK (filing_frequency IN ('MONTHLY','QRMP')),
  ewb_blocked_rule138e BOOLEAN NOT NULL DEFAULT FALSE, gsp_api_enabled BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE invoices_inward_outward (
  invoice_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants,
  direction TEXT NOT NULL CHECK (direction IN ('INWARD','OUTWARD')),
  counterparty_gstin CHAR(15), invoice_no VARCHAR(16) NOT NULL, invoice_date DATE NOT NULL,
  place_of_supply CHAR(2), hsn_sac_code VARCHAR(8),
  taxable_value NUMERIC(15,2) NOT NULL, cgst_amt NUMERIC(15,2) NOT NULL DEFAULT 0,
  sgst_amt NUMERIC(15,2) NOT NULL DEFAULT 0, igst_amt NUMERIC(15,2) NOT NULL DEFAULT 0,
  itc_eligibility TEXT CHECK (itc_eligibility IN ('ELIGIBLE','BLOCKED_17_5','INELIGIBLE')),
  gstr2b_match_status TEXT CHECK (gstr2b_match_status IN ('EXACT','FUZZY','MISMATCH','MISSING_2B')),
  ims_action TEXT CHECK (ims_action IN ('ACCEPT','REJECT','PENDING')),
  payment_due_180d_date DATE, payment_settled BOOLEAN NOT NULL DEFAULT FALSE,
  tds_section_applicable TEXT, tds_deducted_amt NUMERIC(15,2),
  raw_artifact_s3_uri TEXT, ocr_confidence NUMERIC(4,3),
  -- composite dedup key (report s4.2): SHA256(supplier_gstin + normalized_invoice_no + fy)
  dedup_hash CHAR(64) NOT NULL,
  UNIQUE (tenant_id, dedup_hash)
);

CREATE TABLE eway_bills_and_detentions (
  ewb_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants,
  invoice_id UUID REFERENCES invoices_inward_outward,
  ewb_number CHAR(12), part_a_json JSONB, vehicle_no_part_b TEXT, distance_km INTEGER,
  valid_until_ts TIMESTAMPTZ, detention_mov07_s3_uri TEXT,
  circular_64_38_applicable BOOLEAN, drafted_reply_s3_uri TEXT
);

CREATE TABLE direct_tax_and_employee_records (
  tax_record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants,
  assessment_year CHAR(7) NOT NULL,
  selected_itr_form TEXT CHECK (selected_itr_form IN ('ITR1','ITR2','ITR3','ITR4','ITR5','ITR6','ITR7')),
  turnover_digital_44ad NUMERIC(15,2), turnover_cash_44ad NUMERIC(15,2), cash_ratio_pct NUMERIC(5,2),
  form16_part_a_json JSONB, form16_part_b_json JSONB, form12bb_json JSONB, ais_tis_26as_recon_json JSONB,
  regime_selected TEXT CHECK (regime_selected IN ('NEW_115BAC','OLD')),
  refund_amount_claimed NUMERIC(15,2),
  refund_pathway TEXT CHECK (refund_pathway IN ('SEC_139_1','SEC_139_4','SEC_139_5','SEC_119_2B','FORM_30','REISSUE'))
);

CREATE TABLE corporate_and_labour_registers (
  corp_doc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants,
  spice_plus_srn TEXT, emoa_inc33_json JSONB, eaoa_inc34_json JSONB,
  labour_form_a_json JSONB, labour_form_b_json JSONB
);

-- Append-only, hash-chained (NFR-007)
CREATE TABLE hitl_approvals_and_audit_log (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants,
  actor_role TEXT NOT NULL,
  action_type TEXT NOT NULL CHECK (action_type IN ('RETSAVE','RETFILE_HITL','ITR_SUBMIT_HITL','IMS_ACTION')),
  payload_sha256 CHAR(64),
  verification_method TEXT CHECK (verification_method IN ('EVC_OTP','AADHAAR_OTP','CLASS3_DSC')),
  portal_ack_arn_irn TEXT, prev_event_hash CHAR(64) NOT NULL, event_hash CHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---- Row-level security ------------------------------------------------------------------------------------
-- tenants is keyed by its own id; every other table by tenant_id. current_setting(..., true) -> NULL when unset -> no rows.
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tenants
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

DO $$ DECLARE t TEXT; BEGIN
  FOREACH t IN ARRAY ARRAY['gst_registrations','invoices_inward_outward','eway_bills_and_detentions',
                           'direct_tax_and_employee_records','corporate_and_labour_registers'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format($p$CREATE POLICY tenant_isolation ON %I
      USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)$p$, t);
  END LOOP;
END $$;

ALTER TABLE hitl_approvals_and_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE hitl_approvals_and_audit_log FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_read ON hitl_approvals_and_audit_log FOR SELECT
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
CREATE POLICY tenant_append ON hitl_approvals_and_audit_log FOR INSERT
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
-- no UPDATE/DELETE policy => denied under RLS

GRANT USAGE ON SCHEMA public TO taxsetu_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON tenants, gst_registrations, invoices_inward_outward, eway_bills_and_detentions,
      direct_tax_and_employee_records, corporate_and_labour_registers TO taxsetu_app;
GRANT SELECT, INSERT ON hitl_approvals_and_audit_log TO taxsetu_app;
