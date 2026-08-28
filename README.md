# StudyAI Backend

## Setup (run these in order)

1. `pip install -r requirements.txt`
2. `cp .env.example .env`
3. **Open `.env` and put your Groq API key on this line:**
   ```
   GROQ_API_KEY=gsk_your_actual_key_here
   ```
   Also fill in `SUPABASE_URL` and `SUPABASE_KEY` from your Supabase project's
   Settings -> API page.
4. Run `schema.sql` in your Supabase project's SQL Editor (creates all tables +
   the pgvector similarity function).
5. Start the server:
   ```
   uvicorn app.main:app --reload
   ```
6. Test it's alive: open `http://127.0.0.1:8000/docs` — FastAPI's auto-generated
   Swagger UI, where you can try `/materials/upload` directly with a PDF.

## Where the API key is actually used
- **Read from `.env`**: `app/config.py` (line: `GROQ_API_KEY = os.environ.get("GROQ_API_KEY")`)
- **Used to call Groq**: `app/groq_client.py` (line: `client = Groq(api_key=GROQ_API_KEY)`)
You never need to touch the key anywhere else — every other file imports it
indirectly through `app/config.py`.

## Running the frontend
1. Start the backend first: `uvicorn app.main:app --reload` (must be running at `http://127.0.0.1:8000`)
2. Open `frontend/index.html` directly in a browser, or serve the folder:
   `python3 -m http.server 5500 --directory frontend` then visit `http://127.0.0.1:5500`
3. Upload a PDF on the Home page → it redirects to the Embedding Confirmation
   screen once processing finishes → Start Quiz / View Analytics / Review
   wrong answers, all live against your Supabase data.

**`frontend/config.js`** holds `API_BASE` (backend URL) and a placeholder
`DEMO_USER_ID` — swap that for a real logged-in user id once Supabase Auth is
wired in on the frontend (currently every page acts as one hardcoded user, by
design, since auth isn't built yet — see "Not implemented yet" below).

## What's implemented
- Step 1: Upload -> extract -> chunk -> embed (local, sentence-transformers) -> store in Supabase/pgvector
- Step 2: Topic extraction via Groq
- Step 3: Topic-wise quiz generation via Groq, grounded in per-topic retrieved chunks, with the quality gate (skip topics with <3 relevant chunks)
- Step 4: Quiz read endpoint (no AI call)
- Step 5: Analytics aggregation (no AI call)
- Step 6: Weekly mock test pooling (no AI call)
- Step 7: Wrong-answer review (no AI call)
- Step 8: Weak-topic suggestion (no AI call)

## Not implemented yet (next steps)
- Real auth: every page uses `DEMO_USER_ID` from `frontend/config.js` instead
  of a logged-in session. Endpoints take `user_id` as a plain field, not a
  verified session — swap both for real Supabase Auth before real users touch this.
- Rate limiting / retry logic around Groq calls
- The "Add PDF/Link" flow only handles file uploads, not pasted links (spec
  mentions links as an option; only PDF extraction is implemented)
- Loading state while a PDF is uploading is a single status line, not the
  animated processing screen the original mockup implied
