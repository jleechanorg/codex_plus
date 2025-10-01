"""
Cerebras Middleware - Transforms Codex requests to Cerebras format

This middleware detects when the upstream URL is Cerebras API and applies
the necessary transformations to convert Codex request format to OpenAI-compatible
Cerebras format.
"""

import logging
from typing import Dict, Any, Tuple
from .cerebras_transformer import CodexToCerebrasTransformer

logger = logging.getLogger("codex_plus.cerebras_middleware")


class CerebrasMiddleware:
    """Middleware for transforming Codex requests to Cerebras format"""

    def __init__(self):
        self.transformer = CodexToCerebrasTransformer()
        logger.info("🔧 CerebrasMiddleware initialized")

    def is_cerebras_upstream(self, upstream_url: str) -> bool:
        """Check if upstream URL is Cerebras API"""
        return "api.cerebras.ai" in upstream_url

    def process_request(
        self,
        request_body: Dict[str, Any],
        upstream_url: str,
        original_endpoint: str
    ) -> Tuple[Dict[str, Any], str]:
        """
        Process request and apply transformation if needed.

        Args:
            request_body: Original Codex request body
            upstream_url: Upstream API URL
            original_endpoint: Original endpoint (e.g., "/responses")

        Returns:
            Tuple of (transformed_body, endpoint_to_use)
        """
        try:
            if not self.is_cerebras_upstream(upstream_url):
                logger.debug("📍 Not a Cerebras upstream, skipping transformation")
                return request_body, original_endpoint

            logger.info("🔄 Cerebras upstream detected - applying transformation")
            logger.debug(f"📥 Original request model: {request_body.get('model', 'unknown')}")

            # Transform request to Cerebras format
            transformed_body = self.transformer.transform_request(request_body)

            # Change endpoint to Cerebras chat completions
            # Since upstream_url already contains /v1, we only need the relative path
            cerebras_endpoint = "chat/completions"

            logger.info(f"✅ Request transformed for Cerebras")
            logger.debug(f"📤 Transformed model: {transformed_body.get('model', 'unknown')}")
            logger.debug(f"📍 Endpoint changed: {original_endpoint} → {cerebras_endpoint}")
            logger.debug(f"💬 Messages count: {len(transformed_body.get('messages', []))}")

            if "tools" in transformed_body:
                logger.debug(f"🔧 Tools count: {len(transformed_body['tools'])}")

            return transformed_body, cerebras_endpoint

        except Exception as e:
            logger.error(f"❌ Error during Cerebras transformation: {e}")
            logger.warning("⚠️  Falling back to original request (transformation failed)")
            return request_body, original_endpoint
