"""
Celery task for periodic analytics refresh.

Usage:
    from app.modules.analytics.jobs.tasks import refresh_analytics_task
    refresh_analytics_task.delay(str(branch_id), str(academic_year_id))
"""
