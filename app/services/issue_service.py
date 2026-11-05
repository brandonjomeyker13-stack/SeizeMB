"""Reportes de errores del sitio. No tienen que ver con el catálogo."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.site_issue import IssueStatus, SiteIssue
from app.models.user import User


class IssueNotFoundError(Exception):
    pass


def create(db: Session, *, user: User, title: str, detail: str) -> SiteIssue:
    row = SiteIssue(user_id=user.id, title=title.strip(), detail=detail.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_for_user(db: Session, user_id: int) -> list[SiteIssue]:
    return (
        db.query(SiteIssue)
        .filter(SiteIssue.user_id == user_id)
        .order_by(SiteIssue.created_at.desc())
        .all()
    )


def list_all(db: Session) -> list[SiteIssue]:
    return db.query(SiteIssue).order_by(SiteIssue.created_at.desc()).all()


def solve(db: Session, issue_id: int) -> SiteIssue:
    row = db.query(SiteIssue).filter(SiteIssue.id == issue_id).first()
    if row is None:
        raise IssueNotFoundError("No encontramos ese reporte.")
    row.status = IssueStatus.SOLVED
    row.solved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row
