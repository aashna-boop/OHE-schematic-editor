# OHE Schematic Editor

A full-stack engineering platform for parsing, classifying, editing, and exporting Overhead Equipment (OHE) one-line diagrams. The system automatically converts uploaded OHE PDF drawings into fully editable SVG-based schematics using PDF extraction, symbol classification, topology reconstruction, and a persistent symbol library. 

---
## Authors

Developed by:

- Aashna Suman
- Gaurvi Saini

Under the guidance of the Centre for Railway Information Systems (CRIS)

Project: OHE Schematic Editor Platform
Department: Electrical (TR-D)
Year: 2026

## Overview

The OHE Schematic Editor eliminates manual redrawing of railway OHE diagrams by:

* Parsing existing OHE PDF drawings
* Extracting symbols, labels, and wire geometry
* Classifying symbols using rules, machine learning, and a symbol library
* Reconstructing diagram topology
* Rendering an editable SVG canvas
* Exporting engineering drawings as SVG, PDF, or JSON

### Workflow

```text
PDF Upload
    ↓
PDF Parsing
    ↓
Symbol Library Lookup
    ↓
Rule-Based Classification
    ↓
ML Classification
    ↓
Human Review (if needed)
    ↓
Topology Reconstruction
    ↓
SVG Editor
    ↓
Export & Save
```

---

# Features

## PDF Parsing

Extracts:

* Text labels
* Coordinates
* Bounding boxes
* Vector line paths
* Symbol regions

Built with:

* FastAPI
* Python
* pdfplumber

Example output:

```json
{
  "symbols": [
    {
      "id": "CB-23",
      "label": "CB-23",
      "x": 142.3,
      "y": 88.1
    }
  ],
  "lines": [
    {
      "x1": 142,
      "y1": 88,
      "x2": 210,
      "y2": 88
    }
  ]
}
```

---

## Intelligent Symbol Classification

The classifier uses a four-layer architecture:

### Layer 1 — Symbol Library Database

Checks previously verified label-to-type mappings.

Example:

```text
SM-161 → SPI_Remote
CB-23  → CB
```

### Layer 2 — Rule Engine

Uses deterministic naming conventions.

Examples:

```python
CB-* → CB
SM-* → SPI_Remote
BM-* → AnchorMast
SS-* → SectionInsulator
```

### Layer 3 — Machine Learning

Fallback classifier using:

* scikit-learn
* Fine-tuned BERT

for ambiguous labels.

### Layer 4 — Human Review

Low-confidence predictions are sent to an engineer review queue before entering the editor.

---

## Symbol Library Database

A self-improving knowledge base that stores every verified label classification.

### Benefits

* Instant classification for known symbols
* Reduced ML inference cost
* Learns from every processed diagram
* Preserves human corrections permanently

### Example Schema

```sql
symbol_library
├── id
├── label
├── symbol_type
├── description
├── confidence
├── source
├── created_at
└── updated_at
```

### Available APIs

```http
GET    /api/symbol-library
GET    /api/symbol-library/{label}
POST   /api/symbol-library
POST   /api/symbol-library/seed
GET    /api/symbol-library/stats
```

---

## Graph & Topology Engine

Converts extracted line segments into an engineering connection graph.

### Responsibilities

* Endpoint snapping
* Graph construction
* Symbol attachment
* Connection validation

Built with:

* NetworkX

### Validation Checks

* Floating nodes
* Broken connections
* Dangling wires
* Connectivity issues

---

## Interactive SVG Editor

The editor renders symbols and wires within a single SVG coordinate space.

### Features

* Zoom & pan
* Drag-and-drop symbols
* Grid snapping
* Multi-selection
* Undo/redo
* Wire creation
* Symbol rotation
* Keyboard shortcuts

### State Management

```text
React
  ↓
Zustand Store
  ↓
SVG Canvas
```

---

## Orthogonal Wire Routing

Automatically routes engineering wires using:

* A* pathfinding
* Obstacle avoidance
* Orthogonal routing
* Bend optimization

### Capabilities

* Horizontal/vertical routing
* Symbol collision avoidance
* Minimum-bend path generation
* Route simplification

---

## Upload & Review Workflow

### Upload

* Drag-and-drop PDF
* File validation

### Live Parsing

* WebSocket progress updates
* Real-time extraction status

### Review Screen

Engineers can:

* Review classifications
* Correct symbol types
* Approve low-confidence predictions

Corrections are automatically saved back into the Symbol Library.

---

## Export Engine

Supports multiple output formats.

| Format | Purpose                           |
| ------ | --------------------------------- |
| SVG    | CAD and vector editing            |
| PDF    | Engineering drawings and printing |
| JSON   | Versioning and collaboration      |

---

## Persistence & Authentication

### Database

PostgreSQL stores:

* Diagrams
* Versions
* User ownership
* Symbol library entries

### Authentication

JWT-based security with role management.

Roles:

* Viewer
* Editor
* Admin

---

# Technology Stack

| Layer            | Technology                     |
| ---------------- | ------------------------------ |
| PDF Parsing      | Python, pdfplumber, pdfjs-dist |
| Backend          | FastAPI, SQLAlchemy, NetworkX  |
| Database         | PostgreSQL, JSONB              |
| Frontend         | React 18, Zustand              |
| Canvas           | SVG                            |
| ML               | scikit-learn, Fine-tuned BERT  |
| Routing          | A* Pathfinding                 |
| Export           | jsPDF, Inkscape CLI            |
| Authentication   | JWT                            |
| Realtime Updates | WebSockets                     |

---

# Project Architecture

```text
┌─────────────────────┐
│ PDF Upload          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ PDF Parser          │
│ FastAPI/pdfplumber  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Symbol Library DB   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Rule Engine         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ ML Classifier       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Human Review Queue  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Topology Engine     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ React + Zustand     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ SVG Editor          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Export Engine       │
└─────────────────────┘
```

---

# Development Roadmap

| Phase               | Estimated Duration |
| ------------------- | ------------------ |
| PDF Parsing Backend | 1–2 Weeks          |
| Symbol Classifier   | 1–2 Weeks          |
| Symbol Library DB   | 0.5–1 Week         |
| Topology Engine     | 2–3 Weeks          |
| Frontend Data Layer | 1 Week             |
| SVG Canvas          | 1–2 Weeks          |
| Interaction Layer   | 2 Weeks            |
| Wire Routing        | 1–2 Weeks          |
| Upload & Review UI  | 1 Week             |
| Export Engine       | 1 Week             |
| Persistence & Auth  | 1 Week             |

**Total Estimated Timeline:** 12.5–18 Weeks (2–3 Engineers)

---

# Future Enhancements

* AI-assisted symbol recognition from raster PDFs
* Collaborative multi-user editing
* Diagram comparison and diffing
* CAD/DXF export support
* Railway-specific validation rules
* Advanced analytics for symbol usage patterns

---

## License

Internal CRIS Engineering Project – OHE Editor Platform (TR-D)

Version 1.1 (2026)
