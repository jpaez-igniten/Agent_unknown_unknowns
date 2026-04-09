"""
Test Learning Loop - Hypothesis Graveyard Analysis

Demuestra cómo el sistema aprende del Hypothesis Graveyard:
1. Analiza patrones de rechazo
2. Identifica ortodoxias intocables
3. Detecta hipótesis similares a evitar
4. Genera recomendaciones para mejorar prompts
5. Calcula success/rejection rates

Uso:
    python3 scripts/test_learning_loop.py
"""

import asyncio
import sys
import os

# Agregar path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncpg
from config.settings import get_settings

# Importar componentes de feedback
from packages.core.domain.unknown_unknowns.feedback.collector import FeedbackCollector
from packages.core.domain.unknown_unknowns.feedback.graveyard_analyzer import GraveyardAnalyzer

# Intentar importar LLM
try:
    from packages.core.utils.gemini_wrapper import GeminiLLMWrapper
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


def print_section(title):
    """Imprime header de sección."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


async def main():
    """Ejecuta tests del learning loop."""
    settings = get_settings()
    client_id = "demo_seguros_001"

    print("\n" + "="*80)
    print("  🧠 UNKNOWN UNKNOWNS AGENT - LEARNING LOOP DEMO")
    print("  Hypothesis Graveyard Analysis")
    print("="*80 + "\n")

    try:
        # Conectar a Postgres
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password
        )

        print("✅ Conectado a Postgres\n")

        # Inicializar LLM (opcional)
        llm = None
        if LLM_AVAILABLE and settings.google_api_key:
            llm = GeminiLLMWrapper(
                model=settings.gemini_model,
                api_key=settings.google_api_key,
                temperature=0.1
            )
            print("✅ LLM inicializado\n")

        # Inicializar componentes
        feedback_collector = FeedbackCollector(db_connection=conn)
        graveyard_analyzer = GraveyardAnalyzer(db_connection=conn, llm=llm)

        # ===== TEST 1: ESTADÍSTICAS DEL GRAVEYARD =====
        print_section("📊 TEST 1: ESTADÍSTICAS DEL GRAVEYARD")

        stats = await feedback_collector.get_feedback_stats(client_id=client_id)

        print(f"Total feedback recibido:     {stats['total_feedback']}")
        print(f"Rating promedio:             {stats['avg_rating']:.1f}/5")
        print(f"Impacto total realizado:     ${stats['total_business_impact_usd']:,.0f}")

        print(f"\nPor categoría:")
        for category, data in stats['by_category'].items():
            print(f"   - {category:25s} {data['count']:2d} ({data['avg_rating']:.1f}⭐)")

        # ===== TEST 2: ANÁLISIS DE RECHAZOS =====
        print_section("⚠️ TEST 2: ANÁLISIS DE PATRONES DE RECHAZO")

        rejection_analysis = await graveyard_analyzer.analyze_rejection_patterns(
            client_id=client_id,
            min_samples=1  # Bajo threshold para demo
        )

        print(f"Total rechazados:            {rejection_analysis.get('total_rejected', 0)}")
        print(f"Total insights entregados:   {rejection_analysis.get('total_insights', 0)}")
        print(f"Rejection rate:              {rejection_analysis.get('rejection_rate', 0):.1%}")

        if rejection_analysis.get('by_category'):
            print(f"\nPor categoría:")
            for category, count in rejection_analysis['by_category'].items():
                print(f"   - {category}: {count}")

        if rejection_analysis.get('common_reasons'):
            print(f"\nRazones comunes de rechazo:")
            for i, reason in enumerate(rejection_analysis['common_reasons'][:5], 1):
                print(f"   {i}. {reason[:100]}...")

        if rejection_analysis.get('recommendations'):
            print(f"\n💡 Recomendaciones:")
            for rec in rejection_analysis['recommendations']:
                print(f"   {rec}")

        # ===== TEST 3: PATRONES DE ÉXITO =====
        print_section("✨ TEST 3: PATRONES DE HIPÓTESIS EXITOSAS")

        success_analysis = await graveyard_analyzer.get_successful_hypothesis_patterns(
            client_id=client_id,
            min_impact_usd=0
        )

        print(f"Total exitosas:              {success_analysis.get('total_useful', 0)}")
        print(f"Success rate:                {success_analysis.get('success_rate', 0):.1%}")
        print(f"Impacto total:               ${success_analysis.get('total_business_impact_usd', 0):,.0f}")
        print(f"Impacto promedio:            ${success_analysis.get('avg_impact_usd', 0):,.0f}")

        if success_analysis.get('common_characteristics'):
            print(f"\nCaracterísticas comunes:")
            for char in success_analysis['common_characteristics']:
                print(f"   ✅ {char}")

        if success_analysis.get('top_performers'):
            print(f"\nTop performers:")
            for i, perf in enumerate(success_analysis['top_performers'], 1):
                print(f"\n   {i}. {perf['hypothesis_text'][:80]}...")
                print(f"      Impact: ${perf['impact_usd']:,.0f} | Rating: {perf['rating']}⭐")

        # ===== TEST 4: EVITAR HIPÓTESIS SIMILARES =====
        print_section("🔍 TEST 4: DETECCIÓN DE HIPÓTESIS SIMILARES")

        # Test con hipótesis similar a una rechazada
        test_hypothesis_1 = "El 20% de los agentes con mayor volumen genera contratos con márgenes bajos"

        result1 = await graveyard_analyzer.should_avoid_hypothesis(
            hypothesis_text=test_hypothesis_1,
            client_id=client_id,
            similarity_threshold=0.3  # Bajo threshold para demo
        )

        print(f"Hipótesis de prueba 1:")
        print(f"   \"{test_hypothesis_1}\"")
        print(f"\n   Should avoid:    {'❌ SÍ' if result1['should_avoid'] else '✅ NO'}")
        print(f"   Reason:          {result1['reason']}")
        if result1.get('similar_to'):
            print(f"   Similar to:      {result1['similar_to'][:80]}...")
            print(f"   Similarity:      {result1.get('similarity', 0):.2%}")

        # Test con hipótesis completamente nueva
        test_hypothesis_2 = "Implementar AI-powered underwriting para reducir tiempos de aprobación en 50%"

        result2 = await graveyard_analyzer.should_avoid_hypothesis(
            hypothesis_text=test_hypothesis_2,
            client_id=client_id,
            similarity_threshold=0.3
        )

        print(f"\nHipótesis de prueba 2:")
        print(f"   \"{test_hypothesis_2}\"")
        print(f"\n   Should avoid:    {'❌ SÍ' if result2['should_avoid'] else '✅ NO'}")
        print(f"   Reason:          {result2['reason']}")

        # ===== TEST 5: SUGERENCIAS PARA MEJORAR PROMPTS =====
        print_section("💡 TEST 5: SUGERENCIAS PARA MEJORAR PROMPTS")

        suggestions = await graveyard_analyzer.get_prompt_improvement_suggestions(
            client_id=client_id
        )

        if suggestions:
            print(f"Generadas {len(suggestions)} sugerencias:\n")
            for i, sug in enumerate(suggestions, 1):
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                emoji = priority_emoji.get(sug['priority'], "ℹ️")

                print(f"   {i}. {emoji} [{sug['priority'].upper()}] {sug['prompt_section']}")
                print(f"      Sugerencia: {sug['suggestion']}")
                print(f"      Razón:      {sug['reason']}")
                print()
        else:
            print("   ℹ️  No hay suficientes datos para generar sugerencias")

        # ===== TEST 6: INSIGHTS ÚTILES =====
        print_section("💎 TEST 6: INSIGHTS ÚTILES (HISTÓRICO)")

        useful = await feedback_collector.get_useful_insights(
            client_id=client_id,
            min_impact_usd=0,
            limit=10
        )

        if useful:
            print(f"Encontrados {len(useful)} insights útiles:\n")
            for i, insight in enumerate(useful, 1):
                print(f"   {i}. {insight['hypothesis_text'][:80]}...")
                print(f"      Impact: ${insight['business_impact_realized_usd']:,.0f}")
                print(f"      Rating: {insight['rating']}⭐")
                if insight['comment']:
                    print(f"      Comment: {insight['comment'][:80]}...")
                print()
        else:
            print("   ℹ️  No hay insights útiles registrados aún")

        # ===== TEST 7: REJECTED PATTERNS =====
        print_section("🚫 TEST 7: PATRONES DETALLADOS DE RECHAZO")

        rejected = await feedback_collector.get_rejected_patterns(
            client_id=client_id,
            limit=10
        )

        print(f"Total rechazados:    {rejected['total_rejected']}")
        print(f"Avg rating:          {rejected['avg_rating']:.1f}/5")

        if rejected['common_reasons']:
            print(f"\nRazones de rechazo:")
            for i, reason in enumerate(rejected['common_reasons'][:5], 1):
                print(f"   {i}. {reason[:100]}...")

        if rejected.get('sample_hypotheses'):
            print(f"\nEjemplos de hipótesis rechazadas:")
            for i, sample in enumerate(rejected['sample_hypotheses'][:3], 1):
                print(f"\n   {i}. {sample['hypothesis_text'][:80]}...")
                print(f"      Reason: {sample['reason'][:80]}...")

        # ===== RESUMEN FINAL =====
        print_section("📈 RESUMEN DEL LEARNING LOOP")

        total_feedback = stats['total_feedback']
        rejection_rate = rejection_analysis.get('rejection_rate', 0)
        success_rate = success_analysis.get('success_rate', 0)

        print("Métricas clave:")
        print(f"   Total feedback:          {total_feedback}")
        print(f"   Rejection rate:          {rejection_rate:.1%}")
        print(f"   Success rate:            {success_rate:.1%}")
        print(f"   Total impact realizado:  ${stats['total_business_impact_usd']:,.0f}")

        print(f"\nAprendizajes clave:")
        print(f"   ✅ El sistema puede identificar hipótesis similares y evitar duplicados")
        print(f"   ✅ Analiza patrones de rechazo para mejorar future runs")
        print(f"   ✅ Genera recomendaciones para ajustar prompts LLM")
        print(f"   ✅ Tracking de business impact real de insights")

        print(f"\nPróximos pasos para mejorar:")
        if rejection_rate > 0.5:
            print(f"   🔴 Alta tasa de rechazo - revisar feasibility validation")
        if success_rate < 0.2:
            print(f"   🟡 Baja tasa de éxito - enfocarse más en quick wins")
        if total_feedback < 20:
            print(f"   🟢 Continuar recolectando feedback para mejores insights")

        await conn.close()

        print(f"\n" + "="*80)
        print("✅ LEARNING LOOP DEMO COMPLETADO")
        print("="*80 + "\n")

        print("El Hypothesis Graveyard permite al sistema:")
        print("   1. Aprender de hipótesis rechazadas")
        print("   2. Evitar regenerar hipótesis similares")
        print("   3. Mejorar prompts basado en feedback")
        print("   4. Personalizar por cliente (cada cliente tiene su graveyard)")
        print("   5. Tracking de ROI real de insights\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
