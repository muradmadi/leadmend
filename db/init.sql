-- Initialize LeadMend Database (User: leadmend)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    company_name VARCHAR(255),
    company_domain VARCHAR(255),
    industry VARCHAR(255),
    company_size VARCHAR(255),
    lead_score INTEGER DEFAULT 0,
    source VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- GIN index for fuzzy searching on company name
CREATE INDEX IF NOT EXISTS idx_leads_company_name_trgm ON leads USING gin (company_name gin_trgm_ops);
