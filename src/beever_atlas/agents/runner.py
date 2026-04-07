"""ADK Runner integration for FastAPI.

Provides Runner creation with InMemorySessionService and
session-per-request pattern for use in API route handlers.
"""

import uuid

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session

# Module-level session service shared across the app
_session_service = InMemorySessionService()

APP_NAME = "beever_atlas"


def create_runner(agent: BaseAgent) -> Runner:
    """Create an ADK Runner for the given root agent.

    Args:
        agent: The root ADK Agent (e.g., query_router_agent).

    Returns:
        A Runner instance configured with InMemorySessionService.
    """
    return Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=_session_service,
    )


async def create_session(user_id: str = "anonymous", state: dict | None = None) -> Session:
    """Create a new session for a request.

    Args:
        user_id: User identifier from auth middleware.
        state: Optional initial session state (used by ingestion pipeline).

    Returns:
        An ADK Session with a unique ID.
    """
    session = await _session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=str(uuid.uuid4()),
        state=state or {},
    )
    return session


def get_session_service() -> InMemorySessionService:
    """Return the shared session service instance."""
    return _session_service


async def run_agent(
    agent: BaseAgent,
    state: dict | None = None,
    message: str = "process",
) -> dict:
    """Run an agent standalone and return the final session state.

    Creates a fresh session, drives the agent to completion, and returns
    the resulting session state dict. Useful for invoking LlmAgents outside
    the main pipeline (e.g., coreference resolution, media description).

    Args:
        agent: The ADK agent to run.
        state: Initial session state (prompt context, input data).
        message: User message to send to the agent (required for LlmAgents).

    Returns:
        The final session state after agent completion.
    """
    from google.genai import types

    runner = create_runner(agent)
    session = await create_session(state=state)

    async for _event in runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=message)],
        ),
    ):
        pass  # Drive to completion

    # Re-fetch session to get final state with all deltas applied
    final_session = await _session_service.get_session(
        app_name=APP_NAME,
        user_id=session.user_id,
        session_id=session.id,
    )
    return dict(final_session.state) if final_session else {}
