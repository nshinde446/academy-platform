import uuid

from app.modules.ai.providers.base_provider import BaseAIProvider


class MockAIProvider(BaseAIProvider):

    async def generate_questions(
        self, topic_id: uuid.UUID, count: int, difficulty: str, branch_id: uuid.UUID | None
    ) -> list[dict]:
        questions = []
        for i in range(count):
            questions.append({
                "question_text": f"Mock question {i + 1} on topic {topic_id} [{difficulty}]",
                "options": [
                    {"label": "A", "text": f"Option A for Q{i + 1}"},
                    {"label": "B", "text": f"Option B for Q{i + 1}"},
                    {"label": "C", "text": f"Option C for Q{i + 1}"},
                    {"label": "D", "text": f"Option D for Q{i + 1}"},
                ],
                "correct_answer": "A",
                "difficulty": difficulty,
                "explanation": f"Explanation for mock question {i + 1}.",
            })
        return questions

    async def get_recommendations(
        self, student_id: uuid.UUID, limit: int, branch_id: uuid.UUID | None
    ) -> list[dict]:
        recommendations = []
        topics = [
            ("Kinematics", "Revise projectile motion formulas"),
            ("Thermodynamics", "Practice entropy calculation problems"),
            ("Organic Chemistry", "Focus on reaction mechanisms"),
            ("Calculus", "Work on integration by parts"),
            ("Electrostatics", "Review Gauss's law applications"),
        ]
        for i in range(min(limit, len(topics))):
            topic_name, action = topics[i]
            recommendations.append({
                "topic": topic_name,
                "priority": "HIGH" if i < 2 else "MEDIUM",
                "action": action,
                "reason": f"Student performance below threshold in {topic_name}",
            })
        return recommendations

    async def tutor_response(
        self, student_id: uuid.UUID, question_text: str, context: str | None, branch_id: uuid.UUID | None
    ) -> dict:
        return {
            "answer": (
                f"Great question! Here's a step-by-step explanation for: '{question_text[:80]}...'\n\n"
                "Step 1: Identify the key concepts involved.\n"
                "Step 2: Apply the relevant formula or principle.\n"
                "Step 3: Solve and verify your answer.\n\n"
                "Would you like me to elaborate on any step?"
            ),
            "confidence": 0.85,
            "related_topics": ["Practice Problems", "Formula Sheet", "Video Lecture"],
        }

    async def generate_dpp(
        self, batch_id: uuid.UUID, subjects: list[uuid.UUID], days: int, branch_id: uuid.UUID | None
    ) -> dict:
        schedule = []
        for day in range(1, days + 1):
            day_plan = {
                "day": day,
                "assignments": [],
            }
            for j, subject_id in enumerate(subjects):
                day_plan["assignments"].append({
                    "subject_id": str(subject_id),
                    "question_count": 10,
                    "difficulty_mix": {"EASY": 3, "MEDIUM": 5, "HARD": 2},
                    "estimated_time_minutes": 30,
                })
            schedule.append(day_plan)
        return {
            "batch_id": str(batch_id),
            "total_days": days,
            "schedule": schedule,
        }
