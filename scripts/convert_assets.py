import os

from PIL import Image


def convert_png_to_jpg(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".png"):
                png_path = os.path.join(root, file)
                jpg_path = os.path.splitext(png_path)[0] + ".jpg"
                
                print(f"Converting {png_path} to {jpg_path}...")
                try:
                    with Image.open(png_path) as img:
                        # Convert to RGB if needed (JPEG doesn't support alpha)
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        img.save(jpg_path, "JPEG", quality=85, optimize=True)
                    
                    # Verify JPG exists before deleting PNG
                    if os.path.exists(jpg_path):
                        os.remove(png_path)
                except Exception as e:
                    print(f"Failed to convert {file}: {e}")

if __name__ == "__main__":
    assets_dir = os.path.join("backend", "static", "assets", "catalog")
    if os.path.exists(assets_dir):
        convert_png_to_jpg(assets_dir)
        print("Conversion complete.")
    else:
        print(f"Directory not found: {assets_dir}")
