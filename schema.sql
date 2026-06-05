-- ============================================================
--  OHE Schematic Editor — Symbol Database Schema
--  Source: GP Depot sectioning diagram GP-TGM-Model.pdf
-- ============================================================

-- ── Source diagrams ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diagrams (
    id          TEXT PRIMARY KEY,           -- e.g. "GP-TGM-Model"
    source_file TEXT NOT NULL,              -- original PDF filename
    page_count  INTEGER NOT NULL DEFAULT 1,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Page dimensions ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diagram_pages (
    id          SERIAL PRIMARY KEY,
    diagram_id  TEXT NOT NULL REFERENCES diagrams(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    width       NUMERIC(12, 4) NOT NULL,
    height      NUMERIC(12, 4) NOT NULL
);

-- ── Master symbol library (label → type mapping) ─────────────
--  Grows with every diagram processed; acts as a lookup cache.
CREATE TABLE IF NOT EXISTS symbol_library (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label       TEXT NOT NULL UNIQUE,       -- e.g. "SM-161"
    symbol_type TEXT,                       -- e.g. "SPI_Remote" (NULL = unclassified)
    description TEXT,
    confidence  NUMERIC(4,3) DEFAULT 1.0,  -- 1.0 = manually verified
    source      TEXT DEFAULT 'manual'      -- 'manual' | 'rule' | 'ml_inferred'
        CHECK (source IN ('manual', 'rule', 'ml_inferred')),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Extracted symbols (one row per label per diagram) ─────────
CREATE TABLE IF NOT EXISTS extracted_symbols (
    id          TEXT PRIMARY KEY,           -- e.g. "sym_9e3ce44f"
    diagram_id  TEXT NOT NULL REFERENCES diagrams(id) ON DELETE CASCADE,
    label       TEXT NOT NULL,
    x           NUMERIC(12, 4) NOT NULL,
    y           NUMERIC(12, 4) NOT NULL,
    bbox_x0     NUMERIC(12, 4),
    bbox_y0     NUMERIC(12, 4),
    bbox_x1     NUMERIC(12, 4),
    bbox_y1     NUMERIC(12, 4),
    page        INTEGER NOT NULL DEFAULT 1,
    -- Classification result (populated after Step 2)
    symbol_type TEXT,                       -- NULL until classified
    confidence  NUMERIC(4,3),
    matched_by  TEXT                        -- 'library' | 'rule' | 'ml' | 'manual'
        CHECK (matched_by IN ('library', 'rule', 'ml', 'manual', NULL))
);

-- ── Extracted lines / wire segments ──────────────────────────
CREATE TABLE IF NOT EXISTS extracted_lines (
    id           TEXT PRIMARY KEY,          -- e.g. "line_2a6ea16d"
    diagram_id   TEXT NOT NULL REFERENCES diagrams(id) ON DELETE CASCADE,
    x1           NUMERIC(12, 4) NOT NULL,
    y1           NUMERIC(12, 4) NOT NULL,
    x2           NUMERIC(12, 4) NOT NULL,
    y2           NUMERIC(12, 4) NOT NULL,
    page         INTEGER NOT NULL DEFAULT 1,
    stroke_width NUMERIC(6, 3),
    stroke_color TEXT                       -- raw string e.g. "(0.0, 0.0, 0.0)"
);

-- ── Extracted rects / symbol bounding regions ─────────────────
CREATE TABLE IF NOT EXISTS extracted_rects (
    id         TEXT PRIMARY KEY,            -- e.g. "rect_c15e176f"
    diagram_id TEXT NOT NULL REFERENCES diagrams(id) ON DELETE CASCADE,
    bbox_x0    NUMERIC(12, 4) NOT NULL,
    bbox_y0    NUMERIC(12, 4) NOT NULL,
    bbox_x1    NUMERIC(12, 4) NOT NULL,
    bbox_y1    NUMERIC(12, 4) NOT NULL,
    page       INTEGER NOT NULL DEFAULT 1
);

-- ── Indexes ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_extracted_symbols_diagram  ON extracted_symbols(diagram_id);
CREATE INDEX IF NOT EXISTS idx_extracted_symbols_label    ON extracted_symbols(label);
CREATE INDEX IF NOT EXISTS idx_extracted_symbols_type     ON extracted_symbols(symbol_type);
CREATE INDEX IF NOT EXISTS idx_extracted_lines_diagram    ON extracted_lines(diagram_id);
CREATE INDEX IF NOT EXISTS idx_extracted_rects_diagram    ON extracted_rects(diagram_id);
CREATE INDEX IF NOT EXISTS idx_symbol_library_label       ON symbol_library(label);
