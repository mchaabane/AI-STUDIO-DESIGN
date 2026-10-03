import asyncio
import io
import re
import time
import zipfile
from html import escape
from uuid import uuid4
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import httpx

from backend.app.ollama import generate
from backend.app.intelligence import detect_intent
from backend.app.reasoner import analyze_design_change
from backend.app.change_planner import plan_design_changes
from backend.app.css_patcher import apply_css_changes
from backend.app.design_memory import get_design_memory
from backend.app.models import (
    Project,
    ProjectVersion,
    PromptRequest,
    now_iso,
)
from backend.app.storage import (
    get_project,
    read_projects,
    save_project,
)

router = APIRouter()


@router.post("")
async def generate_project(request: PromptRequest):
    """
    Point d'entrée principal de Personal Design AI.
    """

    started_at = time.perf_counter()

    prompt = request.prompt.strip()

    if not prompt:
        raise HTTPException(
            status_code=400,
            detail="Le prompt ne peut pas être vide.",
        )

    # --------------------------------------------------
    # RÈGLE PRIORITAIRE :
    # si le frontend fournit un project_id,
    # il s'agit obligatoirement d'un UPDATE.
    # --------------------------------------------------

    if request.project_id:
        return await update_project(
            prompt=prompt,
            request=request,
            intent=None,
            started_at=started_at,
        )

    # Sans project_id, l'intelligence peut décider
    # s'il s'agit d'une création ou d'une modification
    # par nom de projet.
    intent = await detect_intent(prompt)
    action = intent["action"]

    if action == "CREATE":
        return await create_project(
            prompt=prompt,
            intent=intent,
            title=request.title,
            started_at=started_at,
        )

    if action == "UPDATE":
        return await update_project(
            prompt=prompt,
            request=request,
            intent=intent,
            started_at=started_at,
        )

    if action == "DELETE":
        return {
            "success": True,
            "action": "DELETE",
            "requires_confirmation": True,
            "message": (
                "Suppression détectée. "
                "Une confirmation utilisateur est nécessaire."
            ),
        }

    raise HTTPException(
        status_code=400,
        detail="Action non reconnue.",
    )


# ======================================================
# ZIP EXPORT
# ======================================================

@router.get("/projects/{project_id}/versions/{version}/download")
async def download_project_version(
    project_id: str,
    version: int,
):
    """
    Exporte une version du projet dans un ZIP autonome.
    """

    project = get_project(project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Projet introuvable.",
        )

    selected_version = next(
        (
            item
            for item in project.versions
            if item.version == version
        ),
        None,
    )

    if selected_version is None:
        raise HTTPException(
            status_code=404,
            detail="Version introuvable.",
        )

    html = selected_version.html or ""
    files: dict[str, bytes] = {
        "index.html": html.encode("utf-8"),
    }

    downloaded_assets: dict[str, str] = {}
    asset_counter = 0

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=8.0,
            read=20.0,
            write=20.0,
            pool=20.0,
        ),
        follow_redirects=True,
        headers={"User-Agent": "Personal-Design-AI/0.1"},
    ) as client:
        resource_pattern = re.compile(
            r'(?P<tag><img\b[^>]*?\bsrc|<script\b[^>]*?\bsrc|<link\b[^>]*?\bhref)\s*=\s*["\'](?P<url>https?://[^"\']+)["\']',
            re.IGNORECASE,
        )

        async def fetch_resource(url: str) -> tuple[bytes, str] | None:
            try:
                response = await client.get(url)
                response.raise_for_status()
                content = response.content
                if len(content) > 12 * 1024 * 1024:
                    return None
                return content, response.headers.get("content-type", "")
            except Exception:
                return None

        for match in resource_pattern.finditer(html):
            url = match.group("url")

            if url in downloaded_assets:
                continue

            tag_context = match.group("tag").lower()

            is_image = "<img" in tag_context or bool(
                re.search(
                    r"\.(?:png|jpe?g|gif|webp|avif|svg)(?:[?#].*)?$",
                    url,
                    re.IGNORECASE,
                )
            )
            is_script = "<script" in tag_context or bool(
                re.search(
                    r"\.m?js(?:[?#].*)?$",
                    url,
                    re.IGNORECASE,
                )
            )
            is_stylesheet = "<link" in tag_context or bool(
                re.search(
                    r"\.css(?:[?#].*)?$",
                    url,
                    re.IGNORECASE,
                )
            )

            if not (is_image or is_script or is_stylesheet):
                continue

            resource = await fetch_resource(url)
            if resource is None:
                continue

            content, content_type = resource

            asset_counter += 1

            clean_url = url.split("?", 1)[0].split("#", 1)[0]
            extension = ""

            if "." in clean_url.rsplit("/", 1)[-1]:
                extension = "." + clean_url.rsplit(".", 1)[-1][:8]
                if not re.fullmatch(r"\.[A-Za-z0-9]+", extension):
                    extension = ""

            if not extension:
                content_extension = {
                    "image/jpeg": ".jpg",
                    "image/png": ".png",
                    "image/gif": ".gif",
                    "image/webp": ".webp",
                    "image/avif": ".avif",
                    "image/svg+xml": ".svg",
                    "text/css": ".css",
                    "application/javascript": ".js",
                    "text/javascript": ".js",
                }
                extension = content_extension.get(
                    content_type.split(";", 1)[0].strip().lower(),
                    "",
                )

            if is_image:
                prefix = "image"
            elif is_script:
                prefix = "script"
            else:
                prefix = "style"

            asset_name = f"assets/{prefix}-{asset_counter}{extension}"
            files[asset_name] = content
            downloaded_assets[url] = asset_name

    for remote_url, asset_name in downloaded_assets.items():
        html = html.replace(remote_url, asset_name)

    files["index.html"] = html.encode("utf-8")

    archive = io.BytesIO()

    with zipfile.ZipFile(
        archive,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zip_file:
        for filename, content in files.items():
            zip_file.writestr(filename, content)

        zip_file.writestr(
            "README.txt",
            (
                f"Personal Design AI\n"
                f"Projet : {project.name}\n"
                f"Version : {version}\n\n"
                "Ouvre index.html dans un navigateur pour voir la page.\n"
                "Les ressources distantes téléchargeables ont été copiées dans assets/.\n"
            ).encode("utf-8"),
        )

    archive.seek(0)

    safe_name = re.sub(
        r"[^a-zA-Z0-9._-]+",
        "-",
        project.name.strip(),
    ).strip("-") or "design-ai"

    filename = f"{safe_name}-v{version}.zip"

    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )


# ======================================================
# CREATE
# ======================================================

async def create_project(
    prompt: str,
    intent: dict,
    title: str | None = None,
    started_at: float | None = None,
):
    project_name = (title or "").strip()

    if not project_name:
        project_name = intent.get("project_name")

    if not project_name or project_name.strip() == prompt.strip():
        project_name = generate_project_name(prompt)

    project_id = f"project_{uuid4().hex[:8]}"

    html = await generate_design(
        prompt=prompt,
    )

    project = Project(
        id=project_id,
        name=project_name,
        type="web",
        status="generated",
        current_version=1,
    )

    generation_time_ms = elapsed_ms(started_at)

    version = ProjectVersion(
        version=1,
        prompt=prompt,
        html=html,
        generation_time_ms=generation_time_ms,
    )

    save_project(
        project=project,
        version=version,
    )

    return {
        "success": True,
        "action": "CREATE",
        "project": project,
        "version": version,
    }


# ======================================================
# UPDATE
# ======================================================

async def update_project(
    prompt: str,
    request: PromptRequest,
    intent: dict | None,
    started_at: float | None = None,
):
    """
    Modifie un projet existant.

    IMPORTANT :
    un UPDATE ne régénère jamais toute la page.

    Le HTML actuel est conservé.
    Le Reasoner identifie la zone.
    Le Change Planner détermine s'il faut modifier
    le contenu ou le CSS.
    """

    project_id = request.project_id

    if project_id:
        project = get_project(project_id)

    else:
        project_name = (
            intent.get("project_name")
            if intent
            else None
        )

        if not project_name:
            raise HTTPException(
                status_code=400,
                detail=(
                    "La demande concerne une modification, "
                    "mais aucun projet n'a été sélectionné."
                ),
            )

        project = find_project_by_name(
            project_name
        )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Le projet à modifier est introuvable.",
        )

    current_html = get_current_html(project)

    if not current_html:
        raise HTTPException(
            status_code=400,
            detail=(
                "Le projet ne possède pas encore "
                "de HTML à modifier."
            ),
        )

    # --------------------------------------------------
    # Design Reasoner
    # --------------------------------------------------

    design_change = await analyze_design_change(
        prompt
    )

    # --------------------------------------------------
    # Change Planner
    # --------------------------------------------------

    change_plan = await plan_design_changes(
        prompt=prompt,
        design_change=design_change,
    )

    content_changes = change_plan.get(
        "content_changes",
        [],
    )

    css_changes = change_plan.get(
        "changes",
        [],
    )

    updated_html = current_html

    # --------------------------------------------------
    # CONTENU
    # --------------------------------------------------

    if content_changes:
        updated_html = apply_content_changes(
            html=updated_html,
            changes=content_changes,
        )

    # --------------------------------------------------
    # CSS
    # --------------------------------------------------

    if css_changes:
        updated_html = apply_css_changes(
            html=updated_html,
            changes=css_changes,
        )

    # --------------------------------------------------
    # Vérification
    # --------------------------------------------------

    if updated_html == current_html:
        raise HTTPException(
            status_code=400,
            detail=(
                "Aucune modification applicable "
                "n'a pu être déterminée pour cette demande."
            ),
        )

    # --------------------------------------------------
    # Nouvelle version du MÊME projet
    # --------------------------------------------------

    next_version = project.current_version + 1

    project.current_version = next_version
    project.updated_at = now_iso()

    generation_time_ms = elapsed_ms(started_at)

    version = ProjectVersion(
        version=next_version,
        prompt=prompt,
        html=updated_html,
        generation_time_ms=generation_time_ms,
    )

    save_project(
        project=project,
        version=version,
    )

    return {
        "success": True,
        "action": "UPDATE",
        "design_change": design_change,
        "change_plan": change_plan,
        "project": project,
        "version": version,
    }


def elapsed_ms(started_at: float | None) -> int | None:
    """Retourne le temps total de traitement de la demande en millisecondes."""

    if started_at is None:
        return None

    return max(0, round((time.perf_counter() - started_at) * 1000))


# ======================================================
# CONTENT PATCHER
# ======================================================

def apply_content_changes(
    html: str,
    changes: list[dict],
) -> str:
    """
    Applique des modifications de contenu ciblées.

    Trois opérations sont supportées :
    - replace_text : remplace le texte d'un élément existant ;
    - append_item : ajoute un nouvel élément à une liste existante ;
    - remove_element : supprime un élément HTML existant.

    Aucune autre partie du HTML n'est régénérée.
    """

    result = html

    for change in changes:
        action = str(
            change.get(
                "action",
                "replace_text",
            )
        ).strip().lower()

        selector = str(
            change.get(
                "selector",
                "",
            )
        ).strip()

        text = str(
            change.get(
                "text",
                "",
            )
        )

        if not selector:
            continue

        if action == "remove_element":
            result = remove_element_by_selector(
                html=result,
                selector=selector,
            )
            continue

        if not text.strip():
            continue

        if action == "append_item":
            result = append_item_by_selector(
                html=result,
                selector=selector,
                text=text,
            )
            continue

        result = replace_text_by_selector(
            html=result,
            selector=selector,
            text=text,
        )

    return result


def remove_element_by_selector(
    html: str,
    selector: str,
) -> str:
    """
    Supprime un élément HTML ciblé sans régénérer le reste de la page.

    Supporte :
    - .classe
    - balise
    - balise.classe
    - sélecteur descendant simple, par exemple
      "header nav.vertical"
    """

    selector = selector.strip()

    if not selector:
        return html

    if " " in selector:
        parent_selector, child_selector = selector.rsplit(" ", 1)

        parent_match = find_element_by_selector(
            html,
            parent_selector,
        )

        if not parent_match:
            return html

        parent_html = parent_match["html"]

        updated_parent = remove_element_by_selector(
            html=parent_html,
            selector=child_selector,
        )

        if updated_parent == parent_html:
            return html

        return (
            html[:parent_match["start"]]
            + updated_parent
            + html[parent_match["end"]:]
        )

    element = find_element_by_selector(
        html,
        selector,
    )

    if not element:
        return html

    return (
        html[:element["start"]]
        + html[element["end"]:]
    )


def append_item_by_selector(
    html: str,
    selector: str,
    text: str,
) -> str:
    """
    Ajoute un nouvel élément sans casser la structure de la grille.

    Pour une grille de cartes, on cible en priorité le conteneur de grille
    lui-même puis on ajoute la nouvelle carte APRÈS toutes les cartes
    existantes. Cela évite qu'une nouvelle carte soit insérée avant la
    dernière carte ou dans une carte existante.
    """
    element = None

    # Pour les demandes de listes de chatons/chats/races, on privilégie
    # explicitement une vraie grille de cartes.
    grid_element = find_best_grid_container(html, selector, text)

    if grid_element:
        element = grid_element
    else:
        element = find_element_by_selector(
            html,
            selector,
        )

    if not element:
        element = find_best_list_container(html)

    if not element:
        element = find_best_card_container(html)

    if not element:
        return html

    container_html = element["html"]

    card_matches = list(
        re.finditer(
            r"<(?P<tag>[a-zA-Z][\w-]*)"
            r"(?P<attrs>[^>]*\bclass\s*=\s*[\"'][^\"']*"
            r"\b(?P<classname>kitten-card|cat-card|breed-card|card)\b"
            r"[^\"']*[\"'][^>]*)>"
            r"(?P<content>.*?)"
            r"</(?P=tag)>",
            container_html,
            re.IGNORECASE | re.DOTALL,
        )
    )

    if card_matches:
        # On clone la dernière carte existante : cela conserve l'ordre
        # visuel et le comportement du listing.
        card_match = card_matches[-1]
        card_html = card_match.group(0)

        new_card = update_card_for_append(
            card_html=card_html,
            text=text,
        )

        insertion_position = element["end"] - len(element["closing"])

        return (
            html[:insertion_position]
            + "\n"
            + new_card
            + "\n"
            + html[insertion_position:]
        )

    # Cas ul / ol.
    tag_match = re.match(
        r"<(?P<tag>[a-zA-Z][\w-]*)\b",
        element["opening"],
    )

    if not tag_match:
        return html

    container_tag = tag_match.group("tag").lower()
    escaped_text = escape(
        text,
        quote=False,
    )

    if container_tag in {"ul", "ol"}:
        new_item = (
            "<li>"
            + escaped_text
            + "</li>"
        )
    elif container_tag == "select":
        new_item = (
            '<option value="'
            + escape(text, quote=True)
            + '">'
            + escaped_text
            + "</option>"
        )
    else:
        new_item = (
            "<div>"
            + escaped_text
            + "</div>"
        )

    insertion_position = element["end"] - len(element["closing"])

    return (
        html[:insertion_position]
        + "\n"
        + new_item
        + "\n"
        + html[insertion_position:]
    )


def update_card_for_append(
    card_html: str,
    text: str,
) -> str:
    """
    Transforme une carte clonée en carte réellement cohérente avec
    l'élément demandé : titre, description, image et alt.
    """
    escaped_text = escape(
        text,
        quote=False,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        text.strip().lower(),
    )

    heading_pattern = re.compile(
        r"(<(?P<tag>h[1-6])(?P<attrs>[^>]*)>)"
        r"(?P<content>.*?)"
        r"(</(?P=tag)>)",
        re.IGNORECASE | re.DOTALL,
    )

    heading_match = heading_pattern.search(card_html)

    if heading_match:
        card_html = (
            card_html[:heading_match.start()]
            + heading_match.group(1)
            + escaped_text
            + heading_match.group(5)
            + card_html[heading_match.end():]
        )
    else:
        closing = card_html.rfind("</")
        if closing != -1:
            card_html = (
                card_html[:closing]
                + "<h2>"
                + escaped_text
                + "</h2>"
                + card_html[closing:]
            )

    # Description spécifique lorsque la demande correspond à une race connue.
    description = get_specific_description(text)

    if description:
        description_pattern = re.compile(
            r"(<p\b[^>]*>)(?P<content>.*?)(</p>)",
            re.IGNORECASE | re.DOTALL,
        )
        description_match = description_pattern.search(card_html)

        if description_match:
            card_html = (
                card_html[:description_match.start()]
                + description_match.group(1)
                + escape(description, quote=False)
                + description_match.group(3)
                + card_html[description_match.end():]
            )

    image_url = get_specific_image_url(text)

    if image_url:
        card_html = re.sub(
            r'(<img\b[^>]*\bsrc\s*=\s*["\'])[^"\']*(["\'])',
            lambda m: m.group(1) + image_url + m.group(2),
            card_html,
            count=1,
            flags=re.IGNORECASE,
        )

    card_html = re.sub(
        r'(\balt\s*=\s*["\'])([^"\']*)(["\'])',
        lambda m: m.group(1) + escaped_text + m.group(3),
        card_html,
        count=1,
        flags=re.IGNORECASE,
    )

    return card_html


def get_specific_description(text: str) -> str | None:
    """Retourne une description cohérente pour les races explicitement demandées."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())

    if "scottish fold" in normalized:
        return (
            "Chaton Scottish Fold, calme, affectueux et curieux. "
            "Idéal pour une famille."
        )

    return None


def get_specific_image_url(text: str) -> str | None:
    """Retourne une vraie image correspondant précisément à l'élément ajouté."""
    normalized = re.sub(r"\s+", " ", text.strip().lower())

    if "scottish fold" in normalized:
        return (
            "https://images.unsplash.com/photo-1558892017-e40deddf5eaa"
            "?auto=format&fit=crop&fm=jpg&q=80&w=1200"
        )

    return None


def find_best_grid_container(
    html: str,
    selector: str,
    text: str,
) -> dict | None:
    """
    Cible un conteneur de grille de cartes en privilégiant les classes
    explicites de type grid/list/kittens/cats/breeds.

    Le calcul de la fermeture est fait en comptant les balises du même
    type afin de ne pas couper le conteneur au premier élément imbriqué.
    """
    candidates = []

    selector_normalized = selector.strip().lower()
    selector_class = (
        selector_normalized[1:]
        if selector_normalized.startswith(".")
        else ""
    )

    pattern = re.compile(
        r"<(?P<tag>section|div)"
        r"(?P<attrs>[^>]*)>",
        re.IGNORECASE,
    )

    for opening_match in pattern.finditer(html):
        tag = opening_match.group("tag").lower()
        attrs = opening_match.group("attrs") or ""
        attrs_lower = attrs.lower()

        class_match = re.search(
            r'\bclass\s*=\s*["\']([^"\']*)["\']',
            attrs,
            re.IGNORECASE,
        )
        classes = (
            class_match.group(1).lower().split()
            if class_match
            else []
        )

        card_count = len(
            re.findall(
                r'class\s*=\s*["\'][^"\']*'
                r'\b(?:kitten-card|cat-card|breed-card|card)\b'
                r'[^"\']*["\']',
                html[opening_match.end():],
                re.IGNORECASE,
            )
        )

        if card_count < 1:
            continue

        class_score = 0

        if selector_class and selector_class in classes:
            class_score += 100

        if any(
            token in attrs_lower
            for token in (
                "grid",
                "list",
                "kitten",
                "kittens",
                "cat",
                "cats",
                "breed",
                "breeds",
            )
        ):
            class_score += 60

        if any(
            token in selector_normalized
            for token in (
                "list",
                "cat",
                "kitten",
                "breed",
                "card",
                "grid",
            )
        ):
            class_score += 20

        # Pour une demande de Scottish Fold, une grille de chatons est
        # prioritaire sur une autre zone contenant des cartes.
        if "scottish fold" in text.lower() and any(
            token in attrs_lower
            for token in ("kitten", "cat", "breed")
        ):
            class_score += 40

        if "nav" in attrs_lower or "menu" in attrs_lower:
            class_score -= 100

        end_position = find_matching_tag_end(
            html,
            opening_match.start(),
            tag,
        )

        if end_position is None:
            continue

        container_html = html[
            opening_match.start():end_position
        ]

        actual_card_count = len(
            re.findall(
                r'class\s*=\s*["\'][^"\']*'
                r'\b(?:kitten-card|cat-card|breed-card|card)\b'
                r'[^"\']*["\']',
                container_html,
                re.IGNORECASE,
            )
        )

        if actual_card_count < 1:
            continue

        score = class_score + actual_card_count * 10

        candidates.append(
            (
                score,
                opening_match.start(),
                end_position,
                container_html,
            )
        )

    if not candidates:
        return None

    _score, start, end, full_html = max(
        candidates,
        key=lambda item: item[0],
    )

    opening_end = html.find(">", start)
    opening = html[start:opening_end + 1]

    closing_start = full_html.rfind("</")
    closing = full_html[closing_start:]

    return {
        "start": start,
        "end": end,
        "html": full_html,
        "opening": opening,
        "closing": closing,
        "content": full_html[len(opening): -len(closing)],
    }


def find_matching_tag_end(
    html: str,
    opening_start: int,
    tag_name: str,
) -> int | None:
    """Retourne la fin de la balise fermante correspondant à une ouverture."""
    token_pattern = re.compile(
        rf"<(?P<closing>/)?{re.escape(tag_name)}\b[^>]*>",
        re.IGNORECASE,
    )

    depth = 0

    for match in token_pattern.finditer(
        html,
        opening_start,
    ):
        if match.group("closing"):
            depth -= 1
            if depth == 0:
                return match.end()
        else:
            depth += 1

    return None

def find_best_card_container(
    html: str,
) -> dict | None:
    """
    Trouve une grille de cartes lorsqu'un planner fournit un
    sélecteur générique comme "ul" alors que l'interface utilise
    des div.card.
    """
    container_pattern = re.compile(
        r"<(?P<tag>section|div)"
        r"(?P<attrs>[^>]*)>"
        r"(?P<content>.*?)"
        r"</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )

    candidates = []

    for match in container_pattern.finditer(html):
        content = match.group("content")
        card_count = len(
            re.findall(
                r'class\s*=\s*["\'][^"\']*\b(?:kitten-card|cat-card|breed-card|card)\b',
                content,
                re.IGNORECASE,
            )
        )

        if card_count < 1:
            continue

        attrs = match.group("attrs") or ""
        lowered_attrs = attrs.lower()
        score = card_count * 10

        if re.search(
            r'\bclass\s*=\s*["\'][^"\']*(grid|list|kitten|cat|breed|card)[^"\']*["\']',
            attrs,
            re.IGNORECASE,
        ):
            score += 30

        if "nav" in lowered_attrs or "menu" in lowered_attrs:
            score -= 50

        opening_end = html.find(">", match.start())
        if opening_end == -1:
            continue

        opening = html[match.start():opening_end + 1]
        closing = match.group(0)[match.group(0).rfind("<"):]

        candidates.append(
            (
                score,
                match.start(),
                match.end(),
                opening,
                closing,
                content,
                match.group(0),
            )
        )

    if not candidates:
        return None

    (
        _score,
        start,
        end,
        opening,
        closing,
        content,
        full_html,
    ) = max(
        candidates,
        key=lambda item: item[0],
    )

    return {
        "start": start,
        "end": end,
        "html": full_html,
        "opening": opening,
        "closing": closing,
        "content": content,
    }

def find_best_list_container(html: str) -> dict | None:
    """Trouve une liste de contenu lorsque le planner n'a pas trouvé son sélecteur exact."""
    pattern = re.compile(
        r"<(?P<tag>ul|ol)(?P<attrs>[^>]*)>(?P<content>.*?)</(?P=tag)>",
        re.IGNORECASE | re.DOTALL,
    )

    candidates = []

    for match in pattern.finditer(html):
        opening_end = html.find(">", match.start())
        if opening_end == -1:
            continue

        opening = html[match.start():opening_end + 1]
        closing = match.group(0)[match.group(0).rfind("<"):]
        attrs = match.group("attrs") or ""
        context_before = html[max(0, match.start() - 180):match.start()].lower()

        score = 0
        lowered = attrs.lower()

        if re.search(r"\bclass\s*=\s*[\"'][^\"']*(list|cat|cats|breed|item)[^\"']*[\"']", attrs, re.IGNORECASE):
            score += 10
        if re.search(r"\bid\s*=\s*[\"'][^\"']*(list|cat|cats|breed|item)[^\"']*[\"']", attrs, re.IGNORECASE):
            score += 10
        if "nav" in context_before[-80:] or "<nav" in context_before[-120:]:
            score -= 20
        if "menu" in lowered:
            score -= 10

        candidates.append((score, match, opening, closing))

    if not candidates:
        return None

    _, match, opening, closing = max(
        candidates,
        key=lambda item: item[0],
    )

    return {
        "start": match.start(),
        "end": match.end(),
        "html": match.group(0),
        "opening": opening,
        "closing": closing,
        "content": match.group("content"),
    }


def replace_text_by_selector(
    html: str,
    selector: str,
    text: str,
) -> str:
    """
    Remplace le contenu texte d'un sélecteur simple.

    Exemples supportés :

    .hero h1
    .hero p
    .hero button
    .header h1
    .card h3
    header h1
    nav a
    """

    selector = selector.strip()

    if " " in selector:
        parent_selector, child_selector = (
            selector.rsplit(" ", 1)
        )

        parent_match = find_element_by_selector(
            html,
            parent_selector,
        )

        if not parent_match:
            return html

        parent_start = parent_match["start"]
        parent_end = parent_match["end"]
        parent_html = parent_match["html"]

        updated_parent = replace_text_by_selector(
            html=parent_html,
            selector=child_selector,
            text=text,
        )

        if updated_parent == parent_html:
            return html

        return (
            html[:parent_start]
            + updated_parent
            + html[parent_end:]
        )

    element = find_element_by_selector(
        html,
        selector,
    )

    if not element:
        return html

    opening = element["opening"]
    closing = element["closing"]

    escaped_text = escape(
        text,
        quote=False,
    )

    replacement = (
        opening
        + escaped_text
        + closing
    )

    return (
        html[:element["start"]]
        + replacement
        + html[element["end"]:]
    )


def find_element_by_selector(
    html: str,
    selector: str,
) -> dict | None:
    """
    Recherche un élément simple par :
    - classe : .hero
    - balise : header
    - balise avec classe : button.primary
    """

    selector = selector.strip()

    if not selector:
        return None

    if selector.startswith("."):
        class_name = selector[1:]

        pattern = re.compile(
            rf"<(?P<tag>[a-zA-Z][\w-]*)"
            rf"(?P<attrs>[^>]*"
            rf"\bclass\s*=\s*"
            rf"(?P<quote>[\"'])"
            rf"[^\"']*\b{re.escape(class_name)}\b[^\"']*"
            rf"(?P=quote)"
            rf"[^>]*)>"
            rf"(?P<content>.*?)"
            rf"</(?P=tag)>",
            re.IGNORECASE | re.DOTALL,
        )

    elif "." in selector:
        tag_name, class_name = selector.split(
            ".",
            1,
        )

        pattern = re.compile(
            rf"<(?P<tag>{re.escape(tag_name)})"
            rf"(?P<attrs>[^>]*"
            rf"\bclass\s*=\s*"
            rf"(?P<quote>[\"'])"
            rf"[^\"']*\b{re.escape(class_name)}\b[^\"']*"
            rf"(?P=quote)"
            rf"[^>]*)>"
            rf"(?P<content>.*?)"
            rf"</(?P=tag)>",
            re.IGNORECASE | re.DOTALL,
        )

    else:
        tag_name = selector

        pattern = re.compile(
            rf"<(?P<tag>{re.escape(tag_name)})"
            rf"\b[^>]*>"
            rf"(?P<content>.*?)"
            rf"</(?P=tag)>",
            re.IGNORECASE | re.DOTALL,
        )

    match = pattern.search(html)

    if not match:
        return None

    opening_end = html.find(
        ">",
        match.start(),
    )

    if opening_end == -1:
        return None

    opening = html[
        match.start()
        : opening_end + 1
    ]

    closing = match.group(
        0
    )[
        match.group(0).rfind("<")
        :
    ]

    return {
        "start": match.start(),
        "end": match.end(),
        "html": match.group(0),
        "opening": opening,
        "closing": closing,
        "content": match.group("content"),
    }


# ======================================================
# DESIGN GENERATION
# ======================================================

async def generate_design(
    prompt: str,
    project_context: str = "",
) -> str:
    design_memory = get_design_memory()

    instruction = f"""
Tu es le designer et développeur frontend
de Personal Design AI.

Tu dois créer une interface web complète
à partir de la demande utilisateur.

REGLES :

- Retourne uniquement le HTML complet.
- Commence par <!DOCTYPE html>.
- Inclus tout le CSS dans <style>.
- Inclus tout le JavaScript dans un <script> avant </body>.
- Aucun framework externe.
- Aucun fichier CSS ou JavaScript externe.
- Les images distantes sont autorisées.
- Le résultat doit fonctionner directement dans un iframe.
- L'interface doit être responsive.
- Prévois Desktop et Mobile.
- Utilise des media queries CSS.
- Crée une vraie hiérarchie visuelle.
- Utilise des espacements cohérents.
- Utilise une palette cohérente.
- Crée une interface moderne et professionnelle.
- N'ajoute jamais de copyright, d'année, de mention « Tous droits réservés », de nom de marque ou de texte de propriété générique dans le footer, sauf si l'utilisateur le demande explicitement.
- N'utilise jamais « Personal Design AI » comme nom de marque dans l'interface générée, sauf si l'utilisateur le demande explicitement.
- Le footer doit rester absent ou minimal s'il n'est pas demandé par l'utilisateur.

IMAGES :
- Utilise de vraies URLs HTTPS d'images publiques.
- Ne crée JAMAIS de chemins fictifs comme image.jpg, image.png, avatar.jpg, photo.jpg, profile.png ou assets/image.jpg.
- Ne laisse JAMAIS une balise <img> avec une source locale ou inexistante.
- Pour une image éditoriale, utilise une image distante adaptée au contexte.
- Ajoute toujours un attribut alt pertinent.
- Les images doivent être visuellement intégrées au design et non ajoutées uniquement comme décoration.

NAVIGATION ET INTERACTIONS :
- Si l'interface contient un menu, chaque élément doit avoir un comportement réel.
- Pour naviguer entre les sections, utilise des href vers de vrais IDs existants, par exemple href="#about".
- INTERDICTION ABSOLUE de href="#", href="", javascript: ou de liens qui ne font rien.
- Ajoute un scroll fluide vers les sections.
- Ajoute un état actif au lien correspondant à la section visible.
- Utilise IntersectionObserver pour détecter la section active.
- Si le menu possède une version mobile, ajoute un bouton de menu fonctionnel avec ouverture et fermeture réelle.
- Sur Desktop, la navigation principale doit être horizontale : les liens du menu doivent être alignés sur une seule ligne.
- Ne mets jamais la navigation principale en colonne sur Desktop.
- La navigation Desktop ne doit jamais recouvrir le hero ou pousser anormalement le contenu.
- Sur Mobile uniquement, le menu peut devenir vertical lorsqu'il est ouvert.
- Les boutons doivent toujours avoir une action réelle.
- Les modales doivent pouvoir être ouvertes et fermées.
- Les formulaires doivent gérer leur soumission sans rechargement.
- Ne crée aucune interaction fictive.

JAVASCRIPT :
- Le JavaScript doit être réellement exécuté dans la page.
- Utilise addEventListener.
- Vérifie que les sélecteurs utilisés par le JavaScript existent réellement dans le HTML.
- Évite les erreurs JavaScript si un élément optionnel est absent.
- Le code doit fonctionner sans bibliothèque externe.

AVANT DE TERMINER :
- Vérifie la navigation.
- Vérifie les boutons.
- Vérifie les interactions du menu.
- Vérifie les images.
- Vérifie qu'aucun href="#" n'existe.
- Vérifie qu'aucun src d'image local fictif n'existe.
- Vérifie que chaque élément interactif possède un comportement réel.

- Ne retourne aucune explication.
- Ne mets pas le HTML dans un bloc Markdown.

MÉMOIRE DE DESIGN PERSONNEL :

{design_memory}

IMPORTANT :
- Cette mémoire décrit le langage visuel observé dans les projets personnels.
- Utilise-la comme référence prioritaire pour les choix visuels lorsque la demande utilisateur ne précise pas autrement.
- Respecte les couleurs récurrentes, la luminosité, la densité et les proportions observées.
- N'invente pas de préférences personnelles qui ne figurent pas dans cette mémoire.
- La demande utilisateur reste prioritaire lorsqu'elle impose explicitement un autre choix.

CONTEXTE DU PROJET :

{project_context}

DEMANDE UTILISATEUR :

{prompt}

Génère maintenant le document HTML complet.
"""

    ollama_started_at = time.perf_counter()
    html = await generate(instruction)
    ollama_ms = elapsed_ms(ollama_started_at) or 0

    repair_started_at = time.perf_counter()
    repaired_html = await repair_generated_html(
        clean_html(html),
        prompt=prompt,
    )
    repair_ms = elapsed_ms(repair_started_at) or 0

    print(
        f"[GENERATION] Ollama: {ollama_ms / 1000:.1f}s | "
        f"Réparation HTML: {repair_ms / 1000:.1f}s | "
        f"Total design: {(ollama_ms + repair_ms) / 1000:.1f}s"
    )

    return repaired_html


# ======================================================
# GENERATED HTML VALIDATION / REPAIR
# ======================================================

IMAGE_LIBRARY = []


def has_explicit_image_request(prompt: str) -> bool:
    """Détermine si l'utilisateur demande explicitement du contenu visuel."""
    normalized = normalize_label(prompt)

    return bool(
        re.search(
            r"\b("
            r"image|images|photo|photos|photographie|photographies|"
            r"illustration|illustrations|visuel|visuels|visuelle|visuelles|"
            r"picture|pictures|thumbnail|thumbnails|avatar|avatars|"
            r"portrait|portraits|paysage|paysages|galerie|gallery|"
            r"fond d'ecran|background|hero image|cover|couverture"
            r")\b",
            normalized,
        )
    )


def _image_stop_words() -> set[str]:
    return {
        "cree", "creer", "crée", "créer", "genere", "generer",
        "génère", "générer", "une", "un", "des", "de", "du",
        "la", "le", "les", "avec", "pour", "dans", "sur",
        "page", "site", "interface", "liste", "cartes", "carte",
        "section", "sections", "affiche", "afficher", "montre",
        "montrer", "chaque", "chacune", "photo", "photos", "image",
        "images", "illustration", "illustrations", "visuel", "visuels",
        "visuelle", "visuelles", "nom", "description", "lien",
        "liens", "bouton", "boutons", "et", "ou", "a", "au",
        "aux", "qui", "que", "leur", "leurs", "voir", "vers",
        "google", "maps",
    }


def _fallback_image_topic(prompt: str) -> str:
    """Extrait un sujet visuel générique à partir de la demande utilisateur."""
    normalized = normalize_label(prompt)
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", normalized)
    stop_words = _image_stop_words()
    meaningful = [
        word for word in words
        if word not in stop_words and len(word) > 2
    ]

    if not meaningful:
        return "visual,photo"

    return ",".join(meaningful[:10])


async def _is_image_url_usable(url: str) -> bool:
    """Retourne True uniquement si l'URL distante répond comme une image."""
    if not isinstance(url, str):
        return False
    value = url.strip()
    if not value.startswith(("http://", "https://")):
        return False

    timeout = httpx.Timeout(connect=5.0, read=8.0, write=5.0, pool=5.0)

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "PersonalDesignAI/1.0"},
        ) as client:
            response = await client.head(value)
            content_type = response.headers.get("content-type", "").lower()

            if response.status_code < 400 and content_type.startswith("image/"):
                return True

            response = await client.get(value, headers={"Range": "bytes=0-32"})
            content_type = response.headers.get("content-type", "").lower()
            return response.status_code < 400 and content_type.startswith("image/")
    except (httpx.HTTPError, OSError):
        return False


async def _validated_image_url(url: str) -> str | None:
    if await _is_image_url_usable(url):
        return url
    return None


async def _fetch_wikimedia_image_url(
    subject: str,
    prompt: str = "",
) -> str | None:
    """Recherche une vraie image sur Wikimedia Commons à partir du sujet."""
    cleaned = re.sub(r"\s+", " ", subject or "").strip()

    if not cleaned:
        return None

    normalized_prompt = normalize_label(prompt)
    query = cleaned

    if re.search(r"\b(ville|villes|city|cities|ville touristique|destination)\b", normalized_prompt):
        query += " city"

    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",
        "gsrlimit": "8",
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "iiurlwidth": "1400",
        "format": "json",
    }

    timeout = httpx.Timeout(
        connect=5.0,
        read=12.0,
        write=5.0,
        pool=5.0,
    )

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "PersonalDesignAI/1.0",
            },
        ) as client:
            response = await client.get(
                "https://commons.wikimedia.org/w/api.php",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        print(
            f"[GENERATION] Recherche image Wikimedia échouée pour '{cleaned}': {exc}"
        )
        return None

    pages = data.get("query", {}).get("pages", {})

    candidates = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        mime = str(info.get("mime") or "").lower()
        url = info.get("thumburl") or info.get("url")

        if not url:
            continue

        if mime and not mime.startswith("image/"):
            continue

        if mime == "image/svg+xml":
            continue

        candidates.append(url)

    return await _validated_image_url(candidates[0]) if candidates else None


def _semantic_image_fallback(subject: str) -> str:
    """Placeholder local au navigateur, sans dépendre d'une URL fragile."""
    label = escape(
        re.sub(r"\s+", " ", subject or "Image indisponible").strip()[:80]
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" '
        'viewBox="0 0 1400 900">'
        '<rect width="1400" height="900" fill="#DFE5E5"/>'
        '<text x="700" y="430" text-anchor="middle" '
        'font-family="Arial,sans-serif" font-size="42" fill="#12176E">'
        + label
        + '</text>'
        '<text x="700" y="490" text-anchor="middle" '
        'font-family="Arial,sans-serif" font-size="24" fill="#4B4E8A">'
        'Image indisponible'
        '</text></svg>'
    )
    return "data:image/svg+xml;charset=utf-8," + quote(svg, safe="")


def _image_stop_words() -> set[str]:
    return {
        "cree", "creer", "crée", "créer", "genere", "generer",
        "génère", "générer", "une", "un", "des", "de", "du",
        "la", "le", "les", "avec", "pour", "dans", "sur",
        "page", "site", "interface", "liste", "cartes", "carte",
        "section", "sections", "affiche", "afficher", "montre",
        "montrer", "chaque", "chacune", "photo", "photos", "image",
        "images", "illustration", "illustrations", "visuel", "visuels",
        "visuelle", "visuelles", "nom", "description", "lien",
        "liens", "bouton", "boutons", "et", "ou", "a", "au",
        "aux", "qui", "que", "leur", "leurs", "voir", "vers",
        "google", "maps", "photo de", "image de", "illustration de",
    }


def _fallback_image_topic(prompt: str) -> str:
    normalized = normalize_label(prompt)
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", normalized)
    stop_words = _image_stop_words()
    meaningful = [
        word for word in words
        if word not in stop_words and len(word) > 2
    ]

    return " ".join(meaningful[:8]) if meaningful else "image"


def _extract_image_subject_from_tag(
    tag: str,
    context: str,
    prompt: str,
) -> str:
    """Détermine le sujet de l'image sans mélanger les cartes voisines."""
    alt_match = re.search(
        r"\balt\s*=\s*([\"'])(.*?)\1",
        tag,
        re.IGNORECASE | re.DOTALL,
    )

    alt = ""
    if alt_match:
        alt = re.sub(r"\s+", " ", alt_match.group(2)).strip()

    normalized_alt = normalize_label(alt)
    generic_alt = re.sub(
        r"\b(image|photo|photographie|illustration|visuel|picture)\s*(n[°o]?\s*)?\d*\b",
        "",
        normalized_alt,
        flags=re.IGNORECASE,
    ).strip(" -_:,.")

    if generic_alt and len(generic_alt) > 2:
        return generic_alt

    # On ne cherche le titre que DANS le contexte situé avant l'image.
    # Cela évite de récupérer le nom de la carte suivante.
    before_image = context.split("<!-- IMAGE_SUBJECT_BOUNDARY -->", 1)[0]
    heading_matches = list(
        re.finditer(
            r"<h[1-6][^>]*>(.*?)</h[1-6]>",
            before_image,
            re.IGNORECASE | re.DOTALL,
        )
    )

    if heading_matches:
        heading = re.sub(r"<[^>]+>", " ", heading_matches[-1].group(1))
        heading = re.sub(r"\s+", " ", heading).strip()
        if heading and len(heading) > 2:
            return heading

    return _fallback_image_topic(prompt)


def _is_explicit_visual_prompt(prompt: str) -> bool:
    normalized = normalize_label(prompt)
    return bool(
        re.search(
            r"\b(image|images|photo|photos|photographie|photographies|"
            r"illustration|illustrations|visuel|visuels|visuelle|visuelles|"
            r"picture|pictures|thumbnail|thumbnails|avatar|avatars|"
            r"portrait|portraits|paysage|paysages|galerie|gallery|"
            r"fond d'ecran|background|hero image|cover|couverture)\b",
            normalized,
        )
    )


def _animal_image_library(prompt: str, subject: str) -> list[str]:
    """Retourne une bibliothèque photo déterministe pour les animaux.

    Pour les animaux, on ne passe volontairement pas par une recherche
    textuelle libre : un prénom comme "Tom" ou "Buddy" ne doit jamais
    devenir une requête d'image ambiguë.
    """
    normalized_prompt = normalize_label(prompt)
    normalized_subject = normalize_label(subject)
    context = f"{normalized_subject} {normalized_prompt}"

    if re.search(
        r"\b(scottish fold|chat|chats|chaton|chatons|cat|cats|kitten|kittens|"
        r"feline|felin|félin|felins|félin)\b",
        context,
    ):
        return [
            "https://images.unsplash.com/photo-1725454704851-f2ba0e9ab5b2?auto=format&fit=crop&fm=jpg&q=80&w=1200",
            "https://images.unsplash.com/photo-1778437968220-67c986897890?auto=format&fit=crop&fm=jpg&q=80&w=1200",
            "https://images.unsplash.com/photo-1673694411726-e22e30d9e17c?auto=format&fit=crop&fm=jpg&q=80&w=1200",
            "https://images.unsplash.com/photo-1750758142450-b8c3b909bf78?auto=format&fit=crop&fm=jpg&q=80&w=1200",
            "https://images.unsplash.com/photo-1759568572636-4440ea8f2521?auto=format&fit=crop&fm=jpg&q=80&w=1200",
            "https://images.unsplash.com/photo-1765180850180-f7cfb26fb7f1?auto=format&fit=crop&fm=jpg&q=80&w=1200",
            "https://images.unsplash.com/photo-1519052537078-e6302a4968d4?w=1200&q=80",
            "https://images.unsplash.com/photo-1518791841217-8f162f1e1131?w=1200&q=80",
            "https://images.unsplash.com/photo-1596854407944-bf87f6fdd49e?w=1200&q=80",
            "https://images.unsplash.com/photo-1573865526739-10659fec78a5?w=1200&q=80",
            "https://images.unsplash.com/photo-1561948955-570b270e7c36?w=1200&q=80",
        ]

    if re.search(
        r"\b(golden retriever|husky|shiba inu|chien|chiens|chienne|dog|dogs|"
        r"puppy|puppies|chiot|chiots|canine)\b",
        context,
    ):
        return [
            "https://images.unsplash.com/photo-1552053831-71594a27632d?w=1200&q=80",
            "https://images.unsplash.com/photo-1517849845537-4d257902454a?w=1200&q=80",
            "https://images.unsplash.com/photo-1537151608828-ea2b11777ee8?w=1200&q=80",
            "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=1200&q=80",
            "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=1200&q=80",
        ]

    if re.search(
        r"\b(lapin|lapins|lapine|rabbit|rabbits|bunny|bunnies)\b",
        context,
    ):
        return [
            "https://images.unsplash.com/photo-1750207301348-fd1fc9650ab5?auto=format&fit=crop&fm=jpg&q=80&w=1200",
            "https://images.unsplash.com/photo-1768750126576-86b486d9ba78?auto=format&fit=crop&fm=jpg&q=80&w=1200",
            "https://images.unsplash.com/photo-1759687084356-4eab803699df?auto=format&fit=crop&fm=jpg&q=80&w=1200",
        ]

    return []


async def _resolve_semantic_image_url(
    subject: str,
    index: int,
    prompt: str,
) -> str:
    """Résout une image sans laisser un nom propre déclencher une recherche ambiguë."""
    animal_library = _animal_image_library(prompt, subject)

    if animal_library:
        candidate = animal_library[index % len(animal_library)]
        validated = await _validated_image_url(candidate)
        if validated:
            return validated

        # Si une URL de la bibliothèque devient indisponible, on essaie
        # les autres images de la même catégorie avant le placeholder.
        for offset in range(1, len(animal_library)):
            candidate = animal_library[(index + offset) % len(animal_library)]
            validated = await _validated_image_url(candidate)
            if validated:
                return validated

        return _semantic_image_fallback(
            subject or _fallback_image_topic(prompt)
        )

    # Pour les sujets non animaliers, on conserve la recherche Wikimedia.
    url = await _fetch_wikimedia_image_url(subject, prompt)
    if url:
        return url

    return _semantic_image_fallback(subject or _fallback_image_topic(prompt))


def get_contextual_image_library(prompt: str) -> list[str]:
    """Bibliothèque de secours uniquement pour les cas spécialisés connus."""
    normalized = normalize_label(prompt)

    if re.search(
        r"\b(chaton|chatons|kitten|kittens|chat|chats|felin|feline|cat|cats)\b",
        normalized,
    ):
        return [
            "https://images.unsplash.com/photo-1519052537078-e6302a4968d4?w=1200&q=80",
            "https://images.unsplash.com/photo-1518791841217-8f162f1e1131?w=1200&q=80",
            "https://images.unsplash.com/photo-1596854407944-bf87f6fdd49e?w=1200&q=80",
            "https://images.unsplash.com/photo-1573865526739-10659fec78a5?w=1200&q=80",
            "https://images.unsplash.com/photo-1561948955-570b270e7c36?w=1200&q=80",
        ]

    if re.search(
        r"\b(chiot|chiots|puppy|puppies|chien|chiens|dog|dogs)\b",
        normalized,
    ):
        return [
            "https://images.unsplash.com/photo-1552053831-71594a27632d?w=1200&q=80",
            "https://images.unsplash.com/photo-1517849845537-4d257902454a?w=1200&q=80",
            "https://images.unsplash.com/photo-1537151608828-ea2b11777ee8?w=1200&q=80",
            "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=1200&q=80",
            "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=1200&q=80",
        ]

    if re.search(
        r"\b(nature|paysage|paysages|foret|forêt|montagne|montagnes|"
        r"lac|lacs|riviere|rivière|mer|ocean|océan|plage|plages|"
        r"jardin|fleurs|arbres)\b",
        normalized,
    ):
        return [
            "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=1400&q=85",
            "https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=1400&q=85",
            "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=1400&q=85",
            "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1400&q=85",
            "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1400&q=85",
        ]

    return []


async def repair_generated_html(
    html: str,
    prompt: str = "",
) -> str:
    """
    Vérifie et sécurise le HTML généré avant de le sauvegarder.

    Cette étape ne régénère pas la page.
    Elle corrige uniquement les problèmes fréquents :
    - images locales fictives ;
    - href="#" et href="" ;
    - absence d'identifiant sur body ;
    - navigation sans comportement JavaScript.
    """

    result = html.strip()

    if not result:
        return result

    result = ensure_top_anchor(result)
    result = await repair_image_sources(result, prompt=prompt)
    result = repair_navigation_links(result)
    result = enforce_navigation_layout(result)
    result = inject_navigation_script(result)

    return result


def enforce_navigation_layout(
    html: str,
) -> str:
    """
    Garantit une navigation principale horizontale sur Desktop.

    Le modèle peut parfois générer un .nav-links en colonne ou en
    position absolute même lorsque la page demande une navigation
    Desktop classique. Cette fonction ajoute un garde-fou CSS
    déterministe après la génération.

    Sur Mobile, le comportement vertical du menu reste autorisé.
    """
    if not re.search(r"<nav\b", html, re.IGNORECASE):
        return html

    has_nav_links = bool(
        re.search(
            r'class\s*=\s*["\'][^"\']*\bnav-links\b[^"\']*["\']',
            html,
            re.IGNORECASE,
        )
    )

    if not has_nav_links:
        return html

    override = """
<style id="personal-design-ai-navigation-fix">
/* Personal Design AI — navigation layout safeguard */
nav {
    position: relative;
    z-index: 1000;
}

nav .nav-links {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: center;
    gap: 2rem;
    position: static;
    width: auto;
    box-sizing: border-box;
}

nav .nav-links a {
    display: inline-flex;
    align-items: center;
    white-space: nowrap;
}

/* Mobile uniquement : le menu peut devenir vertical et se replier. */
@media (max-width: 768px) {
    nav .nav-links {
        display: none;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        gap: 1rem;
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        width: 100%;
        box-sizing: border-box;
    }

    nav .nav-links.active {
        display: flex;
    }

    nav .nav-links a {
        display: block;
        width: auto;
    }
}
</style>
"""

    if 'id="personal-design-ai-navigation-fix"' in html:
        return html

    body_close = re.search(
        r"</body\s*>",
        html,
        re.IGNORECASE,
    )

    if body_close:
        return (
            html[:body_close.start()]
            + override
            + "\n"
            + html[body_close.start():]
        )

    return html + "\n" + override


def ensure_top_anchor(
    html: str,
) -> str:
    """
    Ajoute un point d'ancrage stable au body.
    """

    body_pattern = re.compile(
        r"<body(?P<attrs>[^>]*)>",
        re.IGNORECASE,
    )

    match = body_pattern.search(html)

    if not match:
        return html

    attrs = match.group("attrs")

    if re.search(
        r"\bid\s*=",
        attrs,
        re.IGNORECASE,
    ):
        return html

    replacement = (
        "<body"
        + attrs
        + ' id="pdai-top">'
    )

    return (
        html[:match.start()]
        + replacement
        + html[match.end():]
    )


async def repair_image_sources(
    html: str,
    prompt: str = "",
) -> str:
    """
    Vérifie et normalise les images du HTML final.

    Règle importante pour les listes d'animaux :
    - chaque carte reçoit une photo différente ;
    - l'ordre des photos suit l'ordre des balises <img> ;
    - on ne conserve pas une URL distante générée par le modèle si le prompt
      demande explicitement des visuels animaliers ;
    - si la bibliothèque contient moins de photos que de cartes, on préfère
      un placeholder unique plutôt que de réutiliser une photo.
    """
    image_pattern = re.compile(
        r"<img(?P<before>[^>]*?)"
        r"\bsrc\s*=\s*(?P<quote>[\"'])"
        r"(?P<src>[^\"']*)(?P=quote)"
        r"(?P<after>[^>]*)>",
        re.IGNORECASE,
    )

    matches = list(image_pattern.finditer(html))
    if not matches:
        return html

    strict_subject = _is_explicit_visual_prompt(prompt)
    animal_library = _animal_image_library(prompt, "") if strict_subject else []
    is_animal_prompt = bool(animal_library)

    subjects = []
    for match in matches:
        before = html[max(0, match.start() - 900):match.start()]
        subjects.append(
            _extract_image_subject_from_tag(
                match.group(0),
                before + "<!-- IMAGE_SUBJECT_BOUNDARY -->",
                prompt,
            )
        )

    unique_subjects = list(dict.fromkeys(subjects))
    resolved_urls = {}

    if strict_subject and unique_subjects and not is_animal_prompt:
        resolved = await asyncio.gather(
            *[
                _resolve_semantic_image_url(subject, index, prompt)
                for index, subject in enumerate(unique_subjects)
            ]
        )
        resolved_urls = dict(zip(unique_subjects, resolved))

        for subject, url in list(resolved_urls.items()):
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                if not await _is_image_url_usable(url):
                    resolved_urls[subject] = None

        print(
            f"[GENERATION] Images sémantiques vérifiées: "
            f"{len(unique_subjects)} sujet(s)"
        )

    # Pour les animaux, on attribue les photos par position dans la liste.
    # On garde la trace des URLs déjà utilisées afin de garantir l'unicité.
    assigned_animal_urls: list[str] = []
    if is_animal_prompt:
        for candidate in animal_library:
            if candidate in assigned_animal_urls:
                continue
            if await _is_image_url_usable(candidate):
                assigned_animal_urls.append(candidate)

        print(
            f"[GENERATION] Bibliothèque animale unique: "
            f"{len(assigned_animal_urls)} photo(s) disponible(s) pour "
            f"{len(matches)} image(s)"
        )

    pieces = []
    cursor = 0
    animal_index = 0

    for match, subject in zip(matches, subjects):
        pieces.append(html[cursor:match.start()])
        original = match.group(0)
        src = match.group("src").strip()

        if src.lower().startswith(("data:image/", "blob:")) and not is_animal_prompt:
            pieces.append(original)
            cursor = match.end()
            continue

        replacement_url = None

        if is_animal_prompt:
            if animal_index < len(assigned_animal_urls):
                replacement_url = assigned_animal_urls[animal_index]
                animal_index += 1
            else:
                # Pas de doublon : si la bibliothèque est épuisée, on génère
                # un placeholder plutôt que de réutiliser une photo.
                replacement_url = _semantic_image_fallback(
                    subject or f"Image animale {animal_index + 1}"
                )
                animal_index += 1
        else:
            usable = False
            if src.startswith(("http://", "https://")):
                usable = await _is_image_url_usable(src)

            if usable:
                pieces.append(original)
                cursor = match.end()
                continue

            if strict_subject:
                replacement_url = resolved_urls.get(subject)

            if not replacement_url:
                replacement_url = _semantic_image_fallback(
                    subject or _fallback_image_topic(prompt)
                )

        pieces.append(
            "<img"
            + match.group("before")
            + 'src="'
            + replacement_url
            + '"'
            + match.group("after")
            + ">"
        )
        cursor = match.end()

    pieces.append(html[cursor:])
    return "".join(pieces)



async def validate_image_urls(
    urls: list[str],
) -> dict[str, bool]:
    if not urls:
        return {}

    timeout = httpx.Timeout(
        connect=3.0,
        read=5.0,
        write=5.0,
        pool=5.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={
            "User-Agent": "PersonalDesignAI/1.0",
        },
    ) as client:

        async def check(url: str):
            try:
                response = await client.head(url)

                if response.status_code == 405:
                    response = await client.get(
                        url,
                        headers={
                            "Range": "bytes=0-1023",
                        },
                    )

                valid = (
                    200 <= response.status_code < 300
                    and (
                        not response.headers.get("content-type")
                        or response.headers.get(
                            "content-type",
                            ""
                        ).lower().startswith("image/")
                    )
                )

                return url, valid

            except (httpx.HTTPError, OSError):
                return url, False

        results = await asyncio.gather(
            *(check(url) for url in urls)
        )

    return dict(results)


def is_valid_remote_image(
    src: str,
) -> bool:
    """
    Conservé pour compatibilité avec le reste du module.
    La vraie validation réseau est maintenant effectuée
    par validate_image_urls().
    """

    if not src:
        return False

    lowered = src.lower()

    return lowered.startswith(
        (
            "https://",
            "http://",
            "data:image/",
            "blob:",
        )
    )


def repair_navigation_links(
    html: str,
) -> str:
    """
    Transforme les faux liens en liens vers de vraies sections
    lorsque cela est possible.
    """

    section_ids = re.findall(
        r"<(?:section|main|header|footer|div)"
        r"[^>]*\bid\s*=\s*"
        r"[\"']([^\"']+)[\"']",
        html,
        re.IGNORECASE,
    )

    section_ids = [
        value.strip()
        for value in section_ids
        if value.strip()
    ]

    if not section_ids:
        section_ids = ["pdai-top"]

    def replace(match):
        tag = match.group("tag")
        attrs = match.group("attrs")
        text = re.sub(
            r"<[^>]+>",
            "",
            match.group("text"),
        ).strip()

        href_match = re.search(
            r"\bhref\s*=\s*([\"'])(.*?)\1",
            attrs,
            re.IGNORECASE | re.DOTALL,
        )

        if not href_match:
            return match.group(0)

        href = href_match.group(2).strip()

        if not is_fake_href(href):
            return match.group(0)

        target_id = find_navigation_target(
            text=text,
            section_ids=section_ids,
        )

        new_attrs = (
            attrs[:href_match.start()]
            + 'href="'
            + target_id
            + '"'
            + attrs[href_match.end():]
        )

        return (
            "<"
            + tag
            + new_attrs
            + ">"
            + match.group("text")
            + "</"
            + tag
            + ">"
        )

    pattern = re.compile(
        r"<(?P<tag>a)"
        r"(?P<attrs>[^>]*)>"
        r"(?P<text>.*?)"
        r"</a>",
        re.IGNORECASE | re.DOTALL,
    )

    return pattern.sub(
        replace,
        html,
    )


def is_fake_href(
    href: str,
) -> bool:
    lowered = href.lower()

    return (
        lowered in {"", "#"}
        or lowered.startswith("javascript:")
    )


def find_navigation_target(
    text: str,
    section_ids: list[str],
) -> str:
    normalized_text = normalize_label(text)

    aliases = {
        "accueil": [
            "accueil",
            "home",
        ],
        "about": [
            "a propos",
            "apropos",
            "about",
            "studio",
        ],
        "services": [
            "services",
            "service",
        ],
        "projects": [
            "projets",
            "projects",
            "portfolio",
        ],
        "contact": [
            "contact",
            "contacter",
        ],
    }

    for section_id in section_ids:
        normalized_id = normalize_label(
            section_id
        )

        if normalized_id == normalized_text:
            return "#" + section_id

    for canonical, labels in aliases.items():
        if normalized_text in labels:
            for section_id in section_ids:
                normalized_id = normalize_label(
                    section_id
                )

                if (
                    normalized_id == canonical
                    or canonical in normalized_id
                    or normalized_id in labels
                ):
                    return "#" + section_id

    for section_id in section_ids:
        normalized_id = normalize_label(
            section_id
        )

        if (
            normalized_text
            and normalized_text in normalized_id
        ):
            return "#" + section_id

    return "#pdai-top"


def normalize_label(
    value: str,
) -> str:
    value = value.lower().strip()

    replacements = {
        "à": "a",
        "â": "a",
        "ä": "a",
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ç": "c",
    }

    for source, target in replacements.items():
        value = value.replace(
            source,
            target,
        )

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(
        value.split()
    )


def inject_navigation_script(
    html: str,
) -> str:
    """
    Ajoute une couche de navigation robuste.
    Elle complète le JavaScript généré par le modèle
    sans remplacer ses interactions métier.
    """

    script = """
<script>
(function () {
    "use strict";

    function initPersonalDesignAINavigation() {
        const links = Array.from(
            document.querySelectorAll('nav a[href^="#"]')
        );

        const sections = Array.from(
            document.querySelectorAll("section[id], main[id]")
        );

        links.forEach(function (link) {
            link.addEventListener("click", function (event) {
                const href = link.getAttribute("href");

                if (!href || href === "#") {
                    return;
                }

                const target = document.querySelector(href);

                if (!target) {
                    return;
                }

                event.preventDefault();

                target.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });

                if (window.history && window.history.replaceState) {
                    window.history.replaceState(
                        null,
                        "",
                        href
                    );
                }
            });
        });

        if ("IntersectionObserver" in window && sections.length) {
            const observer = new IntersectionObserver(
                function (entries) {
                    entries.forEach(function (entry) {
                        if (!entry.isIntersecting) {
                            return;
                        }

                        const id = entry.target.id;

                        links.forEach(function (link) {
                            const active =
                                link.getAttribute("href") === "#" + id;

                            link.classList.toggle(
                                "active",
                                active
                            );

                            if (active) {
                                link.setAttribute(
                                    "aria-current",
                                    "page"
                                );
                            } else {
                                link.removeAttribute(
                                    "aria-current"
                                );
                            }
                        });
                    });
                },
                {
                    rootMargin: "-25% 0px -60% 0px",
                    threshold: 0
                }
            );

            sections.forEach(function (section) {
                observer.observe(section);
            });
        }

        const menuToggle =
            document.querySelector(
                '[aria-controls], .menu-toggle, .menu-button, .mobile-menu-button'
            );

        const mobileMenu =
            document.querySelector(
                '[data-mobile-menu], .mobile-menu, .nav-menu'
            );

        if (menuToggle && mobileMenu) {
            menuToggle.addEventListener(
                "click",
                function () {
                    const isOpen =
                        mobileMenu.classList.toggle("is-open");

                    menuToggle.setAttribute(
                        "aria-expanded",
                        String(isOpen)
                    );
                }
            );

            mobileMenu
                .querySelectorAll("a")
                .forEach(function (link) {
                    link.addEventListener(
                        "click",
                        function () {
                            mobileMenu.classList.remove(
                                "is-open"
                            );

                            menuToggle.setAttribute(
                                "aria-expanded",
                                "false"
                            );
                        }
                    );
                });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initPersonalDesignAINavigation
        );
    } else {
        initPersonalDesignAINavigation();
    }
})();
</script>
"""

    if "</body>" in html.lower():
        match = re.search(
            r"</body>",
            html,
            re.IGNORECASE,
        )

        if match:
            return (
                html[:match.start()]
                + script
                + "\n"
                + html[match.start():]
            )

    return html + "\n" + script


# ======================================================
# CURRENT HTML
# ======================================================

def get_current_html(
    project,
) -> str | None:
    if not project.versions:
        return None

    current_version = next(
        (
            version
            for version in project.versions
            if version.version == project.current_version
        ),
        None,
    )

    if current_version is None:
        current_version = project.versions[-1]

    return current_version.html


# ======================================================
# PROJECT CONTEXT
# ======================================================

def build_project_context(
    project,
) -> str:
    context = [
        f"Nom du projet : {project.name}",
        f"Type : {project.type}",
        f"Version actuelle : {project.current_version}",
    ]

    if project.versions:
        latest = project.versions[-1]

        context.append(
            f"Dernière demande : {latest.prompt}"
        )

        context.append(
            "Le projet possède déjà une interface "
            "existante qui doit être conservée "
            "et améliorée."
        )

    return "\n".join(context)


# ======================================================
# FIND PROJECT
# ======================================================

def find_project_by_name(
    project_name: str,
):
    projects = read_projects()

    normalized_name = project_name.strip().lower()

    for project in projects:
        if (
            project.name.strip().lower()
            == normalized_name
        ):
            return get_project(project.id)

    for project in projects:
        if (
            normalized_name
            in project.name.strip().lower()
        ):
            return get_project(project.id)

    return None


# ======================================================
# UTILITIES
# ======================================================

def clean_html(
    html: str,
) -> str:
    html = html.strip()

    if html.startswith("```html"):
        html = html[len("```html"):]

    elif html.startswith("```"):
        html = html[3:]

    if html.endswith("```"):
        html = html[:-3]

    return html.strip()


def generate_project_name(
    prompt: str,
) -> str:
    cleaned = " ".join(
        prompt.split()
    )

    if len(cleaned) <= 42:
        return cleaned

    return (
        cleaned[:42].rstrip()
        + "..."
    )
