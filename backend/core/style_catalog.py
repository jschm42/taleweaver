from typing import Any, Optional


_DEFAULT_IMAGE_STYLES: list[dict[str, Any]] = [
    {
        "id": "dark-fantasy-painting",
        "name": "Dark Fantasy Painting",
        "description": "Moody brushwork with dramatic contrast and medieval grit.",
        "instruction": "dark fantasy painting, dramatic chiaroscuro, textured brush strokes, rich atmosphere",
        "image_url": "/assets/catalog/styles/dark-fantasy-painting.jpg",
    },
    {
        "id": "cinematic-realism",
        "name": "Cinematic Realism",
        "description": "Film-like composition with realistic lighting and depth.",
        "instruction": "cinematic realism, volumetric lighting, detailed environment, film still composition",
        "image_url": "/assets/catalog/styles/cinematic-realism.jpg",
    },
    {
        "id": "stylized-rpg-art",
        "name": "Stylized RPG Art",
        "description": "Bold outlines, vivid palettes, and heroic fantasy readability.",
        "instruction": "stylized RPG concept art, clean silhouettes, vibrant but grounded colors",
        "image_url": "/assets/catalog/styles/stylized-rpg-art.jpg",
    },
    {
        "id": "grimdark-ink-sketch",
        "name": "Grimdark Ink Sketch",
        "description": "Raw, hand-drawn aesthetic with heavy ink washes and scratched textures.",
        "instruction": "grimdark ink sketch, cross-hatching, distressed paper texture, high contrast black and white",
        "image_url": "/assets/catalog/styles/grimdark-ink-sketch.jpg",
    },
    {
        "id": "cyberpunk-neon",
        "name": "Cyberpunk Neon",
        "description": "Vibrant neon lights, rainy cityscapes, and high-tech grit.",
        "instruction": "cyberpunk aesthetic, synthwave colors, neon glow, wet asphalt reflections, futuristic noir",
        "image_url": "/assets/catalog/styles/cyberpunk-neon.jpg",
    },
    {
        "id": "ethereal-watercolor",
        "name": "Ethereal Watercolor",
        "description": "Soft, bleeding colors with a dreamlike, mystical atmosphere.",
        "instruction": "ethereal watercolor painting, soft edges, bleeding pigments, mystical light, dreamy pastel tones",
        "image_url": "/assets/catalog/styles/ethereal-watercolor.jpg",
    },
    {
        "id": "science-fiction",
        "name": "Science-Fiction",
        "description": "Futuristic tech, vast space, and advanced starships.",
        "instruction": "futuristic science fiction world, starships in the sky, sleek high tech architecture, glowing neon lights, cinematic composition",
        "image_url": "/assets/catalog/styles/science-fiction.jpg",
    },
    {
        "id": "pixelart",
        "name": "Pixelart",
        "description": "Classic 90s adventure style with vibrant colors and charming pixels.",
        "instruction": "90s point and click adventure game pixel art, LucasArts style, vibrant limited color palette, pixelated aesthetic",
        "image_url": "/assets/catalog/styles/pixelart.jpg",
    },
]


def default_image_styles_catalog() -> list[dict[str, Any]]:
    """Return a copy of default image styles to avoid accidental mutation."""
    return [dict(item) for item in _DEFAULT_IMAGE_STYLES]


def resolve_style_instruction(
    selected_image_styles: Optional[list[Any]],
    user_catalog: Optional[list[dict[str, Any]]],
) -> str:
    """Resolve style instruction from selected style, then user catalog, then default catalog."""
    if not selected_image_styles:
        return ""

    first_style = selected_image_styles[0]
    style_id = None

    if isinstance(first_style, dict):
        direct_instruction = (first_style.get("instruction") or "").strip()
        if direct_instruction:
            return direct_instruction
        style_id = first_style.get("id") or first_style.get("name")
    elif isinstance(first_style, str):
        style_id = first_style

    if not style_id:
        return ""

    for catalog in (user_catalog or [], default_image_styles_catalog()):
        for entry in catalog:
            if entry.get("id") == style_id or entry.get("name") == style_id:
                return (entry.get("instruction") or "").strip()

    return ""
