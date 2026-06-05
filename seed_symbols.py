"""
seed_symbols.py
───────────────
Reads the parsed JSON output and seeds the OHE symbol database.

Usage:
    python seed_symbols.py                          # uses default JSON path
    python seed_symbols.py path/to/output.json      # custom path
    python seed_symbols.py --db postgresql://...    # custom DB URL

Dependencies:
    pip install psycopg2-binary python-dotenv

Environment variable (or .env file):
    DATABASE_URL=postgresql://user:pass@localhost:5432/ohe_editor
"""

import json
import os
import sys
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_JSON = Path(__file__).parent / "response_1780657676921.json"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ohe_editor")

# ── Label → symbol type rules (Layer 2 classifier) ───────────────────────────

RULES = [
    (r"^SM-",         "SPI_Remote",       "Section Motor – Remote"),
    (r"^SS-",         "SectionInsulator", "Section Switch Insulator"),
    (r"^ES-",         "ES",               "Earthing Switch"),
    (r"^X-",          "SP",               "Section Post"),
    (r"^CB-",         "CB",               "Circuit Breaker"),
    (r"^BM-",         "AnchorMast",       "Anchor Mast"),
    (r"^L-\d+$",      "Feeder",           "Feeder / Link"),
    (r"^SH-",         "Shunt",            "Shunt"),
    (r"^KM-",         "KM",               "Kilometre Post"),
    (r"TSS|FP",       "FP",               "Feeder Post / TSS"),
    (r"^BC$",         "BC",               "Bus Coupler"),
    (r"^PARALLELINGPOST$", "PP",          "Paralleling Post"),
    (r"^GP",          "GP",               "General Post"),
    (r"^\d+$",        "NumericLabel",     "Numeric identifier / track number"),
    (r"^[A-Z]{1,2}$", "AlphaCode",        "Short alpha code"),
]

def classify(label: str) -> tuple[str | None, float, str]:
    """
    Returns (symbol_type, confidence, source).
    source is 'rule' or None (unclassified).
    """
    for pattern, sym_type, _ in RULES:
        if re.search(pattern, label, re.IGNORECASE):
            return sym_type, 1.0, "rule"
    return None, 0.0, "manual"   # falls to human review

def get_description(label: str) -> str | None:
    for pattern, _, desc in RULES:
        if re.search(pattern, label, re.IGNORECASE):
            return desc
    return None

# ── DB helpers ────────────────────────────────────────────────────────────────

def connect(url: str):
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = False
        return conn
    except Exception as e:
        print(f"ERROR: Could not connect to database.\n  {e}")
        print(f"\n  DATABASE_URL used: {url}")
        print("  Set DATABASE_URL env var or pass --db <url>")
        sys.exit(1)

# ── Main seed logic ───────────────────────────────────────────────────────────

def seed(json_path: Path, db_url: str):
    print(f"\n{'─'*60}")
    print(f"  OHE Symbol Database Seeder")
    print(f"{'─'*60}")
    print(f"  JSON : {json_path}")
    print(f"  DB   : {db_url.split('@')[-1]}")   # hide credentials
    print(f"{'─'*60}\n")

    # ── Load JSON ────────────────────────────────────────────
    with open(json_path) as f:
        data = json.load(f)

    source_file = data.get("source_file", json_path.stem)
    page_count  = data.get("page_count", 1)
    pages       = data.get("pages", [])
    symbols     = data.get("symbols", [])
    lines       = data.get("lines", [])
    rects       = data.get("rects", [])

    # Derive a stable diagram_id from the source filename
    diagram_id = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(source_file).stem)[:64]

    print(f"  Diagram ID : {diagram_id}")
    print(f"  Symbols    : {len(symbols)}")
    print(f"  Lines      : {len(lines)}")
    print(f"  Rects      : {len(rects)}")
    print()

    conn = connect(db_url)
    cur  = conn.cursor()
    now  = datetime.now(timezone.utc)

    try:
        # ── 1. Upsert diagram ─────────────────────────────────
        cur.execute("""
            INSERT INTO diagrams (id, source_file, page_count, imported_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
                SET source_file = EXCLUDED.source_file,
                    page_count  = EXCLUDED.page_count,
                    imported_at = EXCLUDED.imported_at
        """, (diagram_id, source_file, page_count, now))
        print("  ✓ diagrams")

        # ── 2. Page dimensions ────────────────────────────────
        cur.execute("DELETE FROM diagram_pages WHERE diagram_id = %s", (diagram_id,))
        if pages:
            execute_values(cur, """
                INSERT INTO diagram_pages (diagram_id, page_number, width, height)
                VALUES %s
            """, [(diagram_id, p["page_number"], p["width"], p["height"]) for p in pages])
        print(f"  ✓ diagram_pages ({len(pages)} rows)")

        # ── 3. Extracted symbols + library upsert ─────────────
        cur.execute("DELETE FROM extracted_symbols WHERE diagram_id = %s", (diagram_id,))

        sym_rows     = []
        library_seen = {}   # label → (symbol_type, confidence, source, description)

        for s in symbols:
            label = s.get("label", "")
            bbox  = s.get("bbox", {})
            sym_type, conf, src = classify(label)

            sym_rows.append((
                s["id"],
                diagram_id,
                label,
                s["x"],
                s["y"],
                bbox.get("x0"), bbox.get("y0"),
                bbox.get("x1"), bbox.get("y1"),
                s.get("page", 1),
                sym_type,
                conf if conf > 0 else None,
                src if sym_type else None,
            ))

            # Collect unique labels for the library (first classification wins)
            if label and label not in library_seen:
                library_seen[label] = (sym_type, conf, src, get_description(label))

        if sym_rows:
            execute_values(cur, """
                INSERT INTO extracted_symbols
                    (id, diagram_id, label, x, y,
                     bbox_x0, bbox_y0, bbox_x1, bbox_y1,
                     page, symbol_type, confidence, matched_by)
                VALUES %s
            """, sym_rows)
        print(f"  ✓ extracted_symbols ({len(sym_rows)} rows)")

        # ── 4. Symbol library upsert ──────────────────────────
        lib_rows = [
            (str(uuid.uuid4()), label, sym_type, desc, conf if conf > 0 else None, src, now, now)
            for label, (sym_type, conf, src, desc) in library_seen.items()
        ]

        if lib_rows:
            execute_values(cur, """
                INSERT INTO symbol_library
                    (id, label, symbol_type, description, confidence, source, created_at, updated_at)
                VALUES %s
                ON CONFLICT (label) DO UPDATE
                    SET symbol_type = EXCLUDED.symbol_type,
                        description = EXCLUDED.description,
                        confidence  = EXCLUDED.confidence,
                        source      = EXCLUDED.source,
                        updated_at  = EXCLUDED.updated_at
            """, lib_rows)

        classified   = sum(1 for _, (t,_,_,_) in library_seen.items() if t)
        unclassified = len(library_seen) - classified
        print(f"  ✓ symbol_library ({len(lib_rows)} unique labels — "
              f"{classified} classified, {unclassified} pending review)")

        # ── 5. Extracted lines ────────────────────────────────
        cur.execute("DELETE FROM extracted_lines WHERE diagram_id = %s", (diagram_id,))

        if lines:
            execute_values(cur, """
                INSERT INTO extracted_lines
                    (id, diagram_id, x1, y1, x2, y2, page, stroke_width, stroke_color)
                VALUES %s
            """, [(
                l["id"], diagram_id,
                l["x1"], l["y1"], l["x2"], l["y2"],
                l.get("page", 1),
                l.get("stroke_width"),
                l.get("stroke_color"),
            ) for l in lines])
        print(f"  ✓ extracted_lines ({len(lines)} rows)")

        # ── 6. Extracted rects ────────────────────────────────
        cur.execute("DELETE FROM extracted_rects WHERE diagram_id = %s", (diagram_id,))

        if rects:
            execute_values(cur, """
                INSERT INTO extracted_rects
                    (id, diagram_id, bbox_x0, bbox_y0, bbox_x1, bbox_y1, page)
                VALUES %s
            """, [(
                r["id"], diagram_id,
                r["bbox"]["x0"], r["bbox"]["y0"],
                r["bbox"]["x1"], r["bbox"]["y1"],
                r.get("page", 1),
            ) for r in rects])
        print(f"  ✓ extracted_rects ({len(rects)} rows)")

        # ── Commit ────────────────────────────────────────────
        conn.commit()
        print(f"\n  ✅ Done. All data committed to database.\n")

        # ── Summary ───────────────────────────────────────────
        print(f"{'─'*60}")
        print(f"  CLASSIFICATION SUMMARY")
        print(f"{'─'*60}")

        from collections import Counter
        type_counts = Counter(t for _, (t,_,_,_) in library_seen.items() if t)
        for sym_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"    {sym_type:<22} {count:>4} unique label(s)")

        if unclassified:
            print(f"\n  ⚠  {unclassified} label(s) not matched by rules — "
                  f"route to ML / manual review:")
            for label, (t,_,_,_) in library_seen.items():
                if not t:
                    print(f"      · {label}")

        print(f"{'─'*60}\n")

    except Exception as e:
        conn.rollback()
        print(f"\n  ❌ ERROR — rolled back all changes.\n  {e}")
        raise
    finally:
        cur.close()
        conn.close()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Parse args
    args = sys.argv[1:]
    db_url    = DATABASE_URL
    json_path = DEFAULT_JSON

    i = 0
    while i < len(args):
        if args[i] == "--db" and i + 1 < len(args):
            db_url = args[i + 1]
            i += 2
        else:
            json_path = Path(args[i])
            i += 1

    if not json_path.exists():
        print(f"ERROR: JSON file not found: {json_path}")
        sys.exit(1)

    seed(json_path, db_url)
