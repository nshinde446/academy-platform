import logging

logger = logging.getLogger(__name__)


async def generate_report_task(job_id: str):
    logger.info("CELERY PLACEHOLDER: would process report job %s", job_id)
