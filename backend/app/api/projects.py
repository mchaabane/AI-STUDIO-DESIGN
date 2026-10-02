from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.storage import (
    delete_project,
    get_project,
    read_projects,
    rename_project,
)


router = APIRouter()


class RenameProjectRequest(BaseModel):
    name: str


@router.get("")
def list_projects():
    """
    Retourne tous les projets.
    """

    return read_projects()


@router.get("/{project_id}")
def get_project_by_id(
    project_id: str,
):
    """
    Retourne un projet avec toutes ses versions.
    """

    project = get_project(
        project_id
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Projet introuvable.",
        )

    return project


@router.patch("/{project_id}")
def rename_project_by_id(
    project_id: str,
    payload: RenameProjectRequest,
):
    """
    Modifie uniquement le nom d'un projet.
    """

    name = payload.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Le nom du projet ne peut pas être vide.",
        )

    if len(name) > 100:
        raise HTTPException(
            status_code=400,
            detail="Le nom du projet ne peut pas dépasser 100 caractères.",
        )

    try:
        project = rename_project(
            project_id,
            name,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Projet introuvable.",
        )

    return {
        "success": True,
        "project": project,
    }


@router.delete("/{project_id}")
def remove_project(
    project_id: str,
):
    """
    Supprime définitivement un projet.

    La confirmation utilisateur est gérée
    par l'interface avant d'appeler cette route.
    """

    project = get_project(
        project_id
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Projet introuvable.",
        )

    delete_project(
        project_id
    )

    return {
        "success": True,
        "message": "Projet supprimé.",
        "project_id": project_id,
    }