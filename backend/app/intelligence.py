import json
import re

from backend.app.ollama import generate


ALLOWED_ACTIONS = {
    "CREATE",
    "UPDATE",
    "DELETE",
}


async def detect_intent(prompt: str) -> dict:
    """
    Analyse une demande utilisateur et identifie son intention.

    Le modèle ne réalise aucune action.
    Il retourne uniquement une intention structurée.
    """

    instruction = f"""
Tu es le moteur d'intention d'une application appelée Personal Design AI.

Ta seule mission est d'identifier l'intention de l'utilisateur.

Les seules actions autorisées sont :

CREATE
UPDATE
DELETE

Règles :

- CREATE = créer un nouveau projet ou une nouvelle interface.
- UPDATE = modifier un projet existant.
- DELETE = supprimer un projet existant.
- Ne réalise jamais l'action.
- Ne génère aucune explication.
- Retourne uniquement un JSON valide.
- Si aucun nom de projet n'est explicitement identifiable, utilise null.

Format obligatoire :

{{
    "action": "CREATE",
    "project_name": null
}}

Demande utilisateur :

{prompt}
"""

    response = await generate(instruction)

    parsed = _extract_json(response)

    if not parsed:
        return {
            "action": "CREATE",
            "project_name": None,
        }

    action = str(parsed.get("action", "CREATE")).upper()

    if action not in ALLOWED_ACTIONS:
        action = "CREATE"

    project_name = parsed.get("project_name")

    if project_name is not None:
        project_name = str(project_name).strip() or None

    return {
        "action": action,
        "project_name": project_name,
    }


def _extract_json(response: str) -> dict | None:
    """
    Extrait le premier objet JSON présent dans la réponse du modèle.
    """

    response = response.strip()

    try:
        result = json.loads(response)

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        pass

    match = re.search(
        r"\{.*?\}",
        response,
        re.DOTALL,
    )

    if not match:
        return None

    try:
        result = json.loads(match.group())

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        return None

    return None