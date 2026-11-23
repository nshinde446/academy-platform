"""Teacher-portal workflow models (Weekend & Star-System SRD).

Kept in one module so the metadata registers them together. Imported by the
portal services and by tests/conftest so ``Base.metadata`` sees them.
"""

from app.modules.teacher_portal.models.workflow_models import (  # noqa: F401
    ApproverLog,
    ApproverMapping,
    AssessmentCategory,
    AssessmentItemMaster,
    PortalNotification,
    SelfAssessment,
    SelfAssessmentItem,
    SelfAssessmentStar,
)

__all__ = [
    "ApproverLog",
    "ApproverMapping",
    "AssessmentCategory",
    "AssessmentItemMaster",
    "PortalNotification",
    "SelfAssessment",
    "SelfAssessmentItem",
    "SelfAssessmentStar",
]
