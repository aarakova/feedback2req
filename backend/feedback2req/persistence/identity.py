from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as Transaction

from feedback2req.persistence.models import Session, User


class DuplicateLogin(Exception):
    pass


class IdentityRepository:
    def __init__(self, tx: Transaction):
        self.tx = tx

    def now(self):
        return self.tx.scalar(select(func.clock_timestamp()))

    def user_by_login(self, login):
        return self.tx.scalar(select(User).where(User.login == login))

    def user_by_id(self, user_id):
        return self.tx.get(User, user_id)

    def create_user(self, login, password_hash):
        user = User(login=login, password_hash=password_hash)
        try:
            with self.tx.begin_nested():
                self.tx.add(user)
                self.tx.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise DuplicateLogin from None
            raise
        return user

    def create_session(self, **values):
        session = Session(**values)
        self.tx.add(session)
        self.tx.flush()
        return session

    def session_for_update(self, token_hash):
        return self.tx.scalar(
            select(Session)
            .where(Session.token_hash == token_hash, Session.revoked_at.is_(None))
            .with_for_update()
        )
