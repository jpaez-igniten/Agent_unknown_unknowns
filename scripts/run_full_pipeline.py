"""
Pipeline Completo End-to-End - Unknown Unknowns Agent

Ejecuta el agente completo desde el inicio hasta el final:
1. FASE 1: Carga/crea BusinessProfile
2. FASE 2: Genera hipótesis (knowledge + anomaly driven)
3. FASE 3: Valida viabilidad técnica y contra datos
4. FASE 4: Calcula delivery scores y muestra resultados
5. Muestra logging detallado en cada paso

Uso:
    python scripts/run_full_pipeline.py [--client-id CLIENT_ID] [--debug]

Opciones:
    --client-id: ID del cliente (default: demo_seguros_001)
    --debug: Habilita logging DEBUG level
    --max-hypotheses: Máximo de hipótesis a generar (default: 15)
    --skip-validation: Salta validación de datos (útil si no hay datos reales)
"""

import asyncio
import json
import sys
import os
import logging
import argparse
from datetime import datetime
from typing import Dict, Any

# Agregar path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncpg
from config.settings import get_settings

# Importar componentes FASE 1
from packages.core.domain.unknown_unknowns.business_context.profile_repository import (
    BusinessProfileRepository
)
from packages.core.domain.unknown_unknowns.business_context.profile_builder import (
    BusinessProfileBuilder
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


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging(debug: bool = False):
    """
    Configura logging detallado con colores y formato legible.
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Formato detallado con colores
    class ColoredFormatter(logging.Formatter):
        """Formatter con colores para diferentes niveles"""

        COLORS = {
            'DEBUG': '\033[36m',     # Cyan
            'INFO': '\033[32m',      # Green
            'WARNING': '\033[33m',   # Yellow
            'ERROR': '\033[31m',     # Red
            'CRITICAL': '\033[35m',  # Magenta
            'RESET': '\033[0m'       # Reset
        }

        def format(self, record):
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            reset = self.COLORS['RESET']

            # Formato: [TIMESTAMP] LEVEL - Module.Function - Message
            timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S.%f')[:-3]

            log_fmt = (
                f"{color}[{timestamp}]{reset} "
                f"{color}{record.levelname:8s}{reset} "
                f"- {record.name:30s} - {record.getMessage()}"
            )

            return log_fmt

    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColoredFormatter())

    # Handler para archivo
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = f"{log_dir}/pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)  # Siempre DEBUG en archivo
    file_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = []  # Limpiar handlers existentes
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Silenciar logs ruidosos
    logging.getLogger('asyncpg').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)

    print(f"\n📝 Logs guardados en: {log_file}\n")

    return logging.getLogger(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def create_db_pool(settings):
    """Crea connection pool a Postgres"""
    logger = logging.getLogger(__name__)
    logger.info(f"Conectando a Postgres: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")

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
        logger.info("✅ Conectado a Postgres exitosamente")
        return pool
    except Exception as e:
        logger.error(f"❌ Error conectando a Postgres: {e}")
        logger.error("\nVerifica que:")
        logger.error("  1. Postgres esté corriendo")
        logger.error("  2. Las credenciales en .env sean correctas")
        logger.error("  3. La base de datos exista")
        logger.error("  4. La migración 012_unknown_unknowns_v2.sql haya sido ejecutada")
        raise


def initialize_llm(settings):
    """Inicializa LLM"""
    logger = logging.getLogger(__name__)

    if not LLM_AVAILABLE:
        logger.error("❌ LLM no disponible (langchain-google-genai no instalado)")
        logger.error("   Ejecuta: pip install langchain-google-genai")
        return None

    if not settings.google_api_key:
        logger.error("❌ GOOGLE_API_KEY no configurado en .env")
        return None

    try:
        llm = GeminiLLMWrapper(
            model=settings.gemini_model,
            api_key=settings.google_api_key,
            temperature=0.1
        )
        logger.info(f"✅ LLM inicializado ({settings.gemini_model})")
        return llm
    except Exception as e:
        logger.error(f"❌ Error inicializando LLM: {e}")
        return None


def print_section_header(title: str, char: str = "="):
    """Imprime header visual para sección"""
    print(f"\n{char * 80}")
    print(f"  {title}")
    print(f"{char * 80}\n")


def print_profile_summary(profile):
    """Imprime resumen del perfil del cliente"""
    print_section_header("📋 BUSINESS PROFILE SUMMARY", "=")

    print(f"Cliente:           {profile.company_name}")
    print(f"ID:                {profile.client_id}")
    print(f"Industria:         {profile.industry}")
    print(f"Business Model:    {profile.business_model}")
    print(f"Completeness:      {profile.profile_completeness:.1%}")
    print(f"Confidence:        {profile.confidence_score:.1%}")

    print(f"\nPrioridades Estratégicas: {len(profile.strategic_priorities)}")
    for i, priority in enumerate(profile.strategic_priorities[:3], 1):
        print(f"  {i}. {priority.priority}")
        print(f"     Owner: {priority.owner} | Deadline: {priority.deadline}")

    print(f"\nKPIs Monitoreados: {len(profile.kpis)}")
    for kpi in profile.kpis[:3]:
        trend_emoji = {"improving": "📈", "declining": "📉", "stable": "➡️"}.get(kpi.trend, "❓")
        print(f"  {trend_emoji} {kpi.name}: {kpi.current}{kpi.unit} (target: {kpi.target}{kpi.unit})")

    print(f"\nOrtodoxias Detectadas: {len(profile.industry_orthodoxies)}")
    high_disruption = profile.get_high_disruption_orthodoxies()
    if high_disruption:
        print(f"  🔥 Alto potencial de disrupción: {len(high_disruption)}")
        for i, orth in enumerate(high_disruption[:2], 1):
            print(f"\n  {i}. {orth.orthodoxy}")
            print(f"     Confidence: {orth.confidence:.2f} | Disruption: {orth.potential_for_disruption}")

    print()


def print_hypothesis_details(hypothesis, index: int = None):
    """Imprime detalles de una hipótesis"""
    prefix = f"{index}. " if index else ""

    print(f"\n{prefix}{'='*76}")
    print(f"ID: {hypothesis.hypothesis_id}")
    print(f"{'='*76}")

    print(f"\n📝 HIPÓTESIS:")
    print(f"   {hypothesis.hypothesis_text}")

    print(f"\n📊 METADATA:")
    print(f"   Type:              {hypothesis.hypothesis_type}")
    print(f"   Category:          {hypothesis.category}")
    print(f"   Portfolio Type:    {hypothesis.portfolio_type.value}")
    print(f"   Generated From:    {hypothesis.generated_from}")

    print(f"\n💡 ACTIONABILITY:")
    print(f"   Decision Owner:    {hypothesis.actionability.decision_owner}")
    print(f"   Estimated Impact:  ${hypothesis.actionability.estimated_impact_usd:,.0f}")
    print(f"   Time to Impact:    {hypothesis.actionability.time_to_impact_months} months")
    print(f"   If True Then:")
    print(f"      {hypothesis.actionability.if_true_then}")

    print(f"\n📈 CONFIDENCE BREAKDOWN:")
    print(f"   Total:             {hypothesis.confidence.confidence_total:.2%}")
    print(f"   Statistical:       {hypothesis.confidence.confidence_statistical:.2%}")
    print(f"   Data Quality:      {hypothesis.confidence.confidence_data_quality:.2%}")
    print(f"   Model:             {hypothesis.confidence.confidence_model:.2%}")

    print(f"\n🎯 DELIVERY SCORE:")
    print(f"   Total:             {hypothesis.delivery_score.delivery_score_total:.1f}/100")
    print(f"   Statistical:       {hypothesis.delivery_score.statistical_confidence_score:.0f}")
    print(f"   Business Impact:   {hypothesis.delivery_score.business_impact_score:.0f}")
    print(f"   Actionability:     {hypothesis.delivery_score.actionability_score:.0f}")
    print(f"   Strategic Align:   {hypothesis.delivery_score.strategic_alignment_score:.0f}")
    print(f"   Should Deliver:    {'✅ YES' if hypothesis.delivery_score.should_deliver else '❌ NO'}")

    if hypothesis.evidence:
        print(f"\n🔍 EVIDENCE:")
        for i, ev in enumerate(hypothesis.evidence[:3], 1):
            print(f"   {i}. {ev}")

    if hypothesis.data_sources_used:
        print(f"\n📊 DATA SOURCES:")
        print(f"   {', '.join(hypothesis.data_sources_used[:5])}")


def print_results_summary(results: Dict[str, Any]):
    """Imprime resumen final de resultados"""
    print_section_header("🎯 PIPELINE RESULTS SUMMARY", "=")

    print(f"Run ID:                  {results['run_id']}")
    print(f"Cliente:                 {results.get('company_name', results['client_id'])}")
    print(f"Duración:                {results.get('duration_seconds', 0):.1f}s")

    print(f"\n📊 FUNNEL:")
    print(f"   Hipótesis generadas:  {results['total_hypotheses_generated']}")
    print(f"   └─ Factibles:         {results['feasible_hypotheses']} ({results['feasible_hypotheses']/max(results['total_hypotheses_generated'],1)*100:.0f}%)")
    print(f"      └─ Validadas:      {results['validated_hypotheses']} ({results['validated_hypotheses']/max(results['feasible_hypotheses'],1)*100:.0f}%)")
    print(f"         └─ Entregables: {results['deliverable_insights']} ({results['deliverable_insights']/max(results['validated_hypotheses'],1)*100:.0f}%)")

    # Portfolio mix
    if results['insights']:
        portfolio_counts = {}
        for insight in results['insights']:
            ptype = insight['portfolio_type']
            portfolio_counts[ptype] = portfolio_counts.get(ptype, 0) + 1

        print(f"\n📂 PORTFOLIO MIX:")
        total = len(results['insights'])
        for ptype in ['quick_win', 'medium_term', 'big_bet', 'exploratory']:
            count = portfolio_counts.get(ptype, 0)
            pct = (count / total * 100) if total > 0 else 0
            bar = "█" * int(pct / 5)
            print(f"   {ptype:15s} {count:2d} ({pct:5.1f}%) {bar}")

    # Top insights
    if results['insights']:
        print(f"\n💎 TOP INSIGHTS ENTREGABLES:")
        for i, insight in enumerate(results['insights'][:5], 1):
            print(f"\n   {i}. [{insight['portfolio_type'].upper()}] Score: {insight['delivery_score']:.1f}/100")
            print(f"      {insight['hypothesis_text']}")
            print(f"      💰 Impact: ${insight['actionability']['estimated_impact_usd']:,.0f}")
            print(f"      👤 Owner: {insight['actionability']['decision_owner']}")

    print()


# ============================================================================
# MAIN PIPELINE
# ============================================================================

async def run_full_pipeline(
    client_id: str,
    max_hypotheses: int = 15,
    skip_validation: bool = False
):
    """
    Ejecuta el pipeline completo end-to-end.
    """
    logger = logging.getLogger(__name__)

    print("\n" + "="*80)
    print("  🚀 UNKNOWN UNKNOWNS AGENT - FULL PIPELINE")
    print("="*80 + "\n")

    print(f"Cliente ID:         {client_id}")
    print(f"Max Hipótesis:      {max_hypotheses}")
    print(f"Skip Validation:    {skip_validation}")
    print(f"Started:            {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    settings = get_settings()
    pool = None
    db_connection = None

    try:
        # ===== INICIALIZACIÓN =====
        print_section_header("🔧 FASE 0: INICIALIZACIÓN", "=")

        logger.info("Inicializando componentes...")

        # Verificar LLM
        llm = initialize_llm(settings)
        if not llm:
            logger.error("CRITICAL: LLM no disponible. El agente requiere LLM para funcionar.")
            print("\n❌ ERROR: LLM no disponible")
            print("\nPara habilitar:")
            print("   1. pip install langchain-google-genai")
            print("   2. Agregar GOOGLE_API_KEY a .env")
            return None

        # Crear DB pool
        pool = await create_db_pool(settings)
        db_connection = await pool.acquire()

        logger.info("Inicializando repositories y componentes...")

        # Inicializar componentes
        profile_repo = BusinessProfileRepository(
            db_pool=pool,
            chroma_client=None,
            embedding_function=None
        )

        profile_builder = BusinessProfileBuilder(
            repository=profile_repo,
            db_connection=db_connection,
            llm=llm
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

        logger.info("✅ Todos los componentes inicializados")

        # ===== FASE 1: BUSINESS PROFILE =====
        print_section_header("📋 FASE 1: BUSINESS PROFILE", "=")

        logger.info(f"Cargando perfil para cliente: {client_id}")
        profile = await profile_repo.get_profile(client_id)

        if not profile:
            logger.warning(f"Perfil no encontrado para {client_id}")
            print(f"\n⚠️  Perfil no encontrado para cliente: {client_id}")
            print("   Para crear un perfil, ejecuta: python scripts/test_phase1.py")
            return None

        logger.info(f"Perfil cargado: {profile.company_name}")
        print_profile_summary(profile)

        # ===== FASE 2+3: PIPELINE COMPLETO =====
        print_section_header("🔬 FASE 2+3: GENERACIÓN Y VALIDACIÓN", "=")

        logger.info("Iniciando pipeline completo de generación y validación...")

        results = await orchestrator.run_discovery_pipeline(
            client_id=client_id,
            max_hypotheses=max_hypotheses,
            min_feasibility_score=0.5,
            enable_human_review=False,  # Skip human review para testing
            validate_with_data=not skip_validation
        )

        # ===== MOSTRAR RESULTADOS =====
        print_results_summary(results)

        # ===== MOSTRAR HIPÓTESIS DETALLADAS =====
        if results['insights']:
            print_section_header("📚 HIPÓTESIS DETALLADAS", "=")

            for i, insight_data in enumerate(results['insights'][:5], 1):
                # Reconstruir objeto Hypothesis desde dict
                # (necesitamos el objeto completo con todos los campos)
                # Por ahora, mostrar resumen desde dict

                print(f"\n{'='*80}")
                print(f"HIPÓTESIS #{i}")
                print(f"{'='*80}")

                print(f"\n📝 {insight_data['hypothesis_text']}")

                print(f"\n📊 Metadata:")
                print(f"   Category:        {insight_data['category']}")
                print(f"   Portfolio:       {insight_data['portfolio_type']}")
                print(f"   Delivery Score:  {insight_data['delivery_score']:.1f}/100")

                print(f"\n💡 Actionability:")
                print(f"   Owner:           {insight_data['actionability']['decision_owner']}")
                print(f"   Impact:          ${insight_data['actionability']['estimated_impact_usd']:,.0f}")
                print(f"   Action:          {insight_data['actionability']['if_true_then'][:100]}...")

                print(f"\n📈 Confidence:")
                print(f"   Total:           {insight_data['confidence']['total']:.2%}")
                print(f"   Statistical:     {insight_data['confidence']['statistical']:.2%}")
                print(f"   Data Quality:    {insight_data['confidence']['data_quality']:.2%}")

        # ===== GUARDAR RESULTADOS =====
        print_section_header("💾 GUARDANDO RESULTADOS", "=")

        output_dir = "results"
        os.makedirs(output_dir, exist_ok=True)

        output_file = f"{output_dir}/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{client_id}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Resultados guardados en: {output_file}")
        print(f"✅ Resultados guardados en: {output_file}")

        # ===== RESUMEN FINAL =====
        print_section_header("✅ PIPELINE COMPLETADO", "=")

        print("🎉 El agente ha ejecutado exitosamente!")
        print(f"\nGenerated:    {results['total_hypotheses_generated']} hipótesis")
        print(f"Feasible:     {results['feasible_hypotheses']} hipótesis")
        print(f"Validated:    {results['validated_hypotheses']} hipótesis")
        print(f"Deliverable:  {results['deliverable_insights']} insights de alto valor")

        if results['deliverable_insights'] > 0:
            total_impact = sum(
                insight['actionability']['estimated_impact_usd']
                for insight in results['insights']
            )
            print(f"\n💰 Impacto potencial total: ${total_impact:,.0f}")

        print(f"\n📝 Resultados completos: {output_file}")
        print()

        return results

    except Exception as e:
        logger.error(f"Error en pipeline: {e}", exc_info=True)
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        # Liberar recursos
        if db_connection and pool:
            await pool.release(db_connection)
        if pool:
            await pool.close()
            logger.info("Conexión a Postgres cerrada")


# ============================================================================
# CLI
# ============================================================================

def main():
    """Entry point para CLI"""
    parser = argparse.ArgumentParser(
        description="Ejecuta el pipeline completo del Unknown Unknowns Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python scripts/run_full_pipeline.py
  python scripts/run_full_pipeline.py --client-id demo_seguros_001 --debug
  python scripts/run_full_pipeline.py --max-hypotheses 20 --skip-validation
        """
    )

    parser.add_argument(
        '--client-id',
        type=str,
        default='demo_seguros_001',
        help='ID del cliente (default: demo_seguros_001)'
    )

    parser.add_argument(
        '--max-hypotheses',
        type=int,
        default=15,
        help='Máximo de hipótesis a generar (default: 15)'
    )

    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Salta validación contra datos reales'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Habilita logging DEBUG level'
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging(debug=args.debug)

    # Run pipeline
    asyncio.run(run_full_pipeline(
        client_id=args.client_id,
        max_hypotheses=args.max_hypotheses,
        skip_validation=args.skip_validation
    ))


if __name__ == "__main__":
    main()
