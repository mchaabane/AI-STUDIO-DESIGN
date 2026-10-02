import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageStat


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DESIGN_LIBRARY_DIR = PROJECT_ROOT / "design-library"
PROJECTS_DIR = DESIGN_LIBRARY_DIR / "projets"
PROFILE_FILE = DESIGN_LIBRARY_DIR / "design-profile.json"


COLOR_DISTANCE_THRESHOLD = 28
IMAGE_SAMPLE_SIZE = 300
MAX_COLORS_PER_PROJECT = 8
MAX_PROFILE_COLORS = 12
WHITESPACE_THRESHOLD = 242
DARK_THRESHOLD = 70



def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def color_distance(
    first: tuple[int, int, int],
    second: tuple[int, int, int],
) -> float:
    return math.sqrt(
        (first[0] - second[0]) ** 2
        + (first[1] - second[1]) ** 2
        + (first[2] - second[2]) ** 2
    )


def classify_color(rgb: tuple[int, int, int]) -> str:
    red, green, blue = rgb

    brightness = (red + green + blue) / 3
    maximum = max(rgb)
    minimum = min(rgb)

    if brightness >= 245 and maximum - minimum <= 12:
        return "white"

    if brightness <= 35 and maximum - minimum <= 20:
        return "black"

    if maximum - minimum <= 18:
        if brightness >= 220:
            return "light-gray"
        if brightness >= 140:
            return "gray"
        return "dark-gray"

    if red > green * 1.12 and red > blue * 1.08:
        if red >= 220 and green >= 180:
            return "warm-light"
        return "red-pink"

    if green > red * 1.12 and green > blue * 1.05:
        return "green"

    if blue > red * 1.12 and blue > green * 1.04:
        if blue >= 190 and red >= 130:
            return "cool-light"
        return "blue"

    if red >= 170 and green >= 130 and blue <= 120:
        return "orange-yellow"

    if red >= 130 and blue >= 100 and green <= red * 0.9:
        return "purple-magenta"

    return "mixed"


def merge_similar_colors(
    counter: Counter,
    threshold: float = COLOR_DISTANCE_THRESHOLD,
) -> list[dict]:
    groups: list[dict] = []

    for rgb, count in counter.most_common():
        matched_group = None

        for group in groups:
            if color_distance(
                rgb,
                group["representative"],
            ) <= threshold:
                matched_group = group
                break

        if matched_group is None:
            groups.append(
                {
                    "representative": rgb,
                    "count": count,
                    "samples": 1,
                }
            )
            continue

        old_count = matched_group["count"]
        new_count = old_count + count
        representative = matched_group["representative"]

        weighted = (
            (
                representative[0] * old_count
                + rgb[0] * count
            )
            / new_count,
            (
                representative[1] * old_count
                + rgb[1] * count
            )
            / new_count,
            (
                representative[2] * old_count
                + rgb[2] * count
            )
            / new_count,
        )

        matched_group["representative"] = tuple(
            round(value) for value in weighted
        )
        matched_group["count"] = new_count
        matched_group["samples"] += 1

    return groups


def get_image_pixels(image: Image.Image) -> list:
    if hasattr(image, "get_flattened_data"):
        return list(image.get_flattened_data())

    return list(image.getdata())


def extract_dominant_colors(
    image: Image.Image,
    limit: int = MAX_COLORS_PER_PROJECT,
) -> list[dict]:
    rgb_image = image.convert("RGB")
    rgb_image.thumbnail(
        (IMAGE_SAMPLE_SIZE, IMAGE_SAMPLE_SIZE)
    )

    colors = get_image_pixels(rgb_image)

    if not colors:
        return []

    counter = Counter(colors)
    groups = merge_similar_colors(counter)

    total = len(colors)
    result = []

    for group in groups[:limit]:
        representative = group["representative"]

        result.append(
            {
                "color": rgb_to_hex(representative),
                "family": classify_color(representative),
                "percentage": round(
                    (group["count"] / total) * 100,
                    2,
                ),
                "variations": group["samples"],
            }
        )

    return result


def calculate_visual_density(
    image: Image.Image,
) -> dict:
    """
    Estime la densité visuelle à partir de la diversité
    des couleurs et du contraste moyen.

    Ce n'est pas une compréhension sémantique de l'interface :
    c'est un indicateur visuel automatique.
    """
    sample = image.convert("RGB")
    sample.thumbnail(
        (IMAGE_SAMPLE_SIZE, IMAGE_SAMPLE_SIZE)
    )

    pixels = get_image_pixels(sample)

    if not pixels:
        return {
            "score": 0,
            "level": "unknown",
            "average_brightness": 0,
            "contrast": 0,
            "color_diversity": 0,
        }

    brightness_values = [
        (pixel[0] + pixel[1] + pixel[2]) / 3
        for pixel in pixels
    ]

    average_brightness = sum(
        brightness_values
    ) / len(brightness_values)

    brightness_std = math.sqrt(
        sum(
            (value - average_brightness) ** 2
            for value in brightness_values
        )
        / len(brightness_values)
    )

    reduced_colors = Counter(
        (
            pixel[0] // 32,
            pixel[1] // 32,
            pixel[2] // 32,
        )
        for pixel in pixels
    )

    color_diversity = len(reduced_colors)

    contrast = min(
        100,
        brightness_std * 2,
    )

    diversity_score = min(
        100,
        color_diversity / 2,
    )

    score = round(
        min(
            100,
            contrast * 0.6
            + diversity_score * 0.4,
        ),
        2,
    )

    if score < 20:
        level = "very-low"
    elif score < 40:
        level = "low"
    elif score < 65:
        level = "medium"
    elif score < 80:
        level = "high"
    else:
        level = "very-high"

    return {
        "score": score,
        "level": level,
        "average_brightness": round(
            average_brightness,
            2,
        ),
        "contrast": round(
            contrast,
            2,
        ),
        "color_diversity": color_diversity,
    }


def calculate_edge_density(
    image: Image.Image,
) -> dict:
    """
    Estime la quantité de transitions visuelles dans l'image.
    Cela donne un indice complémentaire de complexité/densité.
    """
    gray = image.convert("L")
    gray.thumbnail(
        (IMAGE_SAMPLE_SIZE, IMAGE_SAMPLE_SIZE)
    )

    width, height = gray.size

    if width < 2 or height < 2:
        return {
            "score": 0,
            "level": "unknown",
        }

    pixels = get_image_pixels(gray)
    differences = []

    for y in range(height):
        row_offset = y * width

        for x in range(width):
            current = pixels[row_offset + x]

            if x + 1 < width:
                right = pixels[row_offset + x + 1]
                differences.append(
                    abs(current - right)
                )

            if y + 1 < height:
                below = pixels[
                    row_offset + width + x
                ]
                differences.append(
                    abs(current - below)
                )

    if not differences:
        return {
            "score": 0,
            "level": "unknown",
        }

    average_difference = sum(
        differences
    ) / len(differences)

    score = round(
        min(
            100,
            average_difference * 2.5,
        ),
        2,
    )

    if score < 15:
        level = "very-low"
    elif score < 30:
        level = "low"
    elif score < 50:
        level = "medium"
    elif score < 70:
        level = "high"
    else:
        level = "very-high"

    return {
        "score": score,
        "level": level,
    }


def calculate_brightness_profile(
    image: Image.Image,
) -> dict:
    """
    Donne une indication simple sur le caractère clair,
    moyen ou sombre du visuel.
    """
    rgb_image = image.convert("RGB")
    stat = ImageStat.Stat(rgb_image)

    average_rgb = stat.mean

    brightness = (
        average_rgb[0]
        + average_rgb[1]
        + average_rgb[2]
    ) / 3

    if brightness >= 210:
        mode = "light"
    elif brightness >= 125:
        mode = "balanced"
    else:
        mode = "dark"

    return {
        "mode": mode,
        "average_rgb": [
            round(value, 2)
            for value in average_rgb
        ],
        "average_brightness": round(
            brightness,
            2,
        ),
    }



def calculate_composition_profile(image: Image.Image) -> dict:
    """
    Décrit la composition visible sans prétendre identifier des
    composants HTML ou du texte.

    Les mesures portent sur la répartition des zones claires/sombres,
    la concentration visuelle et les directions dominantes.
    """
    sample = image.convert("L")
    sample.thumbnail((IMAGE_SAMPLE_SIZE, IMAGE_SAMPLE_SIZE))

    width, height = sample.size
    if width == 0 or height == 0:
        return {
            "whitespace_ratio": 0,
            "dark_area_ratio": 0,
            "visual_center": {"x": 0.5, "y": 0.5},
            "horizontal_structure": 0,
            "vertical_structure": 0,
            "composition": "balanced",
        }

    pixels = get_image_pixels(sample)
    total = len(pixels)

    whitespace = sum(
        1 for value in pixels if value >= WHITESPACE_THRESHOLD
    ) / total
    dark_area = sum(
        1 for value in pixels if value <= DARK_THRESHOLD
    ) / total

    weighted_total = sum(max(0, 255 - value) for value in pixels)
    if weighted_total:
        center_x = sum(
            (index % width) * max(0, 255 - value)
            for index, value in enumerate(pixels)
        ) / weighted_total / max(width - 1, 1)
        center_y = sum(
            (index // width) * max(0, 255 - value)
            for index, value in enumerate(pixels)
        ) / weighted_total / max(height - 1, 1)
    else:
        center_x = 0.5
        center_y = 0.5

    horizontal_differences = []
    vertical_differences = []

    for y in range(height):
        row = y * width
        for x in range(width - 1):
            horizontal_differences.append(
                abs(pixels[row + x] - pixels[row + x + 1])
            )

    for y in range(height - 1):
        row = y * width
        next_row = row + width
        for x in range(width):
            vertical_differences.append(
                abs(pixels[row + x] - pixels[next_row + x])
            )

    horizontal_structure = (
        min(100, sum(horizontal_differences) / len(horizontal_differences) * 2.5)
        if horizontal_differences
        else 0
    )
    vertical_structure = (
        min(100, sum(vertical_differences) / len(vertical_differences) * 2.5)
        if vertical_differences
        else 0
    )

    if whitespace >= 0.65:
        composition = "airy"
    elif whitespace <= 0.25 and dark_area >= 0.25:
        composition = "dense"
    elif abs(center_x - 0.5) <= 0.08 and abs(center_y - 0.5) <= 0.08:
        composition = "centered"
    elif center_x < 0.43 or center_x > 0.57 or center_y < 0.43 or center_y > 0.57:
        composition = "asymmetric"
    else:
        composition = "balanced"

    return {
        "whitespace_ratio": round(whitespace * 100, 2),
        "dark_area_ratio": round(dark_area * 100, 2),
        "visual_center": {
            "x": round(center_x, 3),
            "y": round(center_y, 3),
        },
        "horizontal_structure": round(horizontal_structure, 2),
        "vertical_structure": round(vertical_structure, 2),
        "composition": composition,
    }



def calculate_shape_profile(image: Image.Image) -> dict:
    """
    Estime le langage géométrique visible de l'interface.

    Cette analyse reste volontairement visuelle : elle ne prétend pas
    reconnaître le HTML réel. Elle cherche surtout à mesurer la présence
    de géométries rectilignes, de courbes et de coins arrondis afin que
    le profil de design puisse conserver une signature de forme.
    """
    sample = image.convert("L")
    sample.thumbnail((IMAGE_SAMPLE_SIZE, IMAGE_SAMPLE_SIZE))

    width, height = sample.size
    if width < 3 or height < 3:
        return {
            "geometry": "unknown",
            "corner_style": "unknown",
            "rectangularity": 0,
            "roundedness": 0,
            "horizontal_edge_ratio": 0,
            "vertical_edge_ratio": 0,
            "diagonal_edge_ratio": 0,
        }

    pixels = get_image_pixels(sample)

    # Un gradient simple permet de repérer les contours sans dépendance
    # supplémentaire à OpenCV ou à une autre librairie.
    horizontal_edges = 0
    vertical_edges = 0
    diagonal_edges = 0
    edge_total = 0

    threshold = 28

    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            center = pixels[row + x]
            left = pixels[row + x - 1]
            right = pixels[row + x + 1]
            above = pixels[row - width + x]
            below = pixels[row + width + x]

            horizontal_change = abs(left - right)
            vertical_change = abs(above - below)

            if horizontal_change < threshold and vertical_change < threshold:
                continue

            edge_total += 1

            if horizontal_change >= threshold and vertical_change < threshold:
                vertical_edges += 1
            elif vertical_change >= threshold and horizontal_change < threshold:
                horizontal_edges += 1
            else:
                diagonal_edges += 1

    if edge_total:
        horizontal_ratio = horizontal_edges / edge_total * 100
        vertical_ratio = vertical_edges / edge_total * 100
        diagonal_ratio = diagonal_edges / edge_total * 100
    else:
        horizontal_ratio = 0
        vertical_ratio = 0
        diagonal_ratio = 0

    # Les interfaces très rectangulaires produisent beaucoup de transitions
    # horizontales/verticales et peu de diagonales.
    rectangularity = min(
        100,
        (horizontal_ratio + vertical_ratio) * 1.15,
    )

    roundedness = min(
        100,
        diagonal_ratio * 2.0,
    )

    # Une estimation supplémentaire des coins : on observe les petites
    # zones de coin de cellules sombres/claires. Les coins très nets ont
    # généralement une transition abrupte sur les deux axes, tandis que
    # les coins arrondis ont une transition plus progressive.
    corner_scores = []

    patch = max(4, min(width, height) // 12)
    corner_positions = [
        (0, 0),
        (width - patch, 0),
        (0, height - patch),
        (width - patch, height - patch),
    ]

    for start_x, start_y in corner_positions:
        local_edges = 0
        local_diagonal = 0

        for dy in range(min(patch, height - start_y)):
            for dx in range(min(patch, width - start_x)):
                x = start_x + dx
                y = start_y + dy

                if x + 1 >= width or y + 1 >= height:
                    continue

                current = pixels[y * width + x]
                right = pixels[y * width + x + 1]
                below = pixels[(y + 1) * width + x]

                horizontal = abs(current - right)
                vertical = abs(current - below)

                if horizontal >= threshold or vertical >= threshold:
                    local_edges += 1

                    if horizontal >= threshold and vertical >= threshold:
                        local_diagonal += 1

        if local_edges:
            corner_scores.append(
                local_diagonal / local_edges * 100
            )

    corner_curve_score = (
        sum(corner_scores) / len(corner_scores)
        if corner_scores
        else 0
    )

    roundedness = round(
        min(100, roundedness * 0.7 + corner_curve_score * 0.3),
        2,
    )
    rectangularity = round(rectangularity, 2)

    if rectangularity >= 62 and roundedness < 35:
        geometry = "rectangular"
    elif roundedness >= 55:
        geometry = "soft-organic"
    else:
        geometry = "mixed"

    if roundedness >= 65:
        corner_style = "rounded"
    elif roundedness >= 35:
        corner_style = "mixed"
    else:
        corner_style = "sharp"

    return {
        "geometry": geometry,
        "corner_style": corner_style,
        "rectangularity": rectangularity,
        "roundedness": roundedness,
        "horizontal_edge_ratio": round(horizontal_ratio, 2),
        "vertical_edge_ratio": round(vertical_ratio, 2),
        "diagonal_edge_ratio": round(diagonal_ratio, 2),
    }


def calculate_color_balance(image: Image.Image) -> dict:
    """Décrit la balance chaud/froid et clair/sombre du visuel."""
    rgb = image.convert("RGB")
    rgb.thumbnail((IMAGE_SAMPLE_SIZE, IMAGE_SAMPLE_SIZE))
    pixels = get_image_pixels(rgb)

    if not pixels:
        return {
            "warm_ratio": 0,
            "cool_ratio": 0,
            "neutral_ratio": 0,
            "dominant_temperature": "neutral",
        }

    warm = 0
    cool = 0
    neutral = 0

    for red, green, blue in pixels:
        spread = max(red, green, blue) - min(red, green, blue)
        if spread <= 18:
            neutral += 1
        elif red > blue * 1.08:
            warm += 1
        elif blue > red * 1.08:
            cool += 1
        else:
            neutral += 1

    total = len(pixels)
    warm_ratio = warm / total * 100
    cool_ratio = cool / total * 100
    neutral_ratio = neutral / total * 100

    if warm_ratio >= cool_ratio + 10:
        temperature = "warm"
    elif cool_ratio >= warm_ratio + 10:
        temperature = "cool"
    else:
        temperature = "neutral"

    return {
        "warm_ratio": round(warm_ratio, 2),
        "cool_ratio": round(cool_ratio, 2),
        "neutral_ratio": round(neutral_ratio, 2),
        "dominant_temperature": temperature,
    }


def build_visual_style_summary(project_results: list[dict]) -> dict:
    if not project_results:
        return {
            "composition_distribution": {},
            "temperature_distribution": {},
            "average_whitespace_ratio": None,
            "average_dark_area_ratio": None,
            "average_horizontal_structure": None,
            "average_vertical_structure": None,
            "shape": {
                "geometry_distribution": {},
                "corner_style_distribution": {},
                "average_rectangularity": None,
                "average_roundedness": None,
                "preferred_geometry": None,
                "preferred_corner_style": None,
            },
        }

    compositions = Counter(
        project["visual_analysis"]["composition"]["composition"]
        for project in project_results
    )
    temperatures = Counter(
        project["visual_analysis"]["color_balance"]["dominant_temperature"]
        for project in project_results
    )

    geometries = Counter(
        project["visual_analysis"]["shape"]["geometry"]
        for project in project_results
    )
    corner_styles = Counter(
        project["visual_analysis"]["shape"]["corner_style"]
        for project in project_results
    )

    def average(key: str) -> float | None:
        values = [
            project["visual_analysis"]["composition"][key]
            for project in project_results
        ]
        return round(sum(values) / len(values), 2) if values else None

    shape_rectangularity = [
        project["visual_analysis"]["shape"]["rectangularity"]
        for project in project_results
    ]
    shape_roundedness = [
        project["visual_analysis"]["shape"]["roundedness"]
        for project in project_results
    ]

    return {
        "composition_distribution": dict(compositions),
        "temperature_distribution": dict(temperatures),
        "average_whitespace_ratio": average("whitespace_ratio"),
        "average_dark_area_ratio": average("dark_area_ratio"),
        "average_horizontal_structure": average("horizontal_structure"),
        "average_vertical_structure": average("vertical_structure"),
        "shape": {
            "geometry_distribution": dict(geometries),
            "corner_style_distribution": dict(corner_styles),
            "average_rectangularity": round(
                sum(shape_rectangularity) / len(shape_rectangularity),
                2,
            ) if shape_rectangularity else None,
            "average_roundedness": round(
                sum(shape_roundedness) / len(shape_roundedness),
                2,
            ) if shape_roundedness else None,
            "preferred_geometry": (
                geometries.most_common(1)[0][0]
                if geometries
                else None
            ),
            "preferred_corner_style": (
                corner_styles.most_common(1)[0][0]
                if corner_styles
                else None
            ),
        },
    }


def analyze_image(image_path: Path) -> dict:
    """
    Analyse un projet visuel.

    Les métriques sont descriptives : elles ne prétendent pas
    comprendre le contenu HTML ou la structure réelle de l'interface.
    """
    with Image.open(image_path) as image:
        colors = extract_dominant_colors(image)
        density = calculate_visual_density(image)
        edge_density = calculate_edge_density(image)
        brightness = calculate_brightness_profile(
            image
        )
        composition = calculate_composition_profile(image)
        color_balance = calculate_color_balance(image)
        shape = calculate_shape_profile(image)

        return {
            "file": str(
                image_path.relative_to(
                    DESIGN_LIBRARY_DIR
                )
            ),
            "width": image.width,
            "height": image.height,
            "aspect_ratio": round(
                image.width / image.height,
                3,
            )
            if image.height
            else None,
            "orientation": (
                "landscape"
                if image.width > image.height
                else "portrait"
                if image.height > image.width
                else "square"
            ),
            "dominant_colors": colors,
            "visual_analysis": {
                "density": density,
                "edge_density": edge_density,
                "brightness": brightness,
                "composition": composition,
                "color_balance": color_balance,
                "shape": shape,
            },
        }


def find_design_images() -> list[Path]:
    supported_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".avif",
    }

    if not PROJECTS_DIR.exists():
        return []

    return sorted(
        path
        for path in PROJECTS_DIR.rglob("*")
        if path.is_file()
        and path.suffix.lower()
        in supported_extensions
    )


def load_profile() -> dict:
    if not PROFILE_FILE.exists():
        return {
            "profile_version": 1,
            "colors": {
                "primary": [],
                "secondary": [],
                "accent": [],
                "background": [],
                "surface": [],
                "text": [],
                "muted_text": [],
                "border": [],
                "success": [],
                "warning": [],
                "error": [],
            },
            "typography": {
                "font_families": [],
                "heading_sizes": [],
                "body_sizes": [],
                "font_weights": [],
                "line_heights": [],
            },
            "spacing": {
                "values": [],
                "section_spacing": [],
                "component_spacing": [],
                "content_padding": [],
            },
            "shape": {
                "border_radius": [],
                "border_widths": [],
                "geometry_distribution": {},
                "corner_style_distribution": {},
                "average_rectangularity": None,
                "average_roundedness": None,
                "preferred_geometry": None,
                "preferred_corner_style": None,
            },
            "effects": {
                "shadows": [],
                "opacity_values": [],
                "blur_values": [],
            },
            "layout": {
                "max_widths": [],
                "grid_columns": [],
                "gaps": [],
                "alignment_patterns": [],
            },
            "components": {
                "buttons": [],
                "cards": [],
                "navigation": [],
                "hero": [],
                "forms": [],
                "modals": [],
                "other": [],
            },
            "style_patterns": {
                "visual_density": [],
                "design_patterns": [],
                "interaction_patterns": [],
            },
            "preferences": {
                "preferred_colors": [],
                "avoided_colors": [],
                "preferred_fonts": [],
                "preferred_shapes": [],
                "preferred_layouts": [],
            },
            "projects_analyzed": [],
            "analysis": {
                "total_projects": 0,
                "last_analysis": None,
            },
        }

    return json.loads(
        PROFILE_FILE.read_text(
            encoding="utf-8",
        )
    )


def save_profile(profile: dict) -> None:
    PROFILE_FILE.write_text(
        json.dumps(
            profile,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def build_profile_color_groups(
    project_results: list[dict],
) -> list[dict]:
    groups: list[dict] = []

    for project in project_results:
        for color in project["dominant_colors"]:
            rgb = hex_to_rgb(color["color"])

            matched_group = None

            for group in groups:
                if color_distance(
                    rgb,
                    group["representative"],
                ) <= COLOR_DISTANCE_THRESHOLD:
                    matched_group = group
                    break

            if matched_group is None:
                groups.append(
                    {
                        "representative": rgb,
                        "project_ids": {
                            project["file"]
                        },
                        "weights": {
                            project["file"]: color[
                                "percentage"
                            ]
                        },
                    }
                )
                continue

            project_id = project["file"]

            if project_id not in matched_group[
                "project_ids"
            ]:
                matched_group["project_ids"].add(
                    project_id
                )
                matched_group["weights"][
                    project_id
                ] = color["percentage"]
            else:
                matched_group["weights"][
                    project_id
                ] += color["percentage"]

    results = []

    for group in groups:
        project_count = len(
            group["project_ids"]
        )

        weights = list(
            group["weights"].values()
        )

        average_weight = (
            sum(weights) / len(weights)
            if weights
            else 0
        )

        results.append(
            {
                "representative": group[
                    "representative"
                ],
                "project_count": project_count,
                "average_weight": round(
                    average_weight,
                    2,
                ),
            }
        )

    return sorted(
        results,
        key=lambda item: (
            item["project_count"],
            item["average_weight"],
        ),
        reverse=True,
    )


def build_profile_visual_summary(
    project_results: list[dict],
) -> dict:
    if not project_results:
        return {
            "orientation_distribution": {},
            "brightness_distribution": {},
            "density_distribution": {},
            "average_aspect_ratio": None,
            "average_density_score": None,
            "average_edge_density_score": None,
            "average_brightness": None,
            "visual_style": build_visual_style_summary(project_results),
        }

    orientations = Counter(
        project["orientation"]
        for project in project_results
    )

    brightness_modes = Counter(
        project["visual_analysis"][
            "brightness"
        ]["mode"]
        for project in project_results
    )

    density_levels = Counter(
        project["visual_analysis"][
            "density"
        ]["level"]
        for project in project_results
    )

    aspect_ratios = [
        project["aspect_ratio"]
        for project in project_results
        if project["aspect_ratio"] is not None
    ]

    density_scores = [
        project["visual_analysis"][
            "density"
        ]["score"]
        for project in project_results
    ]

    edge_scores = [
        project["visual_analysis"][
            "edge_density"
        ]["score"]
        for project in project_results
    ]

    brightness_values = [
        project["visual_analysis"][
            "brightness"
        ]["average_brightness"]
        for project in project_results
    ]

    return {
        "orientation_distribution": dict(
            orientations
        ),
        "brightness_distribution": dict(
            brightness_modes
        ),
        "density_distribution": dict(
            density_levels
        ),
        "average_aspect_ratio": round(
            sum(aspect_ratios)
            / len(aspect_ratios),
            3,
        )
        if aspect_ratios
        else None,
        "average_density_score": round(
            sum(density_scores)
            / len(density_scores),
            2,
        )
        if density_scores
        else None,
        "average_edge_density_score": round(
            sum(edge_scores)
            / len(edge_scores),
            2,
        )
        if edge_scores
        else None,
        "average_brightness": round(
            sum(brightness_values)
            / len(brightness_values),
            2,
        )
        if brightness_values
        else None,
        "visual_style": build_visual_style_summary(project_results),
    }


def analyze_design_library() -> dict:
    profile = load_profile()
    image_paths = find_design_images()

    analyzed_projects = []

    for image_path in image_paths:
        analyzed_projects.append(
            analyze_image(image_path)
        )

    profile["projects_analyzed"] = (
        analyzed_projects
    )

    profile["analysis"]["total_projects"] = (
        len(analyzed_projects)
    )

    profile["analysis"]["last_analysis"] = (
        datetime.now(timezone.utc).isoformat()
    )

    profile["analysis"][
        "visual_summary"
    ] = build_profile_visual_summary(
        analyzed_projects
    )

    profile["colors"]["primary"] = [
        {
            "color": rgb_to_hex(
                group["representative"]
            ),
            "family": classify_color(
                group["representative"]
            ),
            "project_count": group[
                "project_count"
            ],
            "projects_total": len(
                analyzed_projects
            ),
            "average_weight": group[
                "average_weight"
            ],
        }
        for group in build_profile_color_groups(
            analyzed_projects
        )[:MAX_PROFILE_COLORS]
    ]

    save_profile(profile)

    return profile


if __name__ == "__main__":
    profile = analyze_design_library()

    print(
        "Analyse terminée : "
        f"{profile['analysis']['total_projects']} "
        "projet(s) analysé(s)."
    )

    print("\nFamilles de couleurs dominantes:")

    for color in profile["colors"]["primary"]:
        print(
            f"  {color['color']} "
            f"· {color['family']} "
            f"· {color['average_weight']}% moyen "
            f"· {color['project_count']}/"
            f"{color['projects_total']} projet(s)"
        )

    summary = profile["analysis"].get(
        "visual_summary",
        {},
    )

    print("\nRésumé visuel:")

    print(
        "  Orientation : "
        f"{summary.get('orientation_distribution', {})}"
    )

    print(
        "  Luminosité : "
        f"{summary.get('brightness_distribution', {})}"
    )

    print(
        "  Densité : "
        f"{summary.get('density_distribution', {})}"
    )

    print(
        "  Ratio moyen : "
        f"{summary.get('average_aspect_ratio')}"
    )

    print(
        "  Score de densité moyen : "
        f"{summary.get('average_density_score')}"
    )

    print(
        "  Score de transitions moyen : "
        f"{summary.get('average_edge_density_score')}"
    )

    visual_style = summary.get("visual_style", {})

    print(
        "  Composition : "
        f"{visual_style.get('composition_distribution', {})}"
    )

    print(
        "  Espace blanc moyen : "
        f"{visual_style.get('average_whitespace_ratio')}%"
    )

    print(
        "  Température : "
        f"{visual_style.get('temperature_distribution', {})}"
    )

    shape = visual_style.get("shape", {})

    print(
        "  Géométrie : "
        f"{shape.get('geometry_distribution', {})}"
    )

    print(
        "  Coins : "
        f"{shape.get('corner_style_distribution', {})}"
    )

    print(
        "  Arrondi moyen : "
        f"{shape.get('average_roundedness')}"
    )
