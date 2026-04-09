-- ============================================================================
-- Migration 012 v2: Unknown Unknowns Agent (UPDATED)
-- ============================================================================
--
-- Este módulo implementa el Unknown Unknowns Agent basado en la filosofía
-- de la Ventana de Johari aplicada a datos empresariales.
--
-- VERSIÓN 2 - Cambios principales:
-- - Agregado: hypothesis_graveyard (4 categorías de tracking)
-- - Agregado: human_review_queue (primeros 6 meses)
-- - Actualizado: unknown_unknowns_insights (actionability, confidence multi-dimensional, counterfactuals)
-- - Actualizado: unknown_unknowns_runs (métricas adicionales)
--
-- Tablas:
-- 1. business_profiles
-- 2. hypothesis_graveyard (NUEVO)
-- 3. unknown_unknowns_runs
-- 4. unknown_unknowns_insights (ACTUALIZADO)
-- 5. human_review_queue (NUEVO)
--
-- ============================================================================

-- ============================================================================
-- 1. BUSINESS PROFILES
-- ============================================================================
-- Almacena el perfil completo de cada cliente, usado para contextualizar
-- la generación de hipótesis y análisis de insights.

CREATE TABLE IF NOT EXISTS business_profiles (
    -- Identificación
    client_id VARCHAR(255) PRIMARY KEY,

    -- Perfil completo (JSON)
    -- Almacena toda la información del BusinessProfile Pydantic model
    -- INCLUYE: industry_orthodoxies (creencias no cuestionadas detectadas automáticamente)
    profile_data JSONB NOT NULL,

    -- Métricas de calidad del perfil
    profile_completeness FLOAT DEFAULT 0.0 CHECK (profile_completeness >= 0.0 AND profile_completeness <= 1.0),
    confidence_score FLOAT DEFAULT 0.5 CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_enrichment TIMESTAMP WITH TIME ZONE,
    last_hypothesis_run TIMESTAMP WITH TIME ZONE,

    -- Configuración
    is_active BOOLEAN DEFAULT TRUE,
    insights_enabled BOOLEAN DEFAULT TRUE
);

-- Índices para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_business_profiles_industry
    ON business_profiles((profile_data->>'industry'));

CREATE INDEX IF NOT EXISTS idx_business_profiles_business_model
    ON business_profiles((profile_data->>'business_model'));

CREATE INDEX IF NOT EXISTS idx_business_profiles_completeness
    ON business_profiles(profile_completeness DESC);

CREATE INDEX IF NOT EXISTS idx_business_profiles_active
    ON business_profiles(is_active, insights_enabled)
    WHERE is_active = TRUE AND insights_enabled = TRUE;

CREATE INDEX IF NOT EXISTS idx_business_profiles_last_run
    ON business_profiles(last_hypothesis_run);

-- GIN index para búsquedas avanzadas en JSONB (incluye orthodoxies)
CREATE INDEX IF NOT EXISTS idx_business_profiles_data_gin
    ON business_profiles USING GIN(profile_data);

-- Comentarios
COMMENT ON TABLE business_profiles IS 'Perfiles de negocio de clientes para contextualizar generación de hipótesis';
COMMENT ON COLUMN business_profiles.profile_data IS 'Perfil completo en formato JSON (BusinessProfile Pydantic model) - INCLUYE industry_orthodoxies';
COMMENT ON COLUMN business_profiles.profile_completeness IS 'Score de completitud del perfil (0.0-1.0) - Orthodoxies suman 10% al score';
COMMENT ON COLUMN business_profiles.confidence_score IS 'Score de confianza en la precisión del perfil (0.0-1.0)';
COMMENT ON COLUMN business_profiles.last_enrichment IS 'Última vez que se enriqueció el perfil automáticamente';
COMMENT ON COLUMN business_profiles.last_hypothesis_run IS 'Última ejecución del análisis de Unknown Unknowns';


-- ============================================================================
-- 2. HYPOTHESIS GRAVEYARD (NUEVO)
-- ============================================================================
-- Tracking histórico de hipótesis en 4 categorías.
-- Esencial para aprender qué funciona y evitar repetir errores.

CREATE TABLE IF NOT EXISTS hypothesis_graveyard (
    hypothesis_id VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES business_profiles(client_id) ON DELETE CASCADE,
    hypothesis_text TEXT NOT NULL,

    -- Categoría (4 posibles)
    category VARCHAR(50) NOT NULL CHECK (category IN (
        'useful',                -- Insight fue útil, cliente tomó acción
        'rejected',              -- Cliente dijo "no es relevante"
        'already_tried',         -- Cliente ya intentó esto antes y falló
        'politically_impossible' -- Políticamente imposible de implementar
    )),

    -- ===== PARA 'useful' =====
    business_impact_realized_usd DECIMAL(15,2),
    action_taken TEXT,
    who_acted VARCHAR(255),
    when_acted TIMESTAMP WITH TIME ZONE,

    -- ===== PARA 'rejected' =====
    rejection_reason TEXT,
    rejected_by VARCHAR(255),

    -- ===== PARA 'already_tried' =====
    when_tried TIMESTAMP WITH TIME ZONE,
    why_failed TEXT,
    context_then_vs_now TEXT,  -- ¿Qué cambió que podría hacer que funcione ahora?

    -- ===== PARA 'politically_impossible' =====
    why_impossible TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_graveyard_client ON hypothesis_graveyard(client_id);
CREATE INDEX IF NOT EXISTS idx_graveyard_category ON hypothesis_graveyard(category);
CREATE INDEX IF NOT EXISTS idx_graveyard_useful ON hypothesis_graveyard(category, business_impact_realized_usd DESC)
    WHERE category = 'useful';

COMMENT ON TABLE hypothesis_graveyard IS 'Tracking histórico de hipótesis en 4 categorías para aprendizaje';
COMMENT ON COLUMN hypothesis_graveyard.category IS 'useful | rejected | already_tried | politically_impossible';
COMMENT ON COLUMN hypothesis_graveyard.context_then_vs_now IS 'Para already_tried: qué cambió que podría hacer que funcione ahora';


-- ============================================================================
-- 3. UNKNOWN UNKNOWNS RUNS
-- ============================================================================
-- Registro de cada ejecución del análisis de Unknown Unknowns.

CREATE TABLE IF NOT EXISTS unknown_unknowns_runs (
    -- Identificación
    run_id SERIAL PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES business_profiles(client_id) ON DELETE CASCADE,

    -- Configuración de la ejecución
    run_type VARCHAR(50) NOT NULL CHECK (run_type IN ('daily', 'weekly', 'monthly', 'ad_hoc')),
    focus_area VARCHAR(100),  -- 'financial', 'operational', 'commercial', 'supply_chain', NULL (all)
    max_hypotheses INT DEFAULT 20,
    max_insights_to_deliver INT DEFAULT 5,

    -- Timestamps
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Estado
    status VARCHAR(50) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),

    -- Métricas de resultado (ACTUALIZADAS)
    hypotheses_generated INT DEFAULT 0,
    hypotheses_validated INT DEFAULT 0,
    insights_scored_for_delivery INT DEFAULT 0,  -- NUEVO: cuántos pasaron scoring
    insights_delivered INT DEFAULT 0,
    insights_sent_to_refinement INT DEFAULT 0,   -- NUEVO: cuántos fueron a refinement

    -- Performance
    execution_time_seconds INT,
    sql_execution_time_ms INT,

    -- Error tracking
    error_message TEXT,
    error_stack_trace TEXT,

    -- Metadata adicional
    metadata JSONB,

    -- Configuración usada
    config_snapshot JSONB
);

CREATE INDEX IF NOT EXISTS idx_runs_client ON unknown_unknowns_runs(client_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON unknown_unknowns_runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_started ON unknown_unknowns_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_client_type ON unknown_unknowns_runs(client_id, run_type);
CREATE INDEX IF NOT EXISTS idx_runs_focus_area ON unknown_unknowns_runs(focus_area) WHERE focus_area IS NOT NULL;

COMMENT ON TABLE unknown_unknowns_runs IS 'Registro de ejecuciones del análisis de Unknown Unknowns';
COMMENT ON COLUMN unknown_unknowns_runs.insights_scored_for_delivery IS 'Cuántos insights pasaron el delivery score threshold';
COMMENT ON COLUMN unknown_unknowns_runs.insights_sent_to_refinement IS 'Cuántos insights fueron a refinement loop';


-- ============================================================================
-- 4. UNKNOWN UNKNOWNS INSIGHTS (ACTUALIZADO)
-- ============================================================================
-- Almacena cada insight generado, con ACTIONABILITY BUILT-IN.

CREATE TABLE IF NOT EXISTS unknown_unknowns_insights (
    -- Identificación
    insight_id SERIAL PRIMARY KEY,
    run_id INT NOT NULL REFERENCES unknown_unknowns_runs(run_id) ON DELETE CASCADE,
    client_id VARCHAR(255) NOT NULL REFERENCES business_profiles(client_id) ON DELETE CASCADE,

    -- ===== HIPÓTESIS =====
    hypothesis_id VARCHAR(255) NOT NULL,
    hypothesis_text TEXT NOT NULL,
    business_rationale TEXT NOT NULL,
    strategic_alignment TEXT,  -- A cuál prioridad estratégica se alinea

    -- ===== ACTIONABILITY (BUILT-IN) - NUEVO =====
    if_true_then TEXT NOT NULL,  -- "Si esto es verdad, deberíamos [acción específica]"
    if_false_then TEXT,          -- "Si esto es falso, confirma que [status quo está bien]"
    decision_owner VARCHAR(100), -- CFO, COO, CEO, Sales Manager, etc.
    action_threshold JSONB,      -- {"min_impact_usd": 50000, "min_confidence": 0.7}

    -- ===== CLASIFICACIÓN =====
    insight_type VARCHAR(100) NOT NULL CHECK (insight_type IN (
        'correlation',    -- Correlación inesperada
        'anomaly',        -- Anomalía detectada
        'trend',          -- Tendencia significativa
        'opportunity',    -- Oportunidad de negocio
        'risk',           -- Riesgo identificado
        'inefficiency',   -- Ineficiencia operativa
        'hidden_asset',   -- Activo oculto o subutilizado
        'timing',         -- Insight temporal (estacionalidad, etc.)
        'segmentation'    -- Segmentación emergente
    )),
    category VARCHAR(100) NOT NULL CHECK (category IN (
        'financial',
        'operational',
        'commercial',
        'supply_chain',
        'human_resources',
        'customer',
        'product',
        'market',
        'other'
    )),
    portfolio_type VARCHAR(50) NOT NULL CHECK (portfolio_type IN (
        'quick_win',      -- 40% del portfolio
        'medium_term',    -- 40% del portfolio
        'strategic_bet'   -- 20% del portfolio
    )),

    -- ===== EJECUCIÓN SQL =====
    sql_query TEXT NOT NULL,
    sql_results JSONB,
    sql_row_count INT DEFAULT 0,
    sql_execution_time_ms INT,

    -- ===== ANÁLISIS =====
    analysis TEXT NOT NULL,  -- El hallazgo en lenguaje natural

    -- ===== CONFIDENCE SCORING (MULTI-DIMENSIONAL) - ACTUALIZADO =====
    confidence_total FLOAT CHECK (confidence_total BETWEEN 0 AND 100),
    confidence_statistical FLOAT,     -- NUEVO: Confianza estadística
    confidence_data_quality FLOAT,    -- NUEVO: Calidad de los datos
    confidence_model FLOAT,            -- NUEVO: Confianza del modelo/LLM
    confidence_caveats JSONB,          -- NUEVO: Lista de advertencias

    -- ===== IMPACT ASSESSMENT =====
    business_impact_usd DECIMAL(15,2),
    business_impact_percentage DECIMAL(5,2),
    impact_on_strategic_goal TEXT,

    -- ===== COUNTERFACTUALS (PASADO-PRESENTE-FUTURO) - NUEVO =====
    counterfactual_past JSONB,     -- {"period": "6 meses atrás", "metric": "...", "value": ...}
    counterfactual_present JSONB,  -- {"period": "ahora", "metric": "...", "value": ...}
    counterfactual_future JSONB,   -- {"period": "6 meses adelante", "projection": "..."}

    -- ===== DELIVERY SCORE - NUEVO =====
    delivery_score_total FLOAT CHECK (delivery_score_total BETWEEN 0 AND 100),
    delivery_score_breakdown JSONB,  -- {"statistical_confidence": 25, "business_impact": 30, ...}
    should_deliver BOOLEAN DEFAULT FALSE,  -- TRUE si delivery_score >= threshold

    priority INT NOT NULL CHECK (priority BETWEEN 1 AND 5),  -- 5 = crítico

    -- ===== DELIVERY =====
    delivered BOOLEAN DEFAULT FALSE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    delivery_channel VARCHAR(50),  -- 'whatsapp', 'teams', 'email'
    delivery_format VARCHAR(50),   -- 'weekly_insight', 'monthly_report'

    -- ===== FEEDBACK =====
    user_feedback VARCHAR(50) CHECK (user_feedback IN (
        'useful',
        'not_useful',
        'false_positive',
        'already_knew',
        NULL
    )),
    feedback_text TEXT,
    feedback_by VARCHAR(255),
    feedback_at TIMESTAMP WITH TIME ZONE,

    action_taken_by_client TEXT,
    business_impact_realized_usd DECIMAL(15,2),

    -- ===== HUMAN REVIEW (primeros 6 meses) - NUEVO =====
    needs_human_review BOOLEAN DEFAULT TRUE,
    reviewed_by VARCHAR(255),
    review_decision VARCHAR(50) CHECK (review_decision IN ('approve', 'reject', 'needs_refinement', NULL)),
    review_notes TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_insights_client_id ON unknown_unknowns_insights(client_id);
CREATE INDEX IF NOT EXISTS idx_insights_run_id ON unknown_unknowns_insights(run_id);
CREATE INDEX IF NOT EXISTS idx_insights_priority ON unknown_unknowns_insights(priority DESC);
CREATE INDEX IF NOT EXISTS idx_insights_delivered ON unknown_unknowns_insights(delivered);
CREATE INDEX IF NOT EXISTS idx_insights_should_deliver ON unknown_unknowns_insights(should_deliver);  -- NUEVO
CREATE INDEX IF NOT EXISTS idx_insights_category ON unknown_unknowns_insights(category);
CREATE INDEX IF NOT EXISTS idx_insights_type ON unknown_unknowns_insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_insights_portfolio ON unknown_unknowns_insights(portfolio_type);  -- NUEVO
CREATE INDEX IF NOT EXISTS idx_insights_created_at ON unknown_unknowns_insights(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_insights_feedback ON unknown_unknowns_insights(user_feedback) WHERE user_feedback IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_insights_needs_review ON unknown_unknowns_insights(needs_human_review);  -- NUEVO

-- Índice compuesto para queries comunes
CREATE INDEX IF NOT EXISTS idx_insights_client_priority_delivered
    ON unknown_unknowns_insights(client_id, priority DESC, delivered);

-- GIN indexes para búsquedas en JSONB
CREATE INDEX IF NOT EXISTS idx_insights_sql_results_gin
    ON unknown_unknowns_insights USING GIN(sql_results);

CREATE INDEX IF NOT EXISTS idx_insights_metadata_gin
    ON unknown_unknowns_insights USING GIN(metadata);

CREATE INDEX IF NOT EXISTS idx_insights_caveats_gin
    ON unknown_unknowns_insights USING GIN(confidence_caveats);  -- NUEVO

-- Comentarios
COMMENT ON TABLE unknown_unknowns_insights IS 'Insights generados por el Unknown Unknowns Agent con ACTIONABILITY BUILT-IN';
COMMENT ON COLUMN unknown_unknowns_insights.if_true_then IS 'Acción específica a tomar si la hipótesis es verdad';
COMMENT ON COLUMN unknown_unknowns_insights.if_false_then IS 'Qué confirma si la hipótesis es falsa (validación de status quo)';
COMMENT ON COLUMN unknown_unknowns_insights.decision_owner IS 'Quién debe actuar: CFO, COO, CEO, etc.';
COMMENT ON COLUMN unknown_unknowns_insights.action_threshold IS 'Condiciones para tomar acción (min_impact_usd, min_confidence, etc.)';
COMMENT ON COLUMN unknown_unknowns_insights.portfolio_type IS 'quick_win (40%) | medium_term (40%) | strategic_bet (20%)';
COMMENT ON COLUMN unknown_unknowns_insights.confidence_total IS 'Score total de confianza (0-100) = weighted avg de statistical + data_quality + model';
COMMENT ON COLUMN unknown_unknowns_insights.confidence_caveats IS 'Lista de advertencias sobre limitaciones del análisis';
COMMENT ON COLUMN unknown_unknowns_insights.delivery_score_total IS 'Score de delivery (0-100) que determina si se entrega o va a refinement';
COMMENT ON COLUMN unknown_unknowns_insights.should_deliver IS 'TRUE si delivery_score >= threshold (default 70)';
COMMENT ON COLUMN unknown_unknowns_insights.needs_human_review IS 'TRUE durante primeros 6 meses para human-in-the-loop';


-- ============================================================================
-- 5. HUMAN REVIEW QUEUE (NUEVO)
-- ============================================================================
-- Cola de insights pendientes de revisión humana.
-- Usado durante los primeros 6 meses para human-in-the-loop learning.

CREATE TABLE IF NOT EXISTS human_review_queue (
    queue_id SERIAL PRIMARY KEY,
    insight_id INT NOT NULL REFERENCES unknown_unknowns_insights(insight_id) ON DELETE CASCADE,
    client_id VARCHAR(255) NOT NULL,

    -- Queue management
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    assigned_to VARCHAR(255),  -- Email/ID del reviewer
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'in_review', 'completed')),

    -- Priority (hereda de insight)
    priority INT,

    -- Metadata
    metadata JSONB,

    UNIQUE(insight_id)  -- Un insight solo puede estar una vez en la queue
);

CREATE INDEX IF NOT EXISTS idx_review_queue_status ON human_review_queue(status);
CREATE INDEX IF NOT EXISTS idx_review_queue_assigned ON human_review_queue(assigned_to) WHERE assigned_to IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_review_queue_priority ON human_review_queue(priority DESC, queued_at);
CREATE INDEX IF NOT EXISTS idx_review_queue_client ON human_review_queue(client_id);

COMMENT ON TABLE human_review_queue IS 'Cola de insights pendientes de revisión humana (primeros 6 meses)';
COMMENT ON COLUMN human_review_queue.status IS 'pending (inicial) | in_review (asignado) | completed (revisado)';


-- ============================================================================
-- 6. VISTAS ÚTILES
-- ============================================================================

-- Vista: Insights pendientes de entregar (con delivery_score)
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
    i.delivery_score_total,  -- NUEVO
    i.should_deliver,        -- NUEVO
    i.needs_human_review,    -- NUEVO
    i.created_at,
    r.run_type
FROM unknown_unknowns_insights i
JOIN business_profiles bp ON i.client_id = bp.client_id
JOIN unknown_unknowns_runs r ON i.run_id = r.run_id
WHERE i.delivered = FALSE
  AND i.should_deliver = TRUE  -- ACTUALIZADO: usa delivery_score
  AND (i.needs_human_review = FALSE OR i.review_decision = 'approve')  -- NUEVO: solo si aprobado
ORDER BY i.priority DESC, i.delivery_score_total DESC, i.created_at DESC;

COMMENT ON VIEW v_pending_insights IS 'Insights con should_deliver=TRUE y aprobados (o sin review) pendientes de entregar';


-- Vista: Performance de runs (ACTUALIZADA)
CREATE OR REPLACE VIEW v_runs_performance AS
SELECT
    r.client_id,
    bp.profile_data->>'company_name' as company_name,
    r.run_type,
    COUNT(*) as total_runs,
    AVG(r.hypotheses_generated) as avg_hypotheses_generated,
    AVG(r.hypotheses_validated) as avg_hypotheses_validated,
    AVG(r.insights_scored_for_delivery) as avg_insights_scored,  -- NUEVO
    AVG(r.insights_delivered) as avg_insights_delivered,
    AVG(r.insights_sent_to_refinement) as avg_insights_refinement,  -- NUEVO
    AVG(r.execution_time_seconds) as avg_execution_time_seconds,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) as successful_runs,
    SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) as failed_runs
FROM unknown_unknowns_runs r
JOIN business_profiles bp ON r.client_id = bp.client_id
GROUP BY r.client_id, bp.profile_data->>'company_name', r.run_type;


-- Vista: Feedback de insights con graveyard integration
CREATE OR REPLACE VIEW v_insights_feedback AS
SELECT
    i.client_id,
    bp.profile_data->>'company_name' as company_name,
    i.category,
    i.insight_type,
    i.portfolio_type,  -- NUEVO
    i.priority,
    i.user_feedback,
    COUNT(*) as count,
    AVG(i.business_impact_usd) as avg_impact_estimated,
    AVG(i.business_impact_realized_usd) as avg_impact_realized,
    AVG(i.delivery_score_total) as avg_delivery_score,  -- NUEVO
    AVG(i.confidence_total) as avg_confidence  -- NUEVO
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


-- Vista: Human review workload
CREATE OR REPLACE VIEW v_human_review_workload AS
SELECT
    hrq.assigned_to,
    hrq.status,
    COUNT(*) as total_items,
    AVG(EXTRACT(EPOCH FROM (NOW() - hrq.queued_at))/3600) as avg_hours_waiting,
    MIN(hrq.priority) as highest_priority,  -- MIN porque 5=highest
    STRING_AGG(DISTINCT hrq.client_id, ', ') as clients
FROM human_review_queue hrq
WHERE hrq.status != 'completed'
GROUP BY hrq.assigned_to, hrq.status
ORDER BY highest_priority, total_items DESC;

COMMENT ON VIEW v_human_review_workload IS 'Carga de trabajo pendiente por reviewer';


-- ============================================================================
-- 7. FUNCIONES ÚTILES
-- ============================================================================

-- Función: Actualizar timestamp de updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para updated_at
DROP TRIGGER IF EXISTS update_business_profiles_updated_at ON business_profiles;
CREATE TRIGGER update_business_profiles_updated_at
    BEFORE UPDATE ON business_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

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


-- Función: Calcular métricas de un run al completarse
CREATE OR REPLACE FUNCTION finalize_run(p_run_id INT)
RETURNS void AS $$
DECLARE
    v_started_at TIMESTAMP WITH TIME ZONE;
    v_insights_count INT;
    v_insights_scored INT;
    v_delivered_count INT;
    v_refinement_count INT;
BEGIN
    -- Obtener datos del run
    SELECT started_at INTO v_started_at
    FROM unknown_unknowns_runs
    WHERE run_id = p_run_id;

    -- Contar insights
    SELECT
        COUNT(*),
        SUM(CASE WHEN should_deliver = TRUE THEN 1 ELSE 0 END),
        SUM(CASE WHEN delivered = TRUE THEN 1 ELSE 0 END),
        SUM(CASE WHEN should_deliver = FALSE AND delivery_score_total IS NOT NULL THEN 1 ELSE 0 END)
    INTO v_insights_count, v_insights_scored, v_delivered_count, v_refinement_count
    FROM unknown_unknowns_insights
    WHERE run_id = p_run_id;

    -- Actualizar run
    UPDATE unknown_unknowns_runs
    SET
        completed_at = NOW(),
        status = 'completed',
        insights_found = v_insights_count,
        insights_scored_for_delivery = v_insights_scored,
        insights_delivered = v_delivered_count,
        insights_sent_to_refinement = v_refinement_count,
        execution_time_seconds = EXTRACT(EPOCH FROM (NOW() - v_started_at))::INT
    WHERE run_id = p_run_id;

    -- Actualizar last_hypothesis_run en business_profiles
    UPDATE business_profiles
    SET last_hypothesis_run = NOW()
    WHERE client_id = (
        SELECT client_id FROM unknown_unknowns_runs WHERE run_id = p_run_id
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION finalize_run IS 'Finaliza un run calculando métricas y actualizando timestamps';


-- Función: Obtener top insights para un cliente
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

COMMENT ON FUNCTION get_top_insights IS 'Obtiene los top N insights de un cliente ordenados por prioridad y delivery score';


-- Función: Mover insight a graveyard
CREATE OR REPLACE FUNCTION move_to_graveyard(
    p_insight_id INT,
    p_category VARCHAR(50),
    p_rejection_reason TEXT DEFAULT NULL,
    p_business_impact_realized DECIMAL DEFAULT NULL
)
RETURNS void AS $$
DECLARE
    v_hypothesis_id VARCHAR(255);
    v_hypothesis_text TEXT;
    v_client_id VARCHAR(255);
BEGIN
    -- Obtener datos del insight
    SELECT hypothesis_id, hypothesis_text, client_id
    INTO v_hypothesis_id, v_hypothesis_text, v_client_id
    FROM unknown_unknowns_insights
    WHERE insight_id = p_insight_id;

    -- Insertar en graveyard
    INSERT INTO hypothesis_graveyard (
        hypothesis_id,
        client_id,
        hypothesis_text,
        category,
        rejection_reason,
        business_impact_realized_usd
    ) VALUES (
        v_hypothesis_id,
        v_client_id,
        v_hypothesis_text,
        p_category,
        p_rejection_reason,
        p_business_impact_realized
    )
    ON CONFLICT (hypothesis_id) DO UPDATE
    SET
        category = EXCLUDED.category,
        rejection_reason = EXCLUDED.rejection_reason,
        business_impact_realized_usd = EXCLUDED.business_impact_realized_usd,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION move_to_graveyard IS 'Mueve un insight al graveyard con la categoría especificada';


-- ============================================================================
-- FIN DE MIGRACIÓN 012 v2
-- ============================================================================
