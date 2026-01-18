from sqlalchemy.orm import Session
from app.data.models.user import UserModel
from app.repos.user_repo import UserRepo
from app.domain.schemas import UserCreate, UserRead


class UserService:
    def __init__(self, db: Session):
        self.repo = UserRepo(db)

    def create_user(self, payload: UserCreate) -> UserRead:
        existing = self.repo.get_user(payload.id)
        if existing:
            return UserRead(id=existing.id, name=existing.name)

        user = UserModel(id=payload.id, name=payload.name)
        created = self.repo.create_user(user)
        return UserRead(id=created.id, name=created.name)

    def get_user(self, user_id: int) -> UserRead:
        user = self.repo.get_user(user_id)
        if not user:
            raise ValueError("User not found")
        return UserRead(id=user.id, name=user.name)