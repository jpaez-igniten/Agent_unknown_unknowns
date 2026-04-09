"""
Hypothesis Generator - FASE 2

Genera hipótesis usando DUAL APPROACH:
1. Knowledge-driven: Desde strategic priorities, pain points, KPIs
2. Anomaly-driven: Desde anomalías detectadas en los datos
3. Orthodoxy-challenge: Desafía ortodoxos detectados

CRÍTICO: Cada hipótesis incluye:
- Actionability (if_true_then, decision_owner, action_threshold)
- Multi-dimensional confidence
- Delivery score
- Portfolio classification

TARGET MIX:
- 40% quick_win (<3 meses)
- 40% medium_term (3-12 meses)
- 20% strategic_bet (>12 meses)
"""

import logging
import json
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..business_context.profile_schema import BusinessProfile, Orthodoxy
from .models import (
    Hypothesis,
    Actionability,
    ActionThreshold,
    ConfidenceBreakdown,
    DeliveryScoreBreakdown,
    PortfolioType,
    HypothesisStatus
)
from . import prompts

logger = logging.getLogger(__name__)


class HypothesisGenerator:
    """
    Genera hipótesis accionables usando dual approach.

    Combina knowledge-driven (top-down) y anomaly-driven (bottom-up).
    """

    def __init__(self, llm, db_connection=None):
        """
        Args:
            llm: LLM para generación (ej: ChatGoogleGenerativeAI)
            db_connection: Conexión asyncpg (opcional, para anomaly detection)
        """
        self.llm = llm
        self.db = db_connection

    async def generate_hypotheses(
        self,
        profile: BusinessProfile,
        run_id: str,
        max_hypotheses: int = 20,
        include_orthodoxy_challenges: bool = True,
        include_anomaly_driven: bool = True
    ) -> List[Hypothesis]:
        """
        Genera hipótesis usando dual approach.

        Args:
            profile: BusinessProfile del cliente
            run_id: ID del run actual
            max_hypotheses: Máximo de hipótesis a generar
            include_orthodoxy_challenges: Si incluir desafío de ortodoxos
            include_anomaly_driven: Si incluir detección de anomalías

        Returns:
            Lista de Hypothesis objects con actionability completa
        """
        logger.info(f"Generating hypotheses for client {profile.client_id} (run: {run_id})")

        all_hypotheses = []

        try:
            # Preparar contexto
            business_context = profile.to_context_string()

            # Ejecutar ambos métodos en paralelo
            tasks = []

            # 1. Knowledge-driven (SIEMPRE)
            tasks.append(
                self._generate_knowledge_driven(
                    profile=profile,
                    run_id=run_id,
                    business_context=business_context,
                    max_hypotheses=max(max_hypotheses // 2, 5)
                )
            )

            # 2. Anomaly-driven (SI ESTÁ HABILITADO)
            if include_anomaly_driven and self.db:
                tasks.append(
                    self._generate_anomaly_driven(
                        profile=profile,
                        run_id=run_id,
                        business_context=business_context,
                        max_hypotheses=max(max_hypotheses // 4, 3)
                    )
                )

            # 3. Orthodoxy-challenge (SI HAY ORTODOXOS)
            if include_orthodoxy_challenges and profile.industry_orthodoxies:
                tasks.append(
                    self._generate_orthodoxy_challenges(
                        profile=profile,
                        run_id=run_id,
                        business_context=business_context,
                        max_hypotheses=max(max_hypotheses // 4, 3)
                    )
                )

            # Ejecutar en paralelo
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combinar resultados
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error in hypothesis generation: {result}")
                    continue
                if isinstance(result, list):
                    all_hypotheses.extend(result)

            logger.info(f"Generated {len(all_hypotheses)} raw hypotheses")

            # Calcular delivery scores
            all_hypotheses = await self._calculate_delivery_scores(all_hypotheses)

            # Filtrar por delivery score threshold (>=70)
            deliverable = [h for h in all_hypotheses if h.delivery_score.should_deliver]
            logger.info(f"Filtered to {len(deliverable)} deliverable hypotheses (score >=70)")

            # Balancear portfolio mix (40/40/20)
            balanced = self._balance_portfolio_mix(deliverable, max_hypotheses)

            logger.info(
                f"Final portfolio: {len(balanced)} hypotheses "
                f"({self._count_by_portfolio(balanced)})"
            )

            return balanced

        except Exception as e:
            logger.error(f"Error generating hypotheses: {e}")
            return []

    async def _generate_knowledge_driven(
        self,
        profile: BusinessProfile,
        run_id: str,
        business_context: str,
        max_hypotheses: int
    ) -> List[Hypothesis]:
        """
        Genera hipótesis knowledge-driven desde strategic priorities.
        """
        logger.info(f"Generating knowledge-driven hypotheses (max: {max_hypotheses})")

        # Preparar contexto de ortodoxos
        orthodoxies_context = prompts.format_orthodoxies_context(profile.industry_orthodoxies)

        # Construir prompt
        prompt = prompts.build_knowledge_driven_prompt(
            business_context=business_context,
            orthodoxies_context=orthodoxies_context,
            max_hypotheses=max_hypotheses
        )

        try:
            # Invocar LLM
            response = await self.llm.ainvoke(prompt)

            # Parsear respuesta
            hypotheses_data = json.loads(response.content)

            # Convertir a Hypothesis objects
            hypotheses = []
            for hyp_data in hypotheses_data:
                try:
                    hypothesis = self._build_hypothesis_from_dict(
                        hyp_data=hyp_data,
                        client_id=profile.client_id,
                        run_id=run_id
                    )
                    hypotheses.append(hypothesis)
                except Exception as e:
                    logger.warning(f"Could not build hypothesis from LLM output: {e}")
                    continue

            logger.info(f"Generated {len(hypotheses)} knowledge-driven hypotheses")
            return hypotheses

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"LLM response was: {response.content[:500]}")
            return []
        except Exception as e:
            logger.error(f"Error in knowledge-driven generation: {e}")
            return []

    async def _generate_anomaly_driven(
        self,
        profile: BusinessProfile,
        run_id: str,
        business_context: str,
        max_hypotheses: int
    ) -> List[Hypothesis]:
        """
        Genera hipótesis anomaly-driven desde anomalías en datos.

        NOTA: En FASE 2, esto usa detección simple de anomalías.
        En FASE 3+, integrar con anomaly detection avanzado.
        """
        logger.info(f"Generating anomaly-driven hypotheses (max: {max_hypotheses})")

        # Detectar anomalías
        anomalies = await self._detect_anomalies(profile.client_id)

        if not anomalies:
            logger.info("No anomalies detected, skipping anomaly-driven generation")
            return []

        # Preparar contexto de anomalías
        anomalies_context = prompts.format_anomalies_context(anomalies)

        # Construir prompt
        prompt = prompts.build_anomaly_driven_prompt(
            business_context=business_context,
            anomalies_context=anomalies_context,
            max_hypotheses=max_hypotheses
        )

        try:
            # Invocar LLM
            response = await self.llm.ainvoke(prompt)

            # Parsear respuesta
            hypotheses_data = json.loads(response.content)

            # Convertir a Hypothesis objects
            hypotheses = []
            for hyp_data in hypotheses_data:
                try:
                    hypothesis = self._build_hypothesis_from_dict(
                        hyp_data=hyp_data,
                        client_id=profile.client_id,
                        run_id=run_id
                    )
                    hypotheses.append(hypothesis)
                except Exception as e:
                    logger.warning(f"Could not build hypothesis from LLM output: {e}")
                    continue

            logger.info(f"Generated {len(hypotheses)} anomaly-driven hypotheses")
            return hypotheses

        except Exception as e:
            logger.error(f"Error in anomaly-driven generation: {e}")
            return []

    async def _generate_orthodoxy_challenges(
        self,
        profile: BusinessProfile,
        run_id: str,
        business_context: str,
        max_hypotheses: int
    ) -> List[Hypothesis]:
        """
        Genera hipótesis que desafían ortodoxos detectados.
        """
        logger.info(f"Generating orthodoxy-challenge hypotheses (max: {max_hypotheses})")

        all_hypotheses = []

        # Priorizar ortodoxos de alto impacto
        high_disruption = profile.get_high_disruption_orthodoxies()
        orthodoxies_to_challenge = high_disruption[:3]  # Top 3

        if not orthodoxies_to_challenge:
            # Si no hay high-disruption, usar los primeros 2
            orthodoxies_to_challenge = profile.industry_orthodoxies[:2]

        logger.info(f"Challenging {len(orthodoxies_to_challenge)} orthodoxies")

        # Generar hipótesis para cada ortodoxo
        for orthodoxy in orthodoxies_to_challenge:
            orthodoxy_dict = {
                'orthodoxy': orthodoxy.orthodoxy,
                'discovered_by': orthodoxy.discovered_by,
                'confidence': orthodoxy.confidence,
                'potential_for_disruption': orthodoxy.potential_for_disruption,
                'evidence': orthodoxy.evidence
            }

            # Construir prompt
            prompt = prompts.build_orthodoxy_challenge_prompt(
                business_context=business_context,
                orthodoxy_dict=orthodoxy_dict,
                max_hypotheses=2  # 2 hipótesis por ortodoxo
            )

            try:
                # Invocar LLM
                response = await self.llm.ainvoke(prompt)

                # Parsear respuesta
                hypotheses_data = json.loads(response.content)

                # Convertir a Hypothesis objects
                for hyp_data in hypotheses_data:
                    try:
                        hypothesis = self._build_hypothesis_from_dict(
                            hyp_data=hyp_data,
                            client_id=profile.client_id,
                            run_id=run_id
                        )
                        all_hypotheses.append(hypothesis)
                    except Exception as e:
                        logger.warning(f"Could not build hypothesis: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error challenging orthodoxy '{orthodoxy.orthodoxy}': {e}")
                continue

        logger.info(f"Generated {len(all_hypotheses)} orthodoxy-challenge hypotheses")
        return all_hypotheses[:max_hypotheses]

    async def _detect_anomalies(self, client_id: str) -> List[Dict[str, Any]]:
        """
        Detecta anomalías en los datos del cliente.

        NOTA: En FASE 2, esto es una implementación simple.
        En FASE 3+, implementar detección estadística avanzada.
        """
        if not self.db:
            logger.debug("No DB connection, skipping anomaly detection")
            return []

        logger.debug(f"Detecting anomalies for client {client_id}")

        anomalies = []

        # TODO: Implementar detección real de anomalías
        # Por ahora, retornar lista vacía
        # En FASE 3, implementar:
        # - Statistical outliers (z-score > 3)
        # - Sudden changes (period-over-period > 30%)
        # - Unexpected correlations
        # - Segmentation anomalies

        logger.debug(f"Detected {len(anomalies)} anomalies")
        return anomalies

    def _build_hypothesis_from_dict(
        self,
        hyp_data: Dict[str, Any],
        client_id: str,
        run_id: str
    ) -> Hypothesis:
        """
        Construye Hypothesis object desde dict del LLM.
        """
        # Generar hypothesis_id
        hypothesis_id = f"hyp_{uuid.uuid4().hex[:12]}"

        # Parsear actionability
        actionability_data = hyp_data.get('actionability', {})
        actionability = Actionability(
            if_true_then=actionability_data.get('if_true_then', ''),
            if_false_then=actionability_data.get('if_false_then'),
            decision_owner=actionability_data.get('decision_owner', 'CEO'),
            action_threshold=ActionThreshold(**actionability_data.get('action_threshold', {})),
            estimated_effort_hours=actionability_data.get('estimated_effort_hours'),
            estimated_cost_usd=actionability_data.get('estimated_cost_usd'),
            estimated_impact_usd=actionability_data.get('estimated_impact_usd'),
            time_to_impact_months=actionability_data.get('time_to_impact_months')
        )

        # Parsear confidence
        confidence_data = hyp_data.get('confidence', {})
        confidence = ConfidenceBreakdown(
            confidence_total=confidence_data.get('confidence_total', 0.5),
            confidence_statistical=confidence_data.get('confidence_statistical', 0.5),
            confidence_data_quality=confidence_data.get('confidence_data_quality', 0.5),
            confidence_model=confidence_data.get('confidence_model', 0.5),
            confidence_caveats=confidence_data.get('confidence_caveats', [])
        )

        # Parsear portfolio_type
        portfolio_type_str = hyp_data.get('portfolio_type', 'medium_term')
        portfolio_type = PortfolioType(portfolio_type_str)

        # Delivery score (placeholder, se calcula después)
        delivery_score = DeliveryScoreBreakdown(
            statistical_confidence_score=0,
            business_impact_score=0,
            actionability_score=0,
            strategic_alignment_score=0,
            delivery_score_total=0,
            should_deliver=False
        )

        # Construir Hypothesis
        hypothesis = Hypothesis(
            hypothesis_id=hypothesis_id,
            client_id=client_id,
            run_id=run_id,
            hypothesis_text=hyp_data.get('hypothesis_text', ''),
            hypothesis_type=hyp_data.get('hypothesis_type', 'knowledge_driven'),
            category=hyp_data.get('category', 'unknown'),
            generated_from=hyp_data.get('generated_from', 'strategic_priority'),
            source_orthodoxy_id=hyp_data.get('source_orthodoxy_id'),
            source_anomaly_id=hyp_data.get('source_anomaly_id'),
            actionability=actionability,
            confidence=confidence,
            counterfactuals=None,  # TODO: parsear si viene del LLM
            evidence=hyp_data.get('evidence', []),
            data_sources_used=hyp_data.get('data_sources_used', []),
            delivery_score=delivery_score,
            portfolio_type=portfolio_type,
            status=HypothesisStatus.PENDING_VALIDATION,
            created_at=datetime.now()
        )

        return hypothesis

    async def _calculate_delivery_scores(
        self,
        hypotheses: List[Hypothesis]
    ) -> List[Hypothesis]:
        """
        Calcula delivery scores para todas las hipótesis.
        """
        logger.info(f"Calculating delivery scores for {len(hypotheses)} hypotheses")

        for hypothesis in hypotheses:
            try:
                # Calcular componentes del score
                stats_score = self._calculate_statistical_confidence_score(hypothesis)
                impact_score = self._calculate_business_impact_score(hypothesis)
                action_score = self._calculate_actionability_score(hypothesis)
                alignment_score = self._calculate_strategic_alignment_score(hypothesis)

                # Calcular total (weighted average)
                total_score = (
                    stats_score * 0.25 +
                    impact_score * 0.30 +
                    action_score * 0.25 +
                    alignment_score * 0.20
                )

                # Determinar si se debe entregar
                should_deliver = total_score >= 70.0

                # Actualizar delivery_score
                hypothesis.delivery_score = DeliveryScoreBreakdown(
                    statistical_confidence_score=stats_score,
                    business_impact_score=impact_score,
                    actionability_score=action_score,
                    strategic_alignment_score=alignment_score,
                    delivery_score_total=round(total_score, 2),
                    should_deliver=should_deliver
                )

            except Exception as e:
                logger.warning(f"Error calculating delivery score for {hypothesis.hypothesis_id}: {e}")
                # Dejar scores en 0
                continue

        return hypotheses

    def _calculate_statistical_confidence_score(self, hypothesis: Hypothesis) -> float:
        """Calcula statistical confidence score (0-100)."""
        confidence_total = hypothesis.confidence.confidence_total

        if confidence_total >= 0.8:
            return 95.0
        elif confidence_total >= 0.7:
            return 82.0
        elif confidence_total >= 0.6:
            return 67.0
        else:
            return confidence_total * 100 * 0.5  # Penalizar <0.6

    def _calculate_business_impact_score(self, hypothesis: Hypothesis) -> float:
        """Calcula business impact score (0-100)."""
        estimated_impact = hypothesis.actionability.estimated_impact_usd or 0

        if estimated_impact >= 500000:
            return 95.0
        elif estimated_impact >= 200000:
            return 82.0
        elif estimated_impact >= 50000:
            return 67.0
        elif estimated_impact >= 10000:
            return 50.0
        else:
            return 30.0

    def _calculate_actionability_score(self, hypothesis: Hypothesis) -> float:
        """Calcula actionability score (0-100)."""
        score = 0.0

        # if_true_then específico y detallado: +50
        if hypothesis.actionability.if_true_then and len(hypothesis.actionability.if_true_then) > 50:
            score += 50
        elif hypothesis.actionability.if_true_then:
            score += 30

        # decision_owner claro: +20
        if hypothesis.actionability.decision_owner and hypothesis.actionability.decision_owner != 'CEO':
            score += 20
        elif hypothesis.actionability.decision_owner:
            score += 10

        # action_threshold definido: +15
        if hypothesis.actionability.action_threshold.min_confidence is not None:
            score += 15

        # estimated_effort y cost presentes: +15
        if hypothesis.actionability.estimated_cost_usd is not None:
            score += 7.5
        if hypothesis.actionability.estimated_effort_hours is not None:
            score += 7.5

        return score

    def _calculate_strategic_alignment_score(self, hypothesis: Hypothesis) -> float:
        """Calcula strategic alignment score (0-100)."""
        # En FASE 2, usar heurística simple basada en generated_from
        if hypothesis.generated_from == 'strategic_priority':
            return 95.0
        elif hypothesis.generated_from == 'pain_point':
            return 85.0
        elif hypothesis.generated_from == 'kpi_gap':
            return 80.0
        elif hypothesis.generated_from == 'orthodoxy':
            return 75.0
        else:
            return 60.0

    def _balance_portfolio_mix(
        self,
        hypotheses: List[Hypothesis],
        max_hypotheses: int
    ) -> List[Hypothesis]:
        """
        Balancea portfolio mix: 40% quick_win, 40% medium_term, 20% strategic_bet.
        """
        # Separar por portfolio type
        by_type = {
            PortfolioType.QUICK_WIN: [],
            PortfolioType.MEDIUM_TERM: [],
            PortfolioType.STRATEGIC_BET: []
        }

        for hyp in hypotheses:
            by_type[hyp.portfolio_type].append(hyp)

        # Ordenar cada tipo por delivery score (desc)
        for ptype in by_type:
            by_type[ptype].sort(key=lambda h: h.delivery_score.delivery_score_total, reverse=True)

        # Calcular targets
        target_quick = int(max_hypotheses * 0.4)
        target_medium = int(max_hypotheses * 0.4)
        target_strategic = max_hypotheses - target_quick - target_medium

        # Seleccionar
        selected = []
        selected.extend(by_type[PortfolioType.QUICK_WIN][:target_quick])
        selected.extend(by_type[PortfolioType.MEDIUM_TERM][:target_medium])
        selected.extend(by_type[PortfolioType.STRATEGIC_BET][:target_strategic])

        # Si no hay suficientes, rellenar con los mejores disponibles
        if len(selected) < max_hypotheses:
            remaining = [h for h in hypotheses if h not in selected]
            remaining.sort(key=lambda h: h.delivery_score.delivery_score_total, reverse=True)
            selected.extend(remaining[:max_hypotheses - len(selected)])

        return selected[:max_hypotheses]

    def _count_by_portfolio(self, hypotheses: List[Hypothesis]) -> str:
        """Helper para contar hipótesis por portfolio type."""
        counts = {
            PortfolioType.QUICK_WIN: 0,
            PortfolioType.MEDIUM_TERM: 0,
            PortfolioType.STRATEGIC_BET: 0
        }

        for hyp in hypotheses:
            counts[hyp.portfolio_type] += 1

        return (
            f"quick_win: {counts[PortfolioType.QUICK_WIN]}, "
            f"medium_term: {counts[PortfolioType.MEDIUM_TERM]}, "
            f"strategic_bet: {counts[PortfolioType.STRATEGIC_BET]}"
        )
