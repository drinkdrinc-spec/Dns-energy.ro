# D-ENERGY — PRD

## Problem statement
Web app "D-ENERGY" for DNS HOSTESS S.R.L. to manage electrical installation & photovoltaic works in Romania. Romanian UI, responsive (iPhone + desktop). Separate modules; real database, secure auth, persistent storage, file upload (PDF/photos). Prepared for online publishing (accessible via link in Safari). Prosumer dossier and DI-U kept as two distinct modules. Modern professional D-ENERGY visual identity. Reference design supplied as an HTML file (navy/blue/cyan palette, Inter font, left sidebar ERP layout).

## Architecture
- Backend: FastAPI + MongoDB (motor). JWT email/password auth (bcrypt). Generic owner-scoped CRUD under `/api/data/{module}`. Emergent Object Storage for files (`/api/upload`, `/api/files/{path}`). Dashboard stats, settings singleton.
- Frontend: Vite + React 19 + Tailwind v4 + shadcn/sonner. React Router. Config-driven generic ModulePage (`config/modules.js`). AuthContext stores JWT in localStorage (`den_token`), sends `Authorization: Bearer`.
- Auth: single admin role. Admin seeded from env (ADMIN_EMAIL/ADMIN_PASSWORD).

## Users / personas
- Admin/owner (electrician/engineer) managing clients, dossiers, technical records, works.

## Core requirements (static)
Romanian UI, responsive, persistent DB, secure auth, file upload, two separate dossiers (prosumer + DI-U), modern D-ENERGY identity.

## Implemented (2026-06)
- JWT auth + login screen; admin: drinkdrinc@gmail.com.
- Dashboard with KPIs (clients, DI-U, scheme monofilare, pending) + recent dossiers + module tiles.
- Modules (generic CRUD, owner-scoped, search, edit/delete, print-to-PDF): Clienți, Dosar de prosumator (12-item checklist), Dosar de utilizare DI-U (10-item checklist), Scheme monofilare (voltages/fuses/SPD/RCD/grounding + PDF export), Tablouri electrice, Antiinsularizare, Buletine PRAM, Echipamente, Spor de putere/BMP (branșamente, mono↔trifazat), Gestionarea lucrărilor (devize/stadiu).
- Catalog tehnic: invertoare, panouri, baterii LV/HV, BESS with official documentation links.
- Distribuitori România (operator lookup). Simulare fotovoltaică (formula-based kWp/producție). Documente (PDF/photo upload to object storage). Setări firmă.
- Verified by testing agent: 100% backend + frontend on smoke flows.

## Backlog
- P1: Dedicated PRAM measured-values fields; per-record attached files (link uploads to each dossier); works → deviz line items & totals.
- P1: Change-password UI for admin.
- P2: Multi-user roles (admin + technician), per-client document folders view, export dossier bundle as single PDF.
- P2: Address geocoding/map embed in simulation.

## Next tasks
- Wire file attachments directly inside each dossier (prosumator/DI-U) record.
- Expand PRAM module into full measurement bulletin.
