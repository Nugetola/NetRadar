-- Apply through the approved PostgreSQL migration pipeline before deployment.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS vlan_profiles (
  id SERIAL PRIMARY KEY, vlan_id INT UNIQUE NOT NULL, subnet CIDR,
  gateway_ip INET, snmp_version VARCHAR(10) NOT NULL DEFAULT 'v3',
  snmp_credential_ref VARCHAR(200), is_active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY, actor VARCHAR(100) NOT NULL, action VARCHAR(100) NOT NULL,
  resource_type VARCHAR(50), resource_id VARCHAR(100), metadata_json JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_device_status_log_device_recorded ON device_status_log(device_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS ix_tickets_status_opened ON tickets(status, opened_at);
