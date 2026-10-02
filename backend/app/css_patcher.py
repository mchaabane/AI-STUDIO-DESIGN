import re
import unicodedata


# =========================================================
# PALETTE DE COULEURS
# =========================================================

COLOR_VALUES = {
    # Neutres
    "noir": "#111111",
    "blanc": "#FFFFFF",
    "gris": "#6B7280",
    "gris clair": "#D1D5DB",
    "gris foncé": "#374151",
    "gris sombre": "#374151",
    "anthracite": "#1F2937",
    "gris ardoise": "#475569",
    "gris perle": "#E5E7EB",
    "argent": "#C0C0C0",

    # Rouges
    "rouge": "#EF4444",
    "rouge vif": "#DC2626",
    "rouge foncé": "#991B1B",
    "bordeaux": "#7F1D1D",
    "carmin": "#DC143C",
    "corail": "#F97316",
    "corail rouge": "#F43F5E",
    "framboise": "#E11D48",

    # Oranges
    "orange": "#F97316",
    "orange vif": "#EA580C",
    "orange foncé": "#C2410C",
    "terracotta": "#C2410C",
    "abricot": "#FDBA74",
    "pêche": "#FDBA74",

    # Jaunes
    "jaune": "#FACC15",
    "jaune vif": "#EAB308",
    "jaune clair": "#FEF08A",
    "jaune pâle": "#FEF9C3",
    "moutarde": "#CA8A04",
    "doré": "#EAB308",
    "or": "#D4AF37",

    # Verts
    "vert": "#22C55E",
    "vert vif": "#16A34A",
    "vert foncé": "#15803D",
    "vert forêt": "#166534",
    "vert sapin": "#14532D",
    "émeraude": "#10B981",
    "menthe": "#6EE7B7",
    "sauge": "#A3B18A",
    "olive": "#808000",
    "kaki": "#BDB76B",
    "vert kaki": "#BDB76B",
    "lime": "#84CC16",

    # Bleus
    "bleu": "#3B82F6",
    "bleu vif": "#2563EB",
    "bleu foncé": "#1D4ED8",
    "bleu marine": "#1E3A8A",
    "bleu nuit": "#172554",
    "bleu ciel": "#38BDF8",
    "bleu clair": "#93C5FD",
    "azur": "#0EA5E9",
    "turquoise": "#14B8A6",
    "cyan": "#06B6D4",
    "bleu pétrole": "#155E75",
    "bleu roi": "#2563EB",
    "bleu royal": "#2563EB",

    # Violets
    "violet": "#8B5CF6",
    "violet foncé": "#6D28D9",
    "lavande": "#C4B5FD",
    "prune": "#701A75",
    "améthyste": "#9333EA",
    "aubergine": "#581C87",
    "indigo": "#4F46E5",

    # Roses
    "rose": "#EC4899",
    "rose clair": "#F9A8D4",
    "rose pâle": "#FCE7F3",
    "rose poudré": "#F5D0D9",
    "fuchsia": "#D946EF",
    "magenta": "#C026D3",

    # Marrons
    "marron": "#92400E",
    "marron foncé": "#78350F",
    "chocolat": "#78350F",
    "café": "#6F4E37",
    "caramel": "#D97706",
    "cannelle": "#B45309",
    "noisette": "#92400E",

    # Beiges
    "beige": "#F5F0E8",
    "crème": "#FFF7ED",
    "creme": "#FFF7ED",
    "ivoire": "#FFFFF0",
    "écru": "#F5F5DC",
    "ecru": "#F5F5DC",
    "sable": "#E7D7C1",
    "champagne": "#F7E7CE",

    # Métalliques
    "bronze": "#CD7F32",
    "cuivre": "#B87333",
    "platine": "#E5E4E2",
}


CSS_COLOR_VALUES = {
    "transparent",
    "currentcolor",
    "inherit",
    "initial",
    "unset",
}


# =========================================================
# OUTILS TEXTE
# =========================================================

def normalize_text(value: str) -> str:
    value = value.lower().strip()
    value = unicodedata.normalize("NFD", value)
    value = "".join(
        char
        for char in value
        if unicodedata.category(char) != "Mn"
    )
    return value


# =========================================================
# COULEURS
# =========================================================

def detect_color(instruction: str) -> str | None:
    text = instruction.strip()
    normalized = normalize_text(text)

    # Hexadécimal
    hex_match = re.search(
        r"#[0-9a-fA-F]{3,8}",
        text,
    )

    if hex_match:
        return hex_match.group(0)

    # rgb / rgba
    rgb_match = re.search(
        r"rgba?\(\s*[\d.\s%,]+\)",
        text,
        re.IGNORECASE,
    )

    if rgb_match:
        return rgb_match.group(0)

    # Variables CSS
    variable_match = re.search(
        r"var\(\s*--[\w-]+\s*\)",
        text,
        re.IGNORECASE,
    )

    if variable_match:
        return variable_match.group(0)

    # Couleurs nommées.
    # On cherche les noms les plus longs d'abord
    # pour éviter qu'un mot court ne capture une expression plus précise.
    normalized_colors = sorted(
        COLOR_VALUES.items(),
        key=lambda item: len(normalize_text(item[0])),
        reverse=True,
    )

    for name, value in normalized_colors:
        normalized_name = normalize_text(name)

        if re.search(
            rf"(?<!\w){re.escape(normalized_name)}(?!\w)",
            normalized,
        ):
            return value

    # Couleurs CSS natives
    for value in CSS_COLOR_VALUES:
        if re.search(
            rf"(?<!\w){re.escape(value)}(?!\w)",
            normalized,
        ):
            return value

    return None


# =========================================================
# DIMENSIONS
# =========================================================

def detect_dimension(instruction: str, property_name: str) -> str | None:
    text = normalize_text(instruction)

    # Valeur explicite : 20px, 2rem, 10vh, 50%, etc.
    explicit = re.search(
        r"(?<![\w.])(\d+(?:\.\d+)?)(px|rem|em|vh|vw|%)(?!\w)",
        text,
    )

    if explicit:
        return f"{explicit.group(1)}{explicit.group(2)}"

    # Valeurs qualitatives
    if any(
        phrase in text
        for phrase in [
            "beaucoup plus",
            "beaucoup",
            "tres important",
            "tres grand",
            "tres large",
        ]
    ):
        values = {
            "gap": "48px",
            "margin": "48px",
            "padding": "48px",
            "font-size": "32px",
            "line-height": "1.7",
            "letter-spacing": "0.03em",
            "width": "90%",
            "height": "auto",
        }

        return values.get(property_name)

    if any(
        phrase in text
        for phrase in [
            "plus",
            "augment",
            "agrand",
            "aere",
            "aeree",
            "aerer",
        ]
    ):
        values = {
            "gap": "32px",
            "margin": "32px",
            "padding": "32px",
            "font-size": "28px",
            "line-height": "1.6",
            "letter-spacing": "0.02em",
            "width": "85%",
            "height": "auto",
        }

        return values.get(property_name)

    if any(
        phrase in text
        for phrase in [
            "moins",
            "redui",
            "resser",
            "compact",
        ]
    ):
        values = {
            "gap": "12px",
            "margin": "12px",
            "padding": "12px",
            "font-size": "16px",
            "line-height": "1.3",
            "letter-spacing": "0",
            "width": "95%",
            "height": "auto",
        }

        return values.get(property_name)

    return None


# =========================================================
# ALIGNEMENT
# =========================================================

def detect_alignment(instruction: str) -> str | None:
    text = normalize_text(instruction)

    if any(
        word in text
        for word in [
            "centre",
            "centree",
            "centrer",
            "au centre",
        ]
    ):
        return "center"

    if any(
        word in text
        for word in [
            "gauche",
            "aligne a gauche",
        ]
    ):
        return "left"

    if any(
        word in text
        for word in [
            "droite",
            "aligne a droite",
        ]
    ):
        return "right"

    if "justifie" in text:
        return "justify"

    return None


# =========================================================
# VALEUR CSS
# =========================================================

def infer_css_value(
    property_name: str,
    instruction: str,
) -> str | None:

    property_name = property_name.strip().lower()

    # -----------------------------------------------------
    # Couleurs
    # -----------------------------------------------------

    if property_name in {
        "color",
        "background",
        "background-color",
        "border-color",
        "box-shadow",
        "text-shadow",
    }:
        color = detect_color(instruction)

        if color:
            if property_name == "background":
                return color

            if property_name == "box-shadow":
                return f"0 10px 30px {color}"

            if property_name == "text-shadow":
                return f"0 0 10px {color}"

            return color

    # -----------------------------------------------------
    # Dimensions
    # -----------------------------------------------------

    if property_name in {
        "margin",
        "margin-top",
        "margin-right",
        "margin-bottom",
        "margin-left",
        "padding",
        "padding-top",
        "padding-right",
        "padding-bottom",
        "padding-left",
        "gap",
        "font-size",
        "line-height",
        "letter-spacing",
        "width",
        "height",
        "max-width",
        "max-height",
    }:
        value = detect_dimension(
            instruction,
            property_name,
        )

        if value:
            return value

    # -----------------------------------------------------
    # Font weight
    # -----------------------------------------------------

    if property_name == "font-weight":
        text = normalize_text(instruction)

        if any(
            word in text
            for word in [
                "leger",
                "legere",
                "fin",
                "fine",
                "delicat",
            ]
        ):
            return "400"

        if any(
            word in text
            for word in [
                "gras",
                "epais",
                "fort",
                "bold",
            ]
        ):
            return "700"

        return "600"

    # -----------------------------------------------------
    # Font family
    # -----------------------------------------------------

    if property_name == "font-family":
        text = normalize_text(instruction)

        if "serif" in text:
            return "Georgia, 'Times New Roman', serif"

        if any(
            word in text
            for word in [
                "moderne",
                "minimaliste",
                "sans serif",
                "sans-serif",
            ]
        ):
            return "Inter, Arial, sans-serif"

        return "Inter, Arial, sans-serif"

    # -----------------------------------------------------
    # Alignement
    # -----------------------------------------------------

    if property_name in {
        "text-align",
        "justify-content",
        "align-items",
    }:
        alignment = detect_alignment(instruction)

        if alignment:
            if property_name == "text-align":
                return alignment

            if alignment == "left":
                return "flex-start"

            if alignment == "right":
                return "flex-end"

            return alignment

    # -----------------------------------------------------
    # Display / layout
    # -----------------------------------------------------

    if property_name == "display":
        text = normalize_text(instruction)

        if any(
            word in text
            for word in [
                "flex",
                "aligne",
                "centre",
                "centrer",
            ]
        ):
            return "flex"

        if "grid" in text:
            return "grid"

    return None


# =========================================================
# SELECTEURS
# =========================================================

def normalize_selector(selector: str) -> str:
    selector = selector.strip()

    selector = re.sub(
        r"\s*,\s*",
        ", ",
        selector,
    )

    selector = re.sub(
        r"\s+",
        " ",
        selector,
    )

    return selector


def selector_matches_rule(
    rule_selector: str,
    requested_selector: str,
) -> bool:

    rule_selector = normalize_selector(rule_selector)
    requested_selector = normalize_selector(requested_selector)

    if rule_selector == requested_selector:
        return True

    requested_parts = [
        part.strip()
        for part in requested_selector.split(",")
    ]

    rule_parts = [
        part.strip()
        for part in rule_selector.split(",")
    ]

    return all(
        part in rule_parts
        for part in requested_parts
    )


# =========================================================
# MODIFICATION D'UNE RÈGLE CSS EXISTANTE
# =========================================================

def update_css_rule(
    html: str,
    selector: str,
    property_name: str,
    value: str,
) -> tuple[str, bool]:

    selector = normalize_selector(selector)

    # On ne modifie que le contenu des <style>.
    style_pattern = re.compile(
        r"(<style\b[^>]*>)(.*?)(</style>)",
        re.IGNORECASE | re.DOTALL,
    )

    changed = False

    def replace_style(match: re.Match) -> str:
        nonlocal changed

        opening = match.group(1)
        css = match.group(2)
        closing = match.group(3)

        # Recherche d'une règle CSS simple :
        #
        # .hero {
        #     ...
        # }
        #
        # Le pattern est volontairement limité aux règles simples
        # afin d'éviter de casser les media queries.
        rule_pattern = re.compile(
            rf"(?P<selector>(?:^|}})\s*{re.escape(selector)}\s*)"
            rf"\{{(?P<body>[^{{}}]*)\}}",
            re.IGNORECASE | re.DOTALL,
        )

        rule_match = rule_pattern.search(css)

        if not rule_match:
            # Deuxième tentative plus souple pour les sélecteurs
            # contenant plusieurs éléments.
            generic_pattern = re.compile(
                rf"(?P<selector>{re.escape(selector)})"
                rf"\s*\{{(?P<body>[^{{}}]*)\}}",
                re.IGNORECASE | re.DOTALL,
            )

            rule_match = generic_pattern.search(css)

        if rule_match:
            body = rule_match.group("body")

            property_pattern = re.compile(
                rf"(^|[;\n\r])(\s*{re.escape(property_name)}\s*:\s*)"
                rf"[^;}}]+(;?)",
                re.IGNORECASE,
            )

            if property_pattern.search(body):
                new_body = property_pattern.sub(
                    lambda prop_match:
                        f"{prop_match.group(1)}"
                        f"{property_name}: {value}"
                        f"{prop_match.group(3)}",
                    body,
                    count=1,
                )
            else:
                separator = ""
                if body.strip() and not body.rstrip().endswith(";"):
                    separator = ";"

                new_body = (
                    body
                    + separator
                    + f"\n    {property_name}: {value};\n"
                )

            new_css = (
                css[:rule_match.start("body")]
                + new_body
                + css[rule_match.end("body"):]
            )

            changed = True
            return opening + new_css + closing

        return match.group(0)

    result = style_pattern.sub(
        replace_style,
        html,
    )

    return result, changed


# =========================================================
# AJOUT D'UNE RÈGLE CSS
# =========================================================

def append_css_rule(
    html: str,
    selector: str,
    property_name: str,
    value: str,
) -> tuple[str, bool]:

    style_pattern = re.compile(
        r"(<style\b[^>]*>)(.*?)(</style>)",
        re.IGNORECASE | re.DOTALL,
    )

    matches = list(style_pattern.finditer(html))

    if not matches:
        return html, False

    # On ajoute la règle dans le premier <style>.
    match = matches[0]

    opening = match.group(1)
    css = match.group(2)
    closing = match.group(3)

    new_rule = (
        f"\n\n"
        f"{selector} {{\n"
        f"    {property_name}: {value};\n"
        f"}}\n"
    )

    new_style = (
        opening
        + css.rstrip()
        + new_rule
        + closing
    )

    result = (
        html[:match.start()]
        + new_style
        + html[match.end():]
    )

    return result, True


# =========================================================
# FALLBACK POUR LES SELECTEURS COURANTS
# =========================================================

def selector_fallback(
    selector: str,
    property_name: str,
) -> str | None:

    selector = normalize_selector(selector)

    # Fond général de la page
    if selector in {
        "page",
        "body",
        "html",
        ":root",
    }:
        return "body"

    # Alias fréquents
    aliases = {
        "header": "header",
        "en-tete": "header",
        "entete": "header",
        "footer": "footer",
        "hero": ".hero",
        "navigation": "nav",
        "navbar": "nav",
        "menu": "nav",
        "contenu": "main",
        "content": "main",
    }

    normalized = normalize_text(selector)

    return aliases.get(normalized)


# =========================================================
# APPLICATION DES CHANGEMENTS
# =========================================================

def apply_css_changes(
    html: str,
    changes: list[dict],
) -> str:

    current_html = html
    applied_count = 0

    for change in changes:
        if not isinstance(change, dict):
            continue

        property_name = str(
            change.get("property", "")
        ).strip().lower()

        selector = str(
            change.get("selector", "")
        ).strip()

        instruction = str(
            change.get("instruction", "")
        ).strip()

        if not property_name or not selector:
            continue

        value = infer_css_value(
            property_name,
            instruction,
        )

        if not value:
            continue

        # -------------------------------------------------
        # 1. Modification directe de la règle existante
        # -------------------------------------------------

        updated_html, changed = update_css_rule(
            current_html,
            selector,
            property_name,
            value,
        )

        if changed:
            current_html = updated_html
            applied_count += 1
            continue

        # -------------------------------------------------
        # 2. Tentative avec un sélecteur équivalent
        # -------------------------------------------------

        fallback = selector_fallback(
            selector,
            property_name,
        )

        if fallback and fallback != selector:
            updated_html, changed = update_css_rule(
                current_html,
                fallback,
                property_name,
                value,
            )

            if changed:
                current_html = updated_html
                applied_count += 1
                continue

        # -------------------------------------------------
        # 3. Si la règle n'existe pas, on la crée.
        #
        # C'est le point important de cette version.
        # -------------------------------------------------

        target_selector = fallback or selector

        updated_html, changed = append_css_rule(
            current_html,
            target_selector,
            property_name,
            value,
        )

        if changed:
            current_html = updated_html
            applied_count += 1

    # -----------------------------------------------------
    # Aucun changement
    # -----------------------------------------------------

    if applied_count == 0:
        return html

    return current_html