import random
import colorsys
import math
import io
import logging
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

# Type aliases for better readability
ColorRGB = Tuple[int, int, int]
Dimensions = Tuple[int, int]

class PlaceholderConfig(BaseModel):
    """
    Configuration for the placeholder generation.
    Defines visual parameters like color palettes, blob counts, and icon styles.
    """
    palette: List[str] = Field(default=["#4ECDC4", "#45B7D1", "#FFA07A", "#98D8C8"])
    blob_count: int = Field(default=12)
    icon_count: int = Field(default=7)
    icon_size_min: int = Field(default=150)
    icon_size_max: int = Field(default=600)
    icon_stroke_min: int = Field(default=12)
    icon_stroke_max: int = Field(default=7)
    icon_opacity_min: float = Field(default=0.3)
    icon_opacity_max: float = Field(default=0.9)
    blob_opacity: float = Field(default=0.2)
    icon_fill_enabled: bool = Field(default=False)
    include_oil_strokes: bool = Field(default=True)
    gradient_intensity: float = Field(default=0.4)
    background_brightness: float = Field(default=0.6)
    
    model_config = {"extra": "ignore"}

class ColorTheme(Enum):
    """
    Defines HSV (Hue, Saturation, Value) ranges for various adventure tones.
    Format: ((h_min, h_max), (s_min, s_max), (v_min, v_max))
    """
    COLORFUL = ((0.0, 1.0), (0.6, 1.0), (0.8, 1.0))
    HORROR = ((0.85, 1.0), (0.5, 0.9), (0.05, 0.2))      # Blood reds and deep blacks
    SCI_FI = ((0.45, 0.85), (0.7, 1.0), (0.5, 0.9))     # Neon Cyan and Magenta
    SITCOM = ((0.05, 0.2), (0.4, 0.7), (0.8, 1.0))      # Cheerful yellows and oranges
    RPG = ((0.08, 0.4), (0.4, 0.8), (0.3, 0.6))         # Classic fantasy gold, green, brown
    HEROIC = ((0.55, 0.7), (0.6, 0.9), (0.6, 0.9))      # Bold blues and vibrant accents
    MELANCHOLIC = ((0.5, 0.75), (0.1, 0.3), (0.3, 0.6)) # Desaturated, cool grey-blues
    GRIMDARK = ((0.0, 1.0), (0.1, 0.4), (0.05, 0.25))   # Muted, harsh, very dark tones
    MYSTERY = ((0.65, 0.85), (0.5, 0.8), (0.15, 0.4))
    ITEM_DARK = ((0.0, 1.0), (0.1, 0.3), (0.1, 0.3))
    NPC_DARK = ((0.0, 1.0), (0.1, 0.2), (0.1, 0.2))

class ImageGenerationStrategy(ABC):
    """
    Abstract base class for different image generation strategies.
    Promotes the Open-Closed Principle.
    """
    @abstractmethod
    def generate(self, width: int, height: int) -> Image.Image:
        """
        Generates an image with the given dimensions.

        Args:
            width: The width of the image.
            height: The height of the image.

        Returns:
            A PIL Image object.
        """
        pass

class AbstractGeometricGradientStrategy(ImageGenerationStrategy):
    """
    Strategy: Generates a modern, soft background combined with 
    flowing, transparent geometric shapes.
    """
    def __init__(self, theme: Optional[ColorTheme] = None):
        self.theme = theme

    def generate(self, width: int, height: int) -> Image.Image:
        # Base image with random, soft start color
        if self.theme:
            h_range, s_range, v_range = self.theme.value
            base_hue = random.uniform(*h_range)
            bg_color = self._hsv_to_rgb(base_hue, random.uniform(*s_range), random.uniform(*v_range))
        else:
            base_hue = random.random()
            bg_color = self._hsv_to_rgb(base_hue, random.uniform(0.3, 0.6), random.uniform(0.7, 0.9))
            
        img = Image.new("RGBA", (width, height), bg_color + (255,))
        draw = ImageDraw.Draw(img, "RGBA")

        # Generate random, soft circles/blobs for accentuation
        num_shapes = random.randint(3, 7)
        for _ in range(num_shapes):
            self._draw_random_blob(draw, width, height, base_hue)

        return img.convert("RGB")

    def _draw_random_blob(self, draw: ImageDraw.ImageDraw, width: int, height: int, base_hue: float) -> None:
        """Draws a random, semi-transparent ellipse."""
        # Analogous or complementary to the base color
        hue_shift = random.choice([-0.1, 0.1, 0.5]) 
        shape_hue = (base_hue + hue_shift) % 1.0
        
        if self.theme:
            _, s_range, v_range = self.theme.value
            fill_color = self._hsv_to_rgb(shape_hue, random.uniform(*s_range), random.uniform(*v_range))
        else:
            fill_color = self._hsv_to_rgb(shape_hue, random.uniform(0.4, 0.8), random.uniform(0.6, 0.9))
            
        alpha = random.randint(50, 150) # Semi-transparent
        
        # Random position and size
        radius_x = random.randint(int(width * 0.2), int(width * 0.8))
        radius_y = random.randint(int(height * 0.2), int(height * 0.8))
        center_x = random.randint(-radius_x // 2, width + radius_x // 2)
        center_y = random.randint(-radius_y // 2, height + radius_y // 2)
        
        bbox = [
            center_x - radius_x, center_y - radius_y,
            center_x + radius_x, center_y + radius_y
        ]
        
        draw.ellipse(bbox, fill=fill_color + (alpha,))

    @staticmethod
    def _hsv_to_rgb(h: float, s: float, v: float) -> ColorRGB:
        """Converts HSV (0.0 - 1.0) to RGB (0 - 255)."""
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return int(r * 255), int(g * 255), int(b * 255)

class OrganicGradientStrategy(ImageGenerationStrategy):
    """
    Strategy: Creates organic structures and soft gradients 
    ("Mesh Gradients" or "Aurora" effect) using strong Gaussian blur 
    over randomly distributed vector blobs.
    """
    def __init__(self, theme: ColorTheme = ColorTheme.COLORFUL):
        self.theme = theme

    def generate(self, width: int, height: int) -> Image.Image:
        h_range, s_range, v_range = self.theme.value
        
        # 1. Base hue strictly from theme boundaries
        base_hue = random.uniform(*h_range)
        r, g, b = colorsys.hsv_to_rgb(base_hue, random.uniform(*s_range), random.uniform(*v_range))
        bg_color = (int(r * 255), int(g * 255), int(b * 255))
        
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # 2. Draw extremely large, organically placed color blobs
        num_blobs = random.randint(4, 8)
        for _ in range(num_blobs):
            blob_hue = random.uniform(*h_range)
            r_b, g_b, b_b = colorsys.hsv_to_rgb(blob_hue, random.uniform(*s_range), random.uniform(*v_range))
            blob_color = (int(r_b * 255), int(g_b * 255), int(b_b * 255))
            
            # Large radii combined with blur create soft waves
            radius = random.randint(int(min(width, height) * 0.4), int(min(width, height) * 1.0))
            x = random.randint(-radius // 2, width + radius // 2)
            y = random.randint(-radius // 2, height + radius // 2)
            
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=blob_color)

        # 3. Apply Gaussian blur (reduced for subtle form transitions)
        blur_radius = max(width, height) // 10
        img = img.filter(ImageFilter.GaussianBlur(blur_radius))
        
        # 4. Optional: Add a subtle grain effect for a premium feel
        img = self._add_grain(img)
        
        # 5. Add organic topographic patterns
        if random.random() > 0.5:
            img = self._add_topographic_lines(img)
            
        return img

    def _add_topographic_lines(self, img: Image.Image) -> Image.Image:
        """Adds flowing topographic lines that complement the organic gradients."""
        width, height = img.size
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Draw a few large, concentric, semi-transparent arcs
        for _ in range(5):
            cx, cy = random.randint(0, width), random.randint(0, height)
            base_r = random.randint(100, 500)
            color = (255, 255, 255, random.randint(10, 30))
            for i in range(3):
                r = base_r + i * 20
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=1)
                
        return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    def _add_grain(self, img: Image.Image) -> Image.Image:
        """Adds a subtle noise/grain texture."""
        width, height = img.size
        noise = Image.effect_noise((width, height), 20)
        noise = noise.convert("RGB")
        return Image.blend(img, noise, 0.05)

class BlobIconStrategy(ImageGenerationStrategy):
    """
    Backend counterpart to PaperBlobIconGenerator.
    Generates procedural blob + icon images server-side with PIL.
    """

    DEFAULT_ICONS: List[str] = ["star", "heart", "sun", "moon", "cloud", "leaf"]

    def __init__(self, 
                 allowed_icons: Optional[List[str]] = None, 
                 theme: Optional[ColorTheme] = None,
                 config: Optional[PlaceholderConfig] = None):
        self.allowed_icons = allowed_icons or self.DEFAULT_ICONS
        self.theme = theme
        self.config = config or PlaceholderConfig()

    def generate(self, width: int, height: int) -> Image.Image:
        """
        Generates a blob + icon image.
        """
        palette = list(self.config.palette)
        
        # If a theme is provided, we use its colors for the background and blobs
        if self.theme:
            h_range, s_range, v_range = self.theme.value
            base_hue = random.uniform(*h_range)
            r, g, b = colorsys.hsv_to_rgb(base_hue, random.uniform(*s_range), random.uniform(*v_range))
            bg_color = (int(r * 255), int(g * 255), int(b * 255))
            
            # Override palette with theme-consistent colors
            palette = []
            for _ in range(4):
                ph = random.uniform(*h_range)
                pr, pg, pb = colorsys.hsv_to_rgb(ph, random.uniform(*s_range), random.uniform(*v_range))
                palette.append(f"#{int(pr * 255):02x}{int(pg * 255):02x}{int(pb * 255):02x}")
        else:
            bg_color = self._hex_to_rgb(self._pick(palette))
            bg_color = self._adjust_brightness(bg_color, self.config.background_brightness)
        
        img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
        ImageDraw.Draw(img, "RGBA").rectangle([0, 0, width, height], fill=bg_color + (255,))

        self._draw_blobs(img, palette, self.config.blob_count, self.config.blob_opacity, self.config.gradient_intensity)

        if self.config.include_oil_strokes:
            self._draw_oil_strokes(img, palette)

        # Add pattern overlay (Dots or Grids)
        if random.random() > 0.6:
            self._add_pattern_overlay(img, palette)

        self._draw_icons(img, palette)
        return img.convert("RGB")

    def _add_pattern_overlay(self, image: Image.Image, palette: List[str]) -> None:
        """Adds a halftone-like dot grid or line grid overlay."""
        width, height = image.size
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        
        pattern_type = random.choice(["dots", "grid"])
        color = self._hex_to_rgb(self._pick(palette))
        alpha = random.randint(15, 40)
        
        spacing = random.randint(20, 50)
        
        if pattern_type == "dots":
            dot_r = random.randint(1, 3)
            for x in range(0, width, spacing):
                for y in range(0, height, spacing):
                    draw.ellipse([x - dot_r, y - dot_r, x + dot_r, y + dot_r], fill=color + (alpha,))
        else:
            for x in range(0, width, spacing):
                draw.line([(x, 0), (x, height)], fill=color + (alpha // 2,), width=1)
            for y in range(0, height, spacing):
                draw.line([(0, y), (width, y)], fill=color + (alpha // 2,), width=1)
                
        image.alpha_composite(layer)

    def _draw_blobs(self, image: Image.Image, palette: List[str], count: int, opacity: float, intensity: float) -> None:
        width, height = image.size
        blob_alpha = int(max(0.0, min(1.0, opacity)) * 255)

        for _ in range(max(0, count)):
            center_x = random.uniform(0, width)
            center_y = random.uniform(0, height)
            radius = random.uniform(width * 0.15, width * 0.4)
            points = []
            segment_count = 120 # Much higher for smoothness

            # Organic modulation using multiple sine waves
            freq1, amp1 = random.uniform(2, 5), random.uniform(0.1, 0.2)
            freq2, amp2 = random.uniform(6, 10), random.uniform(0.05, 0.1)

            for j in range(segment_count):
                angle = (j / segment_count) * math.tau
                # Radius modulation for "paper.js" organic feel
                mod = 1.0 + amp1 * math.sin(freq1 * angle) + amp2 * math.sin(freq2 * angle)
                r = radius * mod
                points.append((center_x + math.cos(angle) * r, center_y + math.sin(angle) * r))

            base_rgb = self._hex_to_rgb(self._pick(palette))
            blob_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            blob_draw = ImageDraw.Draw(blob_layer, "RGBA")
            
            # Draw the main blob body
            blob_draw.polygon(points, fill=base_rgb + (blob_alpha,))

            # Add a subtle "highlight" or "depth" using a blurred version
            grad_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            grad_draw = ImageDraw.Draw(grad_layer, "RGBA")

            amp = max(0.0, min(1.0, intensity))
            high = self._adjust_brightness(base_rgb, 1.2)
            
            off_angle = random.uniform(0, math.tau)
            offset = radius * 0.2
            hx, hy = center_x - math.cos(off_angle) * offset, center_y - math.sin(off_angle) * offset
            
            # Sub-ellipse for internal gradient
            r_grad = radius * 0.6
            grad_draw.ellipse([hx - r_grad, hy - r_grad, hx + r_grad, hy + r_grad], fill=high + (int(100 * amp),))
            grad_layer = grad_layer.filter(ImageFilter.GaussianBlur(radius=int(radius * 0.2)))

            blob_layer.alpha_composite(grad_layer)
            image.alpha_composite(blob_layer)

    def _draw_oil_strokes(self, image: Image.Image, palette: List[str]) -> None:
        width, height = image.size
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer, "RGBA")

        stroke_count = 160
        for _ in range(stroke_count):
            x = random.uniform(0, width)
            y = random.uniform(0, height)
            length = random.uniform(30, 160)
            angle = random.uniform(0, math.tau)
            x2 = x + math.cos(angle) * length
            y2 = y + math.sin(angle) * length
            color = self._hex_to_rgb(self._pick(palette))
            alpha = random.randint(35, 120)
            stroke_w = random.randint(2, 16)
            draw.line([(x, y), (x2, y2)], fill=color + (alpha,), width=stroke_w)

        image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1)))

    def _draw_icons(self, image: Image.Image, palette: List[str]) -> None:
        width, height = image.size
        count = max(0, self.config.icon_count)

        size_a, size_b = sorted([float(self.config.icon_size_min), float(self.config.icon_size_max)])
        stroke_a, stroke_b = sorted([float(self.config.icon_stroke_min), float(self.config.icon_stroke_max)])
        opa_a, opa_b = sorted([float(self.config.icon_opacity_min), float(self.config.icon_opacity_max)])

        fill_enabled = self.config.icon_fill_enabled

        for _ in range(count):
            icon_name = str(self._pick(self.allowed_icons)).lower()
            size = random.uniform(size_a, size_b)
            stroke_w = max(1, int(round(random.uniform(stroke_a, stroke_b))))
            opacity = max(0.0, min(1.0, random.uniform(opa_a, opa_b)))

            icon_color = self._hex_to_rgb(self._pick(palette))
            if random.random() > 0.7:
                hue_jitter = random.uniform(-0.12, 0.12)
                icon_color = self._shift_hue(icon_color, hue_jitter)

            icon_img = self._draw_icon_shape(icon_name, int(size), icon_color, stroke_w, opacity, fill_enabled)
            rotated = icon_img.rotate(random.uniform(0, 360), resample=Image.Resampling.BICUBIC, expand=True)

            px = int(random.uniform(0, width) - rotated.width / 2)
            py = int(random.uniform(0, height) - rotated.height / 2)
            image.alpha_composite(rotated, dest=(px, py))

    def _draw_icon_shape(self,
                         name: str,
                         size: int,
                         color: ColorRGB,
                         stroke_width: int,
                         opacity: float,
                         fill_enabled: bool) -> Image.Image:
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas, "RGBA")
        a = int(max(0.0, min(1.0, opacity)) * 255)
        stroke = color + (a,)
        fill = color + (int(a * 0.75),) if fill_enabled else None

        cx, cy = size / 2, size / 2
        r = size * 0.36

        if "star" in name:
            pts = []
            for i in range(10):
                rr = r if i % 2 == 0 else r * 0.45
                ang = -math.pi / 2 + i * (math.pi / 5)
                pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
            draw.polygon(pts, outline=stroke, fill=fill, width=stroke_width)
        elif "heart" in name:
            top = size * 0.35
            draw.pieslice([cx - r, top - r * 0.5, cx, top + r * 0.5], 180, 360, fill=fill, outline=stroke, width=stroke_width)
            draw.pieslice([cx, top - r * 0.5, cx + r, top + r * 0.5], 180, 360, fill=fill, outline=stroke, width=stroke_width)
            tri = [(cx - r, top), (cx + r, top), (cx, cy + r)]
            draw.polygon(tri, fill=fill, outline=stroke)
        elif "sun" in name:
            draw.ellipse([cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55], outline=stroke, fill=fill, width=stroke_width)
            for i in range(12):
                ang = i * (math.tau / 12)
                x1, y1 = cx + math.cos(ang) * (r * 0.75), cy + math.sin(ang) * (r * 0.75)
                x2, y2 = cx + math.cos(ang) * (r * 1.05), cy + math.sin(ang) * (r * 1.05)
                draw.line([(x1, y1), (x2, y2)], fill=stroke, width=stroke_width, joint="curve")
        elif "moon" in name:
            draw.ellipse([cx - r * 0.7, cy - r * 0.7, cx + r * 0.7, cy + r * 0.7], outline=stroke, fill=fill, width=stroke_width)
            cut = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            cdraw = ImageDraw.Draw(cut, "RGBA")
            cdraw.ellipse([cx - r * 0.35, cy - r * 0.75, cx + r * 1.05, cy + r * 0.75], fill=(0, 0, 0, 255))
            alpha = canvas.split()[3]
            alpha.paste(0, mask=cut.split()[3])
            canvas.putalpha(alpha)
        elif "sword" in name:
            # Blade
            draw.line([(cx, cy + r), (cx, cy - r * 0.7)], fill=stroke, width=stroke_width * 2)
            # Guard
            draw.line([(cx - r * 0.4, cy + r * 0.3), (cx + r * 0.4, cy + r * 0.3)], fill=stroke, width=stroke_width)
            # Handle
            draw.line([(cx, cy + r * 0.3), (cx, cy + r * 0.6)], fill=stroke, width=stroke_width)
        elif "shield" in name:
            pts = [(cx - r * 0.7, cy - r * 0.7), (cx + r * 0.7, cy - r * 0.7), 
                   (cx + r * 0.7, cy), (cx, cy + r), (cx - r * 0.7, cy)]
            draw.polygon(pts, outline=stroke, fill=fill, width=stroke_width)
        elif "potion" in name:
            draw.ellipse([cx - r * 0.6, cy - r * 0.2, cx + r * 0.6, cy + r], outline=stroke, fill=fill, width=stroke_width)
            draw.rectangle([cx - r * 0.2, cy - r * 0.7, cx + r * 0.2, cy - r * 0.2], outline=stroke, fill=fill, width=stroke_width)
        elif "key" in name:
            draw.ellipse([cx - r * 0.4, cy - r * 0.8, cx + r * 0.4, cy - r * 0.2], outline=stroke, fill=fill, width=stroke_width)
            draw.line([(cx, cy - r * 0.2), (cx, cy + r * 0.8)], fill=stroke, width=stroke_width)
            draw.line([(cx, cy + r * 0.4), (cx + r * 0.3, cy + r * 0.4)], fill=stroke, width=stroke_width)
            draw.line([(cx, cy + r * 0.7), (cx + r * 0.3, cy + r * 0.7)], fill=stroke, width=stroke_width)
        elif "book" in name:
            draw.rectangle([cx - r * 0.6, cy - r * 0.8, cx + r * 0.6, cy + r * 0.8], outline=stroke, fill=fill, width=stroke_width)
            draw.line([(cx, cy - r * 0.8), (cx, cy + r * 0.8)], fill=stroke, width=max(1, stroke_width // 2))
        elif "helm" in name:
            draw.pieslice([cx - r, cy - r, cx + r, cy + r], 180, 360, outline=stroke, fill=fill, width=stroke_width)
            draw.rectangle([cx - r, cy, cx + r, cy + r * 0.2], outline=stroke, fill=fill, width=stroke_width)
            draw.line([(cx, cy - r), (cx, cy - r * 1.2)], fill=stroke, width=stroke_width)
        else:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=stroke, fill=fill, width=stroke_width)

        return canvas

    @staticmethod
    def _hex_to_rgb(color: str) -> ColorRGB:
        c = color.strip().lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        if len(c) != 6:
            return 255, 255, 255
        try:
            return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        except ValueError:
            return 255, 255, 255

    @staticmethod
    def _adjust_brightness(rgb: ColorRGB, factor: float) -> ColorRGB:
        return (
            max(0, min(255, int(rgb[0] * factor))),
            max(0, min(255, int(rgb[1] * factor))),
            max(0, min(255, int(rgb[2] * factor))),
        )

    @staticmethod
    def _shift_hue(rgb: ColorRGB, hue_shift: float) -> ColorRGB:
        r, g, b = [x / 255.0 for x in rgb]
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        h = (h + hue_shift) % 1.0
        r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
        return int(r2 * 255), int(g2 * 255), int(b2 * 255)

    @staticmethod
    def _pick(values: List[Any]) -> Any:
        if not values:
            return "#ffffff"
        return values[random.randrange(0, len(values))]

class PlaceholderImageGenerator:
    """
    Main class for managing and creating placeholder images.
    Uses Dependency Injection for the generation strategy.
    """
    def __init__(self, strategy: Optional[ImageGenerationStrategy] = None):
        # Default fallback set to the organic strategy
        self.strategy = strategy or OrganicGradientStrategy()

    def set_strategy(self, strategy: ImageGenerationStrategy) -> None:
        """Changes the generation strategy at runtime."""
        self.strategy = strategy

    def create_and_save(self, 
                        filepath: str, 
                        size: Dimensions = (800, 600), 
                        quality: int = 85) -> Path:
        """
        Generates the image and saves it to the specified path.
        """
        if size[0] <= 0 or size[1] <= 0:
            raise ValueError("Dimensions must be positive.")

        img = self.strategy.generate(*size)
        
        out_path = Path(filepath)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Optimization parameters for JPEG
        save_kwargs = {"quality": quality, "optimize": True} if out_path.suffix.lower() in ['.jpg', '.jpeg'] else {}
        
        img.save(out_path, **save_kwargs)
        return out_path

# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    # Generates a 1920x1080 JPEG in Mystery style
    generator_mystery = PlaceholderImageGenerator(OrganicGradientStrategy(theme=ColorTheme.MYSTERY))
    saved_path_jpg = generator_mystery.create_and_save("placeholders/hero_mystery.jpg", size=(1920, 1080))
    print(f"Saved: {saved_path_jpg}")
    
    # Generates an 800x800 PNG in Green Woods style
    generator_woods = PlaceholderImageGenerator(OrganicGradientStrategy(theme=ColorTheme.GREEN_WOODS))
    saved_path_png = generator_woods.create_and_save("placeholders/avatar_woods.png", size=(800, 800))
    print(f"Saved: {saved_path_png}")
    
    # Generates a Sci-Fi banner using BlobIconStrategy
    generator_scifi = PlaceholderImageGenerator(BlobIconStrategy(theme=ColorTheme.SCI_FI))
    saved_path_scifi = generator_scifi.create_and_save("placeholders/banner_scifi.jpg", size=(1200, 400))
    print(f"Saved: {saved_path_scifi}")
