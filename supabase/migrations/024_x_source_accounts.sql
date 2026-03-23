-- Migration 024: X/Twitter source accounts for research pipeline scanning
-- Curated list of high-signal individual voices on the AI agent economy.
-- Accounts stored here can be managed via DB without code changes.

-- ═══════════════════════════════════════════════════════
-- x_source_accounts — X accounts scanned as research pipeline sources
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS x_source_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    x_handle        TEXT UNIQUE NOT NULL,
    display_name    TEXT,
    category        TEXT NOT NULL,                      -- macro, builder, crypto, curation
    description     TEXT,                               -- Why this account is relevant
    active          BOOLEAN DEFAULT TRUE,
    priority        INT DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_scanned_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_x_source_accounts_active
    ON x_source_accounts (active) WHERE active = TRUE;
CREATE INDEX IF NOT EXISTS idx_x_source_accounts_category
    ON x_source_accounts (category);

-- Seed the initial curated list
INSERT INTO x_source_accounts (x_handle, display_name, category, description, priority)
VALUES
    -- Macro/Strategic
    ('jvisserlabs',     'Jordi Visser',         'macro',    'AI × macro × crypto investment thesis',                7),
    ('emollick',        'Ethan Mollick',        'macro',    'AI impact on work/economy, Wharton',                   8),
    ('mattshumer_',     'Matt Shumer',          'macro',    'HyperWrite CEO, practitioner-builder',                 7),
    ('erikbryn',        'Erik Brynjolfsson',    'macro',    'Stanford Digital Economy Lab, AI labor',                7),
    -- Builder/Infrastructure
    ('swyx',            'Shawn Wang',           'builder',  'Latent Space, AI engineering, agent frameworks',        8),
    ('hwchase17',       'Harrison Chase',       'builder',  'LangChain, agent orchestration',                       8),
    ('yoheinakajima',   'Yohei Nakajima',       'builder',  'BabyAGI, VC + builder',                                7),
    ('DrJimFan',        'Jim Fan',              'builder',  'NVIDIA GEAR Lab, embodied agents',                     8),
    ('steipete',        'Peter Steinberger',    'builder',  'OpenClaw creator, now at OpenAI',                      7),
    -- AI × Crypto / Agent Commerce
    ('HighCoinviction', 'Daniel Cheung',        'crypto',   'Bittensor, agentic economy infra',                     6),
    ('S4mmyEth',        'S4mmyEth',             'crypto',   'AI agent analysis, crypto-AI intersection',            6),
    ('blknoiz06',       'Ansem',                'crypto',   'AI agent calls in crypto',                             6),
    -- Curation/Pulse
    ('rowancheung',     'Rowan Cheung',         'curation', 'The Rundown AI newsletter',                            7),
    ('andrewng',        'Andrew Ng',            'curation', 'Agentic reasoning frameworks',                         9)
ON CONFLICT (x_handle) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    category     = EXCLUDED.category,
    description  = EXCLUDED.description,
    priority     = EXCLUDED.priority;

-- Index on source_posts for x_source_* prefix (mirrors thought_leader index)
CREATE INDEX IF NOT EXISTS idx_source_posts_x_source
    ON source_posts(source) WHERE source LIKE 'x_source_%';

-- RLS policy (service_role bypasses, but for safety)
ALTER TABLE x_source_accounts ENABLE ROW LEVEL SECURITY;
