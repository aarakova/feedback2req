from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field

from feedback2req.api.routes import Actor, Tx, page
from feedback2req.api.schemas import ClosedModel
from feedback2req.materials import service

router = APIRouter(prefix="/api/v1/projects/{project_id}")


class SourceInput(ClosedModel):
    kind: Literal["text"]
    text: str


class DocumentInput(ClosedModel):
    title: str = Field(min_length=1, max_length=200)
    text: str


def view(row, *, document=False):
    header, state = row
    common = {"id": str(header.id), "state_id": str(state.id), "text": state.text}
    return common | ({"title": state.title} if document else {"kind": header.kind})


@router.post("/sources", status_code=201)
def create_source(project_id: UUID, body: SourceInput, request: Request, tx: Tx, actor: Actor):
    return view(
        service.create(
            tx,
            actor.user.id,
            project_id,
            body.text,
            request.app.state.settings.max_material_text_chars,
        )
    )


@router.get("/sources")
def list_sources(
    project_id: UUID, request: Request, tx: Tx, actor: Actor, cursor: UUID | None = None
):
    limit = request.app.state.settings.page_size
    rows = service.list_materials(tx, actor.user.id, project_id, cursor, limit)
    return page([view(row) for row in rows], limit, lambda item: item["id"])


@router.get("/sources/{material_id}")
def get_source(project_id: UUID, material_id: UUID, tx: Tx, actor: Actor):
    return view(service.read(tx, actor.user.id, project_id, material_id))


@router.post("/documents", status_code=201)
def create_document(project_id: UUID, body: DocumentInput, request: Request, tx: Tx, actor: Actor):
    return view(
        service.create(
            tx,
            actor.user.id,
            project_id,
            body.text,
            request.app.state.settings.max_material_text_chars,
            title=body.title,
        ),
        document=True,
    )


@router.get("/documents")
def list_documents(
    project_id: UUID, request: Request, tx: Tx, actor: Actor, cursor: UUID | None = None
):
    limit = request.app.state.settings.page_size
    rows = service.list_materials(tx, actor.user.id, project_id, cursor, limit, document=True)
    return page([view(row, document=True) for row in rows], limit, lambda item: item["id"])


@router.get("/documents/{material_id}")
def get_document(project_id: UUID, material_id: UUID, tx: Tx, actor: Actor):
    return view(
        service.read(tx, actor.user.id, project_id, material_id, document=True), document=True
    )
