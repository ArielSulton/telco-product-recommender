-- ==============================================
-- Complaints Runtime Signal
-- ==============================================
-- Stores user complaints and exposes complaint_count as a retention signal.

CREATE TABLE IF NOT EXISTS complaints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT check_complaints_status
        CHECK (status IN ('open', 'reviewed', 'resolved'))
);

CREATE INDEX IF NOT EXISTS idx_complaints_user_created
ON complaints(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_complaints_status
ON complaints(status);

ALTER TABLE app_users
ADD COLUMN IF NOT EXISTS complaint_count INTEGER DEFAULT 0 CHECK (complaint_count >= 0);

COMMENT ON TABLE complaints IS 'User complaints used as a runtime retention signal.';
COMMENT ON COLUMN app_users.complaint_count IS 'Total complaint count used by the recommender for retention signals.';
