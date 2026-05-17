import uuid


def process_ai_request(request_id: str):
    """Celery task placeholder for async AI request processing.

    In production, this would be registered as:
        @celery_app.task
        def process_ai_request(request_id: str):
            ...

    The task would create a new DB session and call
    ai_service.process_request(session, uuid.UUID(request_id)).
    """
    pass
