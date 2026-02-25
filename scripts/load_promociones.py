"""
Script de carga del perfil real: Promociones Fantásticas S.A.S.

Uso:
    docker exec unknown-unknowns python scripts/load_promociones.py

Qué hace:
    1. Borra TODOS los perfiles existentes en business_profiles (hard delete)
    2. Carga el perfil real de Promociones Fantásticas S.A.S.
    3. Muestra el completeness score y el client_id para usar en el trigger

Para disparar el pipeline después:
    curl -X POST http://localhost:8088/api/v1/run/promociones_fantasticas_001
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncpg
from config.settings import get_settings
from packages.core.domain.unknown_unknowns.business_context.profile_repository import (
    BusinessProfileRepository
)
from packages.core.domain.unknown_unknowns.business_context.profile_builder import (
    BusinessProfileBuilder
)


# ============================================================================
# PERFIL REAL: PROMOCIONES FANTÁSTICAS S.A.S.
# ============================================================================

CLIENT_ID = "promociones_fantasticas_001"

PROMOCIONES_ONBOARDING_DATA = {
    # ---- Identidad ----
    "company_name": "Promociones Fantásticas S.A.S.",
    "industry": "Manufactura",
    "industry_sub_segment": (
        "Manufactura de empaques y utensilios desechables sostenibles para la industria "
        "alimentaria — pitillos, vasos, platos, cubiertos, cajas, bowls, bandejas, "
        "contenedores y portacomidas en materiales PLA, bagazo de caña y papel"
    ),
    "business_model": "B2B",
    "revenue_model": "Transaccional",

    # ---- Tamaño ----
    "size": {
        "employees": 250,
        "revenue_range": "Confidencial",
        "locations": 1,
        "countries": 20,
        "customers": None
    },

    # ---- Estructura operativa ----
    "key_departments": [
        "Producción",
        "Exportaciones y logística internacional",
        "Ventas y desarrollo de negocio",
        "Compras y abastecimiento",
        "Finanzas y costos"
    ],

    # ---- Sistemas ----
    "erp_system": "SAP",
    "sap_modules": ["FI", "CO", "MM", "SD", "PP"],
    "other_systems": [
        "Power BI (estático, sin análisis proactivo — Igniten es el primer paso hacia analytics conversacional activo)"
    ],
    "data_maturity": "medium",
    "historical_data_years": 7,  # 2018 a la fecha

    # ---- Métrica norte ----
    "north_star_metric": "Volumen de producción exportado y revenue por país/canal",

    # ---- Pain points (los 5 más críticos) ----
    "known_pain_points": [
        (
            "Inventario entre planta y distribución a 20+ países sin visibilidad en tiempo real — "
            "no se sabe con precisión qué hay en tránsito, qué está en bodega de cada destino "
            "y cuándo se va a agotar"
        ),
        (
            "Seguimiento del pipeline con clientes grandes que tienen ciclos de compra largos y "
            "volúmenes variables (Starbucks, Coca-Cola, Grupo Nutresa) — no hay visibilidad de "
            "cuándo van a recomprar ni por qué volumen"
        ),
        (
            "Planificación de producción vs demanda estacional — foodservice tiene picos marcados "
            "(Semana Santa, diciembre, temporadas de fútbol, vacaciones escolares) y la producción "
            "frecuentemente reacciona tarde en lugar de anticiparse"
        ),
        (
            "Costos de materias primas volátiles — PLA, bagazo de caña y papel son commodities "
            "con precio cambiante; no se sabe cuánto margen se pierde en períodos donde el alza "
            "de materias primas no se traslada a precios de venta"
        ),
        (
            "Rentabilidad real por cliente y canal — especialmente en cuentas con logística "
            "internacional compleja; algunos mercados que parecen rentables en bruto pueden ser "
            "neutros o negativos al incluir costos reales de exportación, aranceles y tiempos de tránsito"
        ),
    ],

    # ---- Prioridades estratégicas ----
    "strategic_priorities": [
        {
            "priority": (
                "Consolidar liderazgo en LATAM y Caribe profundizando penetración "
                "en los 20+ países donde ya operan"
            ),
            "deadline": "2026",
            "owner": "Gerencia General",
            "target_metric": "Revenue por mercado y participación por país",
            "current_status": "in_progress"
        },
        {
            "priority": (
                "Escalar manufactura manteniendo estándares de certificación "
                "(ISO 9001, BASC, compostabilidad 7PI740)"
            ),
            "deadline": "2025",
            "owner": "Dirección de Operaciones",
            "target_metric": "Eficiencia de líneas de producción % vs capacidad instalada",
            "current_status": "in_progress"
        },
        {
            "priority": (
                "Diversificar portafolio de pitillos hacia solución completa de empaques — "
                "vasos, platos, contenedores, portacomidas"
            ),
            "deadline": "2026",
            "owner": "Dirección Comercial",
            "target_metric": "Revenue por categoría de producto nueva",
            "current_status": "planning"
        },
    ],

    # ---- KPIs ----
    "kpis": [
        {
            "name": "Eficiencia de líneas de producción",
            "unit": "% vs capacidad instalada",
            "trend": "stable",
            "period": "monthly"
        },
        {
            "name": "Fill rate de pedidos por país/cliente",
            "unit": "%",
            "trend": "stable",
            "period": "monthly"
        },
        {
            "name": "Costo por unidad producida por SKU",
            "unit": "USD",
            "trend": "declining",
            "period": "monthly"
        },
        {
            "name": "Revenue por mercado y por canal",
            "unit": "USD",
            "trend": "improving",
            "period": "monthly"
        },
        {
            "name": "Rotación de inventario de materia prima",
            "unit": "días",
            "trend": "stable",
            "period": "monthly"
        },
        {
            "name": "Margen neto por cliente",
            "unit": "%",
            "trend": "stable",
            "period": "monthly"
        },
    ],

    # ---- Iniciativas activas ----
    "active_initiatives": [
        {
            "name": "Expansión de portafolio hacia solución completa de empaques",
            "status": "planning",
            "owner": "Dirección Comercial"
        },
        {
            "name": "Implementación de analytics conversacional activo con Igniten",
            "status": "in_progress",
            "owner": "Gerencia General"
        },
    ],

    # ---- Regulaciones ----
    "regulatory_constraints": [
        "BASC — Business Alliance for Secure Commerce (comercio exterior seguro)",
        "ISO 9001:2015 — Sistema de gestión de calidad",
        "Certificación 7PI740 — Primera certificación de pitillos compostables en Colombia",
        "Trazabilidad de materiales compostables certificados: FSC, FDA, OK Compost, BPA Free, PFAS Free",
    ],

    # ---- Contexto competitivo ----
    "competitive_context": (
        "Compiten contra importadores asiáticos en precio. Se diferencian por manufactura local "
        "en Colombia, certificaciones internacionales de sostenibilidad (FSC, FDA, OK Compost, "
        "BPA Free, PFAS Free) y la primera certificación de pitillos compostables en Colombia "
        "(7PI740). Clientes de referencia: Starbucks, Coca-Cola, Postobón, Grupo Nutresa, "
        "Nestlé, Dunkin', Cine Colombia, Andrés Carne de Res. La presión de precio es constante "
        "— la eficiencia operativa y la rentabilidad real por cliente son críticas para sostener "
        "márgenes frente a competidores asiáticos."
    ),

    # ---- Preferencias del agente ----
    "preferences": {
        "insight_focus": [
            "Estacionalidad no documentada por SKU y país",
            "Clientes silenciosos en mercados internacionales — detección de churn por frecuencia de compra",
            "Rentabilidad oculta por SKU — identificar SKUs con margen superior al promedio y baja participación",
            "Costo real de exportación por destino — rentabilidad real neta por mercado",
            "Correlación entre precio de materia prima y margen perdido en períodos de alza",
            "Eficiencia de línea de producción por turno, día y material",
            "Oportunidades de cross-sell no capturadas por cuenta",
        ],
        "insight_frequency": "weekly",
        "delivery_channels": ["internal"],
    },
}


# ============================================================================
# MAIN
# ============================================================================

async def main():
    settings = get_settings()
    pool = None

    print("\n" + "=" * 60)
    print("  Carga de perfil: Promociones Fantásticas S.A.S.")
    print("=" * 60)

    try:
        # 1. Conectar a Postgres
        print(f"\n📊 Conectando a Postgres: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}...")
        pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            min_size=1,
            max_size=5
        )
        print("✅ Conectado")

        repository = BusinessProfileRepository(
            db_pool=pool,
            chroma_client=None,
            embedding_function=None
        )
        builder = BusinessProfileBuilder(repository)

        # 2. Borrar TODOS los perfiles existentes
        print("\n🗑️  Borrando todos los perfiles existentes...")
        existing = await repository.list_profiles(active_only=False, limit=500)
        if existing:
            for p in existing:
                await repository.hard_delete_profile(p.client_id)
                print(f"   Eliminado: {p.client_id} ({p.company_name})")
            print(f"   Total eliminados: {len(existing)}")
        else:
            print("   No había perfiles previos.")

        # 3. Cargar el perfil real
        print(f"\n🏭 Creando perfil: {PROMOCIONES_ONBOARDING_DATA['company_name']}...")
        profile = await builder.build_from_onboarding(
            client_id=CLIENT_ID,
            answers=PROMOCIONES_ONBOARDING_DATA
        )

        # 4. Confirmar
        print("\n" + "=" * 60)
        print("✅ Perfil creado exitosamente")
        print("=" * 60)
        print(f"   client_id         : {profile.client_id}")
        print(f"   Empresa           : {profile.company_name}")
        print(f"   Industria         : {profile.industry}")
        print(f"   Pain points       : {len(profile.known_pain_points)}")
        print(f"   Prioridades       : {len(profile.strategic_priorities)}")
        print(f"   KPIs              : {len(profile.kpis)}")
        print(f"   Completeness      : {profile.profile_completeness:.0%}")
        print(f"   Confidence score  : {profile.confidence_score:.0%}")
        print(f"   Datos históricos  : {profile.historical_data_years} años")
        print("\n📡 Para disparar el pipeline, ejecutá:")
        print(f"   curl -X POST http://localhost:8088/api/v1/run/{CLIENT_ID}")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        if pool:
            await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
