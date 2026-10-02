import json
import re

from backend.app.ollama import generate


ALLOWED_TARGETS = {
    "hero",
    "header",
    "navigation",
    "content",
    "card",
    "button",
    "form",
    "footer",
    "typography",
    "layout",
    "color",
    "spacing",
    "mobile",
    "desktop",
    "global",
}

ALLOWED_SCOPES = {
    "target_only",
    "related_elements",
    "global",
}


async def analyze_design_change(
    prompt: str,
) -> dict:
    """
    Analyse une demande de modification
    et retourne une description structurée.
    """

    instruction = f"""
Tu es le Design Reasoner de Personal Design AI.

Ta mission est uniquement d'analyser une demande
de modification d'une interface EXISTANTE.

Tu ne dois PAS générer de HTML.

Tu dois identifier :

1. La zone principale concernée.
2. Les modifications demandées.
3. Le périmètre de la modification.
4. Si la demande concerne le CONTENU ou le STYLE.

Les zones possibles sont :

- hero
- header
- navigation
- content
- card
- button
- form
- footer
- typography
- layout
- color
- spacing
- mobile
- desktop
- global

Le périmètre doit être l'une des valeurs :

- target_only
- related_elements
- global

TYPE DE MODIFICATION :

- "content" = modifier, ajouter ou supprimer un élément ou un contenu HTML existant.
- "style" = modifier couleur, espace, taille, typographie,
  alignement, disposition ou apparence.
- "mixed" = les deux.

IMPORTANT POUR LES SUPPRESSIONS :

Si l'utilisateur demande :
- supprimer un menu
- supprimer la navigation
- enlever un menu
- retirer un menu
- supprimer un élément
- enlever un élément
- retirer un élément

la demande doit être classée comme "content".

Si le mot "menu", "navigation" ou "navbar" est présent
et que la demande demande de supprimer/enlever/retirer cet élément,
la cible DOIT être "navigation".

Exemple :

"Supprime le menu vertical en double."

doit produire :

{{
    "target": "navigation",
    "changes": [
        "supprimer le menu vertical en double"
    ],
    "scope": "target_only",
    "change_type": "content"
}}

Une demande concernant une zone précise doit rester locale.

Exemple :

"Rends le hero plus minimaliste"

doit produire :

"target": "hero"
"scope": "target_only"

et NON :
"scope": "global"

Le scope "global" est autorisé UNIQUEMENT si
l'utilisateur demande explicitement une modification
de toute l'interface, de toute la page, du design global,
de la palette globale ou de la typographie globale.

RÈGLES :

- Retourne uniquement un JSON valide.
- Pas de Markdown.
- Pas d'explication.
- Ne génère jamais de HTML.
- Ne crée jamais de nouvelles fonctionnalités.
- Ne transforme jamais une demande locale en demande globale.
- Une modification de texte ou de structure HTML doit être classée "content".
- Une modification de style doit être classée "style".
- Une suppression d'un élément HTML existant doit être classée "content".

Format obligatoire :

{{
    "target": "hero",
    "changes": [
        "changer le titre du hero"
    ],
    "scope": "target_only",
    "change_type": "content"
}}

DEMANDE UTILISATEUR :

{prompt}
"""

    response = await generate(instruction)
    parsed = extract_json(response)

    # Les demandes de suppression de menu sont suffisamment explicites
    # pour être déterminées sans laisser le modèle choisir une autre zone.
    forced_removal_target = detect_removal_target(prompt)

    if forced_removal_target:
        return {
            "target": forced_removal_target,
            "changes": [prompt.strip()],
            "scope": "target_only",
            "change_type": "content",
        }

    if not parsed:
        return fallback_analysis(prompt)

    target = str(
        parsed.get(
            "target",
            "global",
        )
    ).strip().lower()

    if target not in ALLOWED_TARGETS:
        target = detect_target_from_prompt(prompt)

    changes = parsed.get(
        "changes",
        [],
    )

    if not isinstance(changes, list):
        changes = [str(changes)]

    changes = [
        str(change).strip()
        for change in changes
        if str(change).strip()
    ]

    scope = str(
        parsed.get(
            "scope",
            "related_elements",
        )
    ).strip().lower()

    if scope not in ALLOWED_SCOPES:
        scope = "related_elements"

    change_type = str(
        parsed.get(
            "change_type",
            "style",
        )
    ).strip().lower()

    if change_type not in {
        "content",
        "style",
        "mixed",
    }:
        change_type = infer_change_type(prompt)

    if target != "global":
        if not explicitly_global_request(prompt):
            scope = "target_only"

    return {
        "target": target,
        "changes": changes,
        "scope": scope,
        "change_type": change_type,
    }


def detect_removal_target(
    prompt: str,
) -> str | None:
    """
    Détecte de manière déterministe les demandes de suppression
    d'un menu ou d'une navigation.
    """

    text = prompt.lower().strip()

    removal_keywords = (
        "supprime",
        "supprimer",
        "supprimez",
        "supprimé",
        "enlève",
        "enlever",
        "enlevez",
        "retire",
        "retirer",
        "retirez",
    )

    navigation_keywords = (
        "menu",
        "navigation",
        "navbar",
        "nav",
    )

    has_removal = any(
        keyword in text
        for keyword in removal_keywords
    )

    has_navigation = any(
        keyword in text
        for keyword in navigation_keywords
    )

    if has_removal and has_navigation:
        return "navigation"

    return None


def infer_change_type(
    prompt: str,
) -> str:
    text = prompt.lower()

    content_keywords = [
        "change le texte",
        "changer le texte",
        "modifie le texte",
        "modifier le texte",
        "remplace le texte",
        "remplacer le texte",
        "change le titre",
        "changer le titre",
        "modifie le titre",
        "modifier le titre",
        "remplace le titre",
        "remplacer le titre",
        "change le paragraphe",
        "changer le paragraphe",
        "modifie le paragraphe",
        "modifier le paragraphe",
        "remplace le paragraphe",
        "remplacer le paragraphe",
        "change le bouton",
        "changer le bouton",
        "modifie le bouton",
        "modifier le bouton",
        "remplace le bouton",
        "remplacer le bouton",
        "texte en",
        "titre en",
        "paragraphe en",
        "bouton en",
        "supprime",
        "supprimer",
        "supprimez",
        "enlève",
        "enlever",
        "enlevez",
        "retire",
        "retirer",
        "retirez",
    ]

    style_keywords = [
        "couleur",
        "couleurs",
        "fond",
        "arrière-plan",
        "palette",
        "espace",
        "espacement",
        "aéré",
        "aérée",
        "padding",
        "margin",
        "gap",
        "typographie",
        "police",
        "font",
        "taille",
        "largeur",
        "hauteur",
        "aligner",
        "alignement",
        "centrer",
        "minimaliste",
        "élégant",
        "élégante",
    ]

    has_content = any(
        keyword in text
        for keyword in content_keywords
    )

    has_style = any(
        keyword in text
        for keyword in style_keywords
    )

    if has_content and has_style:
        return "mixed"

    if has_content:
        return "content"

    return "style"


def explicitly_global_request(
    prompt: str,
) -> bool:
    text = prompt.lower().strip()

    global_phrases = [
        "toute la page",
        "toute la plateforme",
        "toute l'interface",
        "toute l'application",
        "tout le site",
        "l'ensemble de la page",
        "l'ensemble de l'interface",
        "l'ensemble du site",
        "le design global",
        "design global",
        "style global",
        "typographie globale",
        "palette globale",
        "couleurs globales",
        "partout",
        "sur toute la page",
        "sur toute l'interface",
        "sur tout le site",
    ]

    return any(
        phrase in text
        for phrase in global_phrases
    )


def fallback_analysis(
    prompt: str,
) -> dict:
    target = detect_removal_target(prompt)

    if target is None:
        target = detect_target_from_prompt(prompt)

    if target != "global":
        scope = "target_only"
    else:
        scope = "global"

    return {
        "target": target,
        "changes": [prompt],
        "scope": scope,
        "change_type": infer_change_type(prompt),
    }


def detect_target_from_prompt(
    prompt: str,
) -> str:
    text = prompt.lower()

    target_keywords = {
        "hero": [
            "hero",
            "section hero",
            "bannière principale",
            "titre principal",
        ],
        "header": [
            "header",
            "en-tête",
            "entête",
        ],
        "navigation": [
            "navigation",
            "menu",
            "navbar",
        ],
        "footer": [
            "footer",
            "pied de page",
        ],
        "button": [
            "bouton",
            "button",
            "cta",
        ],
        "card": [
            "card",
            "carte",
        ],
        "form": [
            "formulaire",
            "form",
        ],
        "typography": [
            "typographie",
            "police",
            "font",
        ],
        "spacing": [
            "espace",
            "espacement",
            "padding",
            "margin",
            "gap",
        ],
        "color": [
            "couleur",
            "couleurs",
            "palette",
        ],
        "content": [
            "contenu",
            "texte",
            "paragraphe",
        ],
    }

    for target, keywords in target_keywords.items():
        for keyword in keywords:
            if keyword in text:
                return target

    return "global"


def extract_json(
    response: str,
) -> dict | None:
    """
    Extrait le premier objet JSON valide
    présent dans la réponse du modèle.
    """

    response = response.strip()

    try:
        result = json.loads(response)

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        pass

    # Recherche d'un objet JSON même si le modèle
    # ajoute accidentellement du texte autour.
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
