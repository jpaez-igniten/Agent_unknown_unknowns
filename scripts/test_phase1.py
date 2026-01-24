"""
Test Script para FASE 1

Prueba la creación de un BusinessProfile desde datos de onboarding:
1. Conecta a Postgres (y opcionalmente ChromaDB)
2. Crea un perfil de ejemplo
3. Guarda en la base de datos
4. Recupera el perfil
5. Muestra el resultado

Uso:
    python scripts/test_phase1.py
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# Agregar path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncpg
from config.settings import get_settings

# Importar modelos y clases
from packages.core.domain.unknown_unknowns.business_context.profile_schema import (
    BusinessProfile,
    StrategicPriority,
    KPI,
    SizeMetrics
)
from packages.core.domain.unknown_unknowns.business_context.profile_repository import (
    BusinessProfileRepository
)
from packages.core.domain.unknown_unknowns.business_context.profile_builder import (
    BusinessProfileBuilder
)


# ============================================================================
# DATOS DE EJEMPLO PARA ONBOARDING
# ============================================================================

EXAMPLE_ONBOARDING_DATA = {
    "company_name": "Seguros Carga S.A.",
    "industry": "Seguros B2B",
    "industry_sub_segment": "Seguros de carga internacional",
    "business_model": "B2B",
    "revenue_model": "Comisión",

    "size": {
        "employees": 250,
        "revenue_range": "$20M-$50M",
        "locations": 3,
        "countries": 2,
        "customers": 450
    },

    "strategic_priorities": [
        {
            "priority": "Reducir costos operativos 15% para fin de Q2 2025",
            "deadline": "Q2 2025",
            "owner": "COO",
            "target_metric": "Costo operativo / Revenue",
            "current_status": "in_progress"
        },
        {
            "priority": "Aumentar margen neto de 8% a 12%",
            "deadline": "Q4 2025",
            "owner": "CFO",
            "target_metric": "Net margin",
            "current_status": "planning"
        },
        {
            "priority": "Mejorar retention de clientes top a 95%",
            "deadline": "Q3 2025",
            "owner": "VP Sales",
            "target_metric": "Client retention rate",
            "current_status": "planning"
        }
    ],

    "known_pain_points": [
        "No sabemos qué clientes son realmente rentables después de descuentos y costos de servicio",
        "Los descuentos se otorgan sin criterio claro, algunos agentes dan hasta 25%",
        "Algunos agentes generan mucho volumen pero bajo margen",
        "No tenemos visibilidad de costos de siniestralidad por cliente",
        "El pricing es estático y no refleja el riesgo real de cada cliente"
    ],

    "north_star_metric": "Margen neto",

    "kpis": [
        {
            "name": "Margen bruto",
            "target": 35.0,
            "current": 28.0,
            "unit": "%",
            "trend": "declining",
            "period": "monthly"
        },
        {
            "name": "Margen neto",
            "target": 12.0,
            "current": 8.0,
            "unit": "%",
            "trend": "stable",
            "period": "monthly"
        },
        {
            "name": "Costo operativo / Revenue",
            "target": 15.0,
            "current": 20.0,
            "unit": "%",
            "trend": "declining",
            "period": "monthly"
        },
        {
            "name": "Client retention (top 20)",
            "target": 95.0,
            "current": 88.0,
            "unit": "%",
            "trend": "improving",
            "period": "annual"
        }
    ],

    "key_departments": [
        "Ventas",
        "Operaciones",
        "Finanzas",
        "Underwriting",
        "Claims"
    ],

    "primary_processes": [
        {
            "name": "Venta de pólizas",
            "department": "Ventas",
            "steps": [
                "Prospección",
                "Cotización",
                "Negociación y descuentos",
                "Cierre",
                "Emisión de póliza"
            ],
            "kpis": ["Conversion rate", "Average premium", "Discount %"],
            "pain_points": ["Descuentos sin control", "Pricing no refleja riesgo"]
        },
        {
            "name": "Gestión de siniestros",
            "department": "Claims",
            "steps": [
                "Reporte",
                "Evaluación",
                "Aprobación",
                "Pago"
            ],
            "kpis": ["Claim ratio", "Time to settle"],
            "pain_points": ["No visibilidad de siniestralidad por cliente"]
        }
    ],

    "active_initiatives": [
        {
            "name": "Implementar pricing dinámico basado en riesgo",
            "status": "planning",
            "start_date": "2025-02-01",
            "expected_completion": "2025-08-31",
            "owner": "CFO",
            "budget": 200000
        },
        {
            "name": "Programa de rentabilización de clientes",
            "status": "planning",
            "start_date": "2025-03-01",
            "expected_completion": "2025-06-30",
            "owner": "VP Sales"
        }
    ],

    "erp_system": "SAP ECC",
    "sap_modules": ["FI", "CO", "SD"],
    "other_systems": [
        "Salesforce (CRM)",
        "Custom underwriting system",
        "Tableau (BI)"
    ],

    "data_maturity": "medium",
    "historical_data_years": 3,

    "industry_benchmarks": {
        "avg_gross_margin": 32.0,
        "avg_net_margin": 10.0,
        "avg_combined_ratio": 95.0,
        "avg_retention_rate": 92.0
    },

    "regulatory_constraints": [
        "Superintendencia de Seguros",
        "GDPR (operaciones en EU)",
        "SOX (por matriz en US)"
    ],

    "competitive_context": "Mercado competitivo con 2 grandes players (40% market share) y 15+ pequeños. Competencia principalmente por precio.",

    "preferences": {
        "insight_frequency": "weekly",
        "focus_areas": ["financial", "commercial"],
        "delivery_channels": ["email"]
    }
}


# ============================================================================
# FUNCIONES DE TEST
# ============================================================================

async def create_db_pool(settings):
    """Crea connection pool a Postgres"""
    print("📊 Conectando a Postgres...")
    try:
        pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            min_size=1,
            max_size=5
        )
        print(f"✅ Conectado a Postgres: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
        return pool
    except Exception as e:
        print(f"❌ Error conectando a Postgres: {e}")
        print("\nVerifica que:")
        print("  1. Postgres esté corriendo")
        print("  2. Las credenciales en .env sean correctas")
        print("  3. La base de datos exista")
        print("  4. La migración 012_unknown_unknowns.sql haya sido ejecutada")
        raise


async def test_create_profile(builder: BusinessProfileBuilder, client_id: str):
    """Test: Crear perfil desde onboarding"""
    print(f"\n{'='*70}")
    print("TEST 1: Crear perfil desde datos de onboarding")
    print(f"{'='*70}")

    try:
        profile = await builder.build_from_onboarding(
            client_id=client_id,
            answers=EXAMPLE_ONBOARDING_DATA
        )

        print(f"\n✅ Perfil creado exitosamente!")
        print(f"   Client ID: {profile.client_id}")
        print(f"   Empresa: {profile.company_name}")
        print(f"   Industria: {profile.industry}")
        print(f"   Completeness: {profile.profile_completeness:.2%}")
        print(f"   Confidence: {profile.confidence_score:.2%}")

        return profile

    except ValueError as e:
        if "already exists" in str(e):
            print(f"\n⚠️  Perfil ya existe: {client_id}")
            print("   Eliminando perfil existente para re-crear...")
            await builder.repository.hard_delete_profile(client_id)
            # Reintentar
            return await builder.build_from_onboarding(client_id, EXAMPLE_ONBOARDING_DATA)
        raise
    except Exception as e:
        print(f"\n❌ Error creando perfil: {e}")
        raise


async def test_retrieve_profile(repository: BusinessProfileRepository, client_id: str):
    """Test: Recuperar perfil de la BD"""
    print(f"\n{'='*70}")
    print("TEST 2: Recuperar perfil desde la base de datos")
    print(f"{'='*70}")

    try:
        profile = await repository.get_profile(client_id)

        if profile:
            print(f"\n✅ Perfil recuperado exitosamente!")
            print(f"\n{profile.to_context_string()}")
            return profile
        else:
            print(f"\n❌ Perfil no encontrado: {client_id}")
            return None

    except Exception as e:
        print(f"\n❌ Error recuperando perfil: {e}")
        raise


async def test_profile_quality(builder: BusinessProfileBuilder, client_id: str):
    """Test: Validar calidad del perfil"""
    print(f"\n{'='*70}")
    print("TEST 3: Validar calidad del perfil")
    print(f"{'='*70}")

    try:
        quality = await builder.validate_profile_quality(client_id)

        print(f"\n📊 Reporte de calidad:")
        print(f"   Quality Score: {quality['quality_score']:.2%}")
        print(f"   Completeness: {quality['completeness']:.2%}")
        print(f"   Confidence: {quality['confidence']:.2%}")
        print(f"   Critical Issues: {quality['critical_issues']}")
        print(f"   Total Suggestions: {quality['total_suggestions']}")
        print(f"   Ready for Hypothesis Generation: {'✅' if quality['ready_for_hypothesis_generation'] else '❌'}")

        if quality['suggestions']:
            print(f"\n💡 Sugerencias de mejora:")
            for i, suggestion in enumerate(quality['suggestions'], 1):
                severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                emoji = severity_emoji.get(suggestion['severity'], "ℹ️")
                print(f"   {i}. {emoji} [{suggestion['severity'].upper()}] {suggestion['field']}")
                print(f"      {suggestion['message']}")

        return quality

    except Exception as e:
        print(f"\n❌ Error validando calidad: {e}")
        raise


async def test_list_profiles(repository: BusinessProfileRepository):
    """Test: Listar todos los perfiles"""
    print(f"\n{'='*70}")
    print("TEST 4: Listar todos los perfiles")
    print(f"{'='*70}")

    try:
        profiles = await repository.list_profiles(active_only=True)

        print(f"\n✅ Encontrados {len(profiles)} perfil(es) activo(s):")
        for i, profile in enumerate(profiles, 1):
            print(f"\n   {i}. {profile.company_name} ({profile.client_id})")
            print(f"      Industria: {profile.industry}")
            print(f"      Completeness: {profile.profile_completeness:.2%}")
            print(f"      Prioridades: {len(profile.strategic_priorities)}")
            print(f"      KPIs: {len(profile.kpis)}")

        return profiles

    except Exception as e:
        print(f"\n❌ Error listando perfiles: {e}")
        raise


async def test_stats(repository: BusinessProfileRepository):
    """Test: Obtener estadísticas"""
    print(f"\n{'='*70}")
    print("TEST 5: Estadísticas de perfiles")
    print(f"{'='*70}")

    try:
        stats = await repository.get_profile_stats()

        print(f"\n📈 Estadísticas:")
        print(f"   Total profiles: {stats['total_profiles']}")
        print(f"   Active profiles: {stats['active_profiles']}")
        print(f"   Average completeness: {stats['avg_completeness']:.2%}")
        print(f"   Profiles with runs: {stats['profiles_with_runs']}")

        if stats['by_industry']:
            print(f"\n   Por industria:")
            for industry_stat in stats['by_industry']:
                print(f"      - {industry_stat['industry']}: {industry_stat['count']}")

        return stats

    except Exception as e:
        print(f"\n❌ Error obteniendo estadísticas: {e}")
        raise


async def test_template_generation(builder: BusinessProfileBuilder):
    """Test: Generar template de onboarding"""
    print(f"\n{'='*70}")
    print("TEST 6: Generar template de onboarding")
    print(f"{'='*70}")

    try:
        template = builder.generate_onboarding_template()

        print(f"\n✅ Template generado:")
        print(json.dumps(template, indent=2, default=str))

        return template

    except Exception as e:
        print(f"\n❌ Error generando template: {e}")
        raise


# ============================================================================
# MAIN TEST SUITE
# ============================================================================

async def main():
    """Ejecuta suite completa de tests para FASE 1"""

    print(f"\n{'#'*70}")
    print("# UNKNOWN UNKNOWNS AGENT - TEST SUITE FASE 1")
    print(f"{'#'*70}\n")

    settings = get_settings()
    pool = None

    try:
        # Crear DB pool
        pool = await create_db_pool(settings)

        # Inicializar repository y builder
        repository = BusinessProfileRepository(
            db_pool=pool,
            chroma_client=None,  # ChromaDB opcional en FASE 1
            embedding_function=None
        )

        builder = BusinessProfileBuilder(repository)

        client_id = "demo_seguros_001"

        # Ejecutar tests
        await test_create_profile(builder, client_id)
        await test_retrieve_profile(repository, client_id)
        await test_profile_quality(builder, client_id)
        await test_list_profiles(repository)
        await test_stats(repository)
        # await test_template_generation(builder)  # Opcional

        print(f"\n{'#'*70}")
        print("# ✅ TODOS LOS TESTS COMPLETADOS EXITOSAMENTE")
        print(f"{'#'*70}\n")

        print("📝 SIGUIENTE PASO:")
        print("   El perfil está creado y listo para FASE 2:")
        print("   - Generación de hipótesis")
        print("   - Validación con SQL")
        print("   - Análisis de insights")
        print("")

    except Exception as e:
        print(f"\n{'#'*70}")
        print("# ❌ TEST SUITE FAILED")
        print(f"{'#'*70}")
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cerrar pool
        if pool:
            await pool.close()
            print("\n👋 Conexión a Postgres cerrada")


if __name__ == "__main__":
    asyncio.run(main())
