import os
import math
import random
import json
import logging
from typing import List, Tuple, Dict, Optional
import numpy as np
import torch
import torchvision
import torchvision.transforms as T
from torchvision.models import ResNet50_Weights
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from rembg import remove
import argparse
import colorsys

# Constants
FINAL_WIDTH, FINAL_HEIGHT = 900, 1200
MIN_PRODUCT_AREA_RATIO = 0.2
MAX_PRODUCT_AREA_RATIO = 0.2
NUM_VARIANTS = 5
CONFIG_FILE = "product_config.json"
BG_FOLDER = "bg"
BG_TITLE_FOLDER = "bg_title"
BOTTOM_MARGIN = 3  # Tiny bottom margin

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductClassifier:
    """Handles image classification using ResNet-50."""
    def __init__(self, labels_file: str = "imagenet_classes.txt"):
        self.model = torchvision.models.resnet50(weights=ResNet50_Weights.IMAGENET1K_V1)
        self.model.eval()
        self.transform = T.Compose([
            T.Resize(256),
            T.CenterCrop(224),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        try:
            with open(labels_file, "r") as f:
                self.labels = [s.strip() for s in f.readlines()]
        except FileNotFoundError:
            logger.error(f"{labels_file} not found. Please download it.")
            raise SystemExit

    def classify(self, img_path: str) -> List[Tuple[str, float]]:
        try:
            img = Image.open(img_path).convert("RGB")
            x = self.transform(img).unsqueeze(0)
            with torch.no_grad():
                logits = self.model(x)
                probs = torch.nn.functional.softmax(logits, dim=1)[0]
            top5_vals, top5_idxs = probs.topk(5)
            return [(self.labels[idx.item()], val.item()) for val, idx in zip(top5_vals, top5_idxs)]
        except Exception as e:
            logger.error(f"Failed to classify {img_path}: {e}")
            return []

    def map_to_product_type(self, top5: List[Tuple[str, float]], file_name: Optional[str] = None) -> str:
        labels = [lbl.lower() for lbl, _ in top5]
        dog_bowl_syns = ["bowl", "dish", "mixing bowl", "crock pot", "soup bowl", "plate"]
        mug_syns = ["mug", "cup", "coffee mug"]

        if any(any(syn in l for syn in dog_bowl_syns) for l in labels):
            return "DOG_BOWL"
        if any(any(syn in l for syn in mug_syns) for l in labels):
            return "MUG"
        if file_name and "bowl" in file_name.lower():
            return "DOG_BOWL"
        if file_name and any(s in file_name.lower() for s in ["mug", "cup"]):
            return "MUG"
        return "UNKNOWN"

def trim_transparent(img: Image.Image) -> Image.Image:
    """Trims transparent areas from an image, returning the cropped result."""
    # Convert to RGBA if not already
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    
    # Get the alpha channel
    alpha = img.split()[3]
    # Find the bounding box of non-transparent pixels
    bbox = alpha.getbbox()
    if bbox:
        # Crop to the non-transparent area
        return img.crop(bbox)
    else:
        # If no non-transparent pixels, return the original (shouldn't happen post-rembg)
        logger.warning("No non-transparent pixels found in image after trimming.")
        return img

class CardRenderer:
    """Renders product cards with pre-loaded backgrounds and title BGs."""
    def __init__(self, bg_folder: str = BG_FOLDER, bg_title_folder: str = BG_TITLE_FOLDER):
        try:
            self.fonts = {
                "title": ImageFont.truetype("arialbd.ttf", 100),
                "subtitle": ImageFont.truetype("Arial.ttf", 50),
            }
        except:
            logger.warning("Arial fonts not found, using defaults.")
            self.fonts = {
                "title": ImageFont.load_default(size=100),
                "subtitle": ImageFont.load_default(size=50),
            }
        
        # Load card backgrounds
        self.bg_files = [f for f in os.listdir(bg_folder) if os.path.isfile(os.path.join(bg_folder, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not self.bg_files:
            logger.error(f"No backgrounds found in {bg_folder}")
            raise SystemExit
        self.bg_folder = bg_folder

        # Load title backgrounds
        self.bg_title_files = [f for f in os.listdir(bg_title_folder) if os.path.isfile(os.path.join(bg_title_folder, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not self.bg_title_files:
            logger.error(f"No title backgrounds found in {bg_title_folder}")
            raise SystemExit
        self.bg_title_folder = bg_title_folder

    @staticmethod
    def brightness(color: Tuple[int, int, int]) -> int:
        return sum(color) // 3

    def load_random_background(self) -> Image.Image:
        """Loads a random card background."""
        bg_file = random.choice(self.bg_files)
        bg_path = os.path.join(self.bg_folder, bg_file)
        bg = Image.open(bg_path).convert("RGBA")
        return bg.resize((FINAL_WIDTH, FINAL_HEIGHT), Image.LANCZOS)

    def load_random_title_bg(self, width: int, height: int) -> Tuple[Image.Image, Tuple[int, int, int]]:
        """Loads a random title background and calculates its average color."""
        bg_file = random.choice(self.bg_title_files)
        bg_path = os.path.join(self.bg_title_folder, bg_file)
        bg = Image.open(bg_path).convert("RGBA")
        bg = bg.resize((width, height), Image.LANCZOS)
        arr = np.array(bg)
        avg_color = tuple(arr[:, :, :3][arr[:, :, 3] > 0].mean(axis=0).astype(int)) if np.any(arr[:, :, 3] > 0) else (128, 128, 128)
        return bg, avg_color

    def draw_text_with_bg(self, draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont, y: int, 
                          max_width: Optional[int]) -> Tuple[int, int]:
        """Draws centered text on a pre-loaded title background."""
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        while max_width and tw > max_width - 100 and font.size > 20:
            font = font.font_variant(size=font.size - 5)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        bg_width = min(tw + 80, FINAL_WIDTH - 40)
        bg_height = th + 40
        bg_x0 = (FINAL_WIDTH - bg_width) // 2
        bg_y0 = y - 20
        tx = (FINAL_WIDTH - tw) // 2
        ty = y

        title_bg, bg_avg_color = self.load_random_title_bg(bg_width, bg_height)
        text_color = (255, 255, 255) if self.brightness(bg_avg_color) < 128 else (0, 0, 0)

        shadow = Image.new("RGBA", (bg_width + 20, bg_height + 20), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.rectangle((10, 10, bg_width + 10, bg_height + 10), fill=(0, 0, 0, 120))
        shadow = shadow.filter(ImageFilter.GaussianBlur(8))
        draw.bitmap((bg_x0 - 10, bg_y0 - 10), shadow)

        draw.bitmap((bg_x0, bg_y0), title_bg)
        draw.text((tx + 5, ty + 5), text, fill=(0, 0, 0, 160), font=font)
        draw.text((tx, ty), text, fill=text_color, font=font)

        return tw, th

    def render(self, no_bg: Image.Image, avg_color: Tuple[int, int, int], title: str, subtitle: str, variant: int) -> Image.Image:
        """Renders a product card with product at the very bottom."""
        bg = self.load_random_background()

        # Trim transparent areas
        no_bg = trim_transparent(no_bg)

        # Scale product
        area = FINAL_WIDTH * FINAL_HEIGHT
        target_area = random.uniform(MIN_PRODUCT_AREA_RATIO, MAX_PRODUCT_AREA_RATIO) * area
        w, h = no_bg.size
        scale = math.sqrt(target_area / (w * h))
        no_bg = no_bg.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Place product at bottom center with 3px margin
        px = (FINAL_WIDTH - no_bg.width) // 2
        py = FINAL_HEIGHT - no_bg.height - BOTTOM_MARGIN  # 3px from bottom

        # Crisp shadow
        shadow = no_bg.convert("L").point(lambda p: 140 if p > 0 else 0).filter(ImageFilter.GaussianBlur(25))
        bg.paste(shadow, (px + 30, py + 30), shadow)
        bg.paste(no_bg, (px, py), no_bg)

        draw = ImageDraw.Draw(bg)
        y = 100

        # Draw title and subtitle
        tw, th = self.draw_text_with_bg(draw, title, self.fonts["title"], y, FINAL_WIDTH)
        y += th + 60
        sw, sh = self.draw_text_with_bg(draw, subtitle, self.fonts["subtitle"], y, FINAL_WIDTH)

        return bg

def load_config(config_file: str) -> Dict:
    default_config = {
        "DOG_BOWL": {"titles": ["DOG BOWL (RED)", "Perfect Dog Bowl"], "subtitles": ["Non-slip design"]},
        "MUG": {"titles": ["COFFEE MUG"], "subtitles": ["Enjoy your hot drinks"]},
        "UNKNOWN": {"titles": ["My Product"], "subtitles": ["No info"]}
    }
    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"{config_file} not found, using default config.")
        return default_config

def main():
    parser = argparse.ArgumentParser(description="Generate product cards with pre-loaded backgrounds.")
    parser.add_argument("--input", default="inputs", help="Input folder path")
    parser.add_argument("--output", default="Results", help="Output folder path")
    parser.add_argument("--variants", type=int, default=NUM_VARIANTS, help="Number of variants per image")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    classifier = ProductClassifier()
    renderer = CardRenderer(BG_FOLDER, BG_TITLE_FOLDER)
    config = load_config(CONFIG_FILE)

    files = sorted(f for f in os.listdir(args.input) if os.path.isfile(os.path.join(args.input, f)))
    if not files:
        logger.error(f"No files in {args.input}")
        return

    logger.info("Available files:")
    for i, f in enumerate(files, 1):
        logger.info(f" {i}. {f}")

    choices = input("\nEnter file numbers (e.g., '1' or '1,2,3'): ").strip()
    if not choices:
        logger.info("No selection made.")
        return

    for ch in [int(n.strip()) for n in choices.split(",") if n.strip().isdigit() and 1 <= int(n) <= len(files)]:
        fname = files[ch - 1]
        img_path = os.path.join(args.input, fname)
        logger.info(f"\nProcessing {fname}")

        top5 = classifier.classify(img_path)
        for lbl, prob in top5:
            logger.info(f"  {lbl} -> {prob:.3f}")

        product_type = classifier.map_to_product_type(top5, fname)
        logger.info(f"Product type: {product_type}")

        no_bg = remove(Image.open(img_path).convert("RGBA"))
        arr = np.array(no_bg)
        avg_color = tuple(arr[:, :, :3][arr[:, :, 3] > 0].mean(axis=0).astype(int)) if np.any(arr[:, :, 3] > 0) else (128, 128, 128)

        if product_type == "UNKNOWN":
            while True:
                ans = input("Product not recognized. Enter custom text? (y/n): ").strip().lower()
                if ans in ["y", "n"]:
                    break
                logger.info("Please enter 'y' or 'n'.")
            if ans == "y":
                title = input("Title (e.g., 'Dog Bowl'): ").strip() or "My Product"
                subtitle = input("Subtitle (e.g., 'Non-slip design'): ").strip() or "No Info"
                logger.info(f"Using custom text: Title='{title}', Subtitle='{subtitle}'")
            else:
                cfg = config["UNKNOWN"]
                title = random.choice(cfg["titles"])
                subtitle = random.choice(cfg["subtitles"])
                logger.info(f"Using default text: Title='{title}', Subtitle='{subtitle}'")
        else:
            cfg = config.get(product_type, config["UNKNOWN"])
            title = random.choice(cfg["titles"])
            subtitle = random.choice(cfg["subtitles"])
            logger.info(f"Using config text: Title='{title}', Subtitle='{subtitle}'")

        out_dir = os.path.join(args.output, os.path.splitext(fname)[0])
        os.makedirs(out_dir, exist_ok=True)
        for i in range(args.variants):
            try:
                img = renderer.render(no_bg.copy(), avg_color, title, subtitle, i)
                out_path = os.path.join(out_dir, f"variant_{i + 1}.png")
                img.save(out_path)
                logger.info(f"Saved: {out_path}")
            except Exception as e:
                logger.error(f"Error generating variant {i + 1} for {fname}: {e}")

if __name__ == "__main__":
    main()