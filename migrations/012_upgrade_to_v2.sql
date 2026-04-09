-- ============================================================================
-- Migration 012 UPGRADE: Upgrade existing schema to v2
-- ============================================================================
-- This script upgrades the existing schema to the v2 version by adding
-- missing columns and tables.
-- ============================================================================

-- 1. Add missing columns to unknown_unknowns_runs
ALTER TABLE unknown_unknowns_runs
ADD COLUMN IF NOT EXISTS insights_scored_for_delivery INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS insights_sent_to_refinement INT DEFAULT 0;

-- 2. Add missing columns to unknown_unknowns_insights
ALTER TABLE unknown_unknowns_insights
ADD COLUMN IF NOT EXISTS if_true_then TEXT,
ADD COLUMN IF NOT EXISTS if_false_then TEXT,
ADD COLUMN IF NOT EXISTS decision_owner VARCHAR(100),
ADD COLUMN IF NOT EXISTS action_threshold JSONB,
ADD COLUMN IF NOT EXISTS portfolio_type VARCHAR(50) CHECK (portfolio_type IN ('quick_win', 'medium_term', 'strategic_bet')),
ADD COLUMN IF NOT EXISTS confidence_total FLOAT CHECK (confidence_total BETWEEN 0 AND 100),
ADD COLUMN IF NOT EXISTS confidence_statistical FLOAT,
ADD COLUMN IF NOT EXISTS confidence_data_quality FLOAT,
ADD COLUMN IF NOT EXISTS confidence_model FLOAT,
ADD COLUMN IF NOT EXISTS confidence_caveats JSONB,
ADD COLUMN IF NOT EXISTS counterfactual_past JSONB,
ADD COLUMN IF NOT EXISTS counterfactual_present JSONB,
ADD COLUMN IF NOT EXISTS counterfactual_future JSONB,
ADD COLUMN IF NOT EXISTS delivery_score_total FLOAT CHECK (delivery_score_total BETWEEN 0 AND 100),
ADD COLUMN IF NOT EXISTS delivery_score_breakdown JSONB,
ADD COLUMN IF NOT EXISTS should_deliver BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS needs_human_review BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(255),
ADD COLUMN IF NOT EXISTS review_decision VARCHAR(50) CHECK (review_decision IN ('approve', 'reject', 'needs_refinement', NULL)),
ADD COLUMN IF NOT EXISTS review_notes TEXT,
ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITH TIME ZONE;

-- 3. Create hypothesis_graveyard table if not exists
CREATE TABLE IF NOT EXISTS hypothesis_graveyard (
    hypothesis_id VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES business_profiles(client_id) ON DELETE CASCADE,
    hypothesis_text TEXT NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN (
        'useful',
        'rejected',
        'already_tried',
        'politically_impossible'
    )),
    business_impact_realized_usd DECIMAL(15,2),
    action_taken TEXT,
    who_acted VARCHAR(255),
    when_acted TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,
    rejected_by VARCHAR(255),
    when_tried TIMESTAMP WITH TIME ZONE,
    why_failed TEXT,
    context_then_vs_now TEXT,
    why_impossible TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_graveyard_client ON hypothesis_graveyard(client_id);
CREATE INDEX IF NOT EXISTS idx_graveyard_category ON hypothesis_graveyard(category);
CREATE INDEX IF NOT EXISTS idx_graveyard_useful ON hypothesis_graveyard(category, business_impact_realized_usd DESC)
    WHERE category = 'useful';

-- 4. Create human_review_queue table if not exists
CREATE TABLE IF NOT EXISTS human_review_queue (
    queue_id SERIAL PRIMARY KEY,
    insight_id INT NOT NULL REFERENCES unknown_unknowns_insights(insight_id) ON DELETE CASCADE,
    client_id VARCHAR(255) NOT NULL,
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    assigned_to VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'in_review', 'completed')),
    priority INT,
    metadata JSONB,
    UNIQUE(insight_id)
);

CREATE INDEX IF NOT EXISTS idx_review_queue_status ON human_review_queue(status);
CREATE INDEX IF NOT EXISTS idx_review_queue_assigned ON human_review_queue(assigned_to) WHERE assigned_to IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_review_queue_priority ON human_review_queue(priority DESC, queued_at);
CREATE INDEX IF NOT EXISTS idx_review_queue_client ON human_review_queue(client_id);

-- 5. Create new indexes for new columns
CREATE INDEX IF NOT EXISTS idx_insights_should_deliver ON unknown_unknowns_insights(should_deliver);
CREATE INDEX IF NOT EXISTS idx_insights_portfolio ON unknown_unknowns_insights(portfolio_type);
CREATE INDEX IF NOT EXISTS idx_insights_needs_review ON unknown_unknowns_insights(needs_human_review);
CREATE INDEX IF NOT EXISTS idx_insights_caveats_gin ON unknown_unknowns_insights USING GIN(confidence_caveats);

-- 6. Update triggers
DROP TRIGGER IF EXISTS update_hypothesis_graveyard_updated_at ON hypothesis_graveyard;
CREATE TRIGGER update_hypothesis_graveyard_updated_at
    BEFORE UPDATE ON hypothesis_graveyard
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_insights_updated_at ON unknown_unknowns_insights;
CREATE TRIGGER update_insights_updated_at
    BEFORE UPDATE ON unknown_unknowns_insights
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 7. Drop and recreate functions with new signatures
DROP FUNCTION IF EXISTS get_top_insights(VARCHAR, INT, BOOLEAN);
CREATE OR REPLACE FUNCTION get_top_insights(
    p_client_id VARCHAR(255),
    p_limit INT DEFAULT 10,
    p_delivered_only BOOLEAN DEFAULT FALSE
)
RETURNS TABLE (
    insight_id INT,
    hypothesis_text TEXT,
    analysis TEXT,
    priority INT,
    portfolio_type VARCHAR(50),
    category VARCHAR(100),
    business_impact_usd DECIMAL(15,2),
    delivery_score_total FLOAT,
    should_deliver BOOLEAN,
    delivered BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        i.insight_id,
        i.hypothesis_text,
        i.analysis,
        i.priority,
        i.portfolio_type,
        i.category,
        i.business_impact_usd,
        i.delivery_score_total,
        i.should_deliver,
        i.delivered,
        i.created_at
    FROM unknown_unknowns_insights i
    WHERE i.client_id = p_client_id
      AND (NOT p_delivered_only OR i.delivered = TRUE)
    ORDER BY i.priority DESC, i.delivery_score_total DESC NULLS LAST, i.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

DROP FUNCTION IF EXISTS finalize_run(INT);
CREATE OR REPLACE FUNCTION finalize_run(p_run_id INT)
RETURNS void AS $$
DECLARE
    v_started_at TIMESTAMP WITH TIME ZONE;
    v_insights_count INT;
    v_insights_scored INT;
    v_delivered_count INT;
    v_refinement_count INT;
BEGIN
    SELECT started_at INTO v_started_at
    FROM unknown_unknowns_runs
    WHERE run_id = p_run_id;

    SELECT
        COUNT(*),
        SUM(CASE WHEN should_deliver = TRUE THEN 1 ELSE 0 END),
        SUM(CASE WHEN delivered = TRUE THEN 1 ELSE 0 END),
        SUM(CASE WHEN should_deliver = FALSE AND delivery_score_total IS NOT NULL THEN 1 ELSE 0 END)
    INTO v_insights_count, v_insights_scored, v_delivered_count, v_refinement_count
    FROM unknown_unknowns_insights
    WHERE run_id = p_run_id;

    UPDATE unknown_unknowns_runs
    SET
        completed_at = NOW(),
        status = 'completed',
        hypotheses_validated = v_insights_count,
        insights_scored_for_delivery = v_insights_scored,
        insights_delivered = v_delivered_count,
        insights_sent_to_refinement = v_refinement_count,
        execution_time_seconds = EXTRACT(EPOCH FROM (NOW() - v_started_at))::INT
    WHERE run_id = p_run_id;

    UPDATE business_profiles
    SET last_hypothesis_run = NOW()
    WHERE client_id = (
        SELECT client_id FROM unknown_unknowns_runs WHERE run_id = p_run_id
    );
END;
$$ LANGUAGE plpgsql;

-- 8. Recreate views with updated columns
DROP VIEW IF EXISTS v_pending_insights;
CREATE OR REPLACE VIEW v_pending_insights AS
SELECT
    i.insight_id,
    i.client_id,
    bp.profile_data->>'company_name' as company_name,
    i.hypothesis_text,
    i.analysis,
    i.priority,
    i.portfolio_type,
    i.category,
    i.business_impact_usd,
    i.delivery_score_total,
    i.should_deliver,
    i.needs_human_review,
    i.created_at,
    r.run_type
FROM unknown_unknowns_insights i
JOIN business_profiles bp ON i.client_id = bp.client_id
JOIN unknown_unknowns_runs r ON i.run_id = r.run_id
WHERE i.delivered = FALSE
  AND i.should_deliver = TRUE
  AND (i.needs_human_review = FALSE OR i.review_decision = 'approve')
ORDER BY i.priority DESC, i.delivery_score_total DESC, i.created_at DESC;

DROP VIEW IF EXISTS v_runs_performance;
CREATE OR REPLACE VIEW v_runs_performance AS
SELECT
    r.client_id,
    bp.profile_data->>'company_name' as company_name,
    r.run_type,
    COUNT(*) as total_runs,
    AVG(r.hypotheses_generated) as avg_hypotheses_generated,
    AVG(r.hypotheses_validated) as avg_hypotheses_validated,
    AVG(r.insights_scored_for_delivery) as avg_insights_scored,
    AVG(r.insights_delivered) as avg_insights_delivered,
    AVG(r.insights_sent_to_refinement) as avg_insights_refinement,
    AVG(r.execution_time_seconds) as avg_execution_time_seconds,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) as successful_runs,
    SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) as failed_runs
FROM unknown_unknowns_runs r
JOIN business_profiles bp ON r.client_id = bp.client_id
GROUP BY r.client_id, bp.profile_data->>'company_name', r.run_type;

DROP VIEW IF EXISTS v_insights_feedback;
CREATE OR REPLACE VIEW v_insights_feedback AS
SELECT
    i.client_id,
    bp.profile_data->>'company_name' as company_name,
    i.category,
    i.insight_type,
    i.portfolio_type,
    i.priority,
    i.user_feedback,
    COUNT(*) as count,
    AVG(i.business_impact_usd) as avg_impact_estimated,
    AVG(i.business_impact_realized_usd) as avg_impact_realized,
    AVG(i.delivery_score_total) as avg_delivery_score,
    AVG(i.confidence_total) as avg_confidence
FROM unknown_unknowns_insights i
JOIN business_profiles bp ON i.client_id = bp.client_id
WHERE i.user_feedback IS NOT NULL
GROUP BY
    i.client_id,
    bp.profile_data->>'company_name',
    i.category,
    i.insight_type,
    i.portfolio_type,
    i.priority,
    i.user_feedback;

DROP VIEW IF EXISTS v_human_review_workload;
CREATE OR REPLACE VIEW v_human_review_workload AS
SELECT
    hrq.assigned_to,
    hrq.status,
    COUNT(*) as total_items,
    AVG(EXTRACT(EPOCH FROM (NOW() - hrq.queued_at))/3600) as avg_hours_waiting,
    MIN(hrq.priority) as highest_priority,
    STRING_AGG(DISTINCT hrq.client_id, ', ') as clients
FROM human_review_queue hrq
WHERE hrq.status != 'completed'
GROUP BY hrq.assigned_to, hrq.status
ORDER BY highest_priority, total_items DESC;

-- ============================================================================
-- END OF UPGRADE MIGRATION
-- ============================================================================
