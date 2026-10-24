import json
import logging
import os
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import ValidationError

from app.schemas.generation import WorkflowGenerateRequest, WorkflowProposal

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"


class AIServiceError(Exception):
    """Base exception for AI generation service errors."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AIServiceNotConfiguredError(AIServiceError):
    def __init__(
        self,
        message: str = "AI workflow generation is not configured. Missing GEMINI_API_KEY.",
    ):
        super().__init__(message=message, status_code=503)


class AIRateLimitError(AIServiceError):
    def __init__(
        self,
        message: str = "AI service rate limit exceeded. Please try again later.",
    ):
        super().__init__(message=message, status_code=429)


class AITimeoutError(AIServiceError):
    def __init__(self, message: str = "AI service request timed out."):
        super().__init__(message=message, status_code=504)


class AIProviderError(AIServiceError):
    def __init__(
        self,
        message: str = "AI service provider encountered an error.",
        status_code: int = 502,
    ):
        super().__init__(message=message, status_code=status_code)


class AIParsingError(AIServiceError):
    def __init__(
        self,
        message: str = "Failed to parse structured workflow proposal from AI provider.",
    ):
        super().__init__(message=message, status_code=502)


def build_generation_prompt(request: WorkflowGenerateRequest) -> str:
    """Construct an actionable, clear prompt for Gemini."""
    prompt_lines = [
        "You are an expert technical project planner and workflow architect.",
        "Analyze the following user goal and constraints, and produce an actionable, structured workflow plan with tasks, estimated durations, priorities, and dependencies.",
        "",
        f"User Goal: {request.goal}",
        f"Experience Level: {request.experience_level}",
    ]

    if request.deadline_days is not None:
        prompt_lines.append(f"Target Deadline: {request.deadline_days} calendar days")

    if request.hours_per_day is not None:
        prompt_lines.append(f"Available Daily Effort: {request.hours_per_day} hours/day")

    if request.additional_context:
        prompt_lines.append(f"Additional Context / Constraints: {request.additional_context}")

    prompt_lines.extend(
        [
            "",
            "Planning Guidelines:",
            "1. Decompose the goal into 3 to 15 logical, actionable tasks.",
            "2. Assign each task a unique reference like 'T1', 'T2', 'T3', etc.",
            "3. Provide realistic estimated durations in hours (positive float numbers).",
            "4. Assign appropriate priorities ('low', 'medium', 'high', 'urgent').",
            "5. Identify prerequisite dependencies ('depends_on' as a list of prerequisite task refs).",
            "   - Independent tasks must have an empty 'depends_on' list.",
            "   - Do NOT create dependency cycles. A task cannot depend on itself or on future tasks.",
            "6. Provide a concise, professional title and description for the workflow.",
        ]
    )

    return "\n".join(prompt_lines)


class WorkflowAIGenerator:
    """Service to generate workflow proposals using Google's Gemini SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL

    def generate_proposal(self, request: WorkflowGenerateRequest) -> WorkflowProposal:
        """Call Gemini to generate a structured workflow proposal."""
        if not self.api_key:
            raise AIServiceNotConfiguredError()

        client = genai.Client(api_key=self.api_key)
        prompt = build_generation_prompt(request)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=WorkflowProposal,
            temperature=0.2,
        )

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        except APIError as exc:
            logger.error("Gemini API error (code %s): %s", getattr(exc, "code", None), exc.message)
            code = getattr(exc, "code", 502)
            if code == 429:
                raise AIRateLimitError() from exc
            if code in (401, 403):
                raise AIProviderError("AI service authentication failed.", status_code=502) from exc
            if code in (408, 504):
                raise AITimeoutError() from exc
            raise AIProviderError(f"AI service provider error: {exc.message}", status_code=502) from exc
        except Exception as exc:
            logger.error("Unexpected error contacting Gemini API: %s", str(exc))
            raise AIProviderError("Unexpected error contacting AI service provider.", status_code=502) from exc

        raw_text = getattr(response, "text", None)
        if not raw_text:
            raise AIParsingError("AI service returned an empty response.")

        try:
            proposal = WorkflowProposal.model_validate_json(raw_text)
        except (ValidationError, json.JSONDecodeError) as exc:
            logger.error("Failed to parse AI output into WorkflowProposal: %s", str(exc))
            raise AIParsingError("Could not validate structured output from AI provider.") from exc

        return proposal


def get_ai_generator() -> WorkflowAIGenerator:
    """FastAPI dependency for obtaining the AI generator instance."""
    return WorkflowAIGenerator()
