import json
import re

from backend.app.ollama import generate


ALLOWED_PROPERTIES = {
    "margin",
    "padding",
    "gap",
    "font-family",
    "font-size",
    "font-weight",
    "line-height",
    "letter-spacing",
    "color",
    "background-color",
    "border-color",
    "width",
    "height",
    "max-width",
    "max-height",
    "justify-content",
    "align-items",
}


async def plan_design_changes(
    prompt: str,
    design_change: dict,
) -> dict:
    """
    Transforme l'analyse du Design Reasoner
    en plan de modifications ciblées.

    Le planner peut produire :
    - des modifications CSS ;
    - des modifications de contenu HTML ;
    - la suppression ciblée d'éléments HTML.

    Il ne génère jamais de page complète.
    """

    target = design_change.get(
        "target",
        "global",
    )

    changes = design_change.get(
        "changes",
        [],
    )

    scope = design_change.get(
        "scope",
        "related_elements",
    )

    change_type = design_change.get(
        "change_type",
        "style",
    )

    removal_words = (
        "supprime", "supprimer", "supprimez", "retire", "retirer", "retirez",
        "enlève", "enlever", "enlevez", "remove", "delete", "deleting",
    )
    prompt_lower = prompt.lower()
    if any(word in prompt_lower for word in removal_words):
        navigation_targets = {
            "navigation", "nav", "menu", "menus", "navbar",
            "navigation-menu", "header-menu",
        }
        if str(target).strip().lower() in navigation_targets:
            return {
                "target": str(target).strip(),
                "scope": str(scope).strip(),
                "changes": [],
                "content_changes": [
                    {
                        "action": "remove_element",
                        "selector": "nav",
                        "text": "",
                        "instruction": prompt.strip(),
                    }
                ],
            }

    changes_text = "\n".join(
        f"- {change}"
        for change in changes
    )

    instruction = f"""
Tu es le Change Planner de Personal Design AI.

Transforme la demande utilisateur en modifications
ciblées sur une interface HTML EXISTANTE.

Tu ne génères jamais de HTML complet.

ZONE CIBLE :

{target}

PÉRIMÈTRE :

{scope}

TYPE :

{change_type}

ANALYSE DU REASONER :

{changes_text}

DEMANDE UTILISATEUR :

{prompt}

RÈGLE ABSOLUE :

Ne propose que des changements directement
justifiés par la demande.

Si l'utilisateur demande un changement de texte,
utilise content_changes.

Si l'utilisateur demande d'ajouter un nouvel élément
dans une liste, utilise content_changes avec
"action": "append_item".

Exemple :

Ajouter "Scottish Fold" dans une liste de chats
doit produire :

"content_changes": [
    {{
        "action": "append_item",
        "selector": "ul",
        "text": "Scottish Fold",
        "instruction": "ajouter un nouvel élément à la liste"
    }}
]

Pour une liste déjà identifiée par une classe, utilise
le sélecteur existant, par exemple ".cat-list",
".cats-list", ".breed-list" ou ".list".

IMPORTANT :
- Pour "ajoute", "ajouter", "ajoute moi", "ajouter un élément",
  "ajouter dans la liste", utilise "action": "append_item".
- Le champ "text" doit contenir exactement le nouvel élément
  demandé.
- Ne remplace pas un élément existant quand l'utilisateur
  demande d'en ajouter un nouveau.

Si l'utilisateur demande de supprimer, retirer ou enlever
un élément HTML existant, utilise content_changes avec
"action": "remove_element".

Exemple :
Supprimer le menu vertical en double du header doit produire :

"content_changes": [
    {{
        "action": "remove_element",
        "selector": "header nav.vertical",
        "instruction": "supprimer le menu vertical en double"
    }}

Pour une suppression, ne mets pas de champ "text".
Utilise le sélecteur le plus précis fourni par le Reasoner.
Ne supprime jamais tout le header si seule une navigation
ou un élément enfant est demandé.

Exemples :

Changer le titre du hero en "Créer sans limites"

doit produire :

"content_changes": [
    {{
        "selector": ".hero h1",
        "text": "Créer sans limites",
        "instruction": "remplacer le texte du titre"
    }}
]

Changer le paragraphe du hero en "Une nouvelle phrase"

doit produire :

"content_changes": [
    {{
        "selector": ".hero p",
        "text": "Une nouvelle phrase",
        "instruction": "remplacer le paragraphe"
    }}
]

Changer le bouton du hero en "Commencer"

doit produire :

"content_changes": [
    {{
        "selector": ".hero button",
        "text": "Commencer",
        "instruction": "remplacer le texte du bouton"
    }}
]

IMPORTANT :

Le champ "text" doit contenir EXACTEMENT le nouveau texte
demandé par l'utilisateur.

Ne reformule jamais ce texte.

Pour une modification de contenu :
- ne crée aucune modification CSS ;
- n'ajoute aucune propriété CSS ;
- ne régénère jamais la page.

Pour une modification CSS :

Si l'utilisateur demande plus d'espace :
- margin
- padding
- gap

Si l'utilisateur demande une typographie :
- font-family
- font-size
- font-weight
- line-height
- letter-spacing

Ne change pas les couleurs si elles ne sont pas demandées.

Ne change pas le background si celui-ci
n'est pas demandé.

Ne change pas la taille si celle-ci
n'est pas demandée.

CIBLAGE :

Si la cible est hero, les sélecteurs doivent
commencer par :

.hero

Exemples :

.hero
.hero h1
.hero p
.hero button
.hero img

FORMAT OBLIGATOIRE :

{{
    "target": "{target}",
    "scope": "{scope}",
    "changes": [
        {{
            "property": "gap",
            "selector": ".hero",
            "instruction": "augmenter l'espace entre les éléments"
        }}
    ],
    "content_changes": [
        {{
            "selector": ".hero h1",
            "text": "Nouveau titre",
            "instruction": "remplacer le texte du titre"
        }}
    ]
}}

Retourne uniquement du JSON valide.
"""

    response = await generate(instruction)
    parsed = extract_json(response)

    if not parsed:
        return {
            "target": str(target).strip(),
            "scope": str(scope).strip(),
            "changes": [],
            "content_changes": [],
        }

    planned_changes = parsed.get(
        "changes",
        [],
    )

    if not isinstance(
        planned_changes,
        list,
    ):
        planned_changes = []

    valid_changes = []

    for change in planned_changes:
        if not isinstance(change, dict):
            continue

        property_name = str(
            change.get(
                "property",
                "",
            )
        ).strip().lower()

        selector = str(
            change.get(
                "selector",
                "",
            )
        ).strip()

        change_instruction = str(
            change.get(
                "instruction",
                "",
            )
        ).strip()

        if property_name not in ALLOWED_PROPERTIES:
            continue

        if not selector:
            continue

        if not change_instruction:
            continue

        if not selector_matches_target(
            selector=selector,
            target=target,
        ):
            continue

        if not change_is_justified(
            property_name=property_name,
            prompt=prompt,
        ):
            continue

        valid_changes.append(
            {
                "property": property_name,
                "selector": selector,
                "instruction": change_instruction,
            }
        )

    content_changes = parsed.get(
        "content_changes",
        [],
    )

    if not isinstance(
        content_changes,
        list,
    ):
        content_changes = []

    valid_content_changes = []

    for change in content_changes:
        if not isinstance(change, dict):
            continue

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

        change_instruction = str(
            change.get(
                "instruction",
                "",
            )
        ).strip()

        if action not in {
            "replace_text",
            "append_item",
            "remove_element",
        }:
            continue

        if not selector:
            continue

        if not change_instruction:
            continue

        if action == "remove_element":
            if not selector_matches_remove_target(
                selector=selector,
                target=target,
            ):
                continue
        else:
            if not text.strip():
                continue

            if action == "append_item":
                if not selector_matches_content_target(
                    selector=selector,
                    target=target,
                ):
                    continue
            elif not selector_matches_target(
                selector=selector,
                target=target,
            ):
                continue

        valid_content_changes.append(
            {
                "action": action,
                "selector": selector,
                "text": text,
                "instruction": change_instruction,
            }
        )

    return {
        "target": str(target).strip(),
        "scope": str(scope).strip(),
        "changes": valid_changes,
        "content_changes": valid_content_changes,
    }


def selector_matches_target(
    selector: str,
    target: str,
) -> bool:
    selector = selector.strip()

    if target == "global":
        return True

    if target == "header":
        return (
            selector == "header"
            or selector.startswith("header ")
            or selector.startswith("header:")
            or selector.startswith("header[")
        )

    normalized_target = str(target).strip().lower()

    if normalized_target in {
        "list",
        "lists",
        "liste",
        "listes",
        "items",
        "item",
        "cards",
        "card-list",
        "cat-list",
        "cats-list",
        "breed-list",
    }:
        list_selectors = {
            "ul",
            "ol",
            "li",
            ".list",
            ".lists",
            ".liste",
            ".listes",
            ".items",
            ".cards",
            ".cat-list",
            ".cats-list",
            ".breed-list",
        }

        return (
            selector in list_selectors
            or any(
                selector.startswith(
                    value + " "
                )
                for value in list_selectors
                if value.startswith(".")
            )
        )

    if normalized_target in {
        "navigation",
        "nav",
        "menu",
        "menus",
        "navbar",
        "navigation-menu",
        "header-menu",
    }:
        navigation_selectors = {
            "nav",
            "header nav",
            ".nav",
            ".navbar",
            ".navigation",
            ".menu",
            ".main-nav",
            ".header-nav",
            ".navigation-menu",
            ".header-menu",
        }

        return (
            selector in navigation_selectors
            or selector.startswith("nav ")
            or selector.startswith("header nav ")
            or selector.startswith(".nav ")
            or selector.startswith(".navbar ")
            or selector.startswith(".navigation ")
            or selector.startswith(".menu ")
        )

    target_selector = f".{target}"

    return (
        selector == target_selector
        or selector.startswith(
            target_selector + " "
        )
        or selector.startswith(
            target_selector + ":"
        )
        or selector.startswith(
            target_selector + "["
        )
    )


def selector_matches_remove_target(
    selector: str,
    target: str,
) -> bool:
    # Validation dédiée aux suppressions d'éléments HTML.
    selector = selector.strip().lower()
    normalized_target = str(target).strip().lower()

    if normalized_target == "global":
        return bool(selector)

    if normalized_target in {
        "header",
        "navigation",
        "nav",
        "menu",
        "menus",
        "navbar",
        "navigation-menu",
        "header-menu",
    }:
        return selector_matches_target(
            selector=selector,
            target=normalized_target,
        )

    return selector_matches_target(
        selector=selector,
        target=target,
    )


def selector_matches_content_target(
    selector: str,
    target: str,
) -> bool:
    """
    Validation dédiée aux ajouts de contenu.

    Un ajout peut cibler un conteneur de liste ou de cartes
    même si le Reasoner a nommé la zone avec un autre terme
    (par exemple "kittens" pour ".kittens-grid").
    """
    selector = selector.strip().lower()
    normalized_target = str(target).strip().lower()

    if normalized_target == "global":
        return True

    list_like_selectors = {
        "ul",
        "ol",
        ".list",
        ".lists",
        ".liste",
        ".listes",
        ".items",
        ".cards",
        ".card-list",
        ".cat-list",
        ".cats-list",
        ".breed-list",
        ".kittens-grid",
        ".cats-grid",
        ".breeds-grid",
        ".kitten-list",
        ".cats-grid",
    }

    if selector in list_like_selectors:
        return True

    list_words = (
        "list",
        "liste",
        "items",
        "cards",
        "card",
        "kitten",
        "kittens",
        "cat",
        "cats",
        "breed",
        "breeds",
        "grid",
    )

    if selector.startswith(".") and any(
        word in selector[1:]
        for word in list_words
    ):
        return True

    if any(
        word in normalized_target
        for word in (
            "list",
            "liste",
            "item",
            "card",
            "kitten",
            "chat",
            "breed",
            "cat",
        )
    ):
        return True

    return selector_matches_target(
        selector=selector,
        target=target,
    )


def change_is_justified(
    property_name: str,
    prompt: str,
) -> bool:
    text = prompt.lower()

    between_elements_keywords = [
        "entre les éléments",
        "entre les elements",
        "entre les blocs",
        "entre les sections",
        "entre les textes",
        "espace entre",
        "espaces entre",
        "écart entre",
        "ecart entre",
        "espacer les éléments",
        "espacer les elements",
    ]

    if any(
        keyword in text
        for keyword in between_elements_keywords
    ):
        return property_name == "gap"

    spacing_keywords = [
        "espace",
        "espaces",
        "espacement",
        "aéré",
        "aérée",
        "aérer",
        "aere",
        "aeree",
        "aerer",
        "padding",
        "margin",
        "gap",
        "vide",
        "respirer",
    ]

    typography_keywords = [
        "typographie",
        "typographique",
        "police",
        "font",
        "caractère",
        "caractères",
        "élégant",
        "élégante",
        "elegant",
        "elegante",
        "lettres",
    ]

    color_keywords = [
        "couleur",
        "couleurs",
        "color",
        "palette",
        "fond",
        "arrière-plan",
        "arriere-plan",
    ]

    size_keywords = [
        "taille",
        "largeur",
        "hauteur",
        "dimension",
    ]

    alignment_keywords = [
        "aligner",
        "alignement",
        "centrer",
        "position",
        "disposition",
    ]

    spacing_properties = {
        "margin",
        "padding",
        "gap",
    }

    typography_properties = {
        "font-family",
        "font-size",
        "font-weight",
        "line-height",
        "letter-spacing",
    }

    color_properties = {
        "color",
        "background-color",
        "border-color",
    }

    size_properties = {
        "width",
        "height",
        "max-width",
        "max-height",
    }

    alignment_properties = {
        "justify-content",
        "align-items",
    }

    if (
        property_name in spacing_properties
        and any(
            keyword in text
            for keyword in spacing_keywords
        )
    ):
        return True

    if (
        property_name in typography_properties
        and any(
            keyword in text
            for keyword in typography_keywords
        )
    ):
        return True

    if (
        property_name in color_properties
        and any(
            keyword in text
            for keyword in color_keywords
        )
    ):
        return True

    if (
        property_name in size_properties
        and any(
            keyword in text
            for keyword in size_keywords
        )
    ):
        return True

    if (
        property_name in alignment_properties
        and any(
            keyword in text
            for keyword in alignment_keywords
        )
    ):
        return True

    return False


def extract_json(
    response: str,
) -> dict | None:
    response = response.strip()

    try:
        result = json.loads(response)

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        pass

    match = re.search(
        r"\{.*\}",
        response,
        re.DOTALL,
    )

    if not match:
        return None

    try:
        result = json.loads(
            match.group()
        )

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        return None

    return None