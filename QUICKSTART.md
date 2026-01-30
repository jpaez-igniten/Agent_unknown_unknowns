# 🚀 Quick Start - FASE 1

Guía rápida para poner en marcha el Unknown Unknowns Agent (FASE 1).

## ⚡ Setup en 5 minutos

### 1. Instalar dependencias

```bash
# Crear virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar
pip install -r requirements.txt
```

### 2. Configurar Postgres

```bash
# Opción A: Usando psql
psql -U postgres
CREATE DATABASE igniten_core;
\q

# Opción B: Usando comando directo
createdb igniten_core

# Ejecutar migración
psql -U postgres -d igniten_core -f migrations/012_unknown_unknowns.sql
```

**Verificar**:
```bash
psql -U postgres -d igniten_core -c "\dt"
```

Deberías ver:
- `business_profiles`
- `unknown_unknowns_runs`
- `unknown_unknowns_insights`

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con tus credenciales (mínimo requerido):

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=igniten_core
POSTGRES_USER=tu_usuario
POSTGRES_PASSWORD=tu_password
```

### 4. Ejecutar tests

```bash
python scripts/test_phase1.py
```

**Output esperado**:
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

...

######################################################################
# ✅ TODOS LOS TESTS COMPLETADOS EXITOSAMENTE
######################################################################
```

---

## 🧪 Probando la implementación

### Crear tu primer perfil

```python
import asyncio
import asyncpg
from config.settings import get_settings
from packages.core.domain.unknown_unknowns.business_context import (
    BusinessProfileRepository,
    BusinessProfileBuilder
)

async def main():
    settings = get_settings()

    # Conectar a Postgres
    pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password
    )

    # Setup
    repo = BusinessProfileRepository(pool)
    builder = BusinessProfileBuilder(repo)

    # Datos de onboarding
    data = {
        "company_name": "Mi Empresa Tech",
        "industry": "SaaS B2B",
        "business_model": "B2B",
        "revenue_model": "Suscripción",
        "strategic_priorities": [
            {
                "priority": "Reducir churn de 8% a 5%",
                "deadline": "Q2 2025",
                "owner": "CEO"
            }
        ],
        "known_pain_points": [
            "No sabemos por qué los clientes cancelan"
        ],
        "north_star_metric": "Net Revenue Retention",
        "kpis": [
            {
                "name": "Churn rate",
                "target": 5.0,
                "current": 8.0,
                "unit": "%",
                "trend": "declining"
            }
        ]
    }

    # Crear perfil
    profile = await builder.build_from_onboarding(
        client_id="mi_empresa_001",
        answers=data
    )

    print(f"✅ Perfil creado!")
    print(f"Completeness: {profile.profile_completeness:.2%}")
    print(f"\nContexto para LLM:\n{profile.to_context_string()}")

    await pool.close()

asyncio.run(main())
```

### Validar calidad del perfil

```python
# Validar antes de generar hipótesis
quality = await builder.validate_profile_quality("mi_empresa_001")

print(f"Quality Score: {quality['quality_score']:.2%}")
print(f"Ready: {quality['ready_for_hypothesis_generation']}")

if quality['suggestions']:
    print("\nSugerencias de mejora:")
    for s in quality['suggestions']:
        print(f"  - [{s['severity']}] {s['message']}")
```

---

## 📊 Verificar en la base de datos

```sql
-- Ver perfiles creados
SELECT
    client_id,
    profile_data->>'company_name' as company,
    profile_data->>'industry' as industry,
    profile_completeness,
    created_at
FROM business_profiles;

-- Ver detalles de un perfil
SELECT
    profile_data
FROM business_profiles
WHERE client_id = 'demo_seguros_001';

-- Estadísticas
SELECT COUNT(*) as total,
       AVG(profile_completeness) as avg_completeness
FROM business_profiles
WHERE is_active = TRUE;
```

---

## 🔧 Troubleshooting

### Error: "connection refused"
```bash
# Verificar que Postgres esté corriendo
pg_isready

# O
ps aux | grep postgres
```

### Error: "database does not exist"
```bash
# Crear base de datos
createdb igniten_core
```

### Error: "relation does not exist"
```bash
# Ejecutar migración
psql -U postgres -d igniten_core -f migrations/012_unknown_unknowns.sql
```

### Error: "module not found"
```bash
# Verificar que virtual env esté activado
which python  # Debería apuntar a venv/bin/python

# Reinstalar dependencias
pip install -r requirements.txt
```

---

## 📚 Próximos pasos

1. **Crear perfiles de tus clientes**
   - Usa el template: `builder.generate_onboarding_template()`
   - Completa con datos reales
   - Valida calidad antes de continuar

2. **Esperar FASE 2**
   - Hypothesis Generation Engine
   - Integración con SQL Expert v2
   - Generación de insights automática

3. **Explorar el código**
   - Ver `packages/core/domain/unknown_unknowns/business_context/`
   - Leer docstrings en cada método
   - Revisar ejemplos en `scripts/test_phase1.py`

---

## 🆘 Ayuda

- Ver documentación completa: `README.md`
- Ver resumen de FASE 1: `docs/FASE1_SUMMARY.md`
- Reportar issues: GitHub Issues

---

**Última actualización**: 2025-01-24
