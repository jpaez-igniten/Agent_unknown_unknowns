# 🧪 Guía Completa de Testing - Unknown Unknowns Agent

**Última actualización**: 2026-01-25

Esta guía te ayudará a probar todo el sistema paso a paso, validar conexiones, y revisar la calidad de las hipótesis generadas.

---

## 📋 Pre-requisitos

### 1. Software Necesario

```bash
# Verificar versiones
python --version  # 3.10+
psql --version    # PostgreSQL 14+
```

### 2. Dependencias Python

```bash
# Activar virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Verificar instalación de LLM
pip list | grep langchain-google-genai
# Si no está: pip install langchain-google-genai
```

### 3. Base de Datos

```bash
# Verificar Postgres está corriendo
pg_isready

# Si no está corriendo (macOS):
brew services start postgresql@14

# Crear base de datos
createdb igniten_core

# Verificar conexión
psql -d igniten_core -c "SELECT version();"
```

---

## 🔧 Setup Inicial

### Paso 1: Configurar Variables de Entorno

```bash
# Copiar ejemplo
cp .env.example .env

# Editar .env con tus credenciales
nano .env
```

**Configuración MÍNIMA** (para testing):
```bash
# PostgreSQL (REQUERIDO)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=igniten_core
POSTGRES_USER=tu_usuario
POSTGRES_PASSWORD=tu_password

# Google API (REQUERIDO para LLM)
GOOGLE_API_KEY=tu_gemini_api_key_aqui

# Delivery Channels (OPCIONAL para testing)
# EMAIL
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=tu_app_password
SMTP_FROM=tu_email@gmail.com

# TEAMS (opcional)
TEAMS_WEBHOOK_URL=https://tu-webhook-teams.com

# WHATSAPP (opcional)
WHATSAPP_API_TOKEN=tu_token
WHATSAPP_PHONE_NUMBER_ID=tu_phone_id
```

**IMPORTANTE**: Para obtener Google API Key:
1. Ve a https://makersuite.google.com/app/apikey
2. Crea un nuevo API key
3. Cópialo al .env

### Paso 2: Ejecutar Migración de Base de Datos

```bash
# Ejecutar migración v2 (incluye todas las tablas)
psql -d igniten_core -f migrations/012_unknown_unknowns_v2.sql

# Verificar que las tablas se crearon
psql -d igniten_core -c "\dt"
```

**Tablas esperadas**:
- `business_profiles`
- `unknown_unknowns_runs`
- `unknown_unknowns_insights`
- `hypothesis_graveyard`
- `human_review_queue`

### Paso 3: Verificar Configuración

```bash
# Script de verificación
python -c "
from config.settings import get_settings
settings = get_settings()
print('✅ Settings loaded')
print(f'DB: {settings.postgres_db}')
print(f'API Key configured: {bool(settings.google_api_key)}')
"
```

---

## 🧪 Testing Fase por Fase

### FASE 1: Business Context Engine

#### Test 1.1: Crear Perfil de Cliente

```bash
# Ejecutar test FASE 1
python scripts/test_phase1.py
```

**Output esperado**:
```
✅ Perfil creado exitosamente!
   Client ID: demo_seguros_001
   Empresa: Seguros Carga S.A.
   Completeness: 75%
   Confidence: 92%

🔍 Ortodoxias detectadas: 3
   - Alto potencial de disrupción: 2
```

#### Test 1.2: Verificar en Base de Datos

```sql
-- Conectar a Postgres
psql -d igniten_core

-- Ver perfil creado
SELECT
    client_id,
    profile_data->>'company_name' as company,
    profile_data->>'industry' as industry,
    profile_completeness,
    jsonb_array_length(profile_data->'industry_orthodoxies') as orthodoxies_count
FROM business_profiles
WHERE client_id = 'demo_seguros_001';

-- Ver ortodoxos detectados
SELECT
    jsonb_array_elements(profile_data->'industry_orthodoxies')->>'orthodoxy' as orthodoxy,
    jsonb_array_elements(profile_data->'industry_orthodoxies')->>'confidence' as confidence,
    jsonb_array_elements(profile_data->'industry_orthodoxies')->>'potential_for_disruption' as disruption
FROM business_profiles
WHERE client_id = 'demo_seguros_001';
```

#### ✅ Checklist FASE 1

- [ ] Perfil se creó correctamente
- [ ] profile_completeness >= 0.70
- [ ] Se detectaron ortodoxos (si LLM configurado)
- [ ] Datos visibles en PostgreSQL
- [ ] to_context_string() genera contexto coherente

---

### FASE 2+3: Hypothesis Generation & Validation

#### Test 2.1: Generar Hipótesis

```bash
# Ejecutar test FASE 2+3
python scripts/test_phase2_3.py
```

**Output esperado**:
```
✅ Generadas 10 hipótesis!

📊 Por tipo:
   - knowledge_driven: 6
   - orthodoxy_challenge: 4

📊 Por portfolio type:
   - quick_win: 4 (40%)
   - medium_term: 4 (40%)
   - strategic_bet: 2 (20%)

💡 Primera hipótesis:
   "Clientes con >3 reclamos rechazados tienen 5x más churn"
   Delivery Score: 84.5/100
   Decision Owner: Chief Customer Officer
```

#### Test 2.2: Validar Calidad de Hipótesis

**Criterios de Calidad**:

1. **Especificidad** ✅
   - ❌ Mal: "Mejorar ventas"
   - ✅ Bien: "Clientes con >3 reclamos rechazados tienen 5x más churn"

2. **Actionability** ✅
   - Debe tener `if_true_then` claro y específico
   - Debe tener `decision_owner` identificado
   - Debe tener `action_threshold` definido

3. **Evidencia** ✅
   - Lista de `evidence` no vacía
   - Referencias a strategic priorities o pain points

4. **Delivery Score** ✅
   - Score total >= 70 para insights entregables
   - Breakdown coherente (statistical, impact, actionability, alignment)

#### Test 2.3: Revisar Hipótesis Individualmente

```python
# Script interactivo para revisar hipótesis
import asyncio
import asyncpg
from config.settings import get_settings

async def review_hypotheses():
    settings = get_settings()
    conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password
    )

    # Si guardaste en BD (en versión futura)
    # Por ahora, revisar desde test output

    await conn.close()

# Ejecutar
asyncio.run(review_hypotheses())
```

#### ✅ Checklist FASE 2+3

- [ ] Se generaron >= 10 hipótesis
- [ ] Portfolio mix cercano a 40/40/20
- [ ] Todas las hipótesis tienen actionability
- [ ] Delivery scores >= 70 para entregables
- [ ] Hipótesis son específicas (no vagas)
- [ ] `if_true_then` es claro y accionable
- [ ] `decision_owner` es un rol específico
- [ ] Feasibility validation funcionó
- [ ] No hay errores de LLM

---

### FASE 4: Delivery & Feedback Loop

#### Test 4.1: Delivery Multi-Canal

```bash
# Ejecutar test FASE 4
python scripts/test_phase4.py
```

**Output esperado**:
```
📧 Simulando delivery de 2 insights...

✅ Delivery orchestration completado!
   Delivery ID: dlv_a3b4c5d6e7f8
   Channel: email
   Feedback URL: https://feedback.igniten.ai/u/dlv_...

📝 Simulando feedback de clientes...

   1. Feedback ÚTIL (cliente usó la hipótesis):
      ✅ Feedback ID: fb_xyz123
      Categoría: useful

   2. Feedback RECHAZADO:
      ✅ Feedback ID: fb_abc456
      Categoría: rejected
```

#### Test 4.2: Verificar Graveyard

```sql
-- Ver entries en hypothesis_graveyard
SELECT
    hypothesis_id,
    category,
    rating,
    business_impact_realized_usd,
    comment,
    feedback_received_at
FROM hypothesis_graveyard
ORDER BY feedback_received_at DESC
LIMIT 10;

-- Stats por categoría
SELECT
    category,
    COUNT(*) as count,
    AVG(rating) as avg_rating,
    SUM(business_impact_realized_usd) as total_impact
FROM hypothesis_graveyard
GROUP BY category;
```

#### Test 4.3: Learning Loop Analysis

**Verificar que el analyzer detecte patrones**:

```python
# Ejemplo de output esperado del analyzer
{
  "rejection_rate": 0.35,
  "recommendations": [
    "⚠️ High rejection rate detected. Consider increasing feasibility threshold.",
    "💰 Cost concerns detected. Focus more on ROI and quick wins."
  ],
  "orthodoxies_to_avoid": [
    "Ortodoxo X que siempre es rechazado"
  ]
}
```

#### ✅ Checklist FASE 4

- [ ] Delivery orchestration funcionó (mock OK si no hay config)
- [ ] Feedback se guardó en hypothesis_graveyard
- [ ] Categorización correcta (useful/rejected/etc.)
- [ ] Business impact se registró (si useful)
- [ ] Stats de graveyard son coherentes
- [ ] Learning loop generó recomendaciones
- [ ] should_avoid_hypothesis funciona

---

## 🔍 Validación de Calidad de Hipótesis

### Script de Validación Automática

```python
# scripts/validate_hypothesis_quality.py
"""
Valida la calidad de hipótesis generadas.
"""

def validate_hypothesis(hypothesis):
    """Valida una hipótesis individual."""
    issues = []
    score = 100

    # 1. Especificidad
    if len(hypothesis.hypothesis_text) < 50:
        issues.append("⚠️ Hipótesis muy corta, falta especificidad")
        score -= 20

    if not any(char.isdigit() for char in hypothesis.hypothesis_text):
        issues.append("⚠️ No hay números/métricas, falta cuantificación")
        score -= 10

    # 2. Actionability
    if not hypothesis.actionability.if_true_then:
        issues.append("❌ CRÍTICO: Falta if_true_then")
        score -= 30
    elif len(hypothesis.actionability.if_true_then) < 30:
        issues.append("⚠️ if_true_then muy vago")
        score -= 15

    if not hypothesis.actionability.decision_owner:
        issues.append("❌ CRÍTICO: Falta decision_owner")
        score -= 20

    # 3. Evidence
    if not hypothesis.evidence:
        issues.append("⚠️ Sin evidencia")
        score -= 15

    # 4. Confidence
    if hypothesis.confidence.confidence_total < 0.6:
        issues.append("⚠️ Confianza baja (<60%)")
        score -= 10

    # 5. Delivery Score
    if hypothesis.delivery_score.delivery_score_total < 70:
        issues.append("ℹ️ Delivery score bajo (<70), no se entregaría")

    return {
        "quality_score": max(0, score),
        "issues": issues,
        "is_high_quality": score >= 70
    }

# Uso
for hyp in hypotheses:
    validation = validate_hypothesis(hyp)
    print(f"\n{hyp.hypothesis_text[:60]}...")
    print(f"Quality Score: {validation['quality_score']}/100")
    for issue in validation['issues']:
        print(f"  {issue}")
```

### Criterios de Calidad por Categoría

#### Quick Wins (40%)
- ✅ Time to impact <= 3 meses
- ✅ Costo implementación bajo
- ✅ Impacto visible y medible
- ✅ Alta confianza (>0.75)

#### Medium Term (40%)
- ✅ Time to impact 3-12 meses
- ✅ ROI claro
- ✅ Requiere inversión moderada
- ✅ Impacto significativo (>$100K)

#### Strategic Bets (20%)
- ✅ Time to impact >12 meses
- ✅ Potencial transformador
- ✅ Alto riesgo aceptable
- ✅ Visión a largo plazo

---

## 🐛 Troubleshooting Común

### Problema 1: "LLM no disponible"

**Síntoma**: Tests fallan con "LLM no disponible"

**Solución**:
```bash
# Verificar instalación
pip install langchain-google-genai

# Verificar API key
python -c "from config.settings import get_settings; print(get_settings().google_api_key[:10])"

# Si no hay key, agregarla a .env
echo "GOOGLE_API_KEY=tu_key_aqui" >> .env
```

### Problema 2: "Connection refused" a Postgres

**Síntoma**: `asyncpg.exceptions.ConnectionRefusedError`

**Solución**:
```bash
# Verificar que Postgres esté corriendo
pg_isready

# Si no:
brew services start postgresql@14  # macOS
sudo service postgresql start       # Linux

# Verificar puerto
lsof -i :5432
```

### Problema 3: "Relation does not exist"

**Síntoma**: `asyncpg.exceptions.UndefinedTableError`

**Solución**:
```bash
# Ejecutar migración
psql -d igniten_core -f migrations/012_unknown_unknowns_v2.sql

# Verificar tablas
psql -d igniten_core -c "\dt"
```

### Problema 4: Hipótesis muy vagas o genéricas

**Síntoma**: Hipótesis como "Mejorar ventas" o "Optimizar procesos"

**Solución**:
```python
# Ajustar prompts para mayor especificidad
# En hypothesis/prompts.py, agregar en instrucciones:
"""
IMPORTANTE:
- Incluir números específicos (ej: "5x más", ">3 reclamos")
- Mencionar segmentos/períodos concretos
- Evitar verbos genéricos (mejorar, optimizar)
- Usar verbos específicos (reducir churn de 8% a 5%)
"""
```

### Problema 5: Delivery score muy bajo

**Síntoma**: Todas las hipótesis con score <70

**Solución**:
```python
# Revisar componentes del score
# En generator.py, ajustar cálculos:

def _calculate_business_impact_score(self, hypothesis):
    estimated_impact = hypothesis.actionability.estimated_impact_usd or 0

    # Ajustar thresholds según tu industria
    if estimated_impact >= 500000:
        return 95.0
    elif estimated_impact >= 200000:  # Reducir threshold
        return 82.0
    # ...
```

### Problema 6: No se detectan ortodoxos

**Síntoma**: `industry_orthodoxies` vacío

**Solución**:
```bash
# Verificar que LLM esté configurado
# Verificar que haya datos históricos/conversaciones

# Ejecutar detección manual
python -c "
import asyncio
from packages.core.domain.unknown_unknowns.business_context.orthodoxy_detector import OrthodoxyDetector
# ... ejecutar detect_orthodoxies
"

# Si persiste, revisar prompts en orthodoxy_detector.py
```

---

## 📊 Dashboard de Validación

### Script de Reporte Completo

```python
# scripts/generate_quality_report.py
"""
Genera reporte completo de calidad del sistema.
"""

import asyncio
import asyncpg
from config.settings import get_settings

async def generate_quality_report():
    settings = get_settings()
    conn = await asyncpg.connect(...)

    report = {
        "timestamp": datetime.now().isoformat(),
        "database": {
            "profiles_count": 0,
            "runs_count": 0,
            "insights_count": 0,
            "graveyard_count": 0
        },
        "quality_metrics": {
            "avg_delivery_score": 0,
            "avg_confidence": 0,
            "portfolio_mix": {},
            "success_rate": 0,
            "rejection_rate": 0
        },
        "recommendations": []
    }

    # Queries...

    print(json.dumps(report, indent=2))

    await conn.close()

asyncio.run(generate_quality_report())
```

---

## ✅ Checklist Final de Validación

### Sistema Completo

- [ ] **FASE 1**: Perfil creado con completeness >70%
- [ ] **FASE 1**: Ortodoxos detectados (>= 2)
- [ ] **FASE 2**: Hipótesis generadas (>= 10)
- [ ] **FASE 2**: Portfolio mix ~40/40/20
- [ ] **FASE 2**: Delivery scores >= 70
- [ ] **FASE 3**: Feasibility validation funcionó
- [ ] **FASE 4**: Delivery orchestration OK
- [ ] **FASE 4**: Feedback guardado en graveyard
- [ ] **FASE 4**: Learning loop genera recomendaciones

### Calidad de Hipótesis

- [ ] Hipótesis son **específicas** (con números/métricas)
- [ ] `if_true_then` es **claro y accionable**
- [ ] `decision_owner` es un **rol específico**
- [ ] `evidence` lista **pain points/priorities reales**
- [ ] `confidence_caveats` menciona **limitaciones reales**
- [ ] No hay hipótesis **genéricas o vagas**
- [ ] Mix de categorías (churn, profitability, operations, etc.)

### Base de Datos

- [ ] Todas las tablas creadas correctamente
- [ ] Datos visibles en `business_profiles`
- [ ] Datos en `hypothesis_graveyard` (después de FASE 4)
- [ ] No hay errores en logs de Postgres

### Integraciones

- [ ] LLM responde correctamente (Gemini)
- [ ] Postgres funciona
- [ ] Settings se cargan OK
- [ ] No hay errores de importación

---

## 🎯 Próximos Pasos Después de Testing

### Si todo funciona ✅

1. **Crear perfiles de clientes reales**
2. **Ejecutar runs con datos reales**
3. **Validar calidad de hipótesis generadas**
4. **Ajustar prompts según feedback**
5. **Configurar delivery channels reales**

### Si hay problemas ❌

1. Revisar logs detallados
2. Usar troubleshooting section arriba
3. Ejecutar tests individuales
4. Verificar configuración paso a paso

---

## 📞 Comandos Útiles de Referencia

```bash
# Ver logs de Postgres
tail -f /usr/local/var/log/postgres.log

# Limpiar base de datos para re-testing
psql -d igniten_core -c "TRUNCATE business_profiles, hypothesis_graveyard CASCADE;"

# Re-ejecutar migración
psql -d igniten_core -f migrations/012_unknown_unknowns_v2.sql

# Verificar uso de API (Gemini)
# Ver en: https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com

# Activar logging detallado
export LOG_LEVEL=DEBUG
python scripts/test_phase2_3.py
```

---

**Happy Testing!** 🧪✨

Si encuentras issues, revisa la sección de Troubleshooting o ejecuta los tests individuales para identificar dónde falla.
