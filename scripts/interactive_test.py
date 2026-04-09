"""
Interactive Testing Script - Unknown Unknowns Agent

Este script te guía paso a paso en el testing del sistema,
mostrando la calidad de las hipótesis en tiempo real.

Uso:
    python scripts/interactive_test.py
"""

import asyncio
import json
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Agregar path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncpg
from config.settings import get_settings

# Importar componentes
from packages.core.domain.unknown_unknowns.business_context.profile_repository import (
    BusinessProfileRepository
)
from packages.core.domain.unknown_unknowns.business_context.profile_builder import (
    BusinessProfileBuilder
)
from packages.core.domain.unknown_unknowns.hypothesis.generator import (
    HypothesisGenerator
)
from packages.core.domain.unknown_unknowns.hypothesis.feasibility_validator import (
    FeasibilityValidator
)
from packages.core.domain.unknown_unknowns.hypothesis.models import Hypothesis

# LLM
try:
    from packages.core.utils.gemini_wrapper import GeminiLLMWrapper
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


# ============================================================================
# HELPERS
# ============================================================================

def print_header(title: str):
    """Imprime header visual"""
    print(f"\n{'='*70}")
    print(f"{title.center(70)}")
    print(f"{'='*70}\n")


def print_step(step_num: int, title: str):
    """Imprime paso actual"""
    print(f"\n{'─'*70}")
    print(f"PASO {step_num}: {title}")
    print(f"{'─'*70}\n")


def print_success(message: str):
    """Imprime mensaje de éxito"""
    print(f"✅ {message}")


def print_warning(message: str):
    """Imprime warning"""
    print(f"⚠️  {message}")


def print_error(message: str):
    """Imprime error"""
    print(f"❌ {message}")


def print_info(message: str):
    """Imprime info"""
    print(f"ℹ️  {message}")


def validate_hypothesis_quality(hypothesis: Hypothesis) -> Dict[str, Any]:
    """
    Valida la calidad de una hipótesis individual.

    Returns:
        Dict con quality_score, issues, y análisis detallado
    """
    issues = []
    warnings = []
    strengths = []
    score = 100

    # 1. Especificidad
    if len(hypothesis.hypothesis_text) < 50:
        issues.append("Hipótesis muy corta - falta especificidad")
        score -= 20
    elif len(hypothesis.hypothesis_text) > 200:
        warnings.append("Hipótesis muy larga - considerar simplificar")

    # Buscar números/métricas
    has_numbers = any(char.isdigit() for char in hypothesis.hypothesis_text)
    if not has_numbers:
        warnings.append("No hay números/métricas - falta cuantificación")
        score -= 10
    else:
        strengths.append("Incluye números/métricas concretas")

    # 2. Actionability
    if not hypothesis.actionability.if_true_then:
        issues.append("CRÍTICO: Falta if_true_then")
        score -= 30
    elif len(hypothesis.actionability.if_true_then) < 30:
        warnings.append("if_true_then muy vago - necesita más detalle")
        score -= 15
    elif len(hypothesis.actionability.if_true_then) > 100:
        strengths.append("if_true_then claro y detallado")

    if not hypothesis.actionability.decision_owner:
        issues.append("CRÍTICO: Falta decision_owner")
        score -= 20
    elif hypothesis.actionability.decision_owner == "CEO":
        warnings.append("Decision owner muy genérico (CEO) - ser más específico")
        score -= 5
    else:
        strengths.append(f"Decision owner específico: {hypothesis.actionability.decision_owner}")

    # Action threshold
    if hypothesis.actionability.action_threshold.min_confidence:
        strengths.append("Tiene action threshold definido")
    else:
        warnings.append("Falta action threshold - dificulta decisión")
        score -= 10

    # 3. Evidence
    if not hypothesis.evidence:
        warnings.append("Sin evidencia - falta contexto")
        score -= 15
    elif len(hypothesis.evidence) >= 2:
        strengths.append(f"Bien fundamentada ({len(hypothesis.evidence)} evidencias)")
    else:
        warnings.append("Poca evidencia - solo 1 fuente")
        score -= 5

    # 4. Confidence
    if hypothesis.confidence.confidence_total < 0.5:
        issues.append("Confianza muy baja (<50%)")
        score -= 20
    elif hypothesis.confidence.confidence_total < 0.7:
        warnings.append("Confianza moderada-baja (<70%)")
        score -= 10
    else:
        strengths.append(f"Alta confianza ({hypothesis.confidence.confidence_total:.0%})")

    # Caveats
    if hypothesis.confidence.confidence_caveats:
        strengths.append(f"Transparency: {len(hypothesis.confidence.confidence_caveats)} caveats mencionados")
    else:
        warnings.append("Sin caveats - falta transparency sobre limitaciones")

    # 5. Delivery Score
    if hypothesis.delivery_score.delivery_score_total < 70:
        warnings.append(f"Delivery score bajo ({hypothesis.delivery_score.delivery_score_total:.0f}/100) - no se entregaría")
        score -= 10
    else:
        strengths.append(f"Alto delivery score ({hypothesis.delivery_score.delivery_score_total:.0f}/100)")

    # 6. Business Impact
    if hypothesis.actionability.estimated_impact_usd:
        if hypothesis.actionability.estimated_impact_usd >= 100000:
            strengths.append(f"Alto impacto estimado (${hypothesis.actionability.estimated_impact_usd:,.0f})")
        else:
            warnings.append(f"Impacto modesto (${hypothesis.actionability.estimated_impact_usd:,.0f})")
    else:
        warnings.append("Sin impacto estimado")
        score -= 5

    # 7. Portfolio Type
    portfolio_ok = {
        "quick_win": "Quick win - bueno para momentum",
        "medium_term": "Medium term - balance correcto",
        "strategic_bet": "Strategic bet - visión largo plazo"
    }
    strengths.append(portfolio_ok.get(hypothesis.portfolio_type.value, "Portfolio type definido"))

    return {
        "quality_score": max(0, min(100, score)),
        "is_high_quality": score >= 70,
        "is_deliverable": hypothesis.delivery_score.should_deliver,
        "issues": issues,
        "warnings": warnings,
        "strengths": strengths,
        "metrics": {
            "specificity": len(hypothesis.hypothesis_text),
            "has_numbers": has_numbers,
            "actionability_length": len(hypothesis.actionability.if_true_then),
            "evidence_count": len(hypothesis.evidence),
            "confidence": hypothesis.confidence.confidence_total,
            "delivery_score": hypothesis.delivery_score.delivery_score_total,
            "estimated_impact": hypothesis.actionability.estimated_impact_usd or 0
        }
    }


def print_hypothesis_analysis(hypothesis: Hypothesis, index: int):
    """Imprime análisis detallado de una hipótesis"""
    validation = validate_hypothesis_quality(hypothesis)

    print(f"\n{'─'*70}")
    print(f"HIPÓTESIS #{index}")
    print(f"{'─'*70}")

    # Texto
    print(f"\n📝 {hypothesis.hypothesis_text}")

    # Quality Score
    score = validation['quality_score']
    score_color = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
    print(f"\n{score_color} Quality Score: {score}/100")

    # Delivery
    if validation['is_deliverable']:
        print(f"✅ ENTREGABLE (Delivery Score: {validation['metrics']['delivery_score']:.0f}/100)")
    else:
        print(f"❌ NO ENTREGABLE (Delivery Score: {validation['metrics']['delivery_score']:.0f}/100)")

    # Metadata
    print(f"\n📊 Metadata:")
    print(f"   Tipo: {hypothesis.hypothesis_type}")
    print(f"   Categoría: {hypothesis.category}")
    print(f"   Portfolio: {hypothesis.portfolio_type.value}")
    print(f"   Confianza: {hypothesis.confidence.confidence_total:.0%}")
    print(f"   Owner: {hypothesis.actionability.decision_owner}")

    # Actionability
    print(f"\n✅ Si es verdadero:")
    print(f"   {hypothesis.actionability.if_true_then[:150]}...")

    if hypothesis.actionability.estimated_impact_usd:
        print(f"\n💰 Impacto estimado: ${hypothesis.actionability.estimated_impact_usd:,.0f}")

    # Evidencia
    if hypothesis.evidence:
        print(f"\n🔬 Evidencia ({len(hypothesis.evidence)}):")
        for i, ev in enumerate(hypothesis.evidence[:2], 1):
            print(f"   {i}. {ev[:80]}...")

    # Strengths
    if validation['strengths']:
        print(f"\n💪 Fortalezas:")
        for strength in validation['strengths'][:3]:
            print(f"   ✓ {strength}")

    # Warnings
    if validation['warnings']:
        print(f"\n⚠️  Advertencias:")
        for warning in validation['warnings']:
            print(f"   ⚠ {warning}")

    # Issues
    if validation['issues']:
        print(f"\n❌ Problemas:")
        for issue in validation['issues']:
            print(f"   ✗ {issue}")


def calculate_portfolio_stats(hypotheses: List[Hypothesis]) -> Dict[str, Any]:
    """Calcula estadísticas del portfolio"""
    total = len(hypotheses)
    if total == 0:
        return {}

    by_type = {}
    by_portfolio = {}
    by_category = {}
    deliverable = 0
    total_impact = 0

    for hyp in hypotheses:
        # Por tipo
        by_type[hyp.hypothesis_type] = by_type.get(hyp.hypothesis_type, 0) + 1

        # Por portfolio
        ptype = hyp.portfolio_type.value
        by_portfolio[ptype] = by_portfolio.get(ptype, 0) + 1

        # Por categoría
        by_category[hyp.category] = by_category.get(hyp.category, 0) + 1

        # Deliverable
        if hyp.delivery_score.should_deliver:
            deliverable += 1

        # Impacto
        if hyp.actionability.estimated_impact_usd:
            total_impact += hyp.actionability.estimated_impact_usd

    return {
        "total": total,
        "deliverable": deliverable,
        "deliverable_pct": (deliverable / total * 100) if total > 0 else 0,
        "total_estimated_impact": total_impact,
        "avg_impact": total_impact / total if total > 0 else 0,
        "by_type": by_type,
        "by_portfolio": by_portfolio,
        "by_category": by_category
    }


# ============================================================================
# MAIN INTERACTIVE TEST
# ============================================================================

async def main():
    """Test interactivo paso a paso"""

    print_header("🧪 UNKNOWN UNKNOWNS AGENT - TEST INTERACTIVO")

    print("""
Este script te guiará paso a paso en el testing del sistema,
mostrando la calidad de las hipótesis generadas.

Presiona ENTER para continuar en cada paso...
""")

    input("Presiona ENTER para comenzar...")

    settings = get_settings()
    pool = None
    db_connection = None

    try:
        # ===== PASO 1: Verificar Configuración =====
        print_step(1, "Verificar Configuración")

        print("Verificando configuración...")
        print(f"   PostgreSQL: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
        print(f"   Google API Key: {'✅ Configurado' if settings.google_api_key else '❌ Falta'}")

        if not settings.google_api_key:
            print_error("GOOGLE_API_KEY no configurado en .env")
            print_info("Edita .env y agrega: GOOGLE_API_KEY=tu_key_aqui")
            return

        if not LLM_AVAILABLE:
            print_error("langchain-google-genai no instalado")
            print_info("Ejecuta: pip install langchain-google-genai")
            return

        print_success("Configuración OK")
        input("\nPresiona ENTER para continuar...")

        # ===== PASO 2: Conectar a Base de Datos =====
        print_step(2, "Conectar a PostgreSQL")

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
            print_success(f"Conectado a PostgreSQL: {settings.postgres_db}")

            # Verificar tablas
            db_connection = await pool.acquire()
            tables = await db_connection.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                  AND table_name IN ('business_profiles', 'hypothesis_graveyard', 'human_review_queue')
            """)

            print(f"\nTablas encontradas: {len(tables)}")
            for table in tables:
                print(f"   ✓ {table['table_name']}")

            if len(tables) < 3:
                print_warning("Faltan tablas. Ejecuta: psql -d igniten_core -f migrations/012_unknown_unknowns_v2.sql")

        except Exception as e:
            print_error(f"Error conectando a PostgreSQL: {e}")
            print_info("Verifica que Postgres esté corriendo: pg_isready")
            return

        input("\nPresiona ENTER para continuar...")

        # ===== PASO 3: Cargar/Crear Perfil =====
        print_step(3, "Cargar Perfil de Cliente")

        profile_repo = BusinessProfileRepository(
            db_pool=pool,
            chroma_client=None,
            embedding_function=None
        )

        client_id = "demo_seguros_001"
        profile = await profile_repo.get_profile(client_id)

        if not profile:
            print_info(f"Perfil {client_id} no existe. Creándolo...")
            print_info("Ejecuta primero: python scripts/test_phase1.py")
            await pool.release(db_connection)
            await pool.close()
            return

        print_success(f"Perfil cargado: {profile.company_name}")
        print(f"\n   Industria: {profile.industry}")
        print(f"   Completeness: {profile.profile_completeness:.0%}")
        print(f"   Strategic Priorities: {len(profile.strategic_priorities)}")
        print(f"   Pain Points: {len(profile.known_pain_points)}")
        print(f"   KPIs: {len(profile.kpis)}")
        print(f"   Ortodoxos detectados: {len(profile.industry_orthodoxies)}")

        if profile.profile_completeness < 0.7:
            print_warning(f"Completeness bajo ({profile.profile_completeness:.0%}). Recomendado: >= 70%")

        input("\nPresiona ENTER para continuar...")

        # ===== PASO 4: Inicializar LLM =====
        print_step(4, "Inicializar LLM (Gemini)")

        llm = GeminiLLMWrapper(
            model=settings.gemini_model,
            api_key=settings.google_api_key,
            temperature=0.1
        )
        print_success(f"LLM inicializado ({settings.gemini_model})")

        input("\nPresiona ENTER para continuar...")

        # ===== PASO 5: Generar Hipótesis =====
        print_step(5, "Generar Hipótesis")

        print("Generando hipótesis (esto puede tomar 30-60 segundos)...")

        hypothesis_gen = HypothesisGenerator(llm=llm, db_connection=db_connection)

        run_id = f"interactive_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        hypotheses = await hypothesis_gen.generate_hypotheses(
            profile=profile,
            run_id=run_id,
            max_hypotheses=10,
            include_orthodoxy_challenges=True,
            include_anomaly_driven=False  # Skip para test rápido
        )

        print_success(f"Generadas {len(hypotheses)} hipótesis!")

        # Stats
        stats = calculate_portfolio_stats(hypotheses)

        print(f"\n📊 Estadísticas del Portfolio:")
        print(f"   Total generadas: {stats['total']}")
        print(f"   Entregables: {stats['deliverable']} ({stats['deliverable_pct']:.0f}%)")
        print(f"   Impacto total estimado: ${stats['total_estimated_impact']:,.0f}")

        print(f"\n📈 Por tipo:")
        for htype, count in stats['by_type'].items():
            pct = count / stats['total'] * 100
            print(f"   {htype}: {count} ({pct:.0f}%)")

        print(f"\n🎯 Por portfolio:")
        for ptype, count in stats['by_portfolio'].items():
            pct = count / stats['total'] * 100
            target = {"quick_win": 40, "medium_term": 40, "strategic_bet": 20}.get(ptype, 0)
            delta = pct - target
            status = "✓" if abs(delta) <= 10 else "⚠"
            print(f"   {status} {ptype}: {count} ({pct:.0f}% | target: {target}%)")

        print(f"\n📁 Por categoría:")
        for category, count in stats['by_category'].items():
            print(f"   {category}: {count}")

        input("\nPresiona ENTER para ver análisis detallado de cada hipótesis...")

        # ===== PASO 6: Analizar Cada Hipótesis =====
        print_step(6, "Análisis Detallado de Hipótesis")

        for i, hyp in enumerate(hypotheses, 1):
            print_hypothesis_analysis(hyp, i)

            if i < len(hypotheses):
                resp = input(f"\nPresiona ENTER para ver siguiente hipótesis (o 's' para saltar al resumen)... ")
                if resp.lower() == 's':
                    break

        # ===== PASO 7: Resumen de Calidad =====
        print_step(7, "Resumen de Calidad")

        # Calcular quality scores
        validations = [validate_hypothesis_quality(h) for h in hypotheses]

        high_quality = sum(1 for v in validations if v['is_high_quality'])
        avg_quality = sum(v['quality_score'] for v in validations) / len(validations) if validations else 0

        print(f"\n📊 Métricas de Calidad:")
        print(f"   Alta calidad (>= 70): {high_quality}/{len(hypotheses)} ({high_quality/len(hypotheses)*100:.0f}%)")
        print(f"   Quality score promedio: {avg_quality:.1f}/100")

        # Issues comunes
        all_issues = []
        all_warnings = []
        for v in validations:
            all_issues.extend(v['issues'])
            all_warnings.extend(v['warnings'])

        if all_issues:
            print(f"\n❌ Problemas detectados ({len(all_issues)} total):")
            issue_counts = {}
            for issue in all_issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1

            for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"   [{count}x] {issue}")

        if all_warnings:
            print(f"\n⚠️  Advertencias ({len(all_warnings)} total):")
            warning_counts = {}
            for warning in all_warnings:
                warning_counts[warning] = warning_counts.get(warning, 0) + 1

            for warning, count in sorted(warning_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"   [{count}x] {warning}")

        # ===== PASO 8: Recomendaciones =====
        print_step(8, "Recomendaciones")

        print("\n💡 Recomendaciones para mejorar:")

        if avg_quality < 70:
            print("\n   🔴 PRIORIDAD ALTA:")
            print("   1. Quality score promedio bajo. Revisar prompts LLM.")
            print("   2. Aumentar especificidad en instrucciones.")

        if stats['deliverable_pct'] < 40:
            print("\n   🔴 PRIORIDAD ALTA:")
            print(f"   1. Solo {stats['deliverable_pct']:.0f}% son entregables (target: >= 60%).")
            print("   2. Ajustar cálculo de delivery scores o mejorar actionability.")

        # Portfolio mix
        quick_pct = stats['by_portfolio'].get('quick_win', 0) / stats['total'] * 100 if stats['total'] > 0 else 0
        if abs(quick_pct - 40) > 15:
            print("\n   🟡 PRIORIDAD MEDIA:")
            print(f"   1. Portfolio mix desbalanceado: quick_win {quick_pct:.0f}% (target: 40%).")

        if not all_issues and not all_warnings:
            print("\n   ✅ ¡Excelente! No hay problemas significativos detectados.")
            print("   El sistema está generando hipótesis de alta calidad.")

        # ===== FINAL =====
        print_header("✅ TEST COMPLETADO")

        print(f"""
RESUMEN EJECUTIVO:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hipótesis generadas:     {len(hypotheses)}
Entregables:            {stats['deliverable']} ({stats['deliverable_pct']:.0f}%)
Quality score promedio: {avg_quality:.1f}/100
Impacto total estimado: ${stats['total_estimated_impact']:,.0f}

Portfolio Mix:
  Quick Wins:     {stats['by_portfolio'].get('quick_win', 0)} ({stats['by_portfolio'].get('quick_win', 0)/stats['total']*100:.0f}% | target: 40%)
  Medium Term:    {stats['by_portfolio'].get('medium_term', 0)} ({stats['by_portfolio'].get('medium_term', 0)/stats['total']*100:.0f}% | target: 40%)
  Strategic Bets: {stats['by_portfolio'].get('strategic_bet', 0)} ({stats['by_portfolio'].get('strategic_bet', 0)/stats['total']*100:.0f}% | target: 20%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRÓXIMOS PASOS:
1. Si todo se ve bien: Ejecutar python scripts/test_phase4.py para testing completo
2. Si hay problemas: Revisar docs/TESTING_GUIDE.md para troubleshooting
3. Para producción: Configurar delivery channels en .env

""")

    except Exception as e:
        print_error(f"Error durante testing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if db_connection and pool:
            await pool.release(db_connection)
        if pool:
            await pool.close()
            print("👋 Conexión cerrada")


if __name__ == "__main__":
    asyncio.run(main())
