"""
Business Profile Repository

Maneja persistencia de BusinessProfile en:
- Postgres: Datos estructurados y queries transaccionales
- ChromaDB: Embeddings para búsqueda semántica de perfiles similares

Patrón Repository para desacoplar la lógica de negocio de la persistencia.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

import asyncpg
from chromadb import Client as ChromaClient
from chromadb.config import Settings

from .profile_schema import (
    BusinessProfile,
    BusinessProfileCreate,
    BusinessProfileUpdate
)

logger = logging.getLogger(__name__)


class BusinessProfileRepository:
    """
    Repository para BusinessProfile con soporte dual:
    - Postgres: Almacenamiento principal (CRUD)
    - ChromaDB: Búsqueda semántica de perfiles similares
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        chroma_client: Optional[ChromaClient] = None,
        embedding_function: Optional[Any] = None
    ):
        """
        Args:
            db_pool: Connection pool de asyncpg para Postgres
            chroma_client: Cliente de ChromaDB (opcional para FASE 1)
            embedding_function: Función para generar embeddings (opcional para FASE 1)
        """
        self.db_pool = db_pool
        self.chroma_client = chroma_client
        self.embedding_function = embedding_function

        # Inicializar colección de ChromaDB si está disponible
        if self.chroma_client:
            try:
                self.collection = self.chroma_client.get_or_create_collection(
                    name="business_profiles",
                    metadata={"description": "Business profiles for semantic search"}
                )
                logger.info("ChromaDB collection 'business_profiles' initialized")
            except Exception as e:
                logger.warning(f"Could not initialize ChromaDB collection: {e}")
                self.collection = None
        else:
            self.collection = None

    # ========== CREATE ==========

    async def create_profile(self, profile: BusinessProfile) -> BusinessProfile:
        """
        Crea un nuevo perfil en Postgres y ChromaDB.

        Args:
            profile: BusinessProfile a crear

        Returns:
            BusinessProfile creado con timestamps actualizados

        Raises:
            ValueError: Si el client_id ya existe
            Exception: Errores de base de datos
        """
        try:
            # Verificar que no exista
            existing = await self.get_profile(profile.client_id)
            if existing:
                raise ValueError(f"Profile for client_id '{profile.client_id}' already exists")

            # Calcular completeness
            profile.profile_completeness = profile.calculate_completeness()
            profile.created_at = datetime.now()
            profile.last_updated = datetime.now()

            # Preparar datos para Postgres
            profile_data = json.loads(profile.json())

            # Insertar en Postgres
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO business_profiles (
                        client_id,
                        profile_data,
                        profile_completeness,
                        confidence_score,
                        created_at,
                        updated_at,
                        is_active,
                        insights_enabled
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    profile.client_id,
                    json.dumps(profile_data),
                    profile.profile_completeness,
                    profile.confidence_score,
                    profile.created_at,
                    profile.last_updated,
                    True,  # is_active
                    True   # insights_enabled
                )

            logger.info(f"Created profile for client_id: {profile.client_id}")

            # Agregar a ChromaDB (si disponible)
            if self.collection and self.embedding_function:
                await self._add_to_chromadb(profile)

            return profile

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating profile for {profile.client_id}: {e}")
            raise

    async def create_from_onboarding(
        self,
        create_data: BusinessProfileCreate
    ) -> BusinessProfile:
        """
        Crea un perfil desde datos de onboarding.

        Args:
            create_data: BusinessProfileCreate con datos básicos

        Returns:
            BusinessProfile creado
        """
        # Convertir a BusinessProfile completo
        profile = BusinessProfile(
            **create_data.dict(),
            created_at=datetime.now(),
            last_updated=datetime.now()
        )

        # Calcular completeness
        profile.profile_completeness = profile.calculate_completeness()

        return await self.create_profile(profile)

    # ========== READ ==========

    async def get_profile(self, client_id: str) -> Optional[BusinessProfile]:
        """
        Obtiene un perfil por client_id.

        Args:
            client_id: ID del cliente

        Returns:
            BusinessProfile o None si no existe
        """
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        profile_data,
                        profile_completeness,
                        confidence_score,
                        created_at,
                        updated_at,
                        last_enrichment,
                        last_hypothesis_run,
                        is_active,
                        insights_enabled
                    FROM business_profiles
                    WHERE client_id = $1
                    """,
                    client_id
                )

            if not row:
                return None

            # Parsear JSON a BusinessProfile
            profile_data = json.loads(row['profile_data'])
            profile = BusinessProfile(**profile_data)

            # Actualizar con datos de metadata de la tabla
            profile.profile_completeness = row['profile_completeness']
            profile.confidence_score = row['confidence_score']
            profile.created_at = row['created_at']
            profile.last_updated = row['updated_at']
            profile.last_enrichment = row['last_enrichment']

            return profile

        except Exception as e:
            logger.error(f"Error getting profile {client_id}: {e}")
            raise

    async def list_profiles(
        self,
        active_only: bool = True,
        min_completeness: float = 0.0,
        limit: int = 100,
        offset: int = 0
    ) -> List[BusinessProfile]:
        """
        Lista perfiles con filtros.

        Args:
            active_only: Solo perfiles activos
            min_completeness: Completeness mínimo
            limit: Límite de resultados
            offset: Offset para paginación

        Returns:
            Lista de BusinessProfile
        """
        try:
            query = """
                SELECT profile_data, profile_completeness, confidence_score
                FROM business_profiles
                WHERE 1=1
            """
            params = []
            param_count = 0

            if active_only:
                param_count += 1
                query += f" AND is_active = ${param_count}"
                params.append(True)

            if min_completeness > 0:
                param_count += 1
                query += f" AND profile_completeness >= ${param_count}"
                params.append(min_completeness)

            query += " ORDER BY profile_completeness DESC, created_at DESC"

            param_count += 1
            query += f" LIMIT ${param_count}"
            params.append(limit)

            param_count += 1
            query += f" OFFSET ${param_count}"
            params.append(offset)

            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

            profiles = []
            for row in rows:
                profile_data = json.loads(row['profile_data'])
                profile = BusinessProfile(**profile_data)
                profile.profile_completeness = row['profile_completeness']
                profile.confidence_score = row['confidence_score']
                profiles.append(profile)

            return profiles

        except Exception as e:
            logger.error(f"Error listing profiles: {e}")
            raise

    # ========== UPDATE ==========

    async def update_profile(
        self,
        client_id: str,
        updates: BusinessProfileUpdate
    ) -> Optional[BusinessProfile]:
        """
        Actualiza un perfil existente.

        Args:
            client_id: ID del cliente
            updates: BusinessProfileUpdate con campos a actualizar

        Returns:
            BusinessProfile actualizado o None si no existe
        """
        try:
            # Obtener perfil actual
            current = await self.get_profile(client_id)
            if not current:
                logger.warning(f"Profile {client_id} not found for update")
                return None

            # Aplicar updates
            update_data = updates.dict(exclude_unset=True)
            for field, value in update_data.items():
                if value is not None:
                    setattr(current, field, value)

            # Actualizar timestamps
            current.last_updated = datetime.now()

            # Recalcular completeness
            current.profile_completeness = current.calculate_completeness()

            # Guardar en Postgres
            profile_data = json.loads(current.json())

            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE business_profiles
                    SET
                        profile_data = $2,
                        profile_completeness = $3,
                        confidence_score = $4,
                        updated_at = $5
                    WHERE client_id = $1
                    """,
                    client_id,
                    json.dumps(profile_data),
                    current.profile_completeness,
                    current.confidence_score,
                    current.last_updated
                )

            logger.info(f"Updated profile for client_id: {client_id}")

            # Actualizar en ChromaDB (si disponible)
            if self.collection and self.embedding_function:
                await self._update_chromadb(current)

            return current

        except Exception as e:
            logger.error(f"Error updating profile {client_id}: {e}")
            raise

    async def update_last_hypothesis_run(self, client_id: str):
        """Actualiza timestamp de última ejecución de hipótesis"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE business_profiles
                    SET last_hypothesis_run = $2
                    WHERE client_id = $1
                    """,
                    client_id,
                    datetime.now()
                )
        except Exception as e:
            logger.error(f"Error updating last_hypothesis_run for {client_id}: {e}")
            raise

    # ========== DELETE ==========

    async def delete_profile(self, client_id: str) -> bool:
        """
        Elimina un perfil (soft delete - marca como inactivo).

        Args:
            client_id: ID del cliente

        Returns:
            True si se eliminó, False si no existía
        """
        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE business_profiles
                    SET is_active = FALSE, updated_at = $2
                    WHERE client_id = $1
                    """,
                    client_id,
                    datetime.now()
                )

            # Verificar si se actualizó algún registro
            rows_affected = int(result.split()[-1])
            if rows_affected > 0:
                logger.info(f"Soft deleted profile: {client_id}")
                return True
            else:
                logger.warning(f"Profile {client_id} not found for deletion")
                return False

        except Exception as e:
            logger.error(f"Error deleting profile {client_id}: {e}")
            raise

    async def hard_delete_profile(self, client_id: str) -> bool:
        """
        Elimina permanentemente un perfil (hard delete).
        CUIDADO: Esto eliminará también runs e insights por CASCADE.

        Args:
            client_id: ID del cliente

        Returns:
            True si se eliminó, False si no existía
        """
        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM business_profiles WHERE client_id = $1",
                    client_id
                )

            rows_affected = int(result.split()[-1])
            if rows_affected > 0:
                logger.warning(f"Hard deleted profile: {client_id}")

                # Eliminar de ChromaDB
                if self.collection:
                    try:
                        self.collection.delete(ids=[client_id])
                    except Exception as e:
                        logger.warning(f"Could not delete from ChromaDB: {e}")

                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Error hard deleting profile {client_id}: {e}")
            raise

    # ========== SEARCH (ChromaDB) ==========

    async def search_similar_profiles(
        self,
        profile: BusinessProfile,
        limit: int = 5
    ) -> List[BusinessProfile]:
        """
        Busca perfiles similares usando búsqueda semántica en ChromaDB.

        Args:
            profile: BusinessProfile de referencia
            limit: Número máximo de resultados

        Returns:
            Lista de BusinessProfile similares

        Note:
            En FASE 1, ChromaDB es opcional. Si no está disponible,
            usa búsqueda simple por industria en Postgres.
        """
        if not self.collection or not self.embedding_function:
            # Fallback: búsqueda simple por industria
            logger.info("ChromaDB not available, using simple industry search")
            return await self._search_by_industry(profile.industry, limit)

        try:
            # Generar embedding del perfil
            context_text = profile.to_context_string()
            embedding = self.embedding_function([context_text])[0]

            # Buscar en ChromaDB
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=limit + 1,  # +1 porque puede incluirse a sí mismo
                include=['metadatas', 'documents']
            )

            # Obtener client_ids de resultados
            similar_client_ids = []
            for client_id in results['ids'][0]:
                if client_id != profile.client_id:  # Excluir el mismo perfil
                    similar_client_ids.append(client_id)

            # Cargar perfiles completos desde Postgres
            similar_profiles = []
            for client_id in similar_client_ids[:limit]:
                p = await self.get_profile(client_id)
                if p:
                    similar_profiles.append(p)

            logger.info(f"Found {len(similar_profiles)} similar profiles for {profile.client_id}")
            return similar_profiles

        except Exception as e:
            logger.error(f"Error searching similar profiles: {e}")
            # Fallback a búsqueda simple
            return await self._search_by_industry(profile.industry, limit)

    async def _search_by_industry(
        self,
        industry: str,
        limit: int = 5
    ) -> List[BusinessProfile]:
        """
        Búsqueda simple por industria (fallback cuando ChromaDB no disponible).
        """
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT profile_data, profile_completeness, confidence_score
                    FROM business_profiles
                    WHERE profile_data->>'industry' = $1
                      AND is_active = TRUE
                    ORDER BY profile_completeness DESC
                    LIMIT $2
                    """,
                    industry,
                    limit
                )

            profiles = []
            for row in rows:
                profile_data = json.loads(row['profile_data'])
                profile = BusinessProfile(**profile_data)
                profile.profile_completeness = row['profile_completeness']
                profile.confidence_score = row['confidence_score']
                profiles.append(profile)

            return profiles

        except Exception as e:
            logger.error(f"Error searching by industry: {e}")
            return []

    # ========== ChromaDB Helper Methods ==========

    async def _add_to_chromadb(self, profile: BusinessProfile):
        """Agrega perfil a ChromaDB para búsqueda semántica"""
        if not self.collection or not self.embedding_function:
            return

        try:
            # Generar texto contextual
            context_text = profile.to_context_string()

            # Generar embedding
            embedding = self.embedding_function([context_text])[0]

            # Agregar a colección
            self.collection.add(
                ids=[profile.client_id],
                embeddings=[embedding],
                documents=[context_text],
                metadatas=[{
                    'company_name': profile.company_name,
                    'industry': profile.industry,
                    'business_model': profile.business_model,
                    'completeness': profile.profile_completeness
                }]
            )

            logger.info(f"Added profile {profile.client_id} to ChromaDB")

        except Exception as e:
            logger.warning(f"Could not add profile to ChromaDB: {e}")

    async def _update_chromadb(self, profile: BusinessProfile):
        """Actualiza perfil en ChromaDB"""
        if not self.collection or not self.embedding_function:
            return

        try:
            # Eliminar versión anterior
            self.collection.delete(ids=[profile.client_id])

            # Agregar versión actualizada
            await self._add_to_chromadb(profile)

        except Exception as e:
            logger.warning(f"Could not update profile in ChromaDB: {e}")

    # ========== Stats & Utilities ==========

    async def get_profile_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas generales de perfiles.

        Returns:
            Dict con estadísticas: total, activos, por industria, completeness promedio, etc.
        """
        try:
            async with self.db_pool.acquire() as conn:
                # Total y activos
                total = await conn.fetchval("SELECT COUNT(*) FROM business_profiles")
                active = await conn.fetchval(
                    "SELECT COUNT(*) FROM business_profiles WHERE is_active = TRUE"
                )

                # Completeness promedio
                avg_completeness = await conn.fetchval(
                    "SELECT AVG(profile_completeness) FROM business_profiles WHERE is_active = TRUE"
                )

                # Por industria
                by_industry = await conn.fetch(
                    """
                    SELECT
                        profile_data->>'industry' as industry,
                        COUNT(*) as count
                    FROM business_profiles
                    WHERE is_active = TRUE
                    GROUP BY profile_data->>'industry'
                    ORDER BY count DESC
                    """
                )

                # Con hipótesis ejecutadas
                with_runs = await conn.fetchval(
                    "SELECT COUNT(*) FROM business_profiles WHERE last_hypothesis_run IS NOT NULL"
                )

            return {
                'total_profiles': total,
                'active_profiles': active,
                'avg_completeness': round(float(avg_completeness or 0), 2),
                'by_industry': [dict(row) for row in by_industry],
                'profiles_with_runs': with_runs
            }

        except Exception as e:
            logger.error(f"Error getting profile stats: {e}")
            raise
