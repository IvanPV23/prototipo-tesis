PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;

-- Estado CRDT de cada vale (réplica local).
CREATE TABLE IF NOT EXISTS vales (
  id TEXT PRIMARY KEY, codigo TEXT NOT NULL, tipo TEXT NOT NULL CHECK (tipo IN ('SALIDA','INGRESO')),
  material TEXT NOT NULL, cantidad REAL NOT NULL CHECK (cantidad > 0), unidad_medida TEXT NOT NULL,
  nodo_origen TEXT NOT NULL, estado TEXT NOT NULL CHECK (estado IN ('ACTIVO','ANULADO')),
  proyecto TEXT NOT NULL, observacion TEXT NOT NULL DEFAULT '',
  field_versions TEXT NOT NULL, version_vector TEXT NOT NULL, actualizado_en TEXT NOT NULL
);

-- Saldo del ítem como PN-Counter.
CREATE TABLE IF NOT EXISTS items (
  item_id TEXT PRIMARY KEY, descripcion TEXT NOT NULL, unidad_medida TEXT NOT NULL,
  stock_referencia REAL NOT NULL, counter_p TEXT NOT NULL DEFAULT '{}', counter_n TEXT NOT NULL DEFAULT '{}',
  stock_actual REAL NOT NULL
);

-- Cola local (outbox) y registro de eventos recibidos: append-only.
CREATE TABLE IF NOT EXISTS eventos (
  event_id TEXT PRIMARY KEY, aggregate_id TEXT NOT NULL, event_type TEXT NOT NULL,
  payload TEXT NOT NULL, vector_clock TEXT NOT NULL, device_id TEXT NOT NULL, actor_id TEXT NOT NULL,
  created_at TEXT NOT NULL, origen TEXT NOT NULL CHECK (origen IN ('LOCAL','REMOTO')),
  synced INTEGER NOT NULL DEFAULT 0, lote_id TEXT
);
CREATE INDEX IF NOT EXISTS eventos_pendientes ON eventos(synced, origen);
-- Sólo synced y lote_id pueden cambiar (confirmación de la réplica central).
CREATE TRIGGER IF NOT EXISTS eventos_no_update BEFORE UPDATE ON eventos
WHEN NEW.event_id != OLD.event_id OR NEW.aggregate_id != OLD.aggregate_id OR NEW.event_type != OLD.event_type
  OR NEW.payload != OLD.payload OR NEW.vector_clock != OLD.vector_clock OR NEW.device_id != OLD.device_id
  OR NEW.actor_id != OLD.actor_id OR NEW.created_at != OLD.created_at OR NEW.origen != OLD.origen
BEGIN SELECT RAISE(ABORT, 'eventos append-only'); END;
CREATE TRIGGER IF NOT EXISTS eventos_no_delete BEFORE DELETE ON eventos BEGIN SELECT RAISE(ABORT, 'eventos append-only'); END;

CREATE TABLE IF NOT EXISTS nodo_campo (
  device_id TEXT PRIMARY KEY, estado_conexion TEXT NOT NULL, ultima_sincronizacion TEXT, last_seq INTEGER NOT NULL DEFAULT 0
);
