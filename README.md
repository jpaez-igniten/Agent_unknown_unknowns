# Unknown Unknowns Agent

AI Agent para descubrir "Unknown Unknowns" en datos empresariales, basado en la filosofía de la Ventana de Johari aplicada a business intelligence.

## 📖 Concepto: La Ventana de Johari para Datos

```
                CONOCIDO            DESCONOCIDO
              ┌────────────────┬────────────────┐
CONSCIENTE    │  Arena Abierta │ Punto Ciego    │
              │  (Lo que sé)   │ (Lo que otros  │
              │                │  ven de mí)    │
              ├────────────────┼────────────────┤
INCONSCIENTE  │  Fachada       │ Desconocido    │
              │  (Lo que oculto│ (Unknown       │
              │   a propósito) │  Unknowns) ⭐  │
              └────────────────┴────────────────┘
```

**Objetivo**: Generar hipótesis de negocio que el cliente **nunca ha pensado en hacer**, pero que cuando las ve dicen *"¡Nunca me había preguntado eso y es súper relevante!"*.

**Principio clave**: No usar templates genéricos. Las hipótesis se generan desde un **conocimiento profundo del negocio del cliente** (industria, prioridades estratégicas, pain points, estructura de datos).

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                  UNKNOWN UNKNOWNS AGENT                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. BUSINESS CONTEXT ENGINE                                │
│     └─ BusinessProfile: Perfil profundo del cliente        │
│        - Strategic priorities                              │
│        - Pain points                                       │
│        - KPIs, North Star Metric                          │
│        - Industry benchmarks                              │
│                                                             │
│  2. HYPOTHESIS GENERATION ENGINE                           │
│     └─ Genera hipótesis contextualizadas                  │
│        - Alineadas con prioridades estratégicas           │
│        - Abordan pain points desde ángulos no obvios      │
│        - Factibles con datos disponibles                  │
│                                                             │
│  3. VALIDATION & ANALYSIS PIPELINE                         │
│     └─ Valida hipótesis con SQL                           │
│     └─ Detecta patrones significativos                    │
│     └─ Cuantifica impacto de negocio                      │
│                                                             │
│  4. DELIVERY & FEEDBACK LOOP                               │
│     └─ Entrega insights priorizados                       │
│     └─ Aprende de feedback del cliente                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Estado Actual: FASE 1 - Business Context Engine

### ✅ Implementado

1. **BusinessProfile Schema** (`packages/core/domain/unknown_unknowns/business_context/`)
   - Modelo Pydantic completo con todos los campos necesarios
   - Métodos de validación y cálculo de completeness
   - Métodos helper para contexto del LLM

2. **Migración SQL** (`migrations/012_unknown_unknowns.sql`)
   - Tabla `business_profiles`: Almacena perfiles de clientes
   - Tabla `unknown_unknowns_runs`: Tracking de ejecuciones
   - Tabla `unknown_unknowns_insights`: Insights generados
   - Vistas y funciones útiles
   - Índices optimizados para queries frecuentes

3. **BusinessProfileRepository** (`profile_repository.py`)
   - CRUD completo para BusinessProfile
   - Integración con Postgres (principal)
   - Soporte para ChromaDB (opcional, para búsqueda semántica)
   - Búsqueda de perfiles similares
   - Estadísticas y utilities

4. **BusinessProfileBuilder** (`profile_builder.py`)
   - Construcción de perfil desde onboarding manual
   - Validación de datos de entrada
   - Cálculo de completeness y confidence scores
   - Validador de calidad del perfil
   - Template generator para onboarding

5. **Configuration** (`config/settings.py`)
   - Settings usando Pydantic Settings
   - Soporte para .env
   - Configuración de databases, LLM, delivery channels, etc.

6. **Test Suite** (`scripts/test_phase1.py`)
   - Tests completos para FASE 1
   - Creación, recuperación, validación de perfiles
   - Estadísticas y reporting

### 📋 Próximas Fases

**FASE 2**: Hypothesis Generation Engine
- LLM-based hypothesis generator
- Integración con SQL Expert v2
- Factibilidad técnica checker

**FASE 3**: Validation & Analysis Pipeline
- SQL validator usando SQL Expert
- Pattern detector con heurísticas + LLM
- Impact quantifier

**FASE 4**: Delivery & Feedback Loop
- Multi-channel delivery (email, Teams, WhatsApp)
- Feedback collection
- Learning loop

## 🛠️ Setup

### 1. Requisitos

- Python 3.10+
- PostgreSQL 14+
- (Opcional) Neo4j 5+
- (Opcional) ChromaDB
- (Opcional) Redis

### 2. Instalación

```bash
# Clonar repositorio
cd Agent_unknown_unknowns

# Crear virtual environment
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales
```

### 3. Base de Datos

```bash
# Crear base de datos en Postgres
createdb igniten_core

# O usando psql:
psql -U postgres
CREATE DATABASE igniten_core;
\q

# Ejecutar migración
psql -U postgres -d igniten_core -f migrations/012_unknown_unknowns.sql
```

### 4. Configuración `.env`

Edita `.env` con tus credenciales:

```bash
# Postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=igniten_core
POSTGRES_USER=tu_usuario
POSTGRES_PASSWORD=tu_password

# Gemini (para FASE 2+)
GOOGLE_API_KEY=tu_api_key_de_gemini

# Otros (opcional)
# NEO4J_URI=bolt://localhost:7687
# CHROMADB_HOST=localhost
# REDIS_HOST=localhost
```

## 🧪 Testing FASE 1

```bash
# Ejecutar test suite completo
python scripts/test_phase1.py
```

Esto hará:
1. ✅ Conectar a Postgres
2. ✅ Crear un perfil de ejemplo (empresa de seguros)
3. ✅ Guardar en la base de datos
4. ✅ Recuperar el perfil
5. ✅ Validar calidad del perfil
6. ✅ Listar perfiles
7. ✅ Mostrar estadísticas

**Output esperado:**

```
######################################################################
# UNKNOWN UNKNOWNS AGENT - TEST SUITE FASE 1
######################################################################

📊 Conectando a Postgres...
✅ Conectado a Postgres: localhost:5432/igniten_core

======================================================================
TEST 1: Crear perfil desde datos de onboarding
======================================================================

✅ Perfil creado exitosamente!
   Client ID: demo_seguros_001
   Empresa: Seguros Carga S.A.
   Industria: Seguros B2B
   Completeness: 75%
   Confidence: 92%

[... más tests ...]

######################################################################
# ✅ TODOS LOS TESTS COMPLETADOS EXITOSAMENTE
######################################################################
```

## 📂 Estructura del Proyecto

```
Agent_unknown_unknowns/
├── packages/
│   └── core/
│       ├── domain/
│       │   └── unknown_unknowns/
│       │       ├── business_context/      # FASE 1 ✅
│       │       │   ├── profile_schema.py
│       │       │   ├── profile_repository.py
│       │       │   └── profile_builder.py
│       │       ├── hypothesis/            # FASE 2 (TODO)
│       │       ├── analysis/              # FASE 3 (TODO)
│       │       └── delivery/              # FASE 4 (TODO)
│       └── api/
│           └── routes/                     # API endpoints (TODO)
├── migrations/
│   └── 012_unknown_unknowns.sql           # ✅
├── config/
│   ├── __init__.py
│   └── settings.py                        # ✅
├── scripts/
│   └── test_phase1.py                     # ✅
├── .env.example                           # ✅
├── requirements.txt                        # ✅
└── README.md                              # ✅
```

## 🎯 Uso (FASE 1)

### Crear un perfil de negocio

```python
import asyncio
from packages.core.domain.unknown_unknowns.business_context import (
    BusinessProfileBuilder,
    BusinessProfileRepository
)

async def create_profile():
    # Setup repository
    pool = await asyncpg.create_pool(...)
    repository = BusinessProfileRepository(pool)
    builder = BusinessProfileBuilder(repository)

    # Datos de onboarding
    onboarding_data = {
        "company_name": "Mi Empresa S.A.",
        "industry": "Retail",
        "business_model": "B2C",
        "revenue_model": "Transaccional",
        "strategic_priorities": [
            {
                "priority": "Reducir costos 20%",
                "deadline": "Q2 2025",
                "owner": "COO"
            }
        ],
        "known_pain_points": [
            "No sabemos qué productos son rentables"
        ],
        "north_star_metric": "Margen neto",
        # ... más campos
    }

    # Crear perfil
    profile = await builder.build_from_onboarding(
        client_id="mi_empresa_001",
        answers=onboarding_data
    )

    print(f"Perfil creado: {profile.company_name}")
    print(f"Completeness: {profile.profile_completeness:.2%}")

asyncio.run(create_profile())
```

### Recuperar y validar perfil

```python
# Obtener perfil
profile = await repository.get_profile("mi_empresa_001")

# Validar calidad
quality = await builder.validate_profile_quality("mi_empresa_001")
print(f"Quality score: {quality['quality_score']:.2%}")
print(f"Ready for hypotheses: {quality['ready_for_hypothesis_generation']}")

# Ver sugerencias
for suggestion in quality['suggestions']:
    print(f"- {suggestion['message']}")
```

### Ver contexto para LLM

```python
# Generar contexto string para prompts
context = profile.to_context_string()
print(context)

# Output:
# Cliente: Mi Empresa S.A.
# Industria: Retail
# Modelo: B2C (Transaccional)
#
# Prioridades estratégicas:
#   1. Reducir costos 20% (Q2 2025)
#
# Pain points conocidos:
#   - No sabemos qué productos son rentables
#
# North Star Metric: Margen neto
# ...
```

## 📊 Database Schema

### business_profiles
```sql
- client_id (PK)
- profile_data (JSONB)          # BusinessProfile completo
- profile_completeness (FLOAT)   # 0.0 - 1.0
- confidence_score (FLOAT)       # 0.0 - 1.0
- created_at, updated_at
- last_hypothesis_run
- is_active, insights_enabled
```

### unknown_unknowns_runs
```sql
- run_id (PK)
- client_id (FK)
- run_type                       # 'daily', 'weekly', 'monthly', 'ad_hoc'
- started_at, completed_at
- status                         # 'running', 'completed', 'failed'
- hypotheses_generated
- hypotheses_validated
- insights_delivered
```

### unknown_unknowns_insights
```sql
- insight_id (PK)
- run_id (FK)
- client_id (FK)
- hypothesis_text
- insight_type                   # 'anomaly', 'correlation', 'opportunity', etc.
- category                       # 'financial', 'operational', 'commercial', etc.
- sql_query, sql_results
- analysis                       # El hallazgo en lenguaje natural
- business_impact_usd
- priority (1-5)
- delivered, user_feedback
```

## 🔮 Roadmap

- [x] **FASE 1**: Business Context Engine
  - [x] BusinessProfile schema
  - [x] Database migration
  - [x] Repository layer
  - [x] Profile builder
  - [x] Test suite

- [ ] **FASE 2**: Hypothesis Generation Engine
  - [ ] HypothesisGenerator con LLM
  - [ ] Integration con BusinessProfile
  - [ ] Factibilidad técnica validator
  - [ ] Similar profiles search (ChromaDB)

- [ ] **FASE 3**: Validation & Analysis
  - [ ] SQL Expert v2 integration
  - [ ] Pattern detector (heuristics + LLM)
  - [ ] Business impact quantifier
  - [ ] Significance scorer

- [ ] **FASE 4**: Delivery & Learning
  - [ ] Multi-channel delivery
  - [ ] Feedback collection
  - [ ] Learning loop
  - [ ] Scheduling & automation

- [ ] **FASE 5**: Advanced Features
  - [ ] Schema analysis enrichment
  - [ ] Conversation learning
  - [ ] Neo4j integration
  - [ ] A/B testing de hipótesis

## 🤝 Contributing

Este es un proyecto interno de Igniten. Para contribuir:

1. Crear feature branch
2. Implementar cambios
3. Agregar tests
4. Submit PR

## 📄 License

Proprietary - Igniten © 2025

---

**Status**: 🟢 FASE 1 Completada | En desarrollo de FASE 2

**Last Updated**: 2025-01-24
