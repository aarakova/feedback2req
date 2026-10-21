from sqlalchemy import exists, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from feedback2req.persistence.models import Project, ProjectAccess, User


class ProjectRepository:
    def __init__(self, tx: Session):
        self.tx = tx

    def get(self, project_id, *, for_update=False):
        query = select(Project).where(Project.id == project_id)
        if for_update:
            query = query.with_for_update()
        return self.tx.scalar(query)

    def access(self, project_id, user_id):
        return self.tx.get(ProjectAccess, (project_id, user_id))

    def create(self, user_id, name):
        project = Project(owner_id=user_id, name=name, execution_mode="mock")
        self.tx.add(project)
        self.tx.flush()
        return project

    def list_for_user(self, user_id, cursor, limit):
        membership = exists().where(
            ProjectAccess.project_id == Project.id, ProjectAccess.user_id == user_id
        )
        query = select(Project).where(or_(Project.owner_id == user_id, membership))
        if cursor:
            query = query.where(Project.id > cursor)
        return self.tx.scalars(query.order_by(Project.id).limit(limit + 1)).all()

    def rename(self, project, name):
        project.name = name
        self.tx.flush()

    def registered_user(self, user_id):
        return self.tx.get(User, user_id) is not None

    def set_access(self, project_id, user_id, can_approve):
        self.tx.execute(
            insert(ProjectAccess)
            .values(
                project_id=project_id,
                user_id=user_id,
                can_approve=can_approve,
            )
            .on_conflict_do_update(
                index_elements=[ProjectAccess.project_id, ProjectAccess.user_id],
                set_={"can_approve": can_approve},
            )
        )

    def remove_access(self, project_id, user_id):
        access = self.access(project_id, user_id)
        if access:
            self.tx.delete(access)

    def list_access(self, project_id, owner_id, cursor, limit):
        members = select(ProjectAccess.user_id, ProjectAccess.can_approve).where(
            ProjectAccess.project_id == project_id,
        )
        owner_row = select(User.id, User.id.is_not(None)).where(User.id == owner_id)
        combined = members.union(owner_row).subquery()
        query = select(combined)
        if cursor:
            query = query.where(combined.c.user_id > cursor)
        return self.tx.execute(query.order_by(combined.c.user_id).limit(limit + 1)).all()
