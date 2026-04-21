import random
import colorsys
import math
from typing import List, Tuple

class SVGPlaceholderGenerator:
    """
    Ein Generator für prozedurale, zufällige SVG-Platzhalterbilder.
    Folgt Clean Code Prinzipien: Single Responsibility, Type Hinting und Modularität.
    """

    def __init__(self, width: int = 800, height: int = 600, num_shapes: int = 15):
        self.width = width
        self.height = height
        self.num_shapes = num_shapes
        self.viewbox = f"0 0 {self.width} {self.height}"

    def _random_hex_color(self, saturation_range: Tuple[float, float] = (0.2, 0.5), value_range: Tuple[float, float] = (0.1, 0.4)) -> str:
        """
        Generiert eine zufällige, düstere Hex-Farbe basierend auf dem HSV-Farbraum.
        Optimiert für Dark Fantasy (niedrige Helligkeit, moderate Sättigung).
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
        
        # Berechnung der Vektoren für den Gradientenwinkel
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
        """
        Generiert zufällige geometrische Formen (Kreise und Pfade) als Strings.
        Time Complexity: O(N) wobei N = self.num_shapes
        Space Complexity: O(N) für den resultierenden String
        """
        shapes: List[str] = []
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
                # Generiere ein zufälliges Dreieck / Polygon
                points = []
                for _ in range(3):
                    px = random.randint(-self.width // 4, self.width + self.width // 4)
                    py = random.randint(-self.height // 4, self.height + self.height // 4)
                    points.append(f"{px},{py}")
                points_str = " ".join(points)
                shapes.append(f'<polygon points="{points_str}" fill="{color}" opacity="{opacity:.2f}"/>')

        return "\n".join(shapes)

    def generate(self, title: str = "") -> str:
        """Setzt das finale SVG-Dokument zusammen."""
        svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="{self.viewbox}" width="{self.width}" height="{self.height}">
            {self._generate_gradient_defs()}
            <!-- Background -->
            <rect width="100%" height="100%" fill="url(#bgGradient)"/>
            <!-- Random Shapes -->
            {self._generate_shapes()}
        </svg>"""
        return svg_content

    def save(self, filepath: str, title: str = "") -> None:
        """Speichert das SVG in eine Datei."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.generate(title))
