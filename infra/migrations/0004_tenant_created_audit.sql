-- Admin tenant creation is a privileged action: it goes in the audit chain like everything else.
ALTER TABLE hitl_approvals_and_audit_log DROP CONSTRAINT hitl_audit_action_type_check;
ALTER TABLE hitl_approvals_and_audit_log ADD CONSTRAINT hitl_audit_action_type_check CHECK (action_type IN
  ('RETSAVE','RETFILE_HITL','ITR_SUBMIT_HITL','IMS_ACTION','OTP_ISSUED','FILING_REJECTED','DRAFT_EDITED','RECON_COMPLETED',
   'TALLY_BATCH_STAGED','TALLY_BATCH_APPROVED','TALLY_BATCH_REJECTED','TALLY_BATCH_POSTED','TALLY_BATCH_FAILED',
   'BRIDGE_PAIRED','BRIDGE_REVOKED','ALIAS_LEARNED','TENANT_CREATED'));
