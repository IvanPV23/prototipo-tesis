CREATE TABLE IF NOT EXISTS vales (
  id TEXT PRIMARY KEY, codigo TEXT NOT NULL, material TEXT NOT NULL,
  cantidad REAL NOT NULL, estado TEXT NOT NULL, proyecto TEXT NOT NULL DEFAULT 'GENERAL', vector_clock TEXT NOT NULL,
  device_id TEXT NOT NULL, actualizado_en TEXT NOT NULL,
  field_versions TEXT NOT NULL DEFAULT '{}', counter_p TEXT NOT NULL DEFAULT '{}', counter_n TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS eventos (
  event_id TEXT PRIMARY KEY, aggregate_id TEXT NOT NULL, event_type TEXT NOT NULL,
  payload TEXT NOT NULL, vector_clock TEXT NOT NULL, device_id TEXT NOT NULL,
  created_at TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0
);
-- El payload es inmutable; synced puede cambiar al confirmar la réplica.
CREATE TRIGGER IF NOT EXISTS eventos_no_update BEFORE UPDATE ON eventos
WHEN NEW.event_id != OLD.event_id
  OR NEW.aggregate_id != OLD.aggregate_id
  OR NEW.event_type != OLD.event_type
  OR NEW.payload != OLD.payload
  OR NEW.vector_clock != OLD.vector_clock
  OR NEW.device_id != OLD.device_id
  OR NEW.created_at != OLD.created_at
BEGIN SELECT RAISE(ABORT, 'eventos append-only'); END;
CREATE TRIGGER IF NOT EXISTS eventos_no_delete BEFORE DELETE ON eventos BEGIN SELECT RAISE(ABORT, 'eventos append-only'); END;
CREATE TABLE IF NOT EXISTS nodo_campo (
  device_id TEXT PRIMARY KEY, estado_conexion TEXT NOT NULL, ultima_sincronizacion TEXT NOT NULL
);
