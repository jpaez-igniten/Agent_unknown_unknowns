-- ============================================================================
-- Migration 012: Unknown Unknowns Agent
-- ============================================================================
--
-- Este módulo implementa el Unknown Unknowns Agent basado en la filosofía
-- de la Ventana de Johari aplicada a datos empresariales.
--
-- Tablas creadas:
-- 1. business_profiles: Perfiles de negocio de clientes
-- 2. unknown_unknowns_runs: Ejecuciones del análisis
-- 3. unknown_unknowns_insights: Insights generados y entregados
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

-- GIN index para búsquedas avanzadas en JSONB
CREATE INDEX IF NOT EXISTS idx_business_profiles_data_gin
    ON business_profiles USING GIN(profile_data);

-- Comentarios
COMMENT ON TABLE business_profiles IS 'Perfiles de negocio de clientes para contextualizar generación de hipótesis';
COMMENT ON COLUMN business_profiles.profile_data IS 'Perfil completo en formato JSON (BusinessProfile Pydantic model)';
COMMENT ON COLUMN business_profiles.profile_completeness IS 'Score de completitud del perfil (0.0-1.0)';
COMMENT ON COLUMN business_profiles.confidence_score IS 'Score de confianza en la precisión del perfil (0.0-1.0)';
COMMENT ON COLUMN business_profiles.last_enrichment IS 'Última vez que se enriqueció el perfil automáticamente';
COMMENT ON COLUMN business_profiles.last_hypothesis_run IS 'Última ejecución del análisis de Unknown Unknowns';


-- ============================================================================
-- 2. UNKNOWN UNKNOWNS RUNS
-- ============================================================================
-- Registro de cada ejecución del análisis de Unknown Unknowns.
-- Permite tracking de performance y debugging.

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

    -- Métricas de resultado
    hypotheses_generated INT DEFAULT 0,
    hypotheses_validated INT DEFAULT 0,
    insights_found INT DEFAULT 0,
    insights_delivered INT DEFAULT 0,

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

-- Índices
CREATE INDEX IF NOT EXISTS idx_runs_client_id ON unknown_unknowns_runs(client_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON unknown_unknowns_runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_started_at ON unknown_unknowns_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_client_type ON unknown_unknowns_runs(client_id, run_type);
CREATE INDEX IF NOT EXISTS idx_runs_focus_area ON unknown_unknowns_runs(focus_area) WHERE focus_area IS NOT NULL;

-- Comentarios
COMMENT ON TABLE unknown_unknowns_runs IS 'Registro de ejecuciones del análisis de Unknown Unknowns';
COMMENT ON COLUMN unknown_unknowns_runs.run_type IS 'Tipo de ejecución: daily, weekly, monthly, ad_hoc';
COMMENT ON COLUMN unknown_unknowns_runs.focus_area IS 'Área de enfoque del análisis (NULL = todas las áreas)';
COMMENT ON COLUMN unknown_unknowns_runs.hypotheses_generated IS 'Número de hipótesis generadas por el LLM';
COMMENT ON COLUMN unknown_unknowns_runs.hypotheses_validated IS 'Número de hipótesis validadas exitosamente con SQL';
COMMENT ON COLUMN unknown_unknowns_runs.insights_found IS 'Número de insights significativos encontrados';
COMMENT ON COLUMN unknown_unknowns_runs.insights_delivered IS 'Número de insights entregados al cliente';


-- ============================================================================
-- 3. UNKNOWN UNKNOWNS INSIGHTS
-- ============================================================================
-- Almacena cada insight generado, con su hipótesis, SQL, análisis y feedback.

CREATE TABLE IF NOT EXISTS unknown_unknowns_insights (
    -- Identificación
    insight_id SERIAL PRIMARY KEY,
    run_id INT NOT NULL REFERENCES unknown_unknowns_runs(run_id) ON DELETE CASCADE,
    client_id VARCHAR(255) NOT NULL REFERENCES business_profiles(client_id) ON DELETE CASCADE,

    -- Hipótesis original
    hypothesis_id VARCHAR(255) NOT NULL,
    hypothesis_text TEXT NOT NULL,
    business_rationale TEXT NOT NULL,
    strategic_alignment TEXT,
    pain_point_addressed TEXT,

    -- Clasificación del insight
    insight_type VARCHAR(100) NOT NULL CHECK (insight_type IN (
        'anomaly',           -- Anomalía detectada
        'correlation',       -- Correlación inesperada
        'trend',             -- Tendencia significativa
        'opportunity',       -- Oportunidad de negocio
        'risk',              -- Riesgo identificado
        'inefficiency',      -- Ineficiencia operativa
        'hidden_asset',      -- Activo oculto o subutilizado
        'customer_insight',  -- Insight sobre clientes
        'product_insight',   -- Insight sobre productos
        'financial_leak'     -- Fuga financiera
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

    -- Ejecución SQL
    sql_query TEXT NOT NULL,
    sql_results JSONB,
    sql_row_count INT DEFAULT 0,
    sql_execution_time_ms INT,

    -- Análisis del insight
    analysis TEXT NOT NULL,  -- El hallazgo en lenguaje natural
    significance_reason TEXT,

    -- Impacto de negocio
    business_impact_usd DECIMAL(15,2),
    business_impact_percentage DECIMAL(5,2),
    impact_on_strategic_goal TEXT,

    -- Recomendación
    recommended_action TEXT,
    recommended_owner VARCHAR(100),  -- 'CEO', 'CFO', 'COO', 'Sales Director', etc.

    -- Prioridad (1-5, donde 5 es crítico)
    priority INT NOT NULL CHECK (priority BETWEEN 1 AND 5),

    -- Delivery
    delivered BOOLEAN DEFAULT FALSE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    delivery_channels VARCHAR(255)[],  -- Array: ['email', 'teams', 'whatsapp']

    -- Feedback del usuario
    user_feedback VARCHAR(50) CHECK (user_feedback IN (
        'useful',
        'not_useful',
        'false_positive',
        'already_knew',
        NULL
    )),
    feedback_text TEXT,
    feedback_date TIMESTAMP WITH TIME ZONE,

    -- Acción tomada
    action_taken TEXT,
    action_date TIMESTAMP WITH TIME ZONE,
    business_impact_realized_usd DECIMAL(15,2),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_insights_client_id ON unknown_unknowns_insights(client_id);
CREATE INDEX IF NOT EXISTS idx_insights_run_id ON unknown_unknowns_insights(run_id);
CREATE INDEX IF NOT EXISTS idx_insights_priority ON unknown_unknowns_insights(priority DESC);
CREATE INDEX IF NOT EXISTS idx_insights_delivered ON unknown_unknowns_insights(delivered);
CREATE INDEX IF NOT EXISTS idx_insights_category ON unknown_unknowns_insights(category);
CREATE INDEX IF NOT EXISTS idx_insights_type ON unknown_unknowns_insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_insights_created_at ON unknown_unknowns_insights(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_insights_feedback ON unknown_unknowns_insights(user_feedback) WHERE user_feedback IS NOT NULL;

-- Índice compuesto para queries comunes
CREATE INDEX IF NOT EXISTS idx_insights_client_priority_delivered
    ON unknown_unknowns_insights(client_id, priority DESC, delivered);

-- GIN index para búsquedas en JSONB
CREATE INDEX IF NOT EXISTS idx_insights_sql_results_gin
    ON unknown_unknowns_insights USING GIN(sql_results);

CREATE INDEX IF NOT EXISTS idx_insights_metadata_gin
    ON unknown_unknowns_insights USING GIN(metadata);

-- Comentarios
COMMENT ON TABLE unknown_unknowns_insights IS 'Insights generados por el Unknown Unknowns Agent';
COMMENT ON COLUMN unknown_unknowns_insights.hypothesis_id IS 'ID único de la hipótesis (para tracking)';
COMMENT ON COLUMN unknown_unknowns_insights.insight_type IS 'Tipo de insight: anomaly, correlation, trend, opportunity, risk, etc.';
COMMENT ON COLUMN unknown_unknowns_insights.category IS 'Categoría del área de negocio: financial, operational, commercial, etc.';
COMMENT ON COLUMN unknown_unknowns_insights.priority IS 'Prioridad del insight (1-5, donde 5 es crítico y alineado con top prioridad)';
COMMENT ON COLUMN unknown_unknowns_insights.business_impact_usd IS 'Impacto estimado en USD';
COMMENT ON COLUMN unknown_unknowns_insights.business_impact_percentage IS 'Impacto estimado en % del objetivo estratégico';
COMMENT ON COLUMN unknown_unknowns_insights.recommended_owner IS 'Rol/persona recomendada para actuar sobre el insight';
COMMENT ON COLUMN unknown_unknowns_insights.user_feedback IS 'Feedback del usuario: useful, not_useful, false_positive, already_knew';
COMMENT ON COLUMN unknown_unknowns_insights.business_impact_realized_usd IS 'Impacto real en USD después de tomar acción';


-- ============================================================================
-- 4. VISTAS ÚTILES
-- ============================================================================

-- Vista: Insights pendientes de entregar
CREATE OR REPLACE VIEW v_pending_insights AS
SELECT
    i.insight_id,
    i.client_id,
    bp.profile_data->>'company_name' as company_name,
    i.hypothesis_text,
    i.analysis,
    i.priority,
    i.category,
    i.business_impact_usd,
    i.created_at,
    r.run_type
FROM unknown_unknowns_insights i
JOIN business_profiles bp ON i.client_id = bp.client_id
JOIN unknown_unknowns_runs r ON i.run_id = r.run_id
WHERE i.delivered = FALSE
  AND i.priority >= 3
ORDER BY i.priority DESC, i.created_at DESC;

COMMENT ON VIEW v_pending_insights IS 'Insights con prioridad >= 3 pendientes de entregar';


-- Vista: Performance de runs
CREATE OR REPLACE VIEW v_runs_performance AS
SELECT
    r.client_id,
    bp.profile_data->>'company_name' as company_name,
    r.run_type,
    COUNT(*) as total_runs,
    AVG(r.hypotheses_generated) as avg_hypotheses_generated,
    AVG(r.hypotheses_validated) as avg_hypotheses_validated,
    AVG(r.insights_found) as avg_insights_found,
    AVG(r.insights_delivered) as avg_insights_delivered,
    AVG(r.execution_time_seconds) as avg_execution_time_seconds,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) as successful_runs,
    SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) as failed_runs
FROM unknown_unknowns_runs r
JOIN business_profiles bp ON r.client_id = bp.client_id
GROUP BY r.client_id, bp.profile_data->>'company_name', r.run_type;

COMMENT ON VIEW v_runs_performance IS 'Métricas de performance agregadas por cliente y tipo de run';


-- Vista: Feedback de insights
CREATE OR REPLACE VIEW v_insights_feedback AS
SELECT
    i.client_id,
    bp.profile_data->>'company_name' as company_name,
    i.category,
    i.insight_type,
    i.priority,
    i.user_feedback,
    COUNT(*) as count,
    AVG(i.business_impact_usd) as avg_impact_estimated,
    AVG(i.business_impact_realized_usd) as avg_impact_realized
FROM unknown_unknowns_insights i
JOIN business_profiles bp ON i.client_id = bp.client_id
WHERE i.user_feedback IS NOT NULL
GROUP BY
    i.client_id,
    bp.profile_data->>'company_name',
    i.category,
    i.insight_type,
    i.priority,
    i.user_feedback;

COMMENT ON VIEW v_insights_feedback IS 'Análisis de feedback de insights por categoría y tipo';


-- ============================================================================
-- 5. FUNCIONES ÚTILES
-- ============================================================================

-- Función: Actualizar timestamp de updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para business_profiles
DROP TRIGGER IF EXISTS update_business_profiles_updated_at ON business_profiles;
CREATE TRIGGER update_business_profiles_updated_at
    BEFORE UPDATE ON business_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- Función: Calcular métricas de un run al completarse
CREATE OR REPLACE FUNCTION finalize_run(p_run_id INT)
RETURNS void AS $$
DECLARE
    v_started_at TIMESTAMP WITH TIME ZONE;
    v_insights_count INT;
    v_delivered_count INT;
BEGIN
    -- Obtener datos del run
    SELECT started_at INTO v_started_at
    FROM unknown_unknowns_runs
    WHERE run_id = p_run_id;

    -- Contar insights
    SELECT
        COUNT(*),
        SUM(CASE WHEN delivered = TRUE THEN 1 ELSE 0 END)
    INTO v_insights_count, v_delivered_count
    FROM unknown_unknowns_insights
    WHERE run_id = p_run_id;

    -- Actualizar run
    UPDATE unknown_unknowns_runs
    SET
        completed_at = NOW(),
        status = 'completed',
        insights_found = v_insights_count,
        insights_delivered = v_delivered_count,
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
    category VARCHAR(100),
    business_impact_usd DECIMAL(15,2),
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
        i.category,
        i.business_impact_usd,
        i.delivered,
        i.created_at
    FROM unknown_unknowns_insights i
    WHERE i.client_id = p_client_id
      AND (NOT p_delivered_only OR i.delivered = TRUE)
    ORDER BY i.priority DESC, i.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_top_insights IS 'Obtiene los top N insights de un cliente ordenados por prioridad';


-- ============================================================================
-- 6. DATOS DE EJEMPLO (OPCIONAL - comentado por defecto)
-- ============================================================================
-- Descomentar para insertar datos de ejemplo

/*
-- Perfil de ejemplo: Empresa de Seguros B2B
INSERT INTO business_profiles (client_id, profile_data, profile_completeness, confidence_score)
VALUES (
    'demo_seguros_001',
    '{
        "client_id": "demo_seguros_001",
        "company_name": "Seguros Carga S.A.",
        "industry": "Seguros B2B",
        "industry_sub_segment": "Seguros de carga",
        "business_model": "B2B",
        "revenue_model": "Comisión",
        "size": {
            "employees": 250,
            "revenue_range": "$20M-$50M",
            "locations": 3
        },
        "strategic_priorities": [
            {
                "priority": "Reducir costos operativos 15%",
                "deadline": "Q2 2025",
                "owner": "COO"
            },
            {
                "priority": "Aumentar margen neto a 12%",
                "deadline": "Q4 2025",
                "owner": "CFO"
            }
        ],
        "known_pain_points": [
            "No sabemos qué clientes son realmente rentables",
            "Descuentos se otorgan sin criterio claro",
            "Algunos agentes generan mucho volumen pero bajo margen"
        ],
        "north_star_metric": "Margen neto",
        "kpis": [
            {
                "name": "Margen bruto",
                "target": 0.35,
                "current": 0.28,
                "unit": "%",
                "trend": "declining"
            }
        ],
        "erp_system": "SAP ECC",
        "sap_modules": ["FI", "SD"],
        "data_maturity": "medium",
        "historical_data_years": 3
    }'::jsonb,
    0.75,
    0.85
);
*/

-- ============================================================================
-- FIN DE MIGRACIÓN 012
-- ============================================================================
