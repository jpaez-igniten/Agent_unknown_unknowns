"""
Feasibility Validator - FASE 2

Valida la viabilidad técnica de hipótesis antes de intentar validarlas con datos.

Verifica:
1. ¿Tenemos los datos necesarios?
2. ¿Es técnicamente factible validar con SQL?
3. ¿Qué queries necesitamos?
4. ¿Hay blockers técnicos?

Retorna ValidationResult con feasibility score.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from .models import ValidationResult

logger = logging.getLogger(__name__)


class FeasibilityValidator:
    """
    Valida viabilidad técnica de hipótesis.

    Analiza si tenemos los datos y capacidad técnica para validar cada hipótesis.
    """

    def __init__(self, db_connection, llm):
        """
        Args:
            db_connection: Conexión asyncpg a Postgres
            llm: LLM para análisis (ej: ChatGoogleGenerativeAI)
        """
        self.db = db_connection
        self.llm = llm
        self._available_tables_cache = None

    async def validate_hypothesis_feasibility(
        self,
        hypothesis: Dict[str, Any],
        client_id: str
    ) -> ValidationResult:
        """
        Valida si es técnicamente factible validar esta hipótesis.

        Args:
            hypothesis: Dict con información de la hipótesis
            client_id: ID del cliente

        Returns:
            ValidationResult con feasibility score y detalles
        """
        logger.info(f"Validating feasibility for hypothesis: {hypothesis.get('hypothesis_text', '')[:50]}...")

        try:
            # Obtener tablas disponibles
            available_tables = await self._get_available_tables(client_id)

            # Analizar qué tablas necesitamos
            required_tables = await self._identify_required_tables(hypothesis)

            # Identificar tablas faltantes
            missing_tables = [t for t in required_tables if t not in available_tables]

            # Calcular feasibility score
            feasibility_score = self._calculate_feasibility_score(
                required_tables=required_tables,
                available_tables=available_tables,
                missing_tables=missing_tables,
                hypothesis=hypothesis
            )

            # Determinar si es factible
            is_feasible = feasibility_score >= 0.5 and len(missing_tables) == 0

            # Sugerir queries si es factible
            suggested_queries = []
            if is_feasible:
                suggested_queries = await self._suggest_validation_queries(
                    hypothesis=hypothesis,
                    available_tables=available_tables
                )

            # Identificar blockers
            blockers = self._identify_blockers(
                missing_tables=missing_tables,
                hypothesis=hypothesis
            )

            # Estimar complejidad
            complexity = self._estimate_complexity(
                required_tables=required_tables,
                hypothesis=hypothesis
            )

            # Construir resultado
            result = ValidationResult(
                hypothesis_id=hypothesis.get('hypothesis_id', 'unknown'),
                is_feasible=is_feasible,
                feasibility_score=feasibility_score,
                required_tables=required_tables,
                available_tables=list(set(available_tables) & set(required_tables)),
                missing_tables=missing_tables,
                suggested_queries=suggested_queries,
                estimated_complexity=complexity,
                blockers=blockers,
                validated_at=datetime.now(),
                validator_notes=self._generate_validator_notes(
                    is_feasible=is_feasible,
                    feasibility_score=feasibility_score,
                    blockers=blockers
                )
            )

            logger.info(
                f"Feasibility validation complete: "
                f"score={feasibility_score:.2f}, "
                f"is_feasible={is_feasible}, "
                f"missing_tables={len(missing_tables)}"
            )

            return result

        except Exception as e:
            logger.error(f"Error validating feasibility: {e}")
            # Retornar resultado con is_feasible=False
            return ValidationResult(
                hypothesis_id=hypothesis.get('hypothesis_id', 'unknown'),
                is_feasible=False,
                feasibility_score=0.0,
                required_tables=[],
                available_tables=[],
                missing_tables=[],
                suggested_queries=[],
                estimated_complexity='unknown',
                blockers=[f"Error during validation: {str(e)}"],
                validated_at=datetime.now(),
                validator_notes=f"Validation failed: {str(e)}"
            )

    async def _get_available_tables(self, client_id: str) -> List[str]:
        """
        Obtiene lista de tablas disponibles para el cliente.

        En FASE 2, asumimos schema público.
        En FASE 3+, podríamos tener schemas por cliente.
        """
        # Usar cache si existe
        if self._available_tables_cache is not None:
            return self._available_tables_cache

        try:
            # Query para obtener tablas del schema público
            query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """

            rows = await self.db.fetch(query)
            tables = [row['table_name'] for row in rows]

            # Cachear resultado
            self._available_tables_cache = tables

            logger.debug(f"Found {len(tables)} available tables for client {client_id}")
            return tables

        except Exception as e:
            logger.error(f"Error getting available tables: {e}")
            return []

    async def _identify_required_tables(self, hypothesis: Dict[str, Any]) -> List[str]:
        """
        Identifica qué tablas se necesitan para validar la hipótesis.

        Usa LLM para analizar el texto de la hipótesis y data_sources_used.
        """
        # Primero, intentar con data_sources_used
        data_sources = hypothesis.get('data_sources_used', [])
        if data_sources:
            logger.debug(f"Using data_sources_used from hypothesis: {data_sources}")
            return data_sources

        # Si no hay data_sources, usar LLM para identificar
        logger.debug("No data_sources_used, using LLM to identify required tables")

        prompt = f"""
Analiza esta hipótesis e identifica qué tablas de base de datos se necesitarían para validarla.

HIPÓTESIS:
{hypothesis.get('hypothesis_text', '')}

CATEGORÍA: {hypothesis.get('category', 'unknown')}

CONTEXTO:
{hypothesis.get('evidence', [])}

Identifica tablas genéricas que probablemente existan. Por ejemplo:
- Para churn: "customers", "customer_churn", "subscriptions", "cancellations"
- Para pricing: "pricing_history", "products", "transactions", "discounts"
- Para profitability: "revenue", "costs", "customers", "transactions"
- Para operations: "orders", "shipments", "inventory", "suppliers"

Retorna un JSON array con los nombres de tablas:

```json
{{
  "required_tables": ["table1", "table2", "table3"],
  "reasoning": "Breve explicación"
}}
```

Retorna SOLO el JSON.
"""

        try:
            response = await self.llm.ainvoke(prompt)
            result = json.loads(response.content)
            required_tables = result.get('required_tables', [])

            logger.debug(f"LLM identified required tables: {required_tables}")
            return required_tables

        except Exception as e:
            logger.warning(f"Could not identify required tables with LLM: {e}")
            # Fallback: inferir basado en categoría
            return self._infer_tables_from_category(hypothesis.get('category', 'unknown'))

    def _infer_tables_from_category(self, category: str) -> List[str]:
        """Fallback: infiere tablas genéricas basado en categoría."""
        category_tables = {
            'churn': ['customers', 'customer_churn', 'subscriptions', 'cancellations'],
            'pricing': ['pricing_history', 'products', 'transactions', 'discounts'],
            'profitability': ['revenue', 'costs', 'customers', 'transactions'],
            'operations': ['orders', 'shipments', 'inventory'],
            'sales': ['sales', 'opportunities', 'customers', 'products'],
            'product': ['products', 'usage_data', 'features', 'customers']
        }

        return category_tables.get(category, ['customers', 'transactions', 'revenue'])

    def _calculate_feasibility_score(
        self,
        required_tables: List[str],
        available_tables: List[str],
        missing_tables: List[str],
        hypothesis: Dict[str, Any]
    ) -> float:
        """
        Calcula feasibility score (0-1).

        Componentes:
        - Data availability: 50% (¿tenemos las tablas?)
        - Hypothesis clarity: 30% (¿está clara la hipótesis?)
        - Complexity: 20% (¿es simple de validar?)
        """
        # Data availability score
        if len(required_tables) == 0:
            data_availability_score = 0.5  # No está claro qué se necesita
        else:
            data_availability_score = (len(required_tables) - len(missing_tables)) / len(required_tables)

        # Hypothesis clarity score
        hypothesis_text = hypothesis.get('hypothesis_text', '')
        if len(hypothesis_text) > 50 and hypothesis.get('category') and hypothesis.get('actionability'):
            clarity_score = 1.0
        elif len(hypothesis_text) > 30:
            clarity_score = 0.7
        else:
            clarity_score = 0.3

        # Complexity score (inverse: simple = high score)
        if len(required_tables) <= 2:
            complexity_score = 1.0
        elif len(required_tables) <= 4:
            complexity_score = 0.7
        else:
            complexity_score = 0.4

        # Weighted average
        feasibility_score = (
            data_availability_score * 0.5 +
            clarity_score * 0.3 +
            complexity_score * 0.2
        )

        return round(feasibility_score, 2)

    async def _suggest_validation_queries(
        self,
        hypothesis: Dict[str, Any],
        available_tables: List[str]
    ) -> List[str]:
        """
        Sugiere queries SQL para validar la hipótesis.

        Usa LLM para generar queries basados en la hipótesis y tablas disponibles.
        """
        logger.debug("Suggesting validation queries with LLM")

        prompt = f"""
Sugiere queries SQL para validar esta hipótesis.

HIPÓTESIS:
{hypothesis.get('hypothesis_text', '')}

TABLAS DISPONIBLES:
{', '.join(available_tables[:20])}

CATEGORÍA: {hypothesis.get('category', 'unknown')}

Genera 1-3 queries SQL que:
1. Validen la hipótesis directamente
2. Sean EJECUTABLES (no incluyas datos ficticios)
3. Usen las tablas disponibles
4. Incluyan métricas clave (counts, averages, ratios, etc.)

IMPORTANTE:
- NO uses tablas que no están en la lista de disponibles
- Usa GENERIC column names típicos (id, name, date, amount, customer_id, etc.)
- Si la tabla no existe, sugiere un query conceptual pero marca que es HYPOTHETICAL

Retorna JSON:

```json
{{
  "queries": [
    {{
      "purpose": "Descripción de qué valida este query",
      "sql": "SELECT ... FROM ... WHERE ...",
      "is_hypothetical": false
    }}
  ]
}}
```

Retorna SOLO el JSON.
"""

        try:
            response = await self.llm.ainvoke(prompt)
            result = json.loads(response.content)
            queries_data = result.get('queries', [])

            # Extraer solo los SQL strings
            queries = []
            for q in queries_data:
                if not q.get('is_hypothetical', False):
                    queries.append(q['sql'])

            logger.debug(f"Generated {len(queries)} validation queries")
            return queries

        except Exception as e:
            logger.warning(f"Could not generate queries with LLM: {e}")
            return []

    def _identify_blockers(
        self,
        missing_tables: List[str],
        hypothesis: Dict[str, Any]
    ) -> List[str]:
        """Identifica blockers técnicos."""
        blockers = []

        # Blocker: tablas faltantes
        if missing_tables:
            blockers.append(
                f"Missing {len(missing_tables)} required tables: {', '.join(missing_tables[:3])}"
                + ("..." if len(missing_tables) > 3 else "")
            )

        # Blocker: hipótesis muy vaga
        if len(hypothesis.get('hypothesis_text', '')) < 20:
            blockers.append("Hypothesis text is too vague to validate")

        # Blocker: no hay categoría
        if not hypothesis.get('category'):
            blockers.append("No category specified for hypothesis")

        # Blocker: no hay evidencia
        if not hypothesis.get('evidence'):
            blockers.append("No evidence provided for hypothesis")

        return blockers

    def _estimate_complexity(
        self,
        required_tables: List[str],
        hypothesis: Dict[str, Any]
    ) -> str:
        """
        Estima complejidad de validación.

        Returns:
            'low', 'medium', 'high', 'unknown'
        """
        num_tables = len(required_tables)

        # Factores que aumentan complejidad
        complexity_factors = 0

        if num_tables > 4:
            complexity_factors += 2
        elif num_tables > 2:
            complexity_factors += 1

        # Hipótesis que mencionan "correlation", "predict", "segmentation" son más complejas
        hypothesis_text = hypothesis.get('hypothesis_text', '').lower()
        complex_keywords = ['correlation', 'predict', 'machine learning', 'segmentation', 'cluster']
        if any(keyword in hypothesis_text for keyword in complex_keywords):
            complexity_factors += 1

        # Determinar nivel
        if complexity_factors >= 3:
            return 'high'
        elif complexity_factors >= 1:
            return 'medium'
        else:
            return 'low'

    def _generate_validator_notes(
        self,
        is_feasible: bool,
        feasibility_score: float,
        blockers: List[str]
    ) -> str:
        """Genera notas del validador."""
        if is_feasible:
            return f"Hypothesis is technically feasible (score: {feasibility_score:.2f}). Ready for validation."
        elif blockers:
            return f"Hypothesis is NOT feasible (score: {feasibility_score:.2f}). Blockers: {'; '.join(blockers[:2])}"
        else:
            return f"Hypothesis has low feasibility (score: {feasibility_score:.2f}). Review required."
