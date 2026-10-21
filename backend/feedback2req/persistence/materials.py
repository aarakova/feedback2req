from uuid import uuid4

from sqlalchemy import select

from feedback2req.persistence.models import (
    DocumentState,
    FeedbackSource,
    ProductDocument,
    SourceTextState,
)


class MaterialRepository:
    def __init__(self, tx):
        self.tx = tx

    def create(self, project_id, author_id, text, *, title=None):
        material_id, state_id = uuid4(), uuid4()
        header_values = dict(id=material_id, project_id=project_id, current_state_id=state_id)
        state_values = dict(
            id=state_id, project_id=project_id, text=text, author_id=author_id, origin="human"
        )
        if title is None:
            header = FeedbackSource(**header_values, kind="text", availability="available")
            state = SourceTextState(**state_values, source_id=material_id)
        else:
            header = ProductDocument(**header_values)
            state = DocumentState(**state_values, document_id=material_id, title=title)
        self.tx.add(header)
        self.tx.flush()  # Current-state FK is deferred; the parent exists for the state's FK.
        self.tx.add(state)
        self.tx.flush()
        return header, state

    @staticmethod
    def query(project_id, document):
        header, state = (
            (ProductDocument, DocumentState) if document else (FeedbackSource, SourceTextState)
        )
        owner_id = state.document_id if document else state.source_id
        return (
            select(header, state)
            .join(
                state,
                (state.project_id == header.project_id)
                & (owner_id == header.id)
                & (state.id == header.current_state_id),
            )
            .where(header.project_id == project_id)
        )

    def get(self, project_id, material_id, *, document=False):
        header = ProductDocument if document else FeedbackSource
        return self.tx.execute(
            self.query(project_id, document).where(header.id == material_id)
        ).first()

    def list(self, project_id, cursor, limit, *, document=False):
        header = ProductDocument if document else FeedbackSource
        query = self.query(project_id, document)
        if cursor:
            query = query.where(header.id > cursor)
        return self.tx.execute(query.order_by(header.id).limit(limit + 1)).all()
