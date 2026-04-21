"""PathCourse API client."""

import os
import httpx
from typing import List, Optional, Union

from pathcourse.models import ChatMessage, ChatResponse, EmbeddingResponse, PCH_FAST, PCH_EMBED
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

DEFAULT_BASE_URL = "https://gateway.pathcoursehealth.com"
DEFAULT_TIMEOUT = 60.0


class PathCourseClient:
    """
    Synchronous client for the PathCourse AI gateway.

    Usage:
        from pathcourse import PathCourseClient, PCH_FAST

        client = PathCourseClient(api_key="your-key")
        response = client.chat(
            model=PCH_FAST,
            messages=[{"role": "user", "content": "Hello"}]
        )
        print(response.text)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.api_key = api_key or os.environ.get("PCH_API_KEY")
        if not self.api_key:
            raise AuthenticationError(
                "No API key provided. Pass api_key= or set PCH_API_KEY env var."
            )
        self.base_url = (base_url or os.environ.get("PCH_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )

        # ── SOPHIA capability namespaces ────────────────────────────────────
        # These are thin wrappers on top of self._client so developers get
        # autocomplete + documentation on related endpoints.
        self.memory     = _MemoryAPI(self)
        self.reputation = _ReputationAPI(self)
        self.obs        = _ObsAPI(self)
        self.routing    = _RoutingAPI(self)

    def chat(
        self,
        messages: List[Union[ChatMessage, dict]],
        model: str = PCH_FAST,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> ChatResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of ChatMessage objects or dicts with 'role' and 'content'.
            model: Model name constant (e.g. PCH_FAST, PCH_PRO, PCH_CODER).
            temperature: Sampling temperature 0.0-1.0.
            max_tokens: Maximum tokens in the response.

        Returns:
            ChatResponse with .text convenience accessor.
        """
        normalized = []
        for m in messages:
            if isinstance(m, ChatMessage):
                normalized.append({"role": m.role, "content": m.content})
            else:
                normalized.append(m)

        payload = {
            "model": model,
            "messages": normalized,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        try:
            resp = self._client.post("/v1/chat/completions", json=payload)
        except httpx.TimeoutException:
            raise PathCourseError("Request timed out. Try increasing timeout=.")
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")

        self._raise_for_status(resp)
        data = resp.json()

        choice = data["choices"][0]
        return ChatResponse(
            id=data.get("id", ""),
            model=data.get("model", model),
            content=choice["message"]["content"],
            usage=data.get("usage", {}),
        )

    def embed(
        self,
        input: Union[str, List[str]],
        model: str = PCH_EMBED,
    ) -> EmbeddingResponse:
        """
        Generate text embeddings.

        Args:
            input: A string or list of strings to embed.
            model: Embedding model (default: PCH_EMBED).

        Returns:
            EmbeddingResponse with .embeddings list.
        """
        if isinstance(input, str):
            input = [input]

        payload = {"model": model, "input": input}

        try:
            resp = self._client.post("/v1/embeddings", json=payload)
        except httpx.TimeoutException:
            raise PathCourseError("Embedding request timed out.")
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")

        self._raise_for_status(resp)
        data = resp.json()

        embeddings = [d["embedding"] for d in data.get("data", [])]
        return EmbeddingResponse(
            embeddings=embeddings,
            model=data.get("model", model),
            usage=data.get("usage", {}),
        )

    def translate(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> dict:
        """
        Translate text using pch-translate.

        Args:
            text: Text to translate.
            target_language: ISO language code (e.g. 'en', 'fr', 'de').
            source_language: Optional source language (auto-detected if omitted).

        Returns:
            dict with translated_text, source_language, target_language, usage.
        """
        payload = {
            "model": "pch-translate",
            "text": text,
            "target_language": target_language,
        }
        if source_language:
            payload["source_language"] = source_language

        try:
            resp = self._client.post("/v1/translate", json=payload)
        except httpx.TimeoutException:
            raise PathCourseError("Translation request timed out.")
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")

        self._raise_for_status(resp)
        return resp.json()

    def extract(
        self,
        text: str,
        entity_types: List[str],
    ) -> dict:
        """
        Extract named entities using pch-extract (zero-shot NER).

        Args:
            text: Text to extract entities from.
            entity_types: List of entity type labels (e.g. ['PERSON', 'ORG', 'DATE']).

        Returns:
            dict with entities list and usage.
        """
        payload = {
            "model": "pch-extract",
            "text": text,
            "entity_types": entity_types,
        }

        try:
            resp = self._client.post("/v1/extract", json=payload)
        except httpx.TimeoutException:
            raise PathCourseError("Extraction request timed out.")
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")

        self._raise_for_status(resp)
        return resp.json()

    # ── Auth health check ───────────────────────────────────────────────────
    def verify_key(self) -> bool:
        """
        Verify the API key is valid and the agent service is active.

        Cheap check — hits /v1/balance which does a single Redis GET and no
        billing event. Use this on startup to fail fast on bad credentials.

        Returns:
            True when the key is valid and the agent is active.

        Raises:
            AuthenticationError: 401 — key not recognized.
            PathCourseError:     403 — agent service suspended, or other error.
        """
        try:
            resp = self._client.get("/v1/balance")
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")
        if resp.status_code == 200:
            return True
        self._raise_for_status(resp)
        return False

    def ping(self) -> bool:
        """Alias for verify_key()."""
        return self.verify_key()

    # ── Provisioning (use the module-level pathcourse.claim_key() instead;
    #    this instance method exists for backward compatibility only) ───────
    def claim_key(self, tx_hash: str, wallet: str, poll: bool = True) -> dict:
        """
        Retrieve your API key after depositing USDC to the PCH treasury wallet.

        Polls GET /v1/keys/claim until the key is ready. With poll=True (default)
        this method blocks through the 202 provisioning window; with poll=False
        it returns whatever the first response gives.

        Args:
            tx_hash: The Base L2 transaction hash of the USDC deposit.
            wallet:  The wallet address the USDC was sent from.
            poll:    If True, retry on 202 Accepted until 200 or attempts exhaust.

        Returns:
            dict with api_key, tier, balance_usdc, agent_id.
        """
        import time
        max_attempts = 10 if poll else 1
        last_data = None
        for attempt in range(max_attempts):
            try:
                resp = self._client.get(
                    "/v1/keys/claim",
                    params={"tx_hash": tx_hash, "wallet": wallet},
                )
            except httpx.RequestError as e:
                raise GatewayError(f"Connection error: {e}")

            if resp.status_code == 200:
                return resp.json()

            data = resp.json() if resp.text else {}
            last_data = data

            if resp.status_code == 202 and poll:
                time.sleep(data.get("retry_after_seconds", 15))
                continue
            if resp.status_code == 404 and data.get("error") == "payment_not_found" and poll and attempt < 3:
                time.sleep(30)
                continue
            if resp.status_code >= 400:
                self._raise_for_status(resp)

            if not poll:
                return data

        raise PathCourseError(
            "API key provisioning timed out. "
            "Verify the transaction has confirmed on Base and retry.",
            status_code=504,
            response=last_data,
        )

    def get_balance(self) -> dict:
        """
        Get your current USDC balance on the PathCourse platform.

        Returns:
            dict with balance_usdc, tier, low_balance (bool), topup instructions.
        """
        return self._get_json("/v1/balance")

    # ── Discovery (public, no auth required) ────────────────────────────────
    def get_models(self, scope: Optional[str] = None) -> dict:
        """
        List available models (OpenAI-compatible shape).

        Args:
            scope: Pass ``"my_tier"`` to get only the models your tier can call.
                   Omit (default) for the full public catalog.
        """
        params = {"scope": scope} if scope else None
        return self._get_json("/v1/models", params=params)

    def me(self) -> dict:
        """
        One-call self-profile. Returns identity, certification, wallet,
        balance, Path Score, accessible models, and last-24h activity —
        everything a headless agent needs to know about itself in one call.
        """
        return self._get_json("/v1/me")

    def suggest_model(
        self,
        messages: List[Union[ChatMessage, dict]],
        max_tokens: Optional[int] = None,
        model_hint: Optional[str] = None,
    ) -> dict:
        """
        Ask the gateway which model it would route this prompt to.

        Free, deterministic, no LLM or inference call. Bronze/Silver agents
        can use this to get the same answer the Gold auto-router produces.

        Returns a dict with keys like ``recommended_model``, ``complexity``,
        ``token_count``, ``alternatives``.
        """
        normalized = []
        for m in messages:
            if isinstance(m, ChatMessage):
                normalized.append({"role": m.role, "content": m.content})
            else:
                normalized.append(m)
        body = {"messages": normalized}
        if max_tokens is not None: body["max_tokens"] = max_tokens
        if model_hint:             body["model"] = model_hint
        return self._post_json("/v1/routing/suggest", body)

    def get_pricing(self) -> dict:
        """Fetch the current machine-readable rate sheet."""
        return self._get_json("/v1/pricing")

    # ── Usage & accounting ──────────────────────────────────────────────────
    def get_usage(
        self,
        limit: int = 50,
        model: Optional[str] = None,
        since: Optional[str] = None,
    ) -> dict:
        """
        Fetch your spend history from the PCH ledger.

        Args:
            limit: Max records to return (1..500).
            model: Optional model filter (e.g. 'pch-fast').
            since: Optional ISO-8601 cutoff timestamp.
        """
        params = {"limit": limit}
        if model: params["model"] = model
        if since: params["since"] = since
        return self._get_json("/v1/usage", params=params)

    def get_runway(self) -> dict:
        """Balance-runway forecast: days of service remaining at current burn."""
        return self._get_json("/v1/obs/runway")

    # ── Spend cap ───────────────────────────────────────────────────────────
    def set_budget(self, daily_limit_usdc: float) -> dict:
        """
        Set a daily USDC spend cap, enforced server-side. Pass 0 to remove.
        Resets at midnight UTC.
        """
        return self._post_json("/v1/budget", {"daily_limit_usdc": daily_limit_usdc})

    def get_budget(self) -> dict:
        """Read the current daily spend cap and today's running total."""
        return self._get_json("/v1/budget")

    # ── Webhook alerts ──────────────────────────────────────────────────────
    def register_webhook(self, url: str, threshold_usdc: float = 25.0) -> dict:
        """
        Register a URL to receive balance_low / balance_floor events when your
        balance crosses the threshold.
        """
        return self._post_json(
            "/v1/webhook",
            {"url": url, "threshold_usdc": threshold_usdc},
        )

    def get_webhook(self) -> dict:
        """Read the currently-registered webhook config."""
        return self._get_json("/v1/webhook")

    def delete_webhook(self) -> dict:
        """Remove the registered webhook."""
        try:
            resp = self._client.delete("/v1/webhook")
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")
        self._raise_for_status(resp)
        return resp.json()

    # ── Internal helpers ────────────────────────────────────────────────────
    def _get_json(self, path: str, params: Optional[dict] = None) -> dict:
        try:
            resp = self._client.get(path, params=params or {})
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")
        self._raise_for_status(resp)
        return resp.json()

    def _post_json(self, path: str, body: dict) -> dict:
        try:
            resp = self._client.post(path, json=body)
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")
        self._raise_for_status(resp)
        return resp.json()

    def _put_json(self, path: str, body: dict) -> dict:
        try:
            resp = self._client.put(path, json=body)
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")
        self._raise_for_status(resp)
        return resp.json()

    def _delete_json(self, path: str, body: Optional[dict] = None) -> dict:
        try:
            if body is not None:
                resp = self._client.request("DELETE", path, json=body)
            else:
                resp = self._client.delete(path)
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")
        self._raise_for_status(resp)
        return resp.json()

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: Optional[int] = None,
    ) -> dict:
        """
        Rerank documents by relevance to a query using pch-rerank.

        Args:
            query: The search query.
            documents: List of document strings to rank.
            top_n: Optional number of top results to return.

        Returns:
            dict with ranked results list and usage.
        """
        payload = {
            "model": "pch-rerank",
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n

        try:
            resp = self._client.post("/v1/rerank", json=payload)
        except httpx.TimeoutException:
            raise PathCourseError("Rerank request timed out.")
        except httpx.RequestError as e:
            raise GatewayError(f"Connection error: {e}")

        self._raise_for_status(resp)
        return resp.json()

    def _raise_for_status(self, response: httpx.Response):
        if response.status_code < 400:
            return
        try:
            body = response.json() if response.text else {}
        except Exception:
            body = {}
        server_msg = (
            body.get("message")
            or body.get("detail")
            or body.get("error")
            or response.text
            or f"HTTP {response.status_code}"
        )
        error_code = body.get("error") if isinstance(body.get("error"), str) else None

        if response.status_code == 401:
            raise AuthenticationError(server_msg or "Invalid API key.", status_code=401, response=body)
        if response.status_code == 402:
            raise InsufficientBalanceError(server_msg, status_code=402, response=body)
        if response.status_code == 403:
            if error_code == "model_not_in_tier":
                raise ModelNotInTierError(server_msg, status_code=403, response=body)
            raise ForbiddenError(server_msg, status_code=403, response=body)
        if response.status_code == 404:
            if error_code in ("invalid_model", "model_not_found", "unknown_model"):
                raise ModelNotFoundError(server_msg, status_code=404, response=body)
            raise NotFoundError(server_msg, status_code=404, response=body)
        if response.status_code == 429:
            raise RateLimitError(server_msg or "Rate limit exceeded.", status_code=429, response=body)
        if response.status_code == 503:
            raise InferenceUnavailableError(server_msg, status_code=503, response=body)
        if response.status_code >= 500:
            raise GatewayError(
                f"Gateway error {response.status_code}: {server_msg}",
                status_code=response.status_code, response=body,
            )
        raise PathCourseError(
            f"Request error {response.status_code}: {server_msg}",
            status_code=response.status_code, response=body,
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ═══════════════════════════════════════════════════════════════════════════
# SOPHIA capability namespaces
# ═══════════════════════════════════════════════════════════════════════════
#
# These classes are instantiated by PathCourseClient and exposed as
# client.memory, client.reputation, client.obs, client.routing.
# They wrap the underlying HTTP helpers and give users autocompletion +
# docstrings for related endpoints.
# ═══════════════════════════════════════════════════════════════════════════


class _MemoryAPI:
    """client.memory.* — persistent embedding-based memory via Qdrant + Postgres.

    Costs: $0.001 text store, $0.003 multimodal, $0.002 retrieve, $0.005 summarize + inference.
    """

    def __init__(self, client: "PathCourseClient"):
        self._c = client

    def store(
        self,
        content: str,
        memory_type: str,
        content_type: str = "text",
        tags: Optional[List[str]] = None,
        ttl_days: Optional[int] = None,
        namespace: str = "private",
        importance: float = 0.5,
    ) -> dict:
        """
        Store a memory entry. Embeds and upserts to Qdrant + Postgres atomically.

        memory_type:  episodic | semantic | procedural | working | shared | multimodal
        content_type: text | image | audio | document | voice_transcript
        """
        body = {
            "content": content,
            "memory_type": memory_type,
            "content_type": content_type,
            "namespace": namespace,
            "importance": importance,
        }
        if tags is not None:     body["tags"] = tags
        if ttl_days is not None: body["ttl_days"] = ttl_days
        return self._c._post_json("/v1/memory/store", body)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
        min_score: float = 0.60,
        tags: Optional[List[str]] = None,
        namespace: str = "private",
    ) -> dict:
        """Semantic search over this agent's memories (or a shared namespace)."""
        body = {"query": query, "top_k": top_k, "min_score": min_score, "namespace": namespace}
        if memory_type: body["memory_type"] = memory_type
        if tags:        body["tags"] = tags
        return self._c._post_json("/v1/memory/retrieve", body)

    def update(self, memory_id: str, content: str) -> dict:
        """Re-embed and replace a stored memory entry."""
        return self._c._put_json(f"/v1/memory/update/{memory_id}", {"content": content})

    def forget(self, memory_id: str) -> dict:
        """Delete a memory entry."""
        return self._c._delete_json(f"/v1/memory/forget/{memory_id}")

    def summarize(self, memory_type: Optional[str] = None, namespace: str = "private") -> dict:
        """Compress memories into a semantic summary via pch-pro."""
        body = {"namespace": namespace}
        if memory_type: body["memory_type"] = memory_type
        return self._c._post_json("/v1/memory/summarize", body)

    def create_namespace(self, name: str, max_agents: int = 5) -> dict:
        return self._c._post_json("/v1/memory/namespace/create", {"name": name, "max_agents": max_agents})

    def join_namespace(self, name: str) -> dict:
        return self._c._post_json("/v1/memory/namespace/join", {"name": name})

    def leave_namespace(self, name: str) -> dict:
        return self._c._delete_json("/v1/memory/namespace/leave", {"name": name})


class _ReputationAPI:
    """client.reputation.* — public Path Score + ERC-8004 agent identity."""

    def __init__(self, client: "PathCourseClient"):
        self._c = client

    def score(self, agent_id: str) -> dict:
        """Public Path Score lookup. Free."""
        return self._c._get_json(f"/v1/reputation/score/{agent_id}")

    def check(self, agent_id: str) -> dict:
        """Counterparty trust check — $0.001/query. Returns recommendation + settlement history."""
        return self._c._get_json(f"/v1/reputation/check/{agent_id}")

    def history(self, agent_id: str) -> dict:
        """12-month Path Score trajectory. Free."""
        return self._c._get_json(f"/v1/reputation/history/{agent_id}")

    def erc8004(self, agent_id: str) -> dict:
        """Public ERC-8004 agent identity document. Free."""
        return self._c._get_json(f"/v1/agents/{agent_id}/erc8004.json")


class _ObsAPI:
    """client.obs.* — trace-based observability. Traces, spans, custom events, anomalies."""

    def __init__(self, client: "PathCourseClient"):
        self._c = client

    def trace_start(self, trace_label: Optional[str] = None) -> dict:
        body = {}
        if trace_label: body["trace_label"] = trace_label
        return self._c._post_json("/v1/obs/trace/start", body)

    def trace_end(self, trace_id: str) -> dict:
        return self._c._post_json("/v1/obs/trace/end", {"trace_id": trace_id})

    def get_trace(self, trace_id: str) -> dict:
        return self._c._get_json(f"/v1/obs/trace/{trace_id}")

    def list_traces(self, limit: int = 20, offset: int = 0, status: Optional[str] = None) -> dict:
        params = {"limit": limit, "offset": offset}
        if status: params["status"] = status
        return self._c._get_json("/v1/obs/traces", params=params)

    def get_span(self, span_id: str) -> dict:
        return self._c._get_json(f"/v1/obs/span/{span_id}")

    def log_event(self, trace_id: str, event_type: str, event_payload: Optional[dict] = None) -> dict:
        """Custom structured event — $0.0001/event, Silver+ tier required."""
        body = {"trace_id": trace_id, "event_type": event_type}
        if event_payload is not None: body["event_payload"] = event_payload
        return self._c._post_json("/v1/obs/log/event", body)

    def anomalies(self, days: int = 7) -> dict:
        return self._c._get_json("/v1/obs/anomalies", params={"days": days})

    def analytics(self, days: int = 30) -> dict:
        return self._c._get_json("/v1/obs/analytics", params={"days": days})

    def cost_attribution(self, days: int = 30, trace_id: Optional[str] = None) -> dict:
        params = {"days": days}
        if trace_id: params["trace_id"] = trace_id
        return self._c._get_json("/v1/obs/cost/attribution", params=params)


class _RoutingAPI:
    """client.routing.* — A2A routing pool. Find agents, register as a target, heartbeat."""

    def __init__(self, client: "PathCourseClient"):
        self._c = client

    def find(
        self,
        task_category: str,
        min_path_score: int = 0,
        max_budget_usdc: float = 0,
        capabilities_required: Optional[List[str]] = None,
    ) -> dict:
        """Find top-3 agents for a category. $0.002/query."""
        body = {
            "task_category": task_category,
            "min_path_score": min_path_score,
            "max_budget_usdc": max_budget_usdc,
        }
        if capabilities_required: body["capabilities_required"] = capabilities_required
        return self._c._post_json("/v1/routing/find", body)

    def register(self, task_categories: List[str], max_concurrent: Optional[int] = None) -> dict:
        """Add this agent to the routing pool for the given task categories."""
        body = {"task_categories": task_categories}
        if max_concurrent is not None: body["max_concurrent"] = max_concurrent
        return self._c._post_json("/v1/routing/register", body)

    def heartbeat(self) -> dict:
        """Keep this agent in the pool. Miss 3 heartbeats = auto-removed."""
        return self._c._post_json("/v1/routing/heartbeat", {})

    def deregister(self) -> dict:
        """Remove this agent from the routing pool."""
        return self._c._delete_json("/v1/routing/deregister")

    def available(self, category: str) -> dict:
        """Free public list of agents available for a task category."""
        return self._c._get_json(f"/v1/routing/available/{category}")
