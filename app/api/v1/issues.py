from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user, get_current_user
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.issue import IssueAdminRead, IssueCreate, IssueRead
from app.services import issue_service

router = APIRouter()


@router.post("/", response_model=IssueRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def create_issue(
    request: Request,
    payload: IssueCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return issue_service.create(db, user=current_user, title=payload.title, detail=payload.detail)


@router.get("/mine", response_model=list[IssueRead])
def my_issues(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return issue_service.list_for_user(db, current_user.id)


@router.get("/", response_model=list[IssueAdminRead])
def all_issues(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    rows = issue_service.list_all(db)
    return [
        IssueAdminRead(
            id=row.id,
            title=row.title,
            detail=row.detail,
            status=row.status,
            created_at=row.created_at,
            solved_at=row.solved_at,
            user_name=row.user.name,
            user_email=row.user.email,
        )
        for row in rows
    ]


@router.patch("/{issue_id}/solve", response_model=IssueAdminRead)
def solve_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    try:
        row = issue_service.solve(db, issue_id)
    except issue_service.IssueNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return IssueAdminRead(
        id=row.id,
        title=row.title,
        detail=row.detail,
        status=row.status,
        created_at=row.created_at,
        solved_at=row.solved_at,
        user_name=row.user.name,
        user_email=row.user.email,
    )
