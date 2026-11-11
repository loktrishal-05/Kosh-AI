-- Live GST portal sessions, so they survive across serverless invocations. `state` is Fernet-sealed by the API (never plaintext). Same RLS discipline as 0003.
CREATE TABLE gsp_sessions (
  tenant_id UUID NOT NULL REFERENCES tenants,
  gstin TEXT NOT NULL,
  state TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, gstin)
);
ALTER TABLE gsp_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE gsp_sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON gsp_sessions
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
GRANT SELECT, INSERT, UPDATE ON gsp_sessions TO taxsetu_app;
