import uuid

from app.modules.ai.providers.base_provider import BaseAIProvider


class GeminiProvider(BaseAIProvider):
    """Placeholder for future Gemini integration."""

    async def generate_questions(
        self, topic_id: uuid.UUID, count: int, difficulty: str, branch_id: uuid.UUID | None
    ) -> list[dict]:
        raise NotImplementedError("Gemini provider not yet implemented")

    async def get_recommendations(
        self, student_id: uuid.UUID, limit: int, branch_id: uuid.UUID | None
    ) -> list[dict]:
        raise NotImplementedError("Gemini provider not yet implemented")

    async def tutor_response(
        self, student_id: uuid.UUID, question_text: str, context: str | None, branch_id: uuid.UUID | None
    ) -> dict:
        raise NotImplementedError("Gemini provider not yet implemented")

    async def generate_dpp(
        self, batch_id: uuid.UUID, subjects: list[uuid.UUID], days: int, branch_id: uuid.UUID | None
    ) -> dict:
        raise NotImplementedError("Gemini provider not yet implemented")
