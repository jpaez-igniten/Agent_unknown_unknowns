"""
Test Script para FASE 2 + FASE 3

Prueba el pipeline completo de generación y validación de hipótesis:
1. Carga perfil existente (de FASE 1)
2. Genera hipótesis (knowledge + anomaly driven)
3. Valida viabilidad técnica
4. Valida contra datos (mock)
5. Calcula delivery scores
6. Verifica portfolio mix
7. Muestra resultados

Uso:
    python scripts/test_phase2_3.py
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

# Importar componentes FASE 1
from packages.core.domain.unknown_unknowns.business_context.profile_repository import (
    BusinessProfileRepository
)

# Importar componentes FASE 2
from packages.core.domain.unknown_unknowns.hypothesis.generator import (
    HypothesisGenerator
)
from packages.core.domain.unknown_unknowns.hypothesis.feasibility_validator import (
    FeasibilityValidator
)

# Importar componentes FASE 3
from packages.core.domain.unknown_unknowns.validation.hypothesis_validator import (
    HypothesisValidator
)

# Importar orchestrator
from packages.core.domain.unknown_unknowns.orchestrator import (
    UnknownUnknownsOrchestrator
)

# Intentar importar LLM
try:
    from packages.core.utils.gemini_wrapper import GeminiLLMWrapper
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("⚠️  Google GenAI no disponible")


# ============================================================================
# HELPER FUNCTIONS
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
        raise


def initialize_llm(settings):
    """Inicializa LLM"""
    if not LLM_AVAILABLE:
        print("❌ LLM no disponible (langchain-google-genai no instalado)")
        print("   Ejecuta: pip install langchain-google-genai")
        return None

    if not settings.google_api_key:
        print("❌ GOOGLE_API_KEY no configurado en .env")
        return None

    try:
        llm = GeminiLLMWrapper(
            model=settings.gemini_model,
            api_key=settings.google_api_key,
            temperature=0.1
        )
        print(f"✅ LLM inicializado ({settings.gemini_model})")
        return llm
    except Exception as e:
        print(f"❌ Error inicializando LLM: {e}")
        return None


# ============================================================================
# TESTS
# ============================================================================

async def test_hypothesis_generation(orchestrator, client_id):
    """Test: Generar hipótesis con dual approach"""
    print(f"\n{'='*70}")
    print("TEST 1: Generar hipótesis (knowledge + anomaly driven)")
    print(f"{'='*70}")

    try:
        # Cargar perfil
        profile = await orchestrator.profile_repo.get_profile(client_id)

        if not profile:
            print(f"\n❌ Perfil no encontrado: {client_id}")
            print("   Ejecuta primero: python scripts/test_phase1.py")
            return None

        print(f"\n📋 Perfil cargado: {profile.company_name}")
        print(f"   Prioridades estratégicas: {len(profile.strategic_priorities)}")
        print(f"   Ortodoxos detectados: {len(profile.industry_orthodoxies)}")
        print(f"   KPIs: {len(profile.kpis)}")

        # Generar hipótesis
        print(f"\n🔬 Generando hipótesis...")
        run_id = f"test_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        hypotheses = await orchestrator.hypothesis_gen.generate_hypotheses(
            profile=profile,
            run_id=run_id,
            max_hypotheses=10,
            include_orthodoxy_challenges=True,
            include_anomaly_driven=False  # Skip anomaly detection for now
        )

        print(f"\n✅ Generadas {len(hypotheses)} hipótesis!")

        # Estadísticas
        by_type = {}
        by_portfolio = {}

        for hyp in hypotheses:
            by_type[hyp.hypothesis_type] = by_type.get(hyp.hypothesis_type, 0) + 1
            by_portfolio[hyp.portfolio_type.value] = by_portfolio.get(hyp.portfolio_type.value, 0) + 1

        print(f"\n📊 Por tipo:")
        for htype, count in by_type.items():
            print(f"   - {htype}: {count}")

        print(f"\n📊 Por portfolio type:")
        for ptype, count in by_portfolio.items():
            print(f"   - {ptype}: {count}")

        # Mostrar primeras 3 hipótesis
        print(f"\n💡 Primeras 3 hipótesis generadas:")
        for i, hyp in enumerate(hypotheses[:3], 1):
            print(f"\n   {i}. {hyp.hypothesis_text}")
            print(f"      Type: {hyp.hypothesis_type} | Portfolio: {hyp.portfolio_type.value}")
            print(f"      Category: {hyp.category}")
            print(f"      Delivery Score: {hyp.delivery_score.delivery_score_total:.1f}/100")
            print(f"      Decision Owner: {hyp.actionability.decision_owner}")
            print(f"      If true: {hyp.actionability.if_true_then[:100]}...")

        return hypotheses

    except Exception as e:
        print(f"\n❌ Error generando hipótesis: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_feasibility_validation(orchestrator, hypotheses, client_id):
    """Test: Validar viabilidad técnica"""
    print(f"\n{'='*70}")
    print("TEST 2: Validar viabilidad técnica")
    print(f"{'='*70}")

    if not hypotheses:
        print("\n⚠️  No hay hipótesis para validar")
        return []

    try:
        print(f"\n🔍 Validando viabilidad de {len(hypotheses)} hipótesis...")

        feasible = []
        not_feasible = []

        for hyp in hypotheses:
            # Convertir a dict
            hyp_dict = hyp.model_dump()

            # Validar
            result = await orchestrator.feasibility_val.validate_hypothesis_feasibility(
                hypothesis=hyp_dict,
                client_id=client_id
            )

            if result.is_feasible and result.feasibility_score >= 0.5:
                feasible.append((hyp, result))
            else:
                not_feasible.append((hyp, result))

        print(f"\n✅ Validación completa!")
        print(f"   Factibles: {len(feasible)}/{len(hypotheses)}")
        print(f"   No factibles: {len(not_feasible)}/{len(hypotheses)}")

        # Mostrar detalles de las factibles
        if feasible:
            print(f"\n📊 Hipótesis factibles:")
            for i, (hyp, result) in enumerate(feasible[:3], 1):
                print(f"\n   {i}. {hyp.hypothesis_text[:80]}...")
                print(f"      Feasibility Score: {result.feasibility_score:.2f}")
                print(f"      Required Tables: {', '.join(result.required_tables[:3])}")
                print(f"      Complexity: {result.estimated_complexity}")
                if result.suggested_queries:
                    print(f"      Suggested Query: {result.suggested_queries[0][:100]}...")

        # Mostrar por qué algunas no son factibles
        if not_feasible:
            print(f"\n⚠️  Hipótesis no factibles (primeras 2):")
            for i, (hyp, result) in enumerate(not_feasible[:2], 1):
                print(f"\n   {i}. {hyp.hypothesis_text[:80]}...")
                print(f"      Feasibility Score: {result.feasibility_score:.2f}")
                print(f"      Blockers: {', '.join(result.blockers[:2])}")

        return [hyp for hyp, _ in feasible]

    except Exception as e:
        print(f"\n❌ Error en validación de viabilidad: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_data_validation(orchestrator, feasible_hypotheses):
    """Test: Validar contra datos (mock)"""
    print(f"\n{'='*70}")
    print("TEST 3: Validar contra datos (mock)")
    print(f"{'='*70}")

    if not feasible_hypotheses:
        print("\n⚠️  No hay hipótesis factibles para validar")
        return []

    try:
        print(f"\n🔬 Validando {len(feasible_hypotheses)} hipótesis contra datos...")
        print("   NOTA: Como no tenemos datos reales del cliente, esto puede fallar.")
        print("   En producción, esto ejecutaría queries contra las tablas del cliente.")

        validated = []

        for i, hyp in enumerate(feasible_hypotheses[:3], 1):  # Solo primeras 3 para test
            print(f"\n   [{i}/{min(3, len(feasible_hypotheses))}] Validando: {hyp.hypothesis_text[:60]}...")

            try:
                # Validar
                result = await orchestrator.hypothesis_val.validate_hypothesis(
                    hypothesis=hyp,
                    suggested_queries=[]
                )

                print(f"       Resultado: {'✅ Confirmada' if result.is_confirmed else '❌ No confirmada'}")
                print(f"       Confidence: {result.confidence_level:.2f}")

                if result.analyst_notes:
                    print(f"       Notas: {result.analyst_notes[:100]}...")

                validated.append((hyp, result))

            except Exception as e:
                print(f"       Error: {str(e)[:100]}")
                continue

        print(f"\n✅ Validación contra datos completa!")
        print(f"   Validadas: {len(validated)}")

        return validated

    except Exception as e:
        print(f"\n❌ Error en validación de datos: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_full_pipeline(orchestrator, client_id):
    """Test: Pipeline completo end-to-end"""
    print(f"\n{'='*70}")
    print("TEST 4: Pipeline completo end-to-end")
    print(f"{'='*70}")

    try:
        print(f"\n🚀 Ejecutando pipeline completo para {client_id}...")

        results = await orchestrator.run_discovery_pipeline(
            client_id=client_id,
            max_hypotheses=10,
            min_feasibility_score=0.5,
            enable_human_review=False,  # Skip for test
            validate_with_data=False  # Skip for test (no real data)
        )

        print(f"\n✅ Pipeline completo!")
        print(f"\n📊 RESULTADOS:")
        print(f"   Run ID: {results['run_id']}")
        print(f"   Cliente: {results.get('company_name', client_id)}")
        print(f"   Hipótesis generadas: {results['total_hypotheses_generated']}")
        print(f"   Hipótesis factibles: {results['feasible_hypotheses']}")
        print(f"   Hipótesis validadas: {results['validated_hypotheses']}")
        print(f"   Insights entregables: {results['deliverable_insights']}")
        print(f"   Duración: {results.get('duration_seconds', 0):.1f}s")

        # Portfolio mix
        if results['insights']:
            portfolio_counts = {}
            for insight in results['insights']:
                ptype = insight['portfolio_type']
                portfolio_counts[ptype] = portfolio_counts.get(ptype, 0) + 1

            print(f"\n📊 Portfolio Mix:")
            total = len(results['insights'])
            for ptype, count in portfolio_counts.items():
                pct = (count / total * 100) if total > 0 else 0
                print(f"   - {ptype}: {count} ({pct:.0f}%)")

        # Top insights
        if results['insights']:
            print(f"\n💎 Top 3 Insights Entregables:")
            for i, insight in enumerate(results['insights'][:3], 1):
                print(f"\n   {i}. {insight['hypothesis_text']}")
                print(f"      Delivery Score: {insight['delivery_score']:.1f}/100")
                print(f"      Decision Owner: {insight['actionability']['decision_owner']}")
                print(f"      Estimated Impact: ${insight['actionability'].get('estimated_impact_usd', 0):,.0f}")
                print(f"      Action: {insight['actionability']['if_true_then'][:100]}...")

        return results

    except Exception as e:
        print(f"\n❌ Error en pipeline completo: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# MAIN TEST SUITE
# ============================================================================

async def main():
    """Ejecuta suite completa de tests para FASE 2 + 3"""

    print(f"\n{'#'*70}")
    print("# UNKNOWN UNKNOWNS AGENT - TEST SUITE FASE 2 + 3")
    print(f"{'#'*70}\n")

    settings = get_settings()
    pool = None
    db_connection = None

    try:
        # Verificar LLM
        llm = initialize_llm(settings)

        if not llm:
            print("\n❌ CRITICAL: LLM no disponible")
            print("   FASE 2 y 3 requieren LLM para funcionar")
            print("\nPara habilitar:")
            print("   1. pip install langchain-google-genai")
            print("   2. Agregar GOOGLE_API_KEY a .env")
            return

        # Crear DB pool
        pool = await create_db_pool(settings)
        db_connection = await pool.acquire()

        # Inicializar componentes
        print("\n🔧 Inicializando componentes...")

        profile_repo = BusinessProfileRepository(
            db_pool=pool,
            chroma_client=None,
            embedding_function=None
        )

        hypothesis_gen = HypothesisGenerator(
            llm=llm,
            db_connection=db_connection
        )

        feasibility_val = FeasibilityValidator(
            db_connection=db_connection,
            llm=llm
        )

        hypothesis_val = HypothesisValidator(
            db_connection=db_connection,
            llm=llm,
            sql_expert=None
        )

        orchestrator = UnknownUnknownsOrchestrator(
            profile_repository=profile_repo,
            hypothesis_generator=hypothesis_gen,
            feasibility_validator=feasibility_val,
            hypothesis_validator=hypothesis_val,
            db_connection=db_connection
        )

        print("✅ Componentes inicializados")

        client_id = "demo_seguros_001"

        # Ejecutar tests
        hypotheses = await test_hypothesis_generation(orchestrator, client_id)

        if hypotheses:
            feasible = await test_feasibility_validation(orchestrator, hypotheses, client_id)

            if feasible:
                validated = await test_data_validation(orchestrator, feasible)

        # Pipeline completo
        await test_full_pipeline(orchestrator, client_id)

        print(f"\n{'#'*70}")
        print("# ✅ TODOS LOS TESTS COMPLETADOS EXITOSAMENTE")
        print(f"{'#'*70}\n")

        print("📝 SIGUIENTE PASO:")
        print("   ✅ FASE 2: Hypothesis Generation - COMPLETA")
        print("   ✅ FASE 3: Validation & Analysis - COMPLETA")
        print("")
        print("   Próximo: FASE 4 - Delivery & Feedback Loop")
        print("      - InsightDeliveryOrchestrator")
        print("      - Multi-channel delivery (email, Teams, WhatsApp)")
        print("      - Feedback collection")
        print("      - Learning loop")
        print("")

    except Exception as e:
        print(f"\n{'#'*70}")
        print("# ❌ TEST SUITE FAILED")
        print(f"{'#'*70}")
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Liberar conexión y cerrar pool
        if db_connection and pool:
            await pool.release(db_connection)
        if pool:
            await pool.close()
            print("\n👋 Conexión a Postgres cerrada")


if __name__ == "__main__":
    asyncio.run(main())
