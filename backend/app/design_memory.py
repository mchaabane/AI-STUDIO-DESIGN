import json
from pathlib import Path


PROFILE_PATH = (
    Path(__file__).resolve().parents[2]
    / "design-library"
    / "design-profile.json"
)


def load_design_profile() -> dict:
    if not PROFILE_PATH.exists():
        return {}

    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def _format_color(color: dict) -> str:
    return (
        f"{color.get('color', '?')} "
        f"({color.get('family', 'unknown')}) · "
        f"{color.get('project_count', 0)}/"
        f"{color.get('projects_total', 0)} projets · "
        f"{color.get('average_weight', 0):.2f}% en moyenne"
    )


def _format_distribution(distribution: dict) -> str:
    if not distribution:
        return "non disponible"

    return ", ".join(
        f"{key}: {value}"
        for key, value in distribution.items()
    )


def _format_float(value, decimals: int = 2) -> str:
    if value is None:
        return "non disponible"

    return f"{value:.{decimals}f}"


def _build_visual_summary(projects: list[dict]) -> dict:
    composition_distribution = {}
    temperature_distribution = {}
    whitespace_values = []

    for project in projects:
        visual = project.get("visual_analysis", {})
        composition = visual.get("composition", {})
        color_balance = visual.get("color_balance", {})

        composition_type = composition.get("composition")
        if composition_type:
            composition_distribution[composition_type] = (
                composition_distribution.get(composition_type, 0) + 1
            )

        whitespace_ratio = composition.get("whitespace_ratio")
        if isinstance(whitespace_ratio, (int, float)):
            whitespace_values.append(float(whitespace_ratio))

        temperature = color_balance.get("dominant_temperature")
        if temperature:
            temperature_distribution[temperature] = (
                temperature_distribution.get(temperature, 0) + 1
            )

    return {
        "composition_distribution": composition_distribution,
        "temperature_distribution": temperature_distribution,
        "average_whitespace_ratio": (
            sum(whitespace_values) / len(whitespace_values)
            if whitespace_values
            else None
        ),
    }


def build_design_memory(profile: dict) -> str:
    analysis = profile.get("analysis", {})
    visual_summary = analysis.get("visual_summary", {})
    colors = profile.get("colors", {}).get("primary", [])
    projects = profile.get("projects_analyzed", [])
    derived_summary = _build_visual_summary(projects)

    composition_distribution = derived_summary["composition_distribution"]
    temperature_distribution = derived_summary["temperature_distribution"]
    average_whitespace_ratio = derived_summary["average_whitespace_ratio"]

    lines = [
        "MÉMOIRE DE DESIGN PERSONNEL",
        "",
        (
            "Cette mémoire est construite à partir de "
            f"{analysis.get('total_projects', 0)} projet(s) visuel(s) analysé(s)."
        ),
        "",
        "PALETTE OBSERVÉE",
    ]

    if colors:
        for color in colors:
            lines.append(f"- {_format_color(color)}")
    else:
        lines.append("- Aucune palette analysée.")

    lines.extend(
        [
            "",
            "CARACTÉRISTIQUES VISUELLES OBSERVÉES",
            (
                "- Orientation observée : "
                f"{_format_distribution(visual_summary.get('orientation_distribution', {}))}."
            ),
            (
                "- Luminosité observée : "
                f"{_format_distribution(visual_summary.get('brightness_distribution', {}))}."
            ),
            (
                "- Densité visuelle observée : "
                f"{_format_distribution(visual_summary.get('density_distribution', {}))}."
            ),
            (
                "- Ratio moyen observé : "
                f"{_format_float(visual_summary.get('average_aspect_ratio'), 3)}."
            ),
            (
                "- Score moyen de densité : "
                f"{_format_float(visual_summary.get('average_density_score'), 2)}/100."
            ),
            (
                "- Score moyen de transitions visuelles : "
                f"{_format_float(visual_summary.get('average_edge_density_score'), 2)}/100."
            ),
            (
                "- Composition observée : "
                f"{_format_distribution(composition_distribution)}."
            ),
            (
                "- Espace blanc moyen observé : "
                f"{_format_float(average_whitespace_ratio, 2)}%."
            ),
            (
                "- Température visuelle observée : "
                f"{_format_distribution(temperature_distribution)}."
            ),
        ]
    )

    lines.extend(["", "PROJETS ANALYSÉS"])

    if projects:
        for project in projects:
            dominant_colors = project.get("dominant_colors", [])
            color_names = [
                color.get("color")
                for color in dominant_colors[:4]
                if color.get("color")
            ]

            visual = project.get("visual_analysis", {})
            composition = visual.get("composition", {})
            temperature = visual.get("color_balance", {})

            project_line = (
                f"- {project.get('file', 'projet inconnu')} : "
                f"{project.get('width', '?')}×{project.get('height', '?')}, "
                f"{project.get('orientation', 'unknown')}, "
                f"ratio {_format_float(project.get('aspect_ratio'), 3)}"
            )

            if color_names:
                project_line += (
                    ", couleurs principales : "
                    + ", ".join(color_names)
                )

            composition_type = composition.get("composition")
            if composition_type:
                project_line += f", composition : {composition_type}"

            whitespace_ratio = composition.get("whitespace_ratio")
            if isinstance(whitespace_ratio, (int, float)):
                project_line += (
                    f", espace blanc : "
                    f"{_format_float(whitespace_ratio, 2)}%"
                )

            dominant_temperature = temperature.get("dominant_temperature")
            if dominant_temperature:
                project_line += f", température : {dominant_temperature}"

            lines.append(project_line)
    else:
        lines.append("- Aucun projet analysé.")

    lines.extend(
        [
            "",
            "RÈGLE D'UTILISATION",
            (
                "Utiliser ces observations comme une référence du langage "
                "visuel personnel. Donner davantage de poids aux tendances "
                "présentes dans plusieurs projets qu'aux éléments isolés."
            ),
            (
                "Respecter les couleurs récurrentes, la luminosité, la "
                "densité, la composition, l'espace blanc et la température "
                "visuelle observés lorsque la demande utilisateur ne précise "
                "pas autrement."
            ),
            (
                "Ne pas inventer des préférences personnelles qui ne sont "
                "pas présentes dans la mémoire."
            ),
            (
                "Lorsque l'information n'est pas disponible, choisir une "
                "solution cohérente et sobre plutôt que prétendre connaître "
                "une préférence personnelle."
            ),
        ]
    )

    return "\n".join(lines)


def get_design_memory() -> str:
    profile = load_design_profile()

    if not profile:
        return (
            "Aucune mémoire de design personnelle n'est actuellement disponible."
        )

    return build_design_memory(profile)


if __name__ == "__main__":
    print(get_design_memory())
