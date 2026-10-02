import json
from pathlib import Path

from backend.app.ollama import generate


DESIGN_PROFILE_PATH = (
    Path(__file__).resolve().parents[2]
    / "design-library"
    / "design-profile.json"
)


def load_design_profile() -> dict:
    try:
        with DESIGN_PROFILE_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def build_design_memory_context(profile: dict) -> str:
    if not profile:
        return (
            "Aucune mémoire de design personnelle n'est disponible. "
            "Utilise uniquement les principes de design généraux fournis ci-dessous."
        )

    colors = profile.get("colors", {})
    primary_colors = colors.get("primary", [])
    color_lines = []

    for item in primary_colors:
        color = item.get("color")
        family = item.get("family")
        weight = item.get("average_weight")
        project_count = item.get("project_count")
        if color:
            line = f"- {color}"
            if family:
                line += f" ({family})"
            if weight is not None:
                line += f", poids moyen {weight}%"
            if project_count is not None:
                line += f", présent dans {project_count} projets"
            color_lines.append(line)

    analysis = profile.get("analysis", {})
    visual_summary = analysis.get("visual_summary", {})
    orientation = visual_summary.get("orientation_distribution", {})
    brightness = visual_summary.get("brightness_distribution", {})
    density = visual_summary.get("density_distribution", {})
    visual_style = visual_summary.get("visual_style", {})
    composition = visual_style.get("composition_distribution", {})
    temperature = visual_style.get("temperature_distribution", {})

    memory_lines = [
        "MÉMOIRE DE DESIGN PERSONNELLE",
        "",
        "Cette mémoire provient des interfaces analysées par l'utilisateur.",
        "Elle doit être utilisée comme référence prioritaire pour construire le style visuel.",
        "",
        "PALETTE RÉCURRENTE :",
    ]
    memory_lines.extend(color_lines or ["- Aucune couleur récurrente structurée disponible."])
    memory_lines.extend([
        "",
        "CARACTÉRISTIQUES VISUELLES OBSERVÉES :",
        f"- Orientation : {orientation or 'non renseignée'}",
        f"- Luminosité : {brightness or 'non renseignée'}",
        f"- Densité : {density or 'non renseignée'}",
        f"- Composition : {composition or 'non renseignée'}",
        f"- Température des couleurs : {temperature or 'non renseignée'}",
        f"- Ratio moyen d'espace blanc : {visual_style.get('average_whitespace_ratio', 'non renseigné')}%",
        f"- Ratio moyen de zones sombres : {visual_style.get('average_dark_area_ratio', 'non renseigné')}%",
        "",
        "RÈGLES D'UTILISATION DE LA MÉMOIRE :",
        "- Respecte la palette récurrente dans les couleurs principales de l'interface.",
        "- Utilise les couleurs les plus présentes comme base avant d'introduire d'autres couleurs.",
        "- Conserve le caractère visuel observé dans les captures de référence.",
        "- Ne remplace pas la palette personnelle par une palette générique arbitraire.",
        "- Les couleurs secondaires peuvent être dérivées des couleurs observées si nécessaire.",
        "- Les informations absentes du profil doivent être décidées avec cohérence, sans inventer une préférence personnelle.",
    ])
    return "\n".join(memory_lines)


async def generate_design(
    prompt: str,
    project_context: str = "",
) -> str:
    design_profile = load_design_profile()
    design_memory = build_design_memory_context(design_profile)

    instruction = f"""
Tu es le moteur de génération de Personal Design AI.

Tu es un designer web senior ET un développeur frontend senior.

Ta mission est de transformer la demande utilisateur en une interface web complète.

IMPORTANT :

1. Retourne UNIQUEMENT du HTML.
2. Le document doit commencer par <!DOCTYPE html>.
3. Le CSS doit être directement inclus dans une balise <style>.
4. Le JavaScript doit être directement inclus dans une balise <script> uniquement si nécessaire.
5. Aucun framework externe n'est nécessaire.
6. Aucun fichier externe ne doit être requis.
7. L'interface doit être immédiatement affichable dans un iframe.
8. Le design doit être moderne, cohérent et professionnel.
9. L'interface doit fonctionner sur Desktop ET Mobile.
10. Utilise des media queries CSS pour le responsive.
11. Ne donne aucune explication avant ou après le HTML.
12. Ne mets pas le HTML dans un bloc Markdown.
13. Le contenu doit être réaliste et crédible.
14. La hiérarchie visuelle doit être clairement définie.
15. Utilise une typographie, des espacements et des couleurs cohérents.

PRINCIPES DESIGN :

- forte hiérarchie visuelle ;
- espaces négatifs généreux ;
- compositions équilibrées ;
- titres clairement dominants ;
- boutons et appels à l'action facilement identifiables ;
- responsive pensé dès la conception ;
- éviter les interfaces génériques ou surchargées ;
- éviter les gradients gratuits ;
- éviter les effets visuels inutiles.

RÈGLE PRIORITAIRE — STYLE PERSONNEL :

La mémoire de design ci-dessous représente les interfaces de référence de l'utilisateur.
Elle est prioritaire pour les décisions visuelles.

Tu dois t'en servir activement pour :
- choisir les couleurs ;
- construire la hiérarchie visuelle ;
- définir l'ambiance générale ;
- choisir les contrastes ;
- doser les espaces blancs ;
- organiser la composition.

Ne te contente pas de mentionner ou de copier la mémoire : applique-la réellement dans le CSS et dans la structure HTML.

{design_memory}

CONTEXTE DU PROJET :

{project_context}

DEMANDE UTILISATEUR :

{prompt}

Génère maintenant le document HTML complet.
"""

    html = await generate(instruction)
    return clean_html(html)


def clean_html(html: str) -> str:
    html = html.strip()
    if html.startswith("```html"):
        html = html[len("```html"):]
    elif html.startswith("```"):
        html = html[3:]
    if html.endswith("```"):
        html = html[:-3]
    return html.strip()
