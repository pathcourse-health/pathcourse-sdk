"""Model name constants and data classes for the PathCourse SDK."""

from dataclasses import dataclass
from typing import Optional

# ── Owned GPU models (DeepInfra) ────────────────────────────────────────────
PCH_FAST = "pch-fast"              # Qwen3-14B — $0.44/M tokens — fast reasoning
PCH_PRO = "pch-pro"                # Qwen3-235B — $1.96/M tokens — deep reasoning
PCH_CODER = "pch-coder"            # Qwen3-Coder-480B — $3.50/M tokens — code generation

# ── Multimodal models (DeepInfra) ───────────────────────────────────────────
PCH_IMAGE = "pch-image"            # $0.028/image — text-to-image generation
PCH_AUDIO = "pch-audio"            # $1.85/M chars — TTS standard
PCH_AUDIO_PREMIUM = "pch-audio-premium"  # $37.00/M chars — TTS premium
PCH_DOCUMENTS = "pch-documents"    # $0.26/$1.48 per M tokens in/out — document parsing
PCH_TALK = "pch-talk"              # $0.001/min — voice conversation

# ── Third-party models ──────────────────────────────────────────────────────
CLAUDE_HAIKU = "claude-haiku"      # Anthropic Claude Haiku — Silver+ tier
CLAUDE_SONNET = "claude-sonnet"    # Anthropic Claude Sonnet — Gold tier

# ── CPU-native models ───────────────────────────────────────────────────────
PCH_EMBED = "pch-embed"            # $0.015/M tokens — text embeddings
PCH_TRANSCRIBE = "pch-transcribe"  # $0.0008/min — speech-to-text (109 languages)
PCH_TRANSLATE = "pch-translate"    # $0.08/M chars — translation
PCH_EXTRACT = "pch-extract"        # $0.012/M tokens — zero-shot entity extraction
PCH_RERANK = "pch-rerank"          # $0.025/M tokens — retrieval reranking


@dataclass
class ChatMessage:
    """A single message in a chat conversation."""
    role: str   # "user", "assistant", or "system"
    content: str


@dataclass
class ChatResponse:
    """Response from a PathCourse chat completion."""
    id: str
    model: str
    content: str
    usage: dict
    provider: Optional[str] = None

    @property
    def text(self) -> str:
        """Convenience accessor for response text."""
        return self.content


@dataclass
class EmbeddingResponse:
    """Response from a PathCourse embedding request."""
    embeddings: list
    model: str
    usage: dict
