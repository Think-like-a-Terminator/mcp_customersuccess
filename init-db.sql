-- Initialize Customer Success Database
-- This script sets up sample tables for testing

-- Create users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    hashed_password TEXT NOT NULL,
    disabled BOOLEAN DEFAULT FALSE,
    scopes TEXT[] DEFAULT ARRAY['read', 'write'],
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create api_keys table for API key authentication
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create customers table
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(100) UNIQUE NOT NULL,  -- External account ID
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create call_to_actions table
CREATE TABLE IF NOT EXISTS call_to_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    priority VARCHAR(20) NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'completed', 'cancelled')),
    owner VARCHAR(255),
    due_date TIMESTAMP,
    completed_at TIMESTAMP,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create health_scores table (enhanced version)
CREATE TABLE IF NOT EXISTS health_scores (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(100) UNIQUE NOT NULL,
    overall_score DECIMAL(5,2) NOT NULL CHECK (overall_score >= 0 AND overall_score <= 100),
    status VARCHAR(20) NOT NULL CHECK (status IN ('excellent', 'good', 'at_risk', 'critical')),
    metrics JSONB NOT NULL DEFAULT '[]',  -- Array of metric objects
    trend VARCHAR(20) DEFAULT 'stable' CHECK (trend IN ('improving', 'declining', 'stable')),
    last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create surveys table
CREATE TABLE IF NOT EXISTS surveys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_id VARCHAR(100) UNIQUE NOT NULL,
    account_id VARCHAR(100) NOT NULL,
    survey_type VARCHAR(20) NOT NULL CHECK (survey_type IN ('nps', 'csat', 'custom')),
    recipient_email VARCHAR(255) NOT NULL,
    subject VARCHAR(500),
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_received BOOLEAN DEFAULT FALSE,
    response_score INTEGER,
    response_feedback TEXT,
    response_at TIMESTAMP
);

-- Create risk_alerts table
CREATE TABLE IF NOT EXISTS risk_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(100) NOT NULL,
    risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('none', 'low', 'medium', 'high')),
    risk_factors TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    impact_score DECIMAL(5,2) CHECK (impact_score >= 0 AND impact_score <= 100),
    recommended_actions TEXT[] DEFAULT ARRAY[]::TEXT[],
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create interactions table
CREATE TABLE IF NOT EXISTS interactions (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    interaction_type VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
INSERT INTO customers (account_id, name, email, status) VALUES
    ('acct-001', 'Acme Corporation', 'contact@acme.com', 'active'),
    ('acct-002', 'TechStart Inc', 'hello@techstart.com', 'active'),
    ('acct-003', 'Global Solutions Ltd', 'info@globalsolutions.com', 'active'),
    ('acct-004', 'Digital Dynamics', 'support@digitaldynamics.com', 'at-risk'),
    ('acct-005', 'Innovation Labs', 'team@innovationlabs.com', 'active')
ON CONFLICT (email) DO NOTHING;

-- Insert sample health scores
INSERT INTO health_scores (account_id, overall_score, status, metrics, trend) VALUES
    ('acct-001', 85.5, 'excellent',
     '[{"name":"product_usage","value":90.0,"weight":0.25},{"name":"engagement_score","value":88.0,"weight":0.25},{"name":"support_health","value":92.0,"weight":0.25},{"name":"nps_score","value":72.0,"weight":0.25}]'::jsonb,
     'improving'),
    ('acct-002', 72.0, 'good',
     '[{"name":"product_usage","value":75.0,"weight":0.25},{"name":"engagement_score","value":70.0,"weight":0.25},{"name":"support_health","value":80.0,"weight":0.25},{"name":"nps_score","value":63.0,"weight":0.25}]'::jsonb,
     'stable'),
    ('acct-003', 68.5, 'good',
     '[{"name":"product_usage","value":70.0,"weight":0.25},{"name":"engagement_score","value":65.0,"weight":0.25},{"name":"support_health","value":74.0,"weight":0.25},{"name":"nps_score","value":65.0,"weight":0.25}]'::jsonb,
     'stable'),
    ('acct-004', 38.0, 'at_risk',
     '[{"name":"product_usage","value":30.0,"weight":0.25},{"name":"engagement_score","value":40.0,"weight":0.25},{"name":"support_health","value":25.0,"weight":0.25},{"name":"nps_score","value":57.0,"weight":0.25}]'::jsonb,
     'declining'),
    ('acct-005', 92.0, 'excellent',
     '[{"name":"product_usage","value":95.0,"weight":0.25},{"name":"engagement_score","value":93.0,"weight":0.25},{"name":"support_health","value":98.0,"weight":0.25},{"name":"nps_score","value":82.0,"weight":0.25}]'::jsonb,
     'improving')
ON CONFLICT (account_id) DO NOTHING;

-- Insert sample CTAs
INSERT INTO call_to_actions (id, account_id, title, description, priority, status, owner, due_date, tags) VALUES
    (gen_random_uuid(), 'acct-001', 'Schedule Q3 Business Review', 'Coordinate QBR agenda, attendees, and success metrics with the executive sponsor.', 'high', 'open', 'Sarah Johnson', NOW() + INTERVAL '14 days', ARRAY['qbr','executive']),
    (gen_random_uuid(), 'acct-001', 'Upsell Advanced Analytics Add-on', 'Demo the new analytics dashboard; account is a strong fit based on current usage patterns.', 'medium', 'in_progress', 'Sarah Johnson', NOW() + INTERVAL '21 days', ARRAY['upsell','expansion']),
    (gen_random_uuid(), 'acct-002', 'Complete Onboarding Checklist', 'Three onboarding steps still pending: SSO setup, data import, and admin training.', 'high', 'open', 'Mike Chen', NOW() + INTERVAL '7 days', ARRAY['onboarding']),
    (gen_random_uuid(), 'acct-003', 'Renewal Discussion', 'Contract renews in 60 days. Schedule renewal call and prepare commercial proposal.', 'medium', 'open', 'Sarah Johnson', NOW() + INTERVAL '30 days', ARRAY['renewal']),
    (gen_random_uuid(), 'acct-004', 'Executive Escalation Call', 'Usage has dropped 40% MoM. Escalate to VP level to identify blockers and create recovery plan.', 'urgent', 'open', 'Mike Chen', NOW() + INTERVAL '3 days', ARRAY['at-risk','escalation']),
    (gen_random_uuid(), 'acct-004', 'Send Product Adoption Guide', 'Share the advanced feature adoption playbook to re-engage the user base.', 'high', 'open', 'Mike Chen', NOW() + INTERVAL '5 days', ARRAY['at-risk','adoption']),
    (gen_random_uuid(), 'acct-005', 'Case Study Interview', 'Account is an ideal reference customer. Schedule a 30-min interview for marketing case study.', 'low', 'open', 'Sarah Johnson', NOW() + INTERVAL '45 days', ARRAY['advocacy','marketing'])
ON CONFLICT DO NOTHING;

-- Insert sample risk alerts
INSERT INTO risk_alerts (id, account_id, risk_level, risk_factors, impact_score, recommended_actions, acknowledged, notes) VALUES
    (gen_random_uuid(), 'acct-004', 'high',
     ARRAY['Product usage dropped 40% month-over-month', 'No logins in 18 days', 'Three open support tickets unresolved > 14 days', 'Executive sponsor left the company'],
     87.0,
     ARRAY['Schedule executive escalation call within 48 hours', 'Assign dedicated CSM for recovery plan', 'Offer complimentary admin training session', 'Review and resolve outstanding support tickets'],
     false,
     'Account was previously healthy (score 78) as recently as 60 days ago. Rapid decline correlates with sponsor departure.'),
    (gen_random_uuid(), 'acct-003', 'medium',
     ARRAY['Renewal in 60 days with no renewal conversation started', 'NPS score declined from 72 to 65 last quarter', 'Feature adoption rate below segment average'],
     62.0,
     ARRAY['Initiate renewal conversation by end of week', 'Share feature adoption tips and best practice guide', 'Invite to upcoming customer webinar'],
     false,
     NULL)
ON CONFLICT DO NOTHING;

-- Insert sample interactions
INSERT INTO interactions (customer_id, interaction_type, notes) VALUES
    (1, 'support', 'Resolved billing issue'),
    (1, 'training', 'Conducted onboarding session'),
    (2, 'support', 'Product feature question'),
    (3, 'training', 'Advanced features training'),
    (4, 'support', 'Multiple support tickets this month'),
    (5, 'training', 'Admin training completed');

-- ─── OAuth 2.1 Tables ────────────────────────────────────────────────────────

-- Registered OAuth clients (RFC7591 Dynamic Client Registration)
CREATE TABLE IF NOT EXISTS oauth_clients (
    id TEXT PRIMARY KEY,                                -- client_id
    client_secret TEXT,                                 -- NULL for public clients
    client_name TEXT NOT NULL,
    redirect_uris TEXT[] NOT NULL,
    grant_types TEXT[] DEFAULT ARRAY['authorization_code'],
    response_types TEXT[] DEFAULT ARRAY['code'],
    scope TEXT DEFAULT 'read write',
    token_endpoint_auth_method TEXT DEFAULT 'none',     -- 'none' = public (PKCE only)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Short-lived, single-use authorization codes
CREATE TABLE IF NOT EXISTS oauth_auth_codes (
    code TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES oauth_clients(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    redirect_uri TEXT NOT NULL,
    scope TEXT,
    code_challenge TEXT NOT NULL,
    code_challenge_method TEXT NOT NULL DEFAULT 'S256',
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Issued access and refresh tokens
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id SERIAL PRIMARY KEY,
    access_token_hash TEXT UNIQUE NOT NULL,
    refresh_token_hash TEXT UNIQUE NOT NULL,
    client_id TEXT NOT NULL REFERENCES oauth_clients(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scope TEXT,
    access_token_expires_at TIMESTAMP NOT NULL,
    refresh_token_expires_at TIMESTAMP NOT NULL,
    revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_oauth_tokens_access_hash  ON oauth_tokens(access_token_hash);
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_refresh_hash ON oauth_tokens(refresh_token_hash);
CREATE INDEX IF NOT EXISTS idx_oauth_auth_codes_code      ON oauth_auth_codes(code);
CREATE INDEX IF NOT EXISTS idx_oauth_clients_id           ON oauth_clients(id);

-- ─── End OAuth Tables ─────────────────────────────────────────────────────────

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(verification_token);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active);
CREATE INDEX IF NOT EXISTS idx_api_keys_created_by ON api_keys(created_by);
CREATE INDEX IF NOT EXISTS idx_customers_account_id ON customers(account_id);
CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(status);
CREATE INDEX IF NOT EXISTS idx_ctas_account_id ON call_to_actions(account_id);
CREATE INDEX IF NOT EXISTS idx_ctas_status ON call_to_actions(status);
CREATE INDEX IF NOT EXISTS idx_ctas_priority ON call_to_actions(priority);
CREATE INDEX IF NOT EXISTS idx_ctas_due_date ON call_to_actions(due_date);
CREATE INDEX IF NOT EXISTS idx_health_scores_account_id ON health_scores(account_id);
CREATE INDEX IF NOT EXISTS idx_health_scores_status ON health_scores(status);
CREATE INDEX IF NOT EXISTS idx_surveys_account_id ON surveys(account_id);
CREATE INDEX IF NOT EXISTS idx_surveys_survey_id ON surveys(survey_id);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_account_id ON risk_alerts(account_id);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_risk_level ON risk_alerts(risk_level);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_acknowledged ON risk_alerts(acknowledged);
CREATE INDEX IF NOT EXISTS idx_interactions_customer ON interactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_interactions_created ON interactions(created_at);

-- Insert default admin user (password: admin123)
INSERT INTO users (username, email, full_name, hashed_password, scopes, email_verified) VALUES
    ('admin', 'admin@example.com', 'Administrator', '$2b$12$qaVjaRoZglTvoJVmrW29s.v9YCBEHXa/uqMlCsPXryeBhzqMVnFUq', ARRAY['read', 'write', 'admin'], true)
ON CONFLICT (username) DO NOTHING;

-- Grant permissions (if needed)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
