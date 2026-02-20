-- AI Healthcare Triage System Database Schema
-- PostgreSQL 15+

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    age INTEGER,
    gender VARCHAR(20) CHECK (gender IN ('male', 'female', 'other', 'prefer_not_to_say')),
    comorbidities TEXT[], -- e.g. ['diabetes', 'hypertension']
    language_preference VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Triage sessions
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    chief_complaint TEXT,
    patient_age INTEGER,
    patient_gender VARCHAR(20),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    question_index INTEGER DEFAULT 0,
    total_questions INTEGER DEFAULT 0
);

-- Extracted symptoms per session
CREATE TABLE IF NOT EXISTS session_symptoms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    symptom_key VARCHAR(100) NOT NULL,
    raw_text TEXT,
    severity INTEGER CHECK (severity BETWEEN 1 AND 10),
    duration_text VARCHAR(100),
    duration_hours FLOAT,
    body_location VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Q&A log per session
CREATE TABLE IF NOT EXISTS session_qa_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    question_id VARCHAR(100),
    question_text TEXT,
    answer_text TEXT,
    answer_type VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Triage results
CREATE TABLE IF NOT EXISTS triage_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    triage_label VARCHAR(30) NOT NULL CHECK (triage_label IN ('Emergency', 'Urgent', 'HomeCare')),
    confidence FLOAT,
    probabilities JSONB,
    red_flag_triggered BOOLEAN DEFAULT FALSE,
    red_flag_reason TEXT,
    shap_values JSONB,
    explanation_text TEXT,
    recommended_action TEXT,
    diseases_considered TEXT[],
    remedies TEXT[],
    nutrition_tips TEXT[],
    crisis_response BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit logs (anonymized)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID, -- not a FK to allow orphaned audit entries
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB,
    ip_hash VARCHAR(64), -- hashed IP for anonymization
    user_agent_hash VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_session_symptoms_session_id ON session_symptoms(session_id);
CREATE INDEX IF NOT EXISTS idx_triage_results_session_id ON triage_results(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
