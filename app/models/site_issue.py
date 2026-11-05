"""Un error del sitio, reportado por una clienta. No es un producto."""

import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class IssueStatus(str, enum.Enum):
    OPEN = "OPEN"
    SOLVED = "SOLVED"


class SiteIssue(Base):
    __tablename__ = "site_issues"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(80), nullable=False)
    detail = Column(Text, nullable=False)
    status = Column(Enum(IssueStatus), nullable=False, default=IssueStatus.OPEN)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    solved_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
