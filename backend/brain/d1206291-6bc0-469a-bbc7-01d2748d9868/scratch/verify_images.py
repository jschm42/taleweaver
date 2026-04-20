import asyncio
import os
import sys
import base64
from PIL import Image
import io

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.engine.media_engine import MediaEngine
from backend.core.config import settings

async def test_image_saving():
    print("Testing image saving...")
    
    # Create a dummy red 100x100 PNG image in base64
    img = Image.new('RGB', (100, 100), color = 'red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    b64_data = base64.b64encode(img_byte_arr.getvalue()).decode()
    
    target_dir = os.path.join(settings.DATA_DIR, "test_images")
    os.makedirs(target_dir, exist_ok=True)
    
    # Test PNG saving
    print("Saving PNG...")
    png_path = await MediaEngine._save_b64_image(b64_data, target_dir, "test_save", "png")
    print(f"PNG saved to: {png_path}")
    if png_path and png_path.endswith(".png"):
        print("[OK] PNG extension correct")
    else:
        print("[FAIL] PNG extension incorrect")
        
    # Test JPEG saving quality 85
    print("Saving JPEG 85...")
    jpg_path_85 = await MediaEngine._save_b64_image(b64_data, target_dir, "test_save_85", "jpeg", 85)
    print(f"JPEG 85 saved to: {jpg_path_85}")
    
    # Test JPEG saving quality 10
    print("Saving JPEG 10...")
    jpg_path_10 = await MediaEngine._save_b64_image(b64_data, target_dir, "test_save_10", "jpeg", 10)
    print(f"JPEG 10 saved to: {jpg_path_10}")
    
    # Check file sizes
    size_85 = os.path.getsize(os.path.join(settings.DATA_DIR, "test_images/test_save_85.jpg"))
    size_10 = os.path.getsize(os.path.join(settings.DATA_DIR, "test_images/test_save_10.jpg"))
    print(f"Size 85: {size_85} bytes")
    print(f"Size 10: {size_10} bytes")
    
    if size_10 < size_85:
        print("[OK] JPEG quality setting works (size reduced)")
    else:
        print("[FAIL] JPEG quality setting failed or image too simple")

if __name__ == "__main__":
    asyncio.run(test_image_saving())
