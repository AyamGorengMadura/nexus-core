CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS persons (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    embedding_id TEXT,
    trust_tier TEXT NOT NULL DEFAULT 'unknown',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS interaction_logs (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES persons(id),
    timestamp TIMESTAMP DEFAULT NOW(),
    summary TEXT
);
