"""Search index manager for the Swagger MCP Server.

This module provides the SearchIndexManager class which handles:
- Creating and maintaining Whoosh search indexes
- Processing database data into searchable documents
- Batch indexing operations with progress tracking
- Incremental index updates and optimization
"""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from whoosh import index
from whoosh.index import Index
from whoosh.qparser import MultifieldParser, QueryParser
from whoosh.query import Query
from whoosh.writing import IndexWriter

from ..config.settings import SearchConfig
from ..storage.repositories.endpoint_repository import EndpointRepository
from ..storage.repositories.metadata_repository import MetadataRepository
from ..storage.repositories.schema_repository import SchemaRepository
from .endpoint_indexing import EndpointDocumentProcessor
from .index_schema import (
    convert_endpoint_document_to_index_fields,
    create_search_schema,
    validate_schema_fields,
)


class SearchIndexManager:
    """Manages search index creation, updates, and optimization."""

    def __init__(
        self,
        index_dir: str,
        endpoint_repo: EndpointRepository,
        schema_repo: SchemaRepository,
        metadata_repo: MetadataRepository,
        config: SearchConfig,
    ):
        """Initialize the search index manager.

        Args:
            index_dir: Directory to store search index files
            endpoint_repo: Repository for endpoint data
            schema_repo: Repository for schema data
            metadata_repo: Repository for metadata
            config: Search configuration settings
        """
        self.index_dir = Path(index_dir)
        self.endpoint_repo = endpoint_repo
        self.schema_repo = schema_repo
        self.metadata_repo = metadata_repo
        self.config = config
        self._index: Optional[Index] = None

        # Initialize the comprehensive endpoint document processor
        self.document_processor = EndpointDocumentProcessor()

        # Ensure index directory exists
        self.index_dir.mkdir(parents=True, exist_ok=True)

    @property
    def index(self) -> Index:
        """Get or create the search index.

        Returns:
            Index: Whoosh index instance

        Raises:
            RuntimeError: If index cannot be opened or created
        """
        if self._index is None:
            try:
                if index.exists_in(str(self.index_dir)):
                    self._index = index.open_dir(str(self.index_dir))
                else:
                    schema = create_search_schema()
                    self._index = index.create_in(str(self.index_dir), schema)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to open/create search index: {e}"
                ) from e

        return self._index

    async def create_index_from_database(
        self,
        batch_size: Optional[int] = None,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[int, float]:
        """Create search index from normalized database data.

        Args:
            batch_size: Number of documents to process per batch
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple[int, float]: (documents_indexed, elapsed_time)

        Raises:
            RuntimeError: If index creation fails
        """
        start_time = time.time()
        batch_size = batch_size or self.config.indexing.batch_size
        total_indexed = 0

        try:
            # Clear existing index
            await self._clear_index()

            # Get total count for progress tracking
            total_endpoints = await self.endpoint_repo.count_all()

            if progress_callback:
                await progress_callback(
                    0, total_endpoints, "Starting index creation"
                )

            # Process endpoints in batches
            async for batch_num, documents in self._process_endpoints_in_batches(
                batch_size
            ):
                indexed_count = await self._index_document_batch(documents)
                total_indexed += indexed_count

                if progress_callback:
                    await progress_callback(
                        total_indexed,
                        total_endpoints,
                        f"Indexed batch {batch_num + 1}, {total_indexed} documents total",
                    )

            # Optimize index for search performance
            await self._optimize_index()

            elapsed_time = time.time() - start_time

            if progress_callback:
                await progress_callback(
                    total_indexed,
                    total_endpoints,
                    f"Index creation completed in {elapsed_time:.2f}s",
                )

            return total_indexed, elapsed_time

        except Exception as e:
            raise RuntimeError(f"Index creation failed: {e}") from e

    async def update_endpoint_document(self, endpoint_id: str) -> bool:
        """Update a single endpoint document in the index.

        Args:
            endpoint_id: ID of endpoint to update

        Returns:
            bool: True if document was updated successfully

        Raises:
            RuntimeError: If update operation fails
        """
        try:
            # Get updated endpoint data
            endpoint_data = await self.endpoint_repo.get_by_id(endpoint_id)
            if not endpoint_data:
                # Endpoint deleted, remove from index
                return await self._remove_document(endpoint_id)

            # Create search document
            document = await self._create_search_document(endpoint_data)
            if not validate_schema_fields(document):
                return False

            # Update index
            with self.index.writer() as writer:
                writer.update_document(**document)

            return True

        except Exception as e:
            raise RuntimeError(
                f"Failed to update endpoint {endpoint_id}: {e}"
            ) from e

    async def remove_endpoint_document(self, endpoint_id: str) -> bool:
        """Remove an endpoint document from the index.

        Args:
            endpoint_id: ID of endpoint to remove

        Returns:
            bool: True if document was removed successfully
        """
        return await self._remove_document(endpoint_id)

    async def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the current search index.

        Returns:
            Dict[str, Any]: Index statistics including document count, size, etc.
        """
        try:
            reader = self.index.reader()
            index_size = sum(
                os.path.getsize(os.path.join(self.index_dir, f))
                for f in os.listdir(self.index_dir)
                if os.path.isfile(os.path.join(self.index_dir, f))
            )

            return {
                "document_count": reader.doc_count(),
                "field_count": len(reader.field_names()),
                "index_size_bytes": index_size,
                "index_size_mb": round(index_size / (1024 * 1024), 2),
                "last_modified": max(
                    os.path.getmtime(os.path.join(self.index_dir, f))
                    for f in os.listdir(self.index_dir)
                    if os.path.isfile(os.path.join(self.index_dir, f))
                ),
                "index_version": reader.schema_version()
                if hasattr(reader, "schema_version")
                else 1,
            }

        except Exception as e:
            return {"error": str(e)}

    async def validate_index_integrity(self) -> Dict[str, Any]:
        """Validate the integrity and completeness of the search index.

        Returns:
            Dict[str, Any]: Validation results with any issues found
        """
        issues = []
        stats = {"validation_passed": True}

        try:
            # Check if index exists and is readable
            if not index.exists_in(str(self.index_dir)):
                issues.append("Index directory does not exist")
                stats["validation_passed"] = False
                return {"issues": issues, **stats}

            reader = self.index.reader()

            # Check document count consistency
            db_count = await self.endpoint_repo.count_all()
            index_count = reader.doc_count()

            if db_count != index_count:
                issues.append(
                    f"Document count mismatch: DB has {db_count}, "
                    f"index has {index_count}"
                )
                stats["validation_passed"] = False

            # Check for required fields
            field_names = set(reader.field_names())
            required_fields = {"endpoint_id", "endpoint_path", "http_method"}
            missing_fields = required_fields - field_names

            if missing_fields:
                issues.append(f"Missing required fields: {missing_fields}")
                stats["validation_passed"] = False

            stats.update(
                {
                    "database_document_count": db_count,
                    "index_document_count": index_count,
                    "field_count": len(field_names),
                    "issues_found": len(issues),
                }
            )

        except Exception as e:
            issues.append(f"Validation error: {e}")
            stats["validation_passed"] = False

        return {"issues": issues, **stats}

    # Private methods

    async def _clear_index(self) -> None:
        """Clear all documents from the index."""
        with self.index.writer() as writer:
            writer.commit(mergetype=index.CLEAR)

    async def _process_endpoints_in_batches(
        self, batch_size: int
    ) -> AsyncGenerator[Tuple[int, List[Dict[str, Any]]], None]:
        """Process endpoint data in batches for indexing.

        Args:
            batch_size: Number of endpoints per batch

        Yields:
            Tuple[int, List[Dict]]: (batch_number, list_of_documents)
        """
        offset = 0
        batch_num = 0

        while True:
            endpoints = await self.endpoint_repo.get_all(
                limit=batch_size, offset=offset
            )

            if not endpoints:
                break

            documents = []
            for endpoint in endpoints:
                try:
                    document = await self._create_search_document(endpoint)
                    if validate_schema_fields(document):
                        documents.append(document)
                except Exception as e:
                    # Log error but continue processing
                    print(
                        f"Error processing endpoint {endpoint.get('id', 'unknown')}: {e}"
                    )

            if documents:
                yield batch_num, documents

            offset += batch_size
            batch_num += 1

    async def _index_document_batch(
        self, documents: List[Dict[str, Any]]
    ) -> int:
        """Index a batch of documents.

        Args:
            documents: List of search documents to index

        Returns:
            int: Number of documents successfully indexed
        """
        indexed_count = 0

        with self.index.writer() as writer:
            for document in documents:
                try:
                    writer.add_document(**document)
                    indexed_count += 1
                except Exception as e:
                    # Log error but continue processing
                    endpoint_id = document.get("endpoint_id", "unknown")
                    print(f"Error indexing document {endpoint_id}: {e}")

        return indexed_count

    async def _create_search_document(
        self, endpoint_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert database endpoint data to comprehensive search document.

        Uses the new EndpointDocumentProcessor to create rich, searchable documents
        that capture complete endpoint semantic context as specified in Story 3.2.

        Args:
            endpoint_data: Raw endpoint data from database

        Returns:
            Dict[str, Any]: Comprehensive search document ready for indexing

        Raises:
            ValueError: If endpoint data is invalid
            RuntimeError: If document creation fails
        """
        try:
            # Create comprehensive endpoint document using the new processor
            endpoint_doc = (
                await self.document_processor.create_endpoint_document(
                    endpoint_data
                )
            )

            # Convert to index-ready format
            index_document = convert_endpoint_document_to_index_fields(
                endpoint_doc
            )

            return index_document

        except ValueError as e:
            # Re-raise validation errors
            raise e
        except Exception as e:
            # Wrap other errors in RuntimeError for consistent error handling
            endpoint_id = endpoint_data.get("id", "unknown")
            raise RuntimeError(
                f"Failed to create search document for endpoint {endpoint_id}: {e}"
            ) from e

    async def _optimize_index(self) -> None:
        """Optimize the search index for better performance."""
        with self.index.writer() as writer:
            writer.optimize = True

    async def _remove_document(self, endpoint_id: str) -> bool:
        """Remove a document from the index by endpoint ID.

        Args:
            endpoint_id: ID of document to remove

        Returns:
            bool: True if document was removed successfully
        """
        try:
            with self.index.writer() as writer:
                deleted_count = writer.delete_by_term(
                    "endpoint_id", endpoint_id
                )
                return deleted_count > 0
        except Exception:
            return False

    def close(self) -> None:
        """Close the search index and release resources."""
        if self._index is not None:
            self._index.close()
            self._index = None
