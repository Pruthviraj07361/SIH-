"""
FastAPI backend for StudyAI. Endpoints map directly to the frontend screens:
  /materials/upload    -> Home page "Add PDF/Link" -> Embedding Confirmation screen
  /materials/{id}/quiz -> Quiz screen (topic-wise or full-material)
  /analytics/{user_id} -> Analytics screen
  /review/{user_id}    -> Review & Learning screen
"""
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, Form
from app.pdf_processing import extract_text, chunk_text
from app.embeddings import store_chunks, search_similar_chunks
from app.groq_client import extract_topics, generate_quiz_for_topic
from app.db import get_client
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="Sankhayasetu")
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# ---- Frontend page routes (match the exact filenames used in <a href> / <script src>) ----

@app.get("/")
def serve_index():
    return FileResponse("frontend/index.html")

@app.get("/index.html")
def serve_index_html():
    return FileResponse("frontend/index.html")

@app.get("/config.js")
def serve_config():
    return FileResponse("frontend/config.js")

@app.get("/quiz.html")
def serve_quiz_page():
    return FileResponse("frontend/quiz.html")

@app.get("/analytics.html")
def serve_analytics_page():
    return FileResponse("frontend/analytics.html")

@app.get("/review.html")
def serve_review_page():
    return FileResponse("frontend/review.html")

@app.get("/mock-test.html")
def serve_mock_test_page():
    return FileResponse("frontend/mock-test.html")

@app.get("/embedding-confirmation.html")
def serve_embedding_confirmation_page():
    return FileResponse("frontend/embedding-confirmation.html")

@app.get("/login.html")
def serve_login_page():
    return FileResponse("frontend/login.html")

@app.get("/signup.html")
def serve_signup_page():
    return FileResponse("frontend/signup.html")

@app.get("/onboarding.html")
def serve_onboarding_page():
    return FileResponse("frontend/onboarding.html")

@app.get("/dashboard.html")
def serve_dashboard_page():
    return FileResponse("frontend/dashboard.html")


# Allow the static frontend (opened via file:// or a local dev server on a
# different port) to call this API from the browser.
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your real frontend origin before going live
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- API routes (data endpoints) ----

@app.get("/materials")
def list_materials(user_id: str):
    """Home page: recent materials list, with live embedding_status."""
    supabase = get_client()
    return supabase.table("materials").select("*").eq("user_id", user_id).order(
        "upload_date", desc=True
    ).execute().data


@app.get("/materials/{material_id}")
def get_material(material_id: str):
    """Embedding Confirmation screen: stats for one material."""
    supabase = get_client()
    material = supabase.table("materials").select("*").eq("id", material_id).execute().data[0]
    chunk_count = len(supabase.table("chunks").select("id").eq("material_id", material_id).execute().data)
    topics = supabase.table("topics").select("*").eq("material_id", material_id).execute().data
    return {**material, "chunk_count": chunk_count, "topics": topics}


@app.get("/materials/{material_id}/topics")
def get_topics(material_id: str):
    """Quiz screen: topic picker."""
    supabase = get_client()
    return supabase.table("topics").select("*").eq("material_id", material_id).execute().data


@app.post("/quiz-sessions")
def create_quiz_session(user_id: str = Form(...), type: str = Form(...)):
    """Called when the user starts a quiz/mock test, before logging attempts."""
    supabase = get_client()
    row = supabase.table("quiz_sessions").insert({"user_id": user_id, "type": type}).execute().data[0]
    return row


@app.patch("/quiz-sessions/{session_id}/complete")
def complete_quiz_session(session_id: str, score: int = Form(...)):
    supabase = get_client()
    from datetime import datetime
    supabase.table("quiz_sessions").update({
        "completed_at": datetime.utcnow().isoformat(), "score": score
    }).eq("id", session_id).execute()
    return {"status": "completed"}


@app.get("/quiz-sessions")
def list_quiz_sessions(user_id: str):
    """Dashboard 'My Quizzes' tab: quiz history, oldest first so index+1 gives
    the 'Quiz N' numbering the frontend displays. Adds per-session totals so
    the list/analysis views don't need a second round trip per quiz."""
    supabase = get_client()
    sessions = supabase.table("quiz_sessions").select("*").eq(
        "user_id", user_id
    ).order("started_at").execute().data
    for s in sessions:
        attempts = supabase.table("attempts").select("is_correct").eq(
            "quiz_session_id", s["id"]
        ).execute().data
        s["total_questions"] = len(attempts)
        s["correct_count"] = sum(1 for a in attempts if a["is_correct"])
    return sessions


@app.get("/quiz-sessions/{session_id}/attempts")
def get_session_attempts(session_id: str):
    """Dashboard 'My Quizzes' detail view: every question in this one quiz,
    with the user's answer and the correct one, for review."""
    supabase = get_client()
    return supabase.table("attempts").select(
        "selected_answer, is_correct, questions(question_text, options, correct_answer, explanation)"
    ).eq("quiz_session_id", session_id).execute().data


@app.post("/materials/upload")
async def upload_material(user_id: str = Form(...), file: UploadFile = File(...)):
    """Step 1 (embed) + Step 2 (topics) + Step 3 (quiz gen) end-to-end."""
    supabase = get_client()

    # Save upload to a temp file so pypdf can read it
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    # Create the materials row
    material = supabase.table("materials").insert({
        "user_id": user_id,
        "filename": file.filename,
        "embedding_status": "pending",
    }).execute().data[0]
    material_id = material["id"]

    # Step 1: extract, chunk, embed
    text = extract_text(tmp_path)
    chunks = chunk_text(text)
    store_chunks(material_id, chunks)
    supabase.table("materials").update({"embedding_status": "done"}).eq("id", material_id).execute()

    # Step 2: topic extraction
    topic_names = extract_topics(text)
    topic_rows = supabase.table("topics").insert(
        [{"material_id": material_id, "topic_name": t} for t in topic_names]
    ).execute().data

    # Step 3: topic-wise quiz generation
    MIN_RELEVANT_CHUNKS = 3  # quality gate from the spec
    questions_created = 0
    for topic in topic_rows:
        relevant = search_similar_chunks(material_id, topic["topic_name"], top_k=5)
        if len(relevant) < MIN_RELEVANT_CHUNKS:
            continue  # skip topics with no real grounding (e.g. syllabus-only mentions)

        quiz_items = generate_quiz_for_topic(topic["topic_name"], relevant, n_questions=4)
        rows = [{
            "material_id": material_id,
            "topic_id": topic["id"],
            "question_text": q["question_text"],
            "options": q["options"],
            "correct_answer": q["correct_answer"],
            "explanation": q.get("explanation", ""),
        } for q in quiz_items]
        if rows:
            supabase.table("questions").insert(rows).execute()
            questions_created += len(rows)

    return {
        "material_id": material_id,
        "embedding_status": "done",
        "chunks_created": len(chunks),
        "topics_found": len(topic_rows),
        "questions_created": questions_created,
    }


@app.get("/materials/{material_id}/quiz")
def get_quiz(material_id: str, topic_id: str | None = None):
    """Step 4: pure read, filtered by topic if given, else the whole material."""
    supabase = get_client()
    query = supabase.table("questions").select("*").eq("material_id", material_id)
    if topic_id:
        query = query.eq("topic_id", topic_id)
    return query.execute().data


@app.post("/attempts")
def log_attempt(user_id: str = Form(...), question_id: str = Form(...),
                 quiz_session_id: str = Form(...), selected_answer: str = Form(...)):
    """Logs one answer; is_correct is computed and stored now, not re-derived later."""
    supabase = get_client()
    question = supabase.table("questions").select("correct_answer").eq("id", question_id).execute().data[0]
    is_correct = selected_answer == question["correct_answer"]
    supabase.table("attempts").insert({
        "user_id": user_id,
        "question_id": question_id,
        "quiz_session_id": quiz_session_id,
        "selected_answer": selected_answer,
        "is_correct": is_correct,
    }).execute()
    return {"is_correct": is_correct}


@app.get("/analytics/{user_id}")
def get_analytics(user_id: str):
    """Step 5 + Step 8: topic-wise accuracy and weakest-topic suggestion. Pure aggregation."""
    supabase = get_client()
    attempts = supabase.table("attempts").select(
        "is_correct, question_id, questions(topic_id, topics(topic_name))"
    ).eq("user_id", user_id).execute().data

    by_topic: dict[str, dict] = {}
    for a in attempts:
        topic = a["questions"]["topics"]["topic_name"]
        by_topic.setdefault(topic, {"correct": 0, "total": 0})
        by_topic[topic]["total"] += 1
        if a["is_correct"]:
            by_topic[topic]["correct"] += 1

    breakdown = [
        {"topic": t, "accuracy": round(100 * v["correct"] / v["total"]), "attempts": v["total"]}
        for t, v in by_topic.items()
    ]
    breakdown.sort(key=lambda x: x["accuracy"])  # weakest first
    return {"breakdown": breakdown, "weakest_topic": breakdown[0]["topic"] if breakdown else None}


@app.get("/review/{user_id}")
def get_wrong_answers(user_id: str):
    """Step 7: wrong-answer review, joined to the stored explanation."""
    supabase = get_client()
    return supabase.table("attempts").select(
        "selected_answer, questions(question_text, correct_answer, explanation)"
    ).eq("user_id", user_id).eq("is_correct", False).execute().data


@app.get("/mock-test/{user_id}")
def get_weekly_mock(user_id: str):
    """Step 6: pool questions from materials uploaded this week."""
    supabase = get_client()
    from datetime import datetime, timedelta
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    recent_materials = supabase.table("materials").select("id").eq("user_id", user_id).gte(
        "upload_date", week_ago
    ).execute().data
    material_ids = [m["id"] for m in recent_materials]
    if not material_ids:
        return []
    return supabase.table("questions").select("*").in_("material_id", material_ids).execute().data


@app.post("/profile")
def save_profile(user_id: str = Form(...), username: str = Form(...),
                  department: str = Form(...), age: int = Form(...),
                  goal: str = Form(...)):
    """Onboarding screen: called once, right after signup."""
    supabase = get_client()
    row = supabase.table("profiles").upsert({
        "user_id": user_id,
        "username": username,
        "department": department,
        "age": age,
        "goal": goal,
    }).execute().data[0]
    return row


@app.get("/profile/{user_id}")
def get_profile(user_id: str):
    """Used to check whether onboarding is already done (e.g. on login),
    and to populate the dashboard's profile card."""
    supabase = get_client()
    rows = supabase.table("profiles").select("*").eq("user_id", user_id).execute().data
    return rows[0] if rows else None


@app.get("/dashboard/{user_id}")
def get_dashboard(user_id: str):
    """Dashboard screen: profile + top-line stats + recent materials +
    weakest-topic focus areas, aggregated in one call."""
    supabase = get_client()

    profile = supabase.table("profiles").select("*").eq("user_id", user_id).execute().data
    profile = profile[0] if profile else None

    sessions = supabase.table("quiz_sessions").select("id, score, completed_at").eq(
        "user_id", user_id
    ).execute().data
    completed = [s for s in sessions if s["completed_at"]]
    quizzes_completed = len(completed)

    attempts = supabase.table("attempts").select(
        "is_correct, questions(topic_id, topics(topic_name))"
    ).eq("user_id", user_id).execute().data
    total_attempts = len(attempts)
    correct_attempts = sum(1 for a in attempts if a["is_correct"])
    average_score = round(100 * correct_attempts / total_attempts) if total_attempts else 0

    by_topic: dict[str, dict] = {}
    for a in attempts:
        topic = a["questions"]["topics"]["topic_name"]
        by_topic.setdefault(topic, {"correct": 0, "total": 0})
        by_topic[topic]["total"] += 1
        if a["is_correct"]:
            by_topic[topic]["correct"] += 1
    topic_accuracies = [
        {"topic": t, "accuracy": round(100 * v["correct"] / v["total"])}
        for t, v in by_topic.items()
    ]
    topic_accuracies.sort(key=lambda x: x["accuracy"])
    competency_progress = (
        round(sum(t["accuracy"] for t in topic_accuracies) / len(topic_accuracies))
        if topic_accuracies else 0
    )
    weak_areas = topic_accuracies[:3]  # lowest-accuracy topics -> "Recommended Focus Areas"

    materials = supabase.table("materials").select("*").eq("user_id", user_id).order(
        "upload_date", desc=True
    ).limit(3).execute().data

    return {
        "profile": profile,
        "quizzes_completed": quizzes_completed,
        "average_score": average_score,
        "competency_progress": competency_progress,
        "recent_materials": materials,
        "weak_areas": weak_areas,
    }