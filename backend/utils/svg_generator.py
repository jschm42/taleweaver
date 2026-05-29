import colorsys
import math
import os
import random
import re

from backend.utils.path_security import ensure_within_data_dir


class SVGPlaceholderGenerator:
    """
    Ein Generator für prozedurale, zufällige SVG-Platzhalterbilder.
    Kann auch vordefinierte SVG-Assets laden und anpassen.
    Folgt Clean Code Prinzipien: Single Responsibility, Type Hinting und Modularität.
    """

    def __init__(self, width: int = 800, height: int = 600, num_shapes: int = 15):
        self.width = width
        self.height = height
        self.num_shapes = num_shapes
        self.viewbox = f"0 0 {self.width} {self.height}"
        
        # Pfad zu den Frontend-Assets relativ zum Projekt-Root
        self.assets_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "frontend", "src", "assets", "svg"
        )

    def _random_hex_color(self, saturation_range: tuple[float, float] = (0.2, 0.5), value_range: tuple[float, float] = (0.1, 0.4)) -> str:
        """
        Generiert eine zufällige, düstere Hex-Farbe basierend auf dem HSV-Farbraum.
        """
        hue = random.random()
        saturation = random.uniform(*saturation_range)
        value = random.uniform(*value_range)
        
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

    def _generate_gradient_defs(self) -> str:
        """Generiert die SVG <defs> mit einem zufälligen linearen Gradienten."""
        color_start = self._random_hex_color()
        color_end = self._random_hex_color()
        angle = random.randint(0, 360)
        
        x1 = round(50 + math.cos(math.radians(angle)) * 50)
        y1 = round(50 + math.sin(math.radians(angle)) * 50)
        x2 = round(50 + math.cos(math.radians(angle + 180)) * 50)
        y2 = round(50 + math.sin(math.radians(angle + 180)) * 50)

        return f"""
        <defs>
            <linearGradient id="bgGradient" x1="{x1}%" y1="{y1}%" x2="{x2}%" y2="{y2}%">
                <stop offset="0%" stop-color="{color_start}" />
                <stop offset="100%" stop-color="{color_end}" />
            </linearGradient>
        </defs>
        """

    def _generate_shapes(self) -> str:
        """Generiert zufällige geometrische Formen."""
        shapes: list[str] = []
        for _ in range(self.num_shapes):
            shape_type = random.choice(["circle", "polygon"])
            color = self._random_hex_color(saturation_range=(0.3, 0.8), value_range=(0.8, 1.0))
            opacity = random.uniform(0.1, 0.6)

            if shape_type == "circle":
                cx = random.randint(0, self.width)
                cy = random.randint(0, self.height)
                r = random.randint(self.width // 10, self.width // 2)
                shapes.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity="{opacity:.2f}"/>')
            else:
                points = []
                for _ in range(3):
                    px = random.randint(-self.width // 4, self.width + self.width // 4)
                    py = random.randint(-self.height // 4, self.height + self.height // 4)
                    points.append(f"{px},{py}")
                points_str = " ".join(points)
                shapes.append(f'<polygon points="{points_str}" fill="{color}" opacity="{opacity:.2f}"/>')

        return "\n".join(shapes)

    def _load_svg_asset(self, filename: str, color_override: str = None) -> str:
        """Lädt eine SVG-Datei aus dem Assets-Ordner und passt optional die Farbe an."""
        path = os.path.join(self.assets_dir, filename)
        if not os.path.exists(path):
            # Fallback auf generisches prozedurales SVG falls Datei fehlt
            return self._generate_fallback_svg()
        
        with open(path, encoding='utf-8') as f:
            content = f.read()
            
        if color_override:
            # Ersetzt alle Vorkommen von fill="..." mit der Wunschfarbe
            content = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', f'fill="{color_override}"', content)
            
        # Extract everything between <svg ...> and </svg>
        match_content = re.search(r'<svg[^>]*>(.*)</svg>', content, re.DOTALL)
        
        # Robust viewBox extraction (handles spaces and commas)
        match_viewbox = re.search(r'viewBox="(-?\d+\.?\d*)[\s,]+(-?\d+\.?\d*)[\s,]+(\d+\.?\d*)[\s,]+(\d+\.?\d*)"', content)
        
        # Fallback to width/height if viewBox is missing
        match_w = re.search(r'\bwidth="(\d+\.?\d*)"', content)
        match_h = re.search(r'\bheight="(\d+\.?\d*)"', content)
        
        if match_content:
            inner_content = match_content.group(1)
            
            # Determine source dimensions
            vb_w, vb_h = 512.0, 512.0
            if match_viewbox:
                vb_w = float(match_viewbox.group(3))
                vb_h = float(match_viewbox.group(4))
            elif match_w and match_h:
                vb_w = float(match_w.group(1))
                vb_h = float(match_h.group(1))
            
            # Target size is 70% of the 512x512 tile
            target_size = 512 * 0.7
            scale = target_size / max(vb_w, vb_h)
            
            # Centering translation
            tx = (512 - (vb_w * scale)) / 2
            ty = (512 - (vb_h * scale)) / 2
            
            return f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">{self._generate_gradient_defs()}<rect width="100%" height="100%" fill="url(#bgGradient)"/><g transform="translate({tx:.1f}, {ty:.1f}) scale({scale:.3f})">{inner_content}</g></svg>'
            
        return content

    def _generate_fallback_svg(self) -> str:
        """Fallbacks falls ein Asset nicht gefunden wird."""
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{self.viewbox}" width="{self.width}" height="{self.height}">
            {self._generate_gradient_defs()}
            <rect width="100%" height="100%" fill="url(#bgGradient)"/>
            {self._generate_shapes()}
        </svg>"""

    def _generate_ra_pawn(self, color: str = "#555555") -> str:
        """Generiert das ra-pawn Icon mit einem größeren Abstand zum Rand."""
        path_data = "M255.875 19.47c-33.142 0-59.844 26.822-59.844 60.186 0 33.364 26.703 60.156 59.845 60.156 33.142 0 59.875-26.792 59.875-60.156S289.017 19.47 255.875 19.47zm-50.688 120.343c-2.908 1.23-5.658 2.53-8.187 3.937-14.467 8.046-21.47 17.86-21.47 27.094 0 9.234 7.003 19.08 21.47 27.125 14.467 8.044 35.51 13.436 58.875 13.436 23.365 0 44.408-5.392 58.875-13.437 14.467-8.047 21.47-17.892 21.47-27.126 0-9.234-7.003-19.048-21.47-27.094-2.53-1.406-5.28-2.708-8.188-3.938-13.696 11.647-31.392 18.688-50.687 18.688-19.3 0-36.996-7.034-50.688-18.688zm78.875 87.906c-8.948 1.54-18.394 2.374-28.187 2.374-9.315 0-18.316-.758-26.875-2.156 2.69 6.923 4.36 14.186 4.906 21.656 2.456 33.554-17.04 69.573-58.47 93.594l-.155.093-.155.095c-20.062 10.653-30.28 24.056-30.28 36.97 0 12.9 10.28 26.46 30.343 37.217 20.062 10.76 48.86 17.844 80.75 17.844s60.687-7.085 80.75-17.844c20.062-10.758 30.343-24.318 30.343-37.218 0-13.127-10.773-26.656-31.655-37.406l-.22-.125-.186-.094c-40.344-23.394-58.705-59.676-55.908-93.22.626-7.497 2.31-14.813 5-21.78zM128.845 395.655c-5.592 3.72-10.256 7.61-13.875 11.53-6.9 7.48-9.94 14.64-9.94 21.845 0 7.206 3.04 14.397 9.94 21.876 6.898 7.48 17.6 14.852 31.28 21.125 27.36 12.547 66.42 20.69 109.625 20.69 43.206 0 82.295-8.143 109.656-20.69 13.682-6.27 24.352-13.644 31.25-21.124 6.9-7.48 9.97-14.67 9.97-21.875 0-7.204-3.07-14.363-9.97-21.842-3.597-3.902-8.238-7.767-13.78-11.47-5.638 15.6-19.584 28.706-37.5 38.313-23.533 12.62-54.947 20.095-89.563 20.095-34.615 0-66.06-7.474-89.593-20.094-17.94-9.62-31.887-22.747-37.5-38.374z"
        # Scale down by factor 0.7 and center within the 512x512 viewbox
        # target_size = 512 * 0.7 = 358.4
        # tx = (512 - 358.4) / 2 = 76.8
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">{self._generate_gradient_defs()}<rect width="100%" height="100%" fill="url(#bgGradient)"/><g transform="translate(76.8, 76.8) scale(0.7)"><path fill="{color}" d="{path_data}"/></g></svg>'

    def generate(self, title: str = "", category: str = "") -> str:
        """Erzeugt das finale SVG basierend auf der Kategorie."""
        cat = category.upper()
        if cat in ["NPC", "AVATAR", "CHARACTER"]:
            # Nutze das ra-pawn Icon für NPCs und Protagonisten (Avatare)
            return self._generate_ra_pawn(color="#555555")
        elif cat.startswith("ITEM"):
            # Check for specific item types
            if "WEAPON" in cat:
                return f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">{self._generate_gradient_defs()}<rect width="100%" height="100%" fill="url(#bgGradient)"/><g transform="translate(0, 0)">' \
                       f'<line x1="256" y1="400" x2="256" y2="112" stroke="#ffffff" stroke-width="24" stroke-linecap="round"/>' \
                       f'<line x1="176" y1="320" x2="336" y2="320" stroke="#ffffff" stroke-width="16" stroke-linecap="round"/>' \
                       f'<line x1="256" y1="320" x2="256" y2="400" stroke="#ffffff" stroke-width="16" stroke-linecap="round"/>' \
                       f'</g></svg>'
            elif "KEY" in cat:
                return f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">{self._generate_gradient_defs()}<rect width="100%" height="100%" fill="url(#bgGradient)"/><g transform="translate(0, 0)">' \
                       f'<circle cx="256" cy="160" r="50" stroke="#ffffff" stroke-width="20" fill="none"/>' \
                       f'<line x1="256" y1="210" x2="256" y2="400" stroke="#ffffff" stroke-width="20" stroke-linecap="round"/>' \
                       f'<line x1="256" y1="310" x2="310" y2="310" stroke="#ffffff" stroke-width="20" stroke-linecap="round"/>' \
                       f'<line x1="256" y1="370" x2="310" y2="370" stroke="#ffffff" stroke-width="20" stroke-linecap="round"/>' \
                       f'</g></svg>'
            elif "CONSUMABLE" in cat or "POTION" in cat:
                return f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">{self._generate_gradient_defs()}<rect width="100%" height="100%" fill="url(#bgGradient)"/><g transform="translate(0, 0)">' \
                       f'<circle cx="256" cy="320" r="100" stroke="#ffffff" stroke-width="20" fill="none"/>' \
                       f'<rect x="220" y="140" width="72" height="80" stroke="#ffffff" stroke-width="20" fill="none" rx="8"/>' \
                       f'<line x1="256" y1="220" x2="256" y2="320" stroke="#ffffff" stroke-width="12" stroke-dasharray="8 8"/>' \
                       f'</g></svg>'
            elif "READABLE" in cat or "BOOK" in cat or "SCROLL" in cat:
                return f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">{self._generate_gradient_defs()}<rect width="100%" height="100%" fill="url(#bgGradient)"/><g transform="translate(0, 0)">' \
                       f'<rect x="140" y="110" width="232" height="292" stroke="#ffffff" stroke-width="20" fill="none" rx="12"/>' \
                       f'<line x1="256" y1="110" x2="256" y2="402" stroke="#ffffff" stroke-width="12"/>' \
                       f'<line x1="170" y1="180" x2="230" y2="180" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>' \
                       f'<line x1="170" y1="240" x2="230" y2="240" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>' \
                       f'<line x1="170" y1="300" x2="230" y2="300" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>' \
                       f'<line x1="282" y1="180" x2="342" y2="180" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>' \
                       f'<line x1="282" y1="240" x2="342" y2="240" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>' \
                       f'<line x1="282" y1="300" x2="342" y2="300" stroke="#ffffff" stroke-width="8" stroke-linecap="round"/>' \
                       f'</g></svg>'
            elif "WEARABLE" in cat or "ARMOR" in cat or "SHIELD" in cat or "HELM" in cat:
                return f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">{self._generate_gradient_defs()}<rect width="100%" height="100%" fill="url(#bgGradient)"/><g transform="translate(0, 0)">' \
                       f'<path d="M 140,140 L 372,140 L 372,256 C 372,340 310,400 256,430 C 202,400 140,340 140,256 Z" stroke="#ffffff" stroke-width="20" fill="none" stroke-linejoin="round"/>' \
                       f'</g></svg>'
            else:
                # Nutze den Lederbeutel als Standard für Items
                return self._load_svg_asset("medieval-leather-pouch.svg", color_override="#555555")
            
        return self._generate_fallback_svg()

    def save(self, filepath: str, title: str = "", category: str = "") -> None:
        """Speichert das SVG in eine Datei."""
        normalized_path = os.path.normpath(filepath)
        filename = os.path.basename(normalized_path)
        if not filename or filename in {".", ".."}:
            raise ValueError("Invalid filepath: invalid filename.")
        if any(sep in filename for sep in (os.sep, os.altsep) if sep):
            raise ValueError("Invalid filepath: filename must be a single path component.")

        resolved_path = ensure_within_data_dir(normalized_path)

        parent_dir = os.path.dirname(resolved_path)
        if not parent_dir:
            raise ValueError("Invalid filepath: missing parent directory.")
        safe_parent_dir = ensure_within_data_dir(parent_dir)
        os.makedirs(safe_parent_dir, exist_ok=True)
        with open(resolved_path, 'w', encoding='utf-8') as f:
            f.write(self.generate(title, category))

