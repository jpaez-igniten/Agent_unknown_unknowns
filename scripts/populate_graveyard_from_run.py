"""
Script para poblar el Hypothesis Graveyard con hipótesis de un run previo.

Toma las 5 hipótesis generadas en el run anterior y las guarda en el graveyard
como "rejected" por "system_feasibility_validator" para demostrar el learning loop.

Uso:
    python3 scripts/populate_graveyard_from_run.py
"""

import asyncio
import json
import sys
import os

# Agregar path para imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncpg
from config.settings import get_settings


# Las 5 hipótesis generadas en el run anterior (del log)
HYPOTHESES_DATA = [
    {
        "hypothesis_id": "hyp_cd675abaca83",
        "hypothesis_text": "El 15% de los agentes genera el 70% de los contratos con márgenes por debajo del 25%",
        "category": "profitability",
        "hypothesis_type": "knowledge_driven",
        "portfolio_type": "quick_win",
        "delivery_score": 76.5,
        "rejection_reason": "Not feasible (score: 0.44). Missing tables: agent_performance_table, commission_payout_data, contract_margin_analysis",
        "missing_tables": ["agent_performance_table", "commission_payout_data", "contract_margin_analysis"]
    },
    {
        "hypothesis_id": "hyp_1469f50e9815",
        "hypothesis_text": "El 20% de los clientes con mayores descuentos (>15%) tiene un claim ratio 30% superior al promedio",
        "category": "profitability",
        "hypothesis_type": "knowledge_driven",
        "portfolio_type": "quick_win",
        "delivery_score": 81.2,
        "rejection_reason": "Not feasible (score: 0.44). Missing tables: sales_discounts_table, claims_history, customer_profitability_report",
        "missing_tables": ["sales_discounts_table", "claims_history", "customer_profitability_report"]
    },
    {
        "hypothesis_id": "hyp_78ab11c8c3a4",
        "hypothesis_text": "Los clientes del segmento 'Long Tail' (80% inferior por revenue) consumen el 45% de los costos operativos pero solo generan el 15% del revenue",
        "category": "operational_efficiency",
        "hypothesis_type": "knowledge_driven",
        "portfolio_type": "medium_term",
        "delivery_score": 74.8,
        "rejection_reason": "Not feasible (score: 0.44). Missing tables: crm_support_logs, operational_cost_allocation, revenue_by_customer",
        "missing_tables": ["crm_support_logs", "operational_cost_allocation", "revenue_by_customer"]
    },
    {
        "hypothesis_id": "hyp_2c276cddc639",
        "hypothesis_text": "Los clientes Top 20 que no han recibido una auditoría de riesgo en 18+ meses tienen un churn rate del 25% vs 8% del resto",
        "category": "customer_retention",
        "hypothesis_type": "knowledge_driven",
        "portfolio_type": "medium_term",
        "delivery_score": 79.3,
        "rejection_reason": "Not feasible (score: 0.44). Missing tables: customer_interaction_logs, churn_history, claims_severity_data",
        "missing_tables": ["customer_interaction_logs", "churn_history", "claims_severity_data"]
    },
    {
        "hypothesis_id": "hyp_c594f6a15e54",
        "hypothesis_text": "Implementar un recargo por riesgo dinámico (Dynamic Risk Surcharge) basado en geolocalización de carga y tipo de mercancía podría aumentar margen 3-5% sin afectar volumen",
        "category": "pricing_innovation",
        "hypothesis_type": "knowledge_driven",
        "portfolio_type": "strategic_bet",
        "delivery_score": 72.1,
        "rejection_reason": "Not feasible (score: 0.44). Missing tables: claims_geo_data, pricing_engine_logs, market_benchmark_rates",
        "missing_tables": ["claims_geo_data", "pricing_engine_logs", "market_benchmark_rates"]
    }
]


async def populate_graveyard():
    """Pobla el graveyard con las hipótesis del run anterior."""
    settings = get_settings()
    client_id = "demo_seguros_001"

    print(f"\n🔄 Poblando Hypothesis Graveyard para {client_id}...")
    print(f"   Hipótesis a insertar: {len(HYPOTHESES_DATA)}\n")

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

        inserted = 0
        for i, hyp_data in enumerate(HYPOTHESES_DATA, 1):
            try:
                metadata = {
                    "hypothesis_type": hyp_data["hypothesis_type"],
                    "portfolio_type": hyp_data["portfolio_type"],
                    "delivery_score": hyp_data["delivery_score"],
                    "feasibility_score": 0.44,
                    "missing_tables": hyp_data["missing_tables"],
                    "generated_from": "knowledge_driven",
                    "category": hyp_data["category"]
                }

                query = """
                    INSERT INTO hypothesis_graveyard (
                        hypothesis_id,
                        client_id,
                        hypothesis_text,
                        category,
                        rejection_reason,
                        rejected_by,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (hypothesis_id) DO UPDATE SET
                        hypothesis_text = EXCLUDED.hypothesis_text,
                        rejection_reason = EXCLUDED.rejection_reason,
                        metadata = EXCLUDED.metadata,
                        updated_at = now()
                """

                await conn.execute(
                    query,
                    hyp_data["hypothesis_id"],
                    client_id,
                    hyp_data["hypothesis_text"],
                    "rejected",  # Categoría del graveyard
                    hyp_data["rejection_reason"],
                    "system_feasibility_validator",
                    json.dumps(metadata)
                )

                print(f"   [{i}/{len(HYPOTHESES_DATA)}] ✅ {hyp_data['hypothesis_id']}")
                print(f"        {hyp_data['hypothesis_text'][:80]}...")
                print(f"        Category: {hyp_data['category']} | Score: {hyp_data['delivery_score']}")
                print()

                inserted += 1

            except Exception as e:
                print(f"   [{i}/{len(HYPOTHESES_DATA)}] ❌ Error: {e}\n")
                continue

        await conn.close()

        print(f"✅ Poblado completo!")
        print(f"   Hipótesis insertadas: {inserted}/{len(HYPOTHESES_DATA)}")

        # Mostrar estadísticas del graveyard
        print(f"\n" + "="*70)
        print("📊 HYPOTHESIS GRAVEYARD - ESTADÍSTICAS")
        print("="*70 + "\n")

        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password
        )

        # Count por categoría
        result = await conn.fetch("""
            SELECT category, COUNT(*) as count
            FROM hypothesis_graveyard
            WHERE client_id = $1
            GROUP BY category
            ORDER BY count DESC
        """, client_id)

        print("Por categoría:")
        for row in result:
            print(f"   - {row['category']}: {row['count']}")

        # Count por rejected_by
        result = await conn.fetch("""
            SELECT rejected_by, COUNT(*) as count
            FROM hypothesis_graveyard
            WHERE client_id = $1 AND rejected_by IS NOT NULL
            GROUP BY rejected_by
            ORDER BY count DESC
        """, client_id)

        print(f"\nPor rejected_by:")
        for row in result:
            print(f"   - {row['rejected_by']}: {row['count']}")

        # Total
        result = await conn.fetchrow("""
            SELECT COUNT(*) as total
            FROM hypothesis_graveyard
            WHERE client_id = $1
        """, client_id)

        print(f"\nTotal en graveyard: {result['total']}")

        await conn.close()

        print(f"\n" + "="*70)
        print("✨ El Hypothesis Graveyard está listo para el Learning Loop!")
        print("="*70 + "\n")

        print("Próximo paso:")
        print("   python3 scripts/test_learning_loop.py")
        print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(populate_graveyard())
