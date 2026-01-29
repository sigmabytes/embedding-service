"""Amazon Bedrock embedding strategy (§6.1)."""

import json

import boto3
import botocore

from app.config.embedding.models import EmbeddingConfig
from app.config.settings import get_settings
from app.services.embedder.base import BaseEmbeddingStrategy


class BedrockEmbeddingStrategy(BaseEmbeddingStrategy):
    """
    Amazon Bedrock embeddings. Supports Titan (e.g. amazon.titan-embed-text-v1,
    amazon.titan-embed-text-v2:0) and other Bedrock embedding models.
    Uses IAM credentials (profile/env/instance). Region from config.region or
    settings.aws_region or AWS_REGION.
    """

    @property
    def strategy_name(self) -> str:
        return "bedrock"

    def embed(self, texts: list[str], config: EmbeddingConfig) -> list[list[float]]:
        if not texts:
            return []
        region = config.region or get_settings().aws_region or None
        client = boto3.client("bedrock-runtime", region_name=region)
        model_id = config.model
        results: list[list[float]] = []
        for text in texts:
            body = json.dumps({"inputText": text})
            try:
                response = client.invoke_model(
                    modelId=model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=body,
                )
            except botocore.exceptions.ClientError as e:
                raise ValueError(f"Bedrock invoke_model failed: {e}") from e
            payload = json.loads(response["body"].read().decode("utf-8"))
            emb = payload.get("embedding")
            if emb is None:
                # Titan V2 can return embeddingsByType
                by_type = payload.get("embeddingsByType") or {}
                emb = by_type.get("float") or list(by_type.values())[0] if by_type else None
            if not emb:
                raise ValueError("Bedrock response contained no embedding")
            results.append(emb if isinstance(emb[0], float) else [float(x) for x in emb])
        return results
