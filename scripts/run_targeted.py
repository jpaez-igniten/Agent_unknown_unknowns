"""
Run Targeted — Deep Dive Run

Corre hipótesis específicas que surgieron del análisis del Run #2.
Las respuestas del Run #2 dejaron preguntas abiertas concretas con tablas
SAP identificadas — este run las responde directamente.

Cómo correr:
    docker exec unknown-unknowns python scripts/run_targeted.py
"""

import asyncio
import sys

sys.path.insert(0, "/app")

from config.settings import get_settings
from packages.core.scheduler.runner import PipelineRunner, HypothesisTemplate
from packages.core.agent_client.client import AgentClientError

# ============================================================================
# LAS 3 HIPÓTESIS ESPECÍFICAS (Deep dive sobre resultados del Run #2)
# ============================================================================

TARGETED_QUESTIONS = [
    # --- HIPÓTESIS 1: Rentabilidad real por cliente export (ampliación Insight #5) ---
    # El agente encontró bandejas/cajas en canal USD con márgenes 2.9%-4.2%
    # y pitillos locales 11.3%. Ahora identificamos los clientes específicos.
    (
        "Para Promociones Fantásticas S.A.S. (manufactura empaques PLA/bagazo, "
        "exporta a 20+ países LATAM/Caribe, SAP con 7 años de datos desde 2018): "
        "¿Cuáles son los 10 clientes de exportación (canal USD) con menor margen neto real "
        "al incluir costos logísticos de SAP? "
        "Busca en OINV (facturas venta), PCH7 (costos empaque/logística), INV22 (componentes costo), "
        "ORLS (relaciones cliente). "
        "Muestra: CardCode, nombre cliente, país destino, revenue USD, costo logístico USD, "
        "margen neto %, y cuántas facturas. "
        "Ordena de menor a mayor margen neto. "
        "Si no hay datos directos de costo logístico, usa TotalExpns de OINV como proxy."
    ),

    # --- HIPÓTESIS 2: Clientes con pipeline atascado >90 días (ampliación Insight #2) ---
    # El agente identificó $252M COP en INDUSTRIALES y $180M en DISTRIBUIDORES
    # con ciclos >90-120 días. Ahora nombramos los clientes reales.
    (
        "Para Promociones Fantásticas S.A.S. (B2B manufactura, clientes industriales grandes "
        "como Grupo Nutresa, Starbucks, Coca-Cola): "
        "¿Cuáles son los 15 clientes con órdenes de venta abiertas (pipeline) de más de 90 días? "
        "Busca en ORDR (órdenes de venta, DocStatus='O'), OCRD (maestro clientes), "
        "y si existe OSLP (vendedores). "
        "Muestra: CardCode, nombre cliente, segmento (GroupCode de OCRD), "
        "monto total COP de órdenes abiertas, cantidad de órdenes, días promedio abierto "
        "(desde DocDate hasta hoy), y vendedor asignado (SlpCode). "
        "Ordena por monto total descendente. "
        "Separa los resultados por segmento: INDUSTRIALES vs DISTRIBUIDORES vs EXPORTACIONES."
    ),

    # --- HIPÓTESIS 3: Revenue por familia de producto en export (ampliación #7+#8) ---
    # El agente preguntó '¿qué productos representan 80% de exportaciones a USA y Ecuador?'
    # y encontró que Sorbiflex domina ~80% del portafolio. Ahora cuantificamos por familia.
    (
        "Para Promociones Fantásticas S.A.S. (portafolio: pitillos Sorbiflex PLA, vasos, "
        "platos, contenedores, portacomidas, bandejas en materiales PLA/bagazo/papel): "
        "¿Cuál es la distribución de revenue de los últimos 24 meses por familia de producto "
        "en el canal de exportación (facturas en USD)? "
        "Busca en OINV (facturas), INV1 (líneas factura), OITM (maestro items con ItemGroup), "
        "OITB (grupos de items). "
        "Agrupa por ItemGroup o por categoría derivada del ItemCode/ItemName "
        "(pitillos, vasos, platos, contenedores, portacomidas, otros). "
        "Muestra: familia de producto, revenue total USD, % del total, cantidad unidades, "
        "precio promedio por unidad, y top 3 países destino por familia. "
        "Identifica qué familia tiene mejor margen relativo (si hay datos de costo). "
        "Incluye también el split por los 5 principales países destino (Ecuador, USA, Guatemala, "
        "Panamá, Costa Rica)."
    ),
]


async def main():
    settings = get_settings()

    print("=" * 60)
    print("  Deep Dive Run — 3 Hipótesis Específicas")
    print("  (seguimiento de hallazgos del Run #2)")
    print("=" * 60)
    print(f"\nAgente: {settings.agent_base_url}")
    print(f"Postgres: {settings.postgres_host}/{settings.postgres_db}")
    print(f"Hipótesis a correr: {len(TARGETED_QUESTIONS)}\n")

    runner = PipelineRunner(settings)
    await runner.initialize()

    try:
        hypotheses = HypothesisTemplate.generate_targeted(TARGETED_QUESTIONS)
        client_id = "promociones_fantasticas_001"

        # Crear el run en DB
        run_id = await runner.run_repo.create_run(
            client_id=client_id,
            run_type="ad_hoc",
            max_hypotheses=len(hypotheses)
        )
        print(f"Run #{run_id} creado en DB\n")

        insights_saved = 0

        for idx, hyp in enumerate(hypotheses, 1):
            print(f"[{idx}/{len(hypotheses)}] Enviando hipótesis al agente...")
            print(f"  Tema: {hyp['business_rationale']}")
            print(f"  Texto (primeros 120 chars): {hyp['hypothesis_text'][:120]}...")

            conversation_id = f"uu_{run_id}_{hyp['hypothesis_id']}"

            try:
                response = await runner.agent_client.chat(
                    message_text=hyp["hypothesis_text"],
                    conversation_id=conversation_id
                )

                await runner.run_repo.save_insight(
                    run_id=run_id,
                    client_id=client_id,
                    hypothesis=hyp,
                    agent_response=response
                )

                insights_saved += 1
                elapsed_s = response.response_time_ms // 1000
                print(f"  ✓ Insight guardado | {elapsed_s}s | {len(response.raw_text)} chars\n")

            except AgentClientError as e:
                print(f"  ✗ Error del agente: {e}\n")
            except Exception as e:
                print(f"  ✗ Error inesperado: {e}\n")

        # Finalizar run
        status = "completed" if insights_saved == len(hypotheses) else (
            "partial" if insights_saved > 0 else "failed"
        )
        await runner.run_repo.finalize_run(
            run_id=run_id,
            hypotheses_generated=len(hypotheses),
            insights_found=insights_saved,
            status=status
        )

        print("=" * 60)
        print(f"  Run #{run_id} finalizado: {insights_saved}/{len(hypotheses)} insights")
        print(f"  Status: {status}")
        print("=" * 60)

    finally:
        await runner.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
