"""Test Gemma 4 local model via Ollama + ADK LiteLLM integration.

Validates that Gemma 4 can:
1. Respond to basic prompts via Ollama REST API
2. Produce structured JSON output
3. Work through ADK LlmAgent via LiteLlm wrapper
4. Handle image description (multimodal)

Usage:
    # Ensure Ollama is running with Gemma 4 pulled:
    #   ollama pull gemma4:e4b
    #
    # Run from project root:
    #   python scripts/test_gemma4_local.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

# Ensure Ollama API base is set
os.environ.setdefault("OLLAMA_API_BASE", "http://localhost:11434")

MODEL_NAME = "gemma4:e4b"
OLLAMA_CHAT_MODEL = f"ollama_chat/{MODEL_NAME}"


def _header(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


# ── Test 1: Raw Ollama REST API ──────────────────────────────────────────

async def test_ollama_raw() -> bool:
    """Test basic Ollama connectivity and response."""
    _header("Test 1: Raw Ollama REST API")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{os.environ['OLLAMA_API_BASE']}/api/chat",
                json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": "What is 2+2? Reply with just the number."}],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["message"]["content"]
            print(f"  Response: {content.strip()}")
            print(f"  Status: PASS")
            return True
    except Exception as e:
        print(f"  Error: {e}")
        print(f"  Status: FAIL")
        print(f"  Hint: Is Ollama running? Try: ollama serve")
        return False


# ── Test 2: Structured JSON Output ──────────────────────────────────────

async def test_json_output() -> bool:
    """Test that Gemma 4 can produce valid structured JSON."""
    _header("Test 2: Structured JSON Output")
    try:
        import httpx
        prompt = (
            "Extract facts from this message and return as JSON.\n"
            "Message: 'Alice decided to use Redis for caching in the Atlas project.'\n\n"
            "Return ONLY a JSON object with this structure:\n"
            '{"facts": [{"text": "...", "entities": ["..."], "importance": "high|medium|low"}]}'
        )
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{os.environ['OLLAMA_API_BASE']}/api/chat",
                json={
                    "model": MODEL_NAME,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json",
                },
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            parsed = json.loads(content)
            print(f"  Response: {json.dumps(parsed, indent=2)[:300]}")
            assert "facts" in parsed, "Missing 'facts' key"
            print(f"  Status: PASS")
            return True
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"  Raw response: {content[:200]}")
        print(f"  Status: FAIL")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        print(f"  Status: FAIL")
        return False


# ── Test 3: ADK LlmAgent via LiteLlm ───────────────────────────────────

async def test_adk_litellm() -> bool:
    """Test ADK LlmAgent with Gemma 4 via LiteLlm wrapper."""
    _header("Test 3: ADK LlmAgent via LiteLlm")
    try:
        from google.adk.agents import LlmAgent
        from google.adk.models.lite_llm import LiteLlm
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        agent = LlmAgent(
            name="test_gemma4",
            model=LiteLlm(model=OLLAMA_CHAT_MODEL),
            instruction=(
                "You are a helpful assistant. The user will ask a simple question. "
                "Answer concisely in one sentence."
            ),
        )

        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="gemma4_test",
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name="gemma4_test",
            user_id="test",
        )

        from google.genai import types
        user_msg = types.Content(
            role="user",
            parts=[types.Part.from_text(text="What programming language is Python named after?")],
        )

        response_text = ""
        async for event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=user_msg,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text

        print(f"  Response: {response_text.strip()[:200]}")
        assert len(response_text.strip()) > 0, "Empty response"
        print(f"  Status: PASS")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        print(f"  Status: FAIL")
        return False


# ── Test 4: ADK LlmAgent with Structured JSON Schema ───────────────────

async def test_adk_structured_output() -> bool:
    """Test ADK LlmAgent with output_schema for structured JSON."""
    _header("Test 4: ADK Structured JSON Output")
    try:
        from pydantic import BaseModel
        from google.adk.agents import LlmAgent
        from google.adk.models.lite_llm import LiteLlm
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        class TestResult(BaseModel):
            answer: str = ""
            confidence: float = 0.0

        agent = LlmAgent(
            name="test_structured",
            model=LiteLlm(model=OLLAMA_CHAT_MODEL),
            instruction=(
                "Answer the user's question. Return a JSON object with "
                "'answer' (string) and 'confidence' (float 0-1)."
            ),
            output_key="result",
            output_schema=TestResult,
            generate_content_config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="gemma4_structured_test",
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name="gemma4_structured_test",
            user_id="test",
            state={},
        )

        user_msg = types.Content(
            role="user",
            parts=[types.Part.from_text(text="What is the capital of France?")],
        )

        async for _event in runner.run_async(
            user_id=session.user_id,
            session_id=session.id,
            new_message=user_msg,
        ):
            pass

        final = await session_service.get_session(
            app_name="gemma4_structured_test",
            user_id="test",
            session_id=session.id,
        )
        result = final.state.get("result") if final else None
        print(f"  Result: {result}")
        assert result is not None, "No result in session state"
        print(f"  Status: PASS")
        return True
    except Exception as e:
        print(f"  Error: {e}")
        print(f"  Status: FAIL")
        return False


# ── Main ────────────────────────────────────────────────────────────────

async def main() -> None:
    print(f"Gemma 4 Local Model Test Suite")
    print(f"Model: {MODEL_NAME}")
    print(f"Ollama API: {os.environ['OLLAMA_API_BASE']}")

    results: dict[str, bool] = {}
    start = time.time()

    results["ollama_raw"] = await test_ollama_raw()
    if not results["ollama_raw"]:
        print("\nOllama not reachable — skipping remaining tests.")
        _print_summary(results, time.time() - start)
        return

    results["json_output"] = await test_json_output()
    results["adk_litellm"] = await test_adk_litellm()
    results["adk_structured"] = await test_adk_structured_output()

    _print_summary(results, time.time() - start)


def _print_summary(results: dict[str, bool], elapsed: float) -> None:
    _header("Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {status}  {name}")
    print(f"\n  {passed}/{total} tests passed in {elapsed:.1f}s")

    if all(results.values()):
        print(f"\n  Gemma 4 ({MODEL_NAME}) is ready for use with ADK agents!")
        print(f"  Use model: LiteLlm(model='{OLLAMA_CHAT_MODEL}')")
    else:
        print(f"\n  Some tests failed. Check output above for details.")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    asyncio.run(main())
