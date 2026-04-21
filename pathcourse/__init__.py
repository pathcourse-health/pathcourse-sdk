"""PathCourse SDK -- Official Python client for the PathCourse AI gateway."""

from pathcourse.client import PathCourseClient
from pathcourse.provisioning import claim_key
from pathcourse.models import (
    PCH_FAST,
    PCH_PRO,
    PCH_CODER,
    PCH_IMAGE,
    PCH_AUDIO,
    PCH_AUDIO_PREMIUM,
    PCH_DOCUMENTS,
    PCH_TALK,
    CLAUDE_HAIKU,
    CLAUDE_SONNET,
    PCH_EMBED,
    PCH_TRANSCRIBE,
    PCH_TRANSLATE,
    PCH_EXTRACT,
    PCH_RERANK,
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
)
from pathcourse.exceptions import (
    PathCourseError,
    AuthenticationError,
    RateLimitError,
    InsufficientBalanceError,
    ForbiddenError,
    ModelNotInTierError,
    NotFoundError,
    ModelNotFoundError,
    InferenceUnavailableError,
    GatewayError,
)

__version__ = "0.3.3"
__all__ = [
    "PathCourseClient",
    "claim_key",
    "PCH_FAST", "PCH_PRO", "PCH_CODER",
    "PCH_IMAGE", "PCH_AUDIO", "PCH_AUDIO_PREMIUM", "PCH_DOCUMENTS", "PCH_TALK",
    "CLAUDE_HAIKU", "CLAUDE_SONNET",
    "PCH_EMBED", "PCH_TRANSCRIBE", "PCH_TRANSLATE", "PCH_EXTRACT", "PCH_RERANK",
    "ChatMessage", "ChatResponse", "EmbeddingResponse",
    "PathCourseError", "AuthenticationError", "RateLimitError",
    "InsufficientBalanceError",
    "ForbiddenError", "ModelNotInTierError",
    "NotFoundError", "ModelNotFoundError",
    "InferenceUnavailableError", "GatewayError",
]
