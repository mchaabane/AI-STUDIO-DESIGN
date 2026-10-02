import json
import shutil
from pathlib import Path

from backend.app.models import Project, ProjectDetail, ProjectVersion


# Racine du projet :
# /Users/chaabane/design-ai-mvp
BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"

PROJECTS_FILE = DATA_DIR / "projects.json"

PROJECTS_DIR = DATA_DIR / "projects"


def ensure_data_directories() -> None:
    """
    Crée les dossiers de données nécessaires au démarrage.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    PROJECTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not PROJECTS_FILE.exists():
        PROJECTS_FILE.write_text(
            "[]",
            encoding="utf-8",
        )


def read_projects() -> list[Project]:
    """
    Retourne tous les projets enregistrés.
    """

    ensure_data_directories()

    raw_data = json.loads(
        PROJECTS_FILE.read_text(
            encoding="utf-8",
        )
    )

    return [
        Project(**project)
        for project in raw_data
    ]


def write_projects(
    projects: list[Project],
) -> None:
    """
    Enregistre la liste complète des projets.
    """

    ensure_data_directories()

    PROJECTS_FILE.write_text(
        json.dumps(
            [
                project.model_dump()
                for project in projects
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def get_project(
    project_id: str,
) -> ProjectDetail | None:
    """
    Retourne un projet avec toutes ses versions.

    Chaque version est stockée dans son propre dossier :

    projects/
        <project_id>/
            version-1/
                index.html
                script.js
                metadata.json
    """

    projects = read_projects()

    project = next(
        (
            project
            for project in projects
            if project.id == project_id
        ),
        None,
    )

    if project is None:
        return None

    project_directory = (
        PROJECTS_DIR / project_id
    )

    versions: list[ProjectVersion] = []

    if project_directory.exists():

        version_directories = sorted(
            (
                directory
                for directory in project_directory.iterdir()
                if directory.is_dir()
                and directory.name.startswith("version-")
            ),
            key=lambda directory: _version_number(
                directory.name
            ),
        )

        for version_directory in version_directories:

            metadata_file = (
                version_directory / "metadata.json"
            )

            html_file = (
                version_directory / "index.html"
            )

            if not metadata_file.exists():
                continue

            metadata = json.loads(
                metadata_file.read_text(
                    encoding="utf-8",
                )
            )

            html = ""

            if html_file.exists():
                html = html_file.read_text(
                    encoding="utf-8",
                )

            versions.append(
                ProjectVersion(
                    version=metadata["version"],
                    prompt=metadata["prompt"],
                    html=html,
                    generation_time_ms=metadata.get(
                        "generation_time_ms"
                    ),
                    created_at=metadata["created_at"],
                )
            )

    return ProjectDetail(
        **project.model_dump(),
        versions=versions,
    )


def save_project(
    project: Project,
    version: ProjectVersion,
) -> None:
    """
    Enregistre le projet et une nouvelle version.

    Chaque version possède son propre dossier contenant :

        index.html
        script.js
        metadata.json
    """

    projects = read_projects()

    existing_project = next(
        (
            item
            for item in projects
            if item.id == project.id
        ),
        None,
    )

    if existing_project is not None:

        index = projects.index(
            existing_project
        )

        projects[index] = project

    else:

        projects.append(project)

    write_projects(projects)

    project_directory = (
        PROJECTS_DIR / project.id
    )

    project_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    version_directory = (
        project_directory
        / f"version-{version.version}"
    )

    version_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    html_file = (
        version_directory / "index.html"
    )

    html_file.write_text(
        version.html,
        encoding="utf-8",
    )

    script_file = (
        version_directory / "script.js"
    )

    script_file.write_text(
        _extract_javascript(version.html),
        encoding="utf-8",
    )

    metadata_file = (
        version_directory / "metadata.json"
    )

    metadata = {
        "version": version.version,
        "prompt": version.prompt,
        "generation_time_ms": version.generation_time_ms,
        "created_at": version.created_at,
    }

    metadata_file.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def rename_project(
    project_id: str,
    name: str,
) -> Project | None:
    """
    Modifie uniquement le nom d'un projet.

    Les versions, fichiers HTML et métadonnées
    de génération restent inchangés.
    """

    normalized_name = name.strip()

    if not normalized_name:
        raise ValueError(
            "Le nom du projet ne peut pas être vide."
        )

    projects = read_projects()

    project = next(
        (
            item
            for item in projects
            if item.id == project_id
        ),
        None,
    )

    if project is None:
        return None

    project.name = normalized_name

    write_projects(projects)

    return project


def delete_project(
    project_id: str,
) -> None:
    """
    Supprime un projet et toutes ses versions.
    """

    projects = read_projects()

    remaining_projects = [
        project
        for project in projects
        if project.id != project_id
    ]

    write_projects(
        remaining_projects
    )

    project_directory = (
        PROJECTS_DIR / project_id
    )

    if project_directory.exists():
        shutil.rmtree(
            project_directory
        )


def _version_number(
    directory_name: str,
) -> int:
    """
    Extrait le numéro depuis un dossier
    comme 'version-12'.
    """

    try:
        return int(
            directory_name.split("-")[-1]
        )
    except ValueError:
        return 0


def _extract_javascript(
    html: str,
) -> str:
    """
    Extrait les blocs JavaScript présents
    dans le HTML.

    Si plusieurs blocs <script> existent,
    ils sont regroupés dans script.js.
    """

    import re

    scripts = re.findall(
        r"<script(?:\s[^>]*)?>(.*?)</script>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not scripts:
        return ""

    return "\n\n".join(
        script.strip()
        for script in scripts
        if script.strip()
    )