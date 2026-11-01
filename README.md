# DNS Energy

Aplicație web DNS Energy: frontend React/Vite și backend FastAPI cu MongoDB.

## Structură
- `frontend/` — interfața web (React + Vite)
- `backend/` — API FastAPI, generarea documentelor și modulele aplicației

## Configurare locală

### Backend
1. Creează `backend/.env` pornind de la `backend/.env.example`.
2. Configurează o instanță MongoDB și setează `MONGO_URL`, `DB_NAME` și un `JWT_SECRET` lung și aleatoriu.
3. Instalează dependențele din `backend/requirements.txt`.
4. Din directorul `backend`, pornește API-ul cu `uvicorn server:app --host 0.0.0.0 --port 8000`.
5. Extragerea AI folosește direct OpenAI când `OPENAI_API_KEY` este configurată; documentele se stochează în Cloudflare R2 prin variabilele `R2_*`.

### Frontend
1. Creează `frontend/.env` pornind de la `frontend/.env.example`.
2. Dacă frontendul și API-ul sunt pe domenii diferite, setează `REACT_APP_BACKEND_URL` la originea publică a backendului, fără `/api` la final. Dacă sunt pe același domeniu, lasă valoarea goală și configurează hostul/proxy-ul să direcționeze `/api` către FastAPI.
3. Din directorul `frontend`, rulează `yarn install`, apoi `yarn build` pentru verificarea/build-ul de producție.

## Securitate
- Nu încărca fișierele `.env`, parole, tokenuri sau chei reale în repository.
- Schimbă valorile de exemplu pentru administrator înainte de a expune backendul public.
- Configurează HTTPS și accesul la MongoDB doar din serviciile autorizate.

## Important
Codul sursă din GitHub nu înseamnă automat că aplicația este publicată sau că serviciile externe sunt configurate. Pentru funcționare în producție trebuie configurate variabilele secrete, MongoDB, stocarea fișierelor și rutarea frontend/API.
