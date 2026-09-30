"""Single AI Agent implementation for USFDS Fraud Investigation using Google ADK."""

import os
from typing import Callable, Generator, List, Optional
from google.adk import Agent
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from usfds_agent.config import GOOGLE_API_KEY
from usfds_agent.prompts import INVESTIGATION_SYSTEM_PROMPT
from usfds_agent.tools import (
    explain_prediction,
    get_case_summary,
    get_user_baseline,
    search_related_cases,
)

# Ensure API Key is available in environment
if GOOGLE_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
    os.environ["GEMINI_API_KEY"] = GOOGLE_API_KEY


def create_fraud_investigator_agent(
    model_name: str = "gemini-3.8-flash",
) -> Agent:
    """Instantiates the Google ADK Single Agent equipped with USFDS investigation tools."""
    tools: List[Callable] = [
        get_case_summary,
        explain_prediction,
        get_user_baseline,
        search_related_cases,
    ]

    agent = Agent(
        name="fraud_investigator_agent",
        description="Senior AI Fraud & AML Investigator for USFDS transaction alert triage and SAR drafting",
        model=model_name,
        instruction=INVESTIGATION_SYSTEM_PROMPT,
        tools=tools,
    )
    return agent


class FraudInvestigationRunner:
    """Orchestrates running investigations on transactions using Google ADK Runner."""

    def __init__(
        self,
        model_name: str = "gemini-3.8-flash",
        session_service: Optional[InMemorySessionService] = None,
    ):
        self.agent = create_fraud_investigator_agent(model_name=model_name)
        self.session_service = session_service or InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name="usfds_fraud_investigation",
            session_service=self.session_service,
            auto_create_session=True,
        )

    def run_investigation(
        self,
        event_id: int,
        analyst_user_id: str = "senior_investigator",
        verbose: bool = True,
    ) -> str:
        """Executes full automated investigation workflow on a specific event_id."""
        user_prompt = f"Yêu cầu điều tra: Hãy tiến hành điều tra toàn diện giao dịch bị cảnh báo có mã event_id = {event_id}. Thực hiện đầy đủ các bước kiểm tra bối cảnh, bóc tách SHAP, phân tích độ lệch hành vi khách hàng, và lập hồ sơ kết luận + dự thảo báo cáo SAR."

        new_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_prompt)],
        )

        session_id = f"session_event_{event_id}"
        events: Generator[Event, None, None] = self.runner.run(
            user_id=analyst_user_id,
            session_id=session_id,
            new_message=new_message,
            state_delta={"event_id": event_id},
        )

        final_response = ""

        for event in events:
            # Handle tool call events if verbose
            if verbose and hasattr(event, "tool_calls") and event.tool_calls:
                for tc in event.tool_calls:
                    print(f"  [AGENT TOOL CALL] -> {tc.name}({tc.args})")

            # Extract generated content chunks
            if hasattr(event, "content") and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_response += part.text

        return final_response
