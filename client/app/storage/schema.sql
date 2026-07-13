CREATE TABLE IF NOT EXISTS vales (
  id TEXT PRIMARY KEY, codigo TEXT NOT NULL, material TEXT NOT NULL,
  cantidad REAL NOT NULL, estado TEXT NOT NULL, proyecto TEXT NOT NULL DEFAULT 'GENERAL', vector_clock TEXT NOT NULL,
  device_id TEXT NOT NULL, actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eventos (
  event_id TEXT PRIMARY KEY, aggregate_id TEXT NOT NULL, event_type TEXT NOT NULL,
  payload TEXT NOT NULL, vector_clock TEXT NOT NULL, device_id TEXT NOT NULL,
  created_at TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0
);
