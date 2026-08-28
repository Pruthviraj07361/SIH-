-- Run this in the Supabase SQL editor (Project -> SQL Editor -> New query).

create extension if not exists vector;

create table if not exists materials (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users not null,
    filename text not null,
    upload_date timestamptz default now(),
    embedding_status text default 'pending'  -- 'pending' | 'done'
);

create table if not exists chunks (
    id uuid primary key default gen_random_uuid(),
    material_id uuid references materials(id) on delete cascade,
    content text not null,
    embedding vector(384)  -- 384 = all-MiniLM-L6-v2 output size
);

create table if not exists topics (
    id uuid primary key default gen_random_uuid(),
    material_id uuid references materials(id) on delete cascade,
    topic_name text not null
);

create table if not exists questions (
    id uuid primary key default gen_random_uuid(),
    material_id uuid references materials(id) on delete cascade,
    topic_id uuid references topics(id) on delete cascade,
    question_text text not null,
    options jsonb not null,
    correct_answer text not null,
    explanation text
);

create table if not exists quiz_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users not null,
    type text not null,  -- 'topic_quiz' | 'full_quiz' | 'weekly_mock'
    started_at timestamptz default now(),
    completed_at timestamptz,
    score int
);

create table if not exists attempts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users not null,
    question_id uuid references questions(id),
    quiz_session_id uuid references quiz_sessions(id),
    selected_answer text,
    is_correct boolean,
    attempted_at timestamptz default now()
);

-- Similarity search function used by app/embeddings.py (search_similar_chunks)
create or replace function match_chunks(
    query_embedding vector(384),
    match_material_id uuid,
    match_count int default 5
)
returns table (id uuid, content text, similarity float)
language sql stable
as $$
    select id, content, 1 - (embedding <=> query_embedding) as similarity
    from chunks
    where material_id = match_material_id
    order by embedding <=> query_embedding
    limit match_count;
$$;
