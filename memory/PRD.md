# D-ENERGY — PRD

## Problem statement
Web app "D-ENERGY" for DNS HOSTESS S.R.L. to manage electrical installation & photovoltaic works in Romania. Romanian UI, responsive. Separate modules; real DB, JWT auth, file uploads (Emergent Object Storage). Prosumer dossier and DI-U kept as two distinct modules. Later requests: AI import of prosumer PDF dossiers, auto-generated dossier documents, and (inspired by public WattEver features, own implementation, no copied code/branding) multi-inverter CEF configuration, technical checks, auto single-line diagram, equipment catalog with datasheets/conformity.

## Architecture
- Backend FastAPI + MongoDB. Files: server.py (auth, generic CRUD `/api/data/{module}`, AI extract, import, docs, CEF/catalog), docgen.py (reportlab docs, portrait+landscape templates), cef.py (CEF checks/proposals/flatten), schema_cef.py (multi-inverter single-line drawing + data table), ai_extract.py (Gemini gemini-3-flash-preview via Emergent LLM key), catalog_seed.py.
- Frontend Vite React 19 + Tailwind; config-driven ModulePage; components/cef/* (CefEditor, GridCard, InverterCard, CefResults, F); ProsumatorTools (AI import, generated docs, catalog files); pages/EquipmentCatalog.jsx.

## Implemented
- 2026-06 MVP: all modules (Clienți, Prosumator, DI-U, Lucrări, Scheme monofilare, Tablouri, Antiinsularizare, PRAM, Echipamente, Spor putere, Catalog links, Simulare, Distribuitori, Documente, Setări).
- 2026-10: AI PDF import (Gemini) → prefilled prosumator form; /import/prosumator creates client, dossier, work, mono, equipment, documents. 11 generated PDFs (Notificare Anexa 2, Împuternicire, Declarații, PV recepție, PV PIF, Buletin priză, Buletin reglaj, Declarație autenticitate, Schema) + bundle. Antal dossier imported (PROS-2026-003).
- 2026-10: CEF editor (N inverters, strings per MPPT, panels, own/shared battery DC/AC, backup, AC/DC cables & protections), live checks (/api/cef/check: Voc cold vs Udc max, Vmp vs MPPT, Isc vs Imax, DC/AC ratio, Iz per IEC 60364-5-52 by material/installation/correction, voltage drop, SPD Ucpv, branșament export limit, shared battery parallel confirmation, anti-islanding auto >27 kW or ATR checkbox), proposals labeled for authorized validation; schema_cef landscape PDF (+ data table); DB catalog (seeded 14 indicative models) with datasheet/conformity upload, reused in dossier (catalog-files, attach to client docs, bundle merge &attach=1). Fixes: numbering, duplicate import 409, cascade delete, settings race, UI polish.
- Tests: iteration_1..3 all passing.

## Backlog
- P1: Official per-operator form templates (Delgaz, Rețele Electrice, Oltenia); DIU generated from prosumator dossier.
- P1: Engineers/PRAM devices in Settings with signatures & metrology expiry; PV probe sheet with measurements.
- P2: Remote client signing link; dossier kanban by events; per-company sizing rule tables; multi-user roles.
