"""
Groq API calls for topic extraction (Step 2) and quiz generation (Step 3).

The API key itself is never referenced here directly — it's read once in
app/config.py from your .env file (GROQ_API_KEY=...) and passed into the
client below. If you ever need to double check it's loading correctly:
    python -c "from app.config import GROQ_API_KEY; print(GROQ_API_KEY[:8])"
"""
import json
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL

client = Groq(api_key=GROQ_API_KEY)


def extract_topics(material_text: str, min_topics: int = 5, max_topics: int = 10) -> list[str]:
    """Sends the full material text to Groq and gets back 5-10 distinct topics."""
    prompt = f"""You are analyzing study material to identify distinct topics/competencies covered.

Extract between {min_topics} and {max_topics} distinct topics from the material below.
Return ONLY a JSON object of the form: {{"topics": ["topic 1", "topic 2", ...]}}

MATERIAL:
{material_text[:12000]}
"""
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)

    # Defensive: some responses come back as a raw list instead of the
    # requested {"topics": [...]} wrapper.
    if isinstance(data, list):
        return data
    return data.get("topics", [])


def generate_quiz_for_topic(topic_name: str, relevant_chunks: list[str], n_questions: int = 4) -> list[dict]:
    """
    Generates MCQs grounded ONLY in the given chunks (retrieved for this
    specific topic via similarity search), per Step 3 of the spec.
    """
    context = "\n\n---\n\n".join(relevant_chunks)
    prompt = f"""Using ONLY the material below, write {n_questions} multiple-choice questions
about the topic "{topic_name}". Each question must be answerable directly from the material —
do not use outside knowledge.

Return ONLY a JSON object of the form:
{{"quiz": [
  {{
    "question_text": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct_answer": "A",
    "explanation": "..."
  }}
]}}

MATERIAL:
{context}
"""
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)

    # Defensive: some responses come back as a raw list instead of the
    # requested {"quiz": [...]} wrapper.
    if isinstance(data, list):
        return data
    return data.get("quiz", [])