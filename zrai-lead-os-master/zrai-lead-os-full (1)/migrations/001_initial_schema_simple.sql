-- ZRAI Lead OS - Initial Database Schema (Simplified - no pgvector)
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==================== LEADS TABLE ====================
CREATE TABLE IF NOT EXISTS leads (
    lead_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_name TEXT NOT NULL,
    category TEXT,
    location TEXT,
    geo_tags TEXT[] DEFAULT '{}',
    website TEXT,
    landing_page_url TEXT,
    phone TEXT,
    emails_found TEXT[] DEFAULT '{}',
    facebook_page TEXT,
    instagram TEXT,
    ads_active BOOLEAN DEFAULT false,
    ad_start_date TIMESTAMP,
    ad_last_seen TIMESTAMP,
    cta_type TEXT CHECK (cta_type IN ('CALL', 'FORM', 'BOOK', 'OTHER')),
    lead_form_detected BOOLEAN DEFAULT false,
    lead_lifecycle_state TEXT DEFAULT 'NEW' CHECK (lead_lifecycle_state IN 
        ('NEW', 'STALE', 'REACTIVATABLE', 'ENGAGED', 'QUALIFIED', 'CLOSED_WON', 'CLOSED_LOST')),
    last_contacted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_lifecycle ON leads(lead_lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_leads_last_contacted ON leads(last_contacted_at);
CREATE INDEX IF NOT EXISTS idx_leads_category ON leads(category);
CREATE INDEX IF NOT EXISTS idx_leads_geo ON leads USING GIN(geo_tags);
CREATE INDEX IF NOT EXISTS idx_leads_business_location ON leads(business_name, location);

-- ==================== LEAD STATE TABLE ====================
CREATE TABLE IF NOT EXISTS lead_state (
    lead_id UUID PRIMARY KEY REFERENCES leads(lead_id) ON DELETE CASCADE,
    current_stage TEXT NOT NULL,
    last_node TEXT NOT NULL,
    last_error TEXT,
    retry_count INTEGER DEFAULT 0,
    next_run_at TIMESTAMP,
    locks TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lead_state_next_run ON lead_state(next_run_at);
CREATE INDEX IF NOT EXISTS idx_lead_state_stage ON lead_state(current_stage);

-- ==================== ENRICHMENT DATA TABLE ====================
CREATE TABLE IF NOT EXISTS enrichment_data (
    lead_id UUID PRIMARY KEY REFERENCES leads(lead_id) ON DELETE CASCADE,
    enrichment_confidence DECIMAL(3,2) CHECK (enrichment_confidence BETWEEN 0 AND 1),
    booking_provider TEXT,
    crm_hint TEXT,
    chat_widget TEXT,
    form_tool TEXT,
    decision_maker_name TEXT,
    decision_maker_linkedin TEXT,
    contact_quality_score INTEGER CHECK (contact_quality_score BETWEEN 0 AND 100),
    normalized_phone TEXT,
    validated_emails TEXT[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== INTENT DATA TABLE ====================
CREATE TABLE IF NOT EXISTS intent_data (
    lead_id UUID PRIMARY KEY REFERENCES leads(lead_id) ON DELETE CASCADE,
    intent_score INTEGER CHECK (intent_score BETWEEN 0 AND 100),
    leak_score INTEGER CHECK (leak_score BETWEEN 0 AND 100),
    reactivation_fit INTEGER CHECK (reactivation_fit BETWEEN 0 AND 100),
    why_this_lead TEXT,
    speed_to_lead_risk TEXT CHECK (speed_to_lead_risk IN ('LOW', 'MED', 'HIGH')),
    review_evidence JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== PROOF ARTIFACTS TABLE ====================
CREATE TABLE IF NOT EXISTS proof_artifacts (
    lead_id UUID PRIMARY KEY REFERENCES leads(lead_id) ON DELETE CASCADE,
    hero_screenshot_url TEXT,
    cta_screenshot_url TEXT,
    audit_bullets JSONB DEFAULT '[]',
    extraction_data JSONB DEFAULT '{}',
    generated_at TIMESTAMP DEFAULT NOW()
);

-- ==================== SCORING RESULTS TABLE ====================
CREATE TABLE IF NOT EXISTS scoring_results (
    lead_id UUID PRIMARY KEY REFERENCES leads(lead_id) ON DELETE CASCADE,
    final_score INTEGER CHECK (final_score BETWEEN 0 AND 100),
    score_breakdown JSONB DEFAULT '{}',
    lead_tier TEXT CHECK (lead_tier IN ('A', 'B', 'C')),
    do_not_contact BOOLEAN DEFAULT false,
    do_not_contact_reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scoring_tier ON scoring_results(lead_tier);
CREATE INDEX IF NOT EXISTS idx_scoring_score ON scoring_results(final_score DESC);
CREATE INDEX IF NOT EXISTS idx_scoring_dnc ON scoring_results(do_not_contact);

-- ==================== OUTREACH QUEUE TABLE ====================
CREATE TABLE IF NOT EXISTS outreach_queue (
    outreach_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID REFERENCES leads(lead_id) ON DELETE CASCADE,
    channel TEXT CHECK (channel IN ('email', 'dm', 'form')),
    variant TEXT CHECK (variant IN ('A', 'B')),
    subject TEXT,
    body TEXT NOT NULL,
    attachments TEXT[] DEFAULT '{}',
    personalization JSONB DEFAULT '{}',
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'sent', 'rejected')),
    requires_approval BOOLEAN DEFAULT true,
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_queue(status);
CREATE INDEX IF NOT EXISTS idx_outreach_lead ON outreach_queue(lead_id);

-- ==================== CONVERSATIONS TABLE ====================
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID REFERENCES leads(lead_id) ON DELETE CASCADE,
    transcript JSONB DEFAULT '[]',
    entities JSONB DEFAULT '{}',
    objection_summary TEXT,
    suggested_close_angle TEXT,
    escalated BOOLEAN DEFAULT false,
    escalated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_lead ON conversations(lead_id);
CREATE INDEX IF NOT EXISTS idx_conversations_escalated ON conversations(escalated);

-- ==================== NEGATIVE SIGNALS TABLE ====================
CREATE TABLE IF NOT EXISTS negative_signals (
    signal_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID REFERENCES leads(lead_id) ON DELETE CASCADE,
    signal_type TEXT CHECK (signal_type IN ('opt_out', 'angry_reply', 'bounce', 'spam_complaint')),
    channel TEXT,
    sentiment_score DECIMAL(3,2),
    message_content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_negative_signals_lead ON negative_signals(lead_id);
CREATE INDEX IF NOT EXISTS idx_negative_signals_type ON negative_signals(signal_type);

-- ==================== DO NOT CONTACT TABLE ====================
CREATE TABLE IF NOT EXISTS do_not_contact (
    lead_id UUID PRIMARY KEY REFERENCES leads(lead_id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dnc_expires ON do_not_contact(expires_at);

-- ==================== AUDIT LOG TABLE ====================
CREATE TABLE IF NOT EXISTS audit_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),
    payload_hash TEXT,
    idempotency_key TEXT UNIQUE,
    result TEXT CHECK (result IN ('success', 'failure')),
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_idempotency ON audit_log(idempotency_key);

-- ==================== USAGE METRICS TABLE ====================
CREATE TABLE IF NOT EXISTS usage_metrics (
    metric_date DATE PRIMARY KEY,
    llm_tokens_used BIGINT DEFAULT 0,
    browser_sessions_used INTEGER DEFAULT 0,
    scraper_runs_used INTEGER DEFAULT 0,
    llm_cost_usd DECIMAL(10,2) DEFAULT 0,
    browser_cost_usd DECIMAL(10,2) DEFAULT 0,
    scraper_cost_usd DECIMAL(10,2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ==================== PLAYBOOKS TABLE (without vector) ====================
CREATE TABLE IF NOT EXISTS playbooks (
    playbook_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    niche TEXT,
    tier TEXT,
    channel TEXT,
    content_type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_playbooks_niche ON playbooks(niche);
CREATE INDEX IF NOT EXISTS idx_playbooks_tier ON playbooks(tier);
CREATE INDEX IF NOT EXISTS idx_playbooks_channel ON playbooks(channel);
CREATE INDEX IF NOT EXISTS idx_playbooks_type ON playbooks(content_type);

-- ==================== CIRCUIT BREAKERS TABLE ====================
CREATE TABLE IF NOT EXISTS circuit_breakers (
    node_name TEXT PRIMARY KEY,
    failure_count INTEGER DEFAULT 0,
    failure_threshold INTEGER DEFAULT 5,
    timeout_seconds INTEGER DEFAULT 300,
    state TEXT DEFAULT 'CLOSED' CHECK (state IN ('CLOSED', 'OPEN', 'HALF_OPEN')),
    last_failure_at TIMESTAMP,
    last_success_at TIMESTAMP
);

-- ==================== ESCALATIONS TABLE ====================
CREATE TABLE IF NOT EXISTS escalations (
    escalation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID REFERENCES leads(lead_id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(conversation_id),
    transcript JSONB DEFAULT '[]',
    entities JSONB DEFAULT '{}',
    objection_summary TEXT,
    suggested_close_angle TEXT,
    proof_pack JSONB,
    escalated_at TIMESTAMP DEFAULT NOW(),
    accepted_at TIMESTAMP,
    accepted_by TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'closed'))
);

CREATE INDEX IF NOT EXISTS idx_escalations_lead ON escalations(lead_id);
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);

-- ==================== GOLDEN DATASET TABLE ====================
CREATE TABLE IF NOT EXISTS golden_dataset (
    entry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID NOT NULL,
    input_data JSONB NOT NULL,
    expected_score INTEGER CHECK (expected_score BETWEEN 0 AND 100),
    expected_tier TEXT CHECK (expected_tier IN ('A', 'B', 'C')),
    expected_outreach_quality TEXT CHECK (expected_outreach_quality IN ('good', 'bad')),
    known_outcome TEXT CHECK (known_outcome IN ('replied', 'meeting', 'closed', 'no_response')),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== A/B TESTS TABLE ====================
CREATE TABLE IF NOT EXISTS ab_tests (
    test_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT UNIQUE NOT NULL,
    variants JSONB NOT NULL,
    metrics TEXT[] DEFAULT '{}',
    guardrails JSONB DEFAULT '{}',
    sample_size INTEGER DEFAULT 200,
    duration_days INTEGER DEFAULT 7,
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'rolled_back')),
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    rolled_back_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ab_tests_status ON ab_tests(status);
CREATE INDEX IF NOT EXISTS idx_ab_tests_name ON ab_tests(name);

-- ==================== A/B METRICS TABLE ====================
CREATE TABLE IF NOT EXISTS ab_metrics (
    metric_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    test_name TEXT NOT NULL,
    lead_id UUID,
    variant TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value DECIMAL(10,4) NOT NULL,
    recorded_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ab_metrics_test ON ab_metrics(test_name);
CREATE INDEX IF NOT EXISTS idx_ab_metrics_variant ON ab_metrics(variant);

-- ==================== DAILY METRICS TABLE ====================
CREATE TABLE IF NOT EXISTS daily_metrics (
    date DATE PRIMARY KEY,
    outreach_sent INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    meetings INTEGER DEFAULT 0,
    qualified INTEGER DEFAULT 0,
    reply_rate DECIMAL(5,4) DEFAULT 0,
    meeting_rate DECIMAL(5,4) DEFAULT 0,
    cost_per_qualified_meeting DECIMAL(10,2) DEFAULT 0,
    false_positive_rate DECIMAL(5,4) DEFAULT 0,
    human_override_rate DECIMAL(5,4) DEFAULT 0,
    total_cost_usd DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==================== HELPER FUNCTION ====================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_leads_updated_at ON leads;
CREATE TRIGGER update_leads_updated_at BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_lead_state_updated_at ON lead_state;
CREATE TRIGGER update_lead_state_updated_at BEFORE UPDATE ON lead_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations;
CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_playbooks_updated_at ON playbooks;
CREATE TRIGGER update_playbooks_updated_at BEFORE UPDATE ON playbooks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_usage_metrics_updated_at ON usage_metrics;
CREATE TRIGGER update_usage_metrics_updated_at BEFORE UPDATE ON usage_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Done!
SELECT 'Migration completed successfully!' as status;
