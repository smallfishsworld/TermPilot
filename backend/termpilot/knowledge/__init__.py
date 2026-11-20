"""Search over the student's own documents.

``index`` ingests files into the search cluster and retrieves passages,
``extract`` pulls plain text out of a single attachment, and ``providers``
wraps the embedding and rerank services. The adapted parsing engine lives in
``engine`` and is imported lazily because it loads large models.
"""

from __future__ import annotations

from termpilot.settings import Settings


def configure(settings: Settings) -> None:
    """Point the engine and the providers at the configured services."""
    from termpilot.knowledge import providers
    from termpilot.knowledge.engine import runtime

    runtime.configure(
        runtime.EngineConfig(
            models_dir=settings.models_dir,
            search_url=settings.search_url,
            search_username=settings.search_username,
            search_password=settings.search_password.get_secret_value() if settings.search_password else None,
            index_prefix=settings.search_index_prefix,
        )
    )
    providers.configure(
        providers.ProviderConfig(
            embedding_base_url=settings.embedding_base_url,
            embedding_api_key=settings.embedding_api_key.get_secret_value() if settings.embedding_api_key else None,
            embedding_model=settings.embedding_model,
            embedding_dimensions=settings.embedding_dimensions,
            batch_size=settings.embedding_batch_size,
            rerank_url=settings.rerank_url,
            rerank_api_key=settings.rerank_api_key.get_secret_value() if settings.rerank_api_key else None,
            rerank_model=settings.rerank_model,
        )
    )
