from sqlalchemy.orm import Session
from app.data.models.user import UserModel

class UserRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_user(self, user_id: int) -> UserModel | None:
        return self.db.get(UserModel, user_id)

    def create_user(self, user: UserModel) -> UserModel:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user