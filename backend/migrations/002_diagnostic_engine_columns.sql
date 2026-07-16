-- Adds the columns the 5-stage diagnostic engine needs: which switch ifIndex
-- a device is wired to (Stage 1 SNMP triangulation), and whether a device is a
-- DNS server (enables the dedicated DNS-service check).
ALTER TABLE devices ADD COLUMN IF NOT EXISTS switch_port_ifindex INT;
ALTER TABLE devices ADD COLUMN IF NOT EXISTS is_dns_server BOOLEAN NOT NULL DEFAULT FALSE;