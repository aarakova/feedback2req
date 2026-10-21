import hashlib
import secrets
import unicodedata
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError
from sqlalchemy.orm import Session as Transaction

from feedback2req.config import Settings
from feedback2req.errors import AppError
from feedback2req.persistence.identity import DuplicateLogin, IdentityRepository
from feedback2req.persistence.models import Session, User


def normalize_login(login: str) -> str:
    value = unicodedata.normalize("NFKC", login).strip().casefold()
    if not 1 <= len(value) <= 128 or any(unicodedata.category(c).startswith("C") for c in value):
        raise AppError(422, "invalid_login", "Invalid login")
    return value


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class Principal:
    user: User
    session: Session


class Identity:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.hasher = PasswordHasher(
            time_cost=settings.argon_time_cost,
            memory_cost=settings.argon_memory_cost,
            parallelism=settings.argon_parallelism,
            type=Type.ID,
        )
        self.dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))

    def register(self, tx: Transaction, login: str, password: str) -> User:
        try:
            return IdentityRepository(tx).create_user(
                normalize_login(login),
                self.hasher.hash(password),
            )
        except DuplicateLogin:
            raise AppError(409, "login_unavailable", "Login is unavailable") from None

    def login(self, tx: Transaction, login: str, password: str):
        repo = IdentityRepository(tx)
        user = repo.user_by_login(normalize_login(login))
        try:
            self.hasher.verify(user.password_hash if user else self.dummy_hash, password)
        except VerificationError:
            raise AppError(401, "invalid_credentials", "Invalid login or password") from None
        if user is None:
            raise AppError(401, "invalid_credentials", "Invalid login or password")
        if self.hasher.check_needs_rehash(user.password_hash):
            user.password_hash = self.hasher.hash(password)
        raw_token = secrets.token_urlsafe(32)
        now = repo.now()
        session = repo.create_session(
            token_hash=token_hash(raw_token),
            user_id=user.id,
            csrf_secret=secrets.token_urlsafe(32),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(seconds=self.settings.session_seconds),
        )
        return Principal(user, session), raw_token

    def authenticate(self, tx: Transaction, raw_token: str | None) -> Principal:
        if not raw_token or len(raw_token) > 128:
            raise AppError(401, "unauthenticated", "A valid session is required")
        repo = IdentityRepository(tx)
        session = repo.session_for_update(token_hash(raw_token))
        # Read time after acquiring the row: a queued request cannot revive an expired session.
        now = repo.now()
        if (
            session is None
            or session.expires_at <= now
            or session.last_seen_at + timedelta(seconds=self.settings.idle_seconds) <= now
        ):
            raise AppError(401, "unauthenticated", "A valid session is required")
        session.last_seen_at = now
        return Principal(repo.user_by_id(session.user_id), session)

    @staticmethod
    def logout(tx: Transaction, principal: Principal):
        principal.session.revoked_at = IdentityRepository(tx).now()
