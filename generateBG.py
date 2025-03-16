import os
import math
import random
import numpy as np
from rembg import remove
from PIL import Image, ImageDraw, ImageFont, ImageFilter

#############################
#   НАСТРОЙКИ И ПАРАМЕТРЫ  #
#############################

FINAL_WIDTH  = 900
FINAL_HEIGHT = 1200

TITLE_TEXT    = "Yoga Mat"
SUBTITLE_TEXT = "Eco-Friendly & Non-Slip"
PRICE_TEXT    = "$49.99"

#############################
INPUT_FOLDER  = "inputs" 
OUTPUT_FOLDER = "Results"
#############################



# Процент площади (от 0.4 до 0.5), который должен занимать продукт
PRODUCT_AREA_RATIO_MIN = 0.4
PRODUCT_AREA_RATIO_MAX = 0.5

#############################
#     ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
#############################

def lighten_color(color, factor=0.2):
    """Осветляем (R,G,B) на factor (0..1)."""
    r, g, b = color
    r = int(r + (255 - r)*factor)
    g = int(g + (255 - g)*factor)
    b = int(b + (255 - b)*factor)
    return (r, g, b)

def darken_color(color, factor=0.2):
    """Затемняем (R,G,B) на factor (0..1)."""
    r, g, b = color
    r = int(r*(1-factor))
    g = int(g*(1-factor))
    b = int(b*(1-factor))
    return (r, g, b)

def load_font(path_list, size):
    """
    Пытается загрузить шрифт из списка путей. 
    Если всё не сработает – load_default().
    """
    for p in path_list:
        try:
            return ImageFont.truetype(p, size)
        except:
            pass
    return ImageFont.load_default()

def load_font_bold(size):
    """Упрощённая загрузка жирного шрифта (Arial Bold)."""
    return load_font([
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",   # Mac
        "C:/Windows/Fonts/arialbd.ttf",                       # Win
        "arialbd.ttf"
    ], size)

def load_font_regular(size):
    """Упрощённая загрузка обычного шрифта (Arial)."""
    return load_font([
        "/System/Library/Fonts/Supplemental/Arial.ttf",        # Mac
        "C:/Windows/Fonts/arial.ttf",                          # Win
        "arial.ttf"
    ], size)

#############################
#     ГЕНЕРАЦИЯ ФОНОВ
#############################

def create_pattern_background(width, height, base_color, pattern_color):
    """
    Паттерн: диагональные линии + полупрозрачная заливка.
    """
    bg = Image.new("RGB", (width, height), base_color)
    draw = ImageDraw.Draw(bg)
    spacing = 50
    for x in range(-height, width+height//2, spacing):
        draw.line([(x, 0), (x + height, height)], fill=pattern_color, width=5)
    # Смягчаем узор
    overlay = Image.new("RGBA", (width, height), (255, 255, 255, 80))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay)
    return bg.convert("RGB")

def create_radial_gradient(width, height, inner_color, outer_color):
    """
    Радиальный градиент: от центра (inner_color) к краям (outer_color).
    """
    import math
    inner = np.array(inner_color, dtype=float)
    outer = np.array(outer_color, dtype=float)

    result = Image.new("RGB", (width, height), tuple(outer.astype(int)))
    pix = np.array(result, dtype=np.uint8)

    cx, cy = width // 2, height // 2
    max_r = math.sqrt(cx**2 + cy**2)

    for y in range(height):
        for x in range(width):
            dist = math.sqrt((x - cx)**2 + (y - cy)**2)
            t = dist / max_r
            color = (1 - t)*inner + t*outer
            pix[y, x] = color.clip(0,255)
    return Image.fromarray(pix, "RGB")

def create_linear_gradient(width, height, top_color, bottom_color):
    """
    Линейный градиент сверху (top_color) вниз (bottom_color).
    """
    top = np.array(top_color, dtype=float)
    bottom = np.array(bottom_color, dtype=float)

    result = Image.new("RGB", (width, height), tuple(top.astype(int)))
    pix = np.array(result, dtype=np.uint8)

    for y in range(height):
        t = y / (height - 1)
        c = (1 - t)*top + t*bottom
        pix[y, :] = c.clip(0,255)
    return Image.fromarray(pix, "RGB")


def create_cloud_background(width, height, base_color):
    """
    Пример "облачного" фона:
      - создаём Noise + Blur + смешивание с base_color
    """
    # 1) Создаём шумовое изображение
    noise = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)

    # 2) Превращаем шум в PIL и слегка блюрим
    noise_img = Image.fromarray(noise, "RGB").filter(ImageFilter.GaussianBlur(10))

    # 3) Заливка базовым цветом
    layer_base = Image.new("RGB", (width, height), base_color)

    # 4) Смешиваем (режим "Screen" или "Lighten")
    #   В Pillow напрямую нет режима "Screen" для blend(), сделаем вручную
    base_arr   = np.array(layer_base, dtype=np.float32)
    noise_arr  = np.array(noise_img,  dtype=np.float32)

    # Screen formula: out = 1 - (1 - A)*(1 - B) / 255-based
    #   => out[i] = 1 - (1 - A[i]/255)*(1 - B[i]/255)
    # Но можно упростить:
    #   out = base/2 + noise/2  (просто обычный Mix),
    #   out = lighten(base, noise), etc.
    # Для наглядности сделаем Lighten:
    out = np.maximum(base_arr, noise_arr)

    final_img = Image.fromarray(out.clip(0,255).astype(np.uint8), "RGB")
    # слегка размоем итог для "облачности"
    final_img = final_img.filter(ImageFilter.GaussianBlur(5))
    return final_img

def create_bokeh_background(width, height, base_color):
    """
    Создаём bokeh-style фон:
      - заливаем base_color
      - рисуем несколько полупрозрачных кругов разных размеров, позиций
      - Blur
    """
    bg = Image.new("RGB", (width, height), base_color)
    draw = ImageDraw.Draw(bg, "RGBA")

    # Рисуем ~30 случайных кругов
    for _ in range(30):
        radius = random.randint(30, 120)
        x = random.randint(-radius, width + radius)
        y = random.randint(-radius, height + radius)

        # Случайный цвет, близкий к белому, с альфой
        c = (255, 255, 255, random.randint(30, 100))
        draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill=c)

    # Слегка размываем
    bokeh = bg.filter(ImageFilter.GaussianBlur(10))

    # Добавим чуть-чуть полупрозрачного белого слоя, чтоб сбалансировать
    overlay = Image.new("RGBA", (width, height), (255,255,255,30))
    out = Image.alpha_composite(bokeh.convert("RGBA"), overlay)
    return out.convert("RGB")


#############################
#    ВСПОМОГАТЕЛЬНЫЙ РИСУНОК
#############################

def draw_text_with_box(draw, text, x, y, font, box_color=None, text_color="white",
                       pad_x=20, pad_y=10, radius=10, max_width=None):
    """
    Рисует текст, опционально создаёт за ним прямоугольник.
    Если max_width задан, автоматически уменьшает шрифт, пока текст не уместится.
    Возвращает (box_w, box_h).
    """
    while True:
        bbox = draw.textbbox((0,0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if max_width is None or text_w <= max_width or font.size <= 10:
            break
        # Уменьшаем шрифт
        font = font.font_variant(size=font.size - 2)

    box_w = text_w + pad_x*2
    box_h = text_h + pad_y*2

    # Рисуем фон (rounded box)
    if box_color:
        draw.rounded_rectangle(
            [x, y, x + box_w, y + box_h],
            fill=box_color, radius=radius
        )
    # Печатаем текст по центру блока
    text_x = x + (box_w - text_w)//2
    text_y = y + (box_h - text_h)//2
    draw.text((text_x, text_y), text, fill=text_color, font=font)

    return (box_w, box_h)


def draw_button(draw, text, x, y, font, bg_color, text_color="white", 
                pad_x=60, pad_y=20, radius=20, max_width=None):
    """
    Делает большую кнопку. Если max_width задан, уменьшаем текст по ширине.
    Возвращает (btn_w, btn_h).
    """
    return draw_text_with_box(draw, text, x, y, font, box_color=bg_color,
                              text_color=text_color, pad_x=pad_x, 
                              pad_y=pad_y, radius=radius, max_width=max_width)


#############################
#     ПОМОЩНИК МАСШТАБА
#############################

def scale_product_to_area(no_bg, min_area, max_area):
    """
    Учитывая min_area и max_area, если продукт меньше/больше – масштабируем.
    Возвращаем (product_img, scale_factor).
    """
    w, h = no_bg.size
    orig_area = w*h
    if orig_area < min_area:
        scale = math.sqrt(min_area / orig_area)
    elif orig_area > max_area:
        scale = math.sqrt(max_area / orig_area)
    else:
        scale = 1.0

    if abs(scale - 1.0) > 1e-3:
        new_w = int(w*scale)
        new_h = int(h*scale)
        no_bg = no_bg.resize((new_w, new_h), Image.LANCZOS)
        return no_bg, scale
    return no_bg, 1.0


#############################
#     5 ВАРИАНТОВ МАКЕТА
#############################

def variant_1(no_bg, avg_color):
    """
    Variant 1 (FIXED so text never goes beyond top area):
      - Паттерн-фон
      - Продукт в НИЖНЕЙ части (40-50% площади), по центру
      - Текст (Title, Subtitle, Price, Button) в верхней зоне
        без выхода за границы + авто-уменьшение шрифтов
    """
    # 1) Создаём паттерн-фон
    base_col = lighten_color(avg_color, 0.3)
    patt_col = darken_color(avg_color, 0.5)
    bg = create_pattern_background(FINAL_WIDTH, FINAL_HEIGHT, base_col, patt_col)

    # 2) Масштабируем продукт под 40-50%
    card_area = FINAL_WIDTH * FINAL_HEIGHT
    product_area_min = int(card_area * PRODUCT_AREA_RATIO_MIN)
    product_area_max = int(card_area * PRODUCT_AREA_RATIO_MAX)
    no_bg, _ = scale_product_to_area(no_bg, product_area_min, product_area_max)

    w, h = no_bg.size
    product_x = (FINAL_WIDTH - w)//2
    product_y = FINAL_HEIGHT - h - 20

    # Тень
    shadow = no_bg.convert("L").point(lambda p: p > 0 and 60).filter(ImageFilter.GaussianBlur(15))
    bg.paste(shadow, (product_x+25, product_y+25), shadow)
    bg.paste(no_bg, (product_x, product_y), no_bg)

    # 3) Рисуем текст в зоне [0 .. product_y - 10]
    draw_obj = ImageDraw.Draw(bg)
    font_title    = load_font_bold(80)
    font_subtitle = load_font_regular(50)
    font_price    = load_font_bold(60)

    # Предельная нижняя граница текста
    text_bottom_limit = product_y - 10

    cur_y = 20  # отступ сверху
    x_center = FINAL_WIDTH//2

    # Title (с цветным прямоугольником)
    box_w, box_h = draw_text_with_box(
        draw_obj, TITLE_TEXT, x_center - 300, cur_y, font_title,
        box_color=darken_color(avg_color,0.4), text_color="white",
        pad_x=40, pad_y=20, radius=30, max_width=600
    )
    cur_y += box_h + 10
    # Если уже вышли за пределы
    if cur_y >= text_bottom_limit:
        return bg  # Текст уже не влез; (реально лучше ещё уменьшать шрифт/товар, но это демо)

    # Subtitle
    sw, sh = draw_text_with_box(
        draw_obj, SUBTITLE_TEXT, x_center - 250, cur_y, font_subtitle,
        box_color=None, text_color="black", pad_x=0, pad_y=0,
        max_width=500
    )
    cur_y += sh + 10
    if cur_y >= text_bottom_limit:
        return bg



    return bg


def variant_2(no_bg, avg_color):
    """
    Variant 2:
      - Радиальный градиент
      - Продукт в нижней части (40-50%)
      - Текст сверху слева
    """
    center_col = darken_color(avg_color, 0.2)
    edge_col   = lighten_color(avg_color, 0.7)
    bg = create_radial_gradient(FINAL_WIDTH, FINAL_HEIGHT, center_col, edge_col)

    # Масштаб в 40-50%
    card_area = FINAL_WIDTH * FINAL_HEIGHT
    no_bg, _ = scale_product_to_area(
        no_bg,
        int(card_area*PRODUCT_AREA_RATIO_MIN),
        int(card_area*PRODUCT_AREA_RATIO_MAX)
    )
    w, h = no_bg.size

    product_x = (FINAL_WIDTH - w)//2
    product_y = FINAL_HEIGHT - h - 100

    shadow = no_bg.convert("L").point(lambda p: p>0 and 70).filter(ImageFilter.GaussianBlur(20))
    bg.paste(shadow, (product_x+30, product_y+30), shadow)
    bg.paste(no_bg, (product_x, product_y), no_bg)

    # Текст (сверху слева)
    draw_obj = ImageDraw.Draw(bg)
    font_title    = load_font_bold(70)
    font_subtitle = load_font_regular(40)
    font_price    = load_font_bold(50)

    left_margin = 50
    cur_y = 50

    # Title
    bw, bh = draw_text_with_box(
        draw_obj, TITLE_TEXT, left_margin, cur_y, font_title,
        box_color=darken_color(avg_color,0.5), text_color="white",
        pad_x=30, pad_y=20, max_width=FINAL_WIDTH - 2*left_margin
    )
    cur_y += bh + 20

    # Subtitle
    sw, sh = draw_text_with_box(
        draw_obj, SUBTITLE_TEXT, left_margin, cur_y, font_subtitle,
        box_color=None, text_color="black",
        pad_x=0, pad_y=0, max_width=FINAL_WIDTH - 2*left_margin
    )
    cur_y += sh + 20



    return bg


def variant_3(no_bg, avg_color):
    """
    Variant 3:
      - Линейный градиент (сверху вниз)
      - Продукт в центре
      - Текст: часть сверху, часть снизу
    """
    top_col = darken_color(avg_color, 0.3)
    bot_col = lighten_color(avg_color, 0.5)
    bg = create_linear_gradient(FINAL_WIDTH, FINAL_HEIGHT, top_col, bot_col)

    card_area = FINAL_WIDTH*FINAL_HEIGHT
    no_bg, _ = scale_product_to_area(
        no_bg,
        int(card_area*PRODUCT_AREA_RATIO_MIN),
        int(card_area*PRODUCT_AREA_RATIO_MAX)
    )
    w, h = no_bg.size

    # Размещаем по центру (вертикально), точнее чуть смещаем
    product_x = (FINAL_WIDTH - w)//2
    product_y = (FINAL_HEIGHT - h)//2

    shadow = no_bg.convert("L").point(lambda p:p>0 and 80).filter(ImageFilter.GaussianBlur(25))
    bg.paste(shadow, (product_x+35, product_y+35), shadow)
    bg.paste(no_bg, (product_x, product_y), no_bg)

    # Текст: сверху (Title, Subtitle), снизу (Price, Button)
    draw_obj = ImageDraw.Draw(bg)
    font_title    = load_font_bold(70)
    font_subtitle = load_font_regular(40)
    font_price    = load_font_bold(50)

    # Сверху
    top_margin = 30
    center_x   = FINAL_WIDTH//2
    # Title
    bw, bh = draw_text_with_box(
        draw_obj, TITLE_TEXT, center_x - 300, top_margin, font_title,
        box_color=darken_color(avg_color,0.4), text_color="white",
        pad_x=40, pad_y=20, max_width=600
    )
    sub_y = top_margin + bh + 20
    # Subtitle
    draw_text_with_box(
        draw_obj, SUBTITLE_TEXT, center_x - 250, sub_y, font_subtitle,
        box_color=None, text_color="black", pad_x=0, pad_y=0,
        max_width=500
    )

    # Снизу
    bottom_margin = 30
    pr_bbox = draw_obj.textbbox((0,0), PRICE_TEXT, font=font_price)
    pr_w = pr_bbox[2] - pr_bbox[0]
    pr_h = pr_bbox[3] - pr_bbox[1]
    price_x = (FINAL_WIDTH - pr_w)//2
    price_y = FINAL_HEIGHT - pr_h - bottom_margin - 120
    draw_obj.text((price_x, price_y), PRICE_TEXT, fill="black", font=font_price)

    # Button


    return bg


def variant_4(no_bg, avg_color):
    """
    Variant 4: 
      - "Cloud" background
      - Продукт снизу
      - Текст в верхней/средней зоне, показывая другую логику
    """
    # 1) Создаём "облачный" фон
    base_col = lighten_color(avg_color, 0.2)
    bg = create_cloud_background(FINAL_WIDTH, FINAL_HEIGHT, base_col)

    # 2) Масштаб продукта
    card_area = FINAL_WIDTH * FINAL_HEIGHT
    no_bg, _ = scale_product_to_area(
        no_bg,
        int(card_area*PRODUCT_AREA_RATIO_MIN),
        int(card_area*PRODUCT_AREA_RATIO_MAX)
    )
    w, h = no_bg.size

    product_x = (FINAL_WIDTH - w)//2
    product_y = FINAL_HEIGHT - h - 60  # снизу

    shadow = no_bg.convert("L").point(lambda p: p>0 and 100).filter(ImageFilter.GaussianBlur(20))
    bg.paste(shadow, (product_x+25, product_y+25), shadow)
    bg.paste(no_bg, (product_x, product_y), no_bg)

    # 3) Текст – сверху/по центру
    draw_obj = ImageDraw.Draw(bg)
    font_title    = load_font_bold(80)
    font_subtitle = load_font_regular(50)
    font_price    = load_font_bold(60)

    cur_y = 30
    center_x = FINAL_WIDTH//2

    # Title (белый полупрозрачный прямоугольник под ним)
    box_col = (255,255,255,120)  # полупрозрачный
    # Pillow не имеет built-in "rounded_rectangle" в RGBA заливке напрямую,
    # сделаем проще – просто draw.rectangle:
    # (или можно создать отдельный слой)
    tw, th = draw_text_with_box(
        draw_obj, TITLE_TEXT, center_x - 300, cur_y, font_title,
        box_color=box_col, text_color="black",
        pad_x=30, pad_y=15, max_width=600
    )
    cur_y += th + 20

    # Subtitle
    sw, sh = draw_text_with_box(
        draw_obj, SUBTITLE_TEXT, center_x - 250, cur_y, font_subtitle,
        box_color=None, text_color="black",
        pad_x=0, pad_y=0, max_width=500
    )
    cur_y += sh + 30


    return bg


def variant_5(no_bg, avg_color):
    """
    Variant 5:
      - "Bokeh" background
      - Продукт по центру
      - Текст вокруг (сверху и снизу), 
        но в более "минималистичном" стиле
    """
    # Создаём bokeh
    base_col = darken_color(avg_color, 0.1)
    bg = create_bokeh_background(FINAL_WIDTH, FINAL_HEIGHT, base_col)

    # Масштаб
    card_area = FINAL_WIDTH * FINAL_HEIGHT
    no_bg, _ = scale_product_to_area(
        no_bg,
        int(card_area*PRODUCT_AREA_RATIO_MIN),
        int(card_area*PRODUCT_AREA_RATIO_MAX)
    )
    w, h = no_bg.size

    product_x = (FINAL_WIDTH - w)//2
    product_y = (FINAL_HEIGHT - h)//2 + 40

    shadow = no_bg.convert("L").point(lambda p:p>0 and 70).filter(ImageFilter.GaussianBlur(25))
    bg.paste(shadow, (product_x+40, product_y+40), shadow)
    bg.paste(no_bg, (product_x, product_y), no_bg)

    # Текст
    draw_obj = ImageDraw.Draw(bg)
    font_title    = load_font_bold(80)
    font_subtitle = load_font_regular(50)
    font_price    = load_font_bold(60)

    # Сверху: Title / Subtitle
    top_margin = 30
    x_center   = FINAL_WIDTH//2

    # Title
    draw_text_with_box(
        draw_obj, TITLE_TEXT,
        x_center - 300, top_margin,
        font_title, box_color=None, text_color="white",
        pad_x=20, pad_y=10, max_width=600
    )
    # Subtitle
    draw_text_with_box(
        draw_obj, SUBTITLE_TEXT,
        x_center - 250, top_margin + 100,
        font_subtitle, box_color=None, text_color="white",
        pad_x=0, pad_y=0, max_width=500
    )

    # Снизу: Price / Button
    bottom_margin = 30
    pr_bbox = draw_obj.textbbox((0,0), PRICE_TEXT, font=font_price)
    pr_w = pr_bbox[2] - pr_bbox[0]
    pr_h = pr_bbox[3] - pr_bbox[1]
    price_x = (FINAL_WIDTH - pr_w)//2
    price_y = FINAL_HEIGHT - pr_h - bottom_margin - 120
    draw_obj.text((price_x, price_y), PRICE_TEXT, fill="white", font=font_price)


    return bg


def variant_6(no_bg, avg_color):
    """
    Variant 6:
      - Split background (two colors)
      - Продукт по центру
      - Текст сверху и снизу в минималистичном стиле
    """
    # 1) Создаём split background
    bg = Image.new("RGB", (FINAL_WIDTH, FINAL_HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(bg)
    
    # Верхняя часть фона
    top_bg_color = lighten_color(avg_color, 0.7)
    draw.rectangle([0, 0, FINAL_WIDTH, FINAL_HEIGHT // 2], fill=top_bg_color)
    
    # Нижняя часть фона
    bottom_bg_color = darken_color(avg_color, 0.3)
    draw.rectangle([0, FINAL_HEIGHT // 2, FINAL_WIDTH, FINAL_HEIGHT], fill=bottom_bg_color)

    # 2) Масштабируем продукт
    card_area = FINAL_WIDTH * FINAL_HEIGHT
    no_bg, _ = scale_product_to_area(
        no_bg,
        int(card_area * PRODUCT_AREA_RATIO_MIN),
        int(card_area * PRODUCT_AREA_RATIO_MAX)
    )
    w, h = no_bg.size

    product_x = (FINAL_WIDTH - w) // 2
    product_y = (FINAL_HEIGHT - h) // 2

    # Тень
    shadow = no_bg.convert("L").point(lambda p: p > 0 and 70).filter(ImageFilter.GaussianBlur(20))
    bg.paste(shadow, (product_x + 25, product_y + 25), shadow)
    bg.paste(no_bg, (product_x, product_y), no_bg)

    # 3) Текст
    draw_obj = ImageDraw.Draw(bg)
    font_title = load_font_bold(70)
    font_subtitle = load_font_regular(40)
    font_price = load_font_bold(50)

    # Сверху: Title
    title_x = (FINAL_WIDTH - 600) // 2
    title_y = 50
    draw_text_with_box(
        draw_obj, TITLE_TEXT, title_x, title_y, font_title,
        box_color=None, text_color="black", pad_x=0, pad_y=0,
        max_width=600
    )

    # Снизу: Subtitle, Price, Button
    bottom_margin = 50
    subtitle_x = (FINAL_WIDTH - 500) // 2
    subtitle_y = FINAL_HEIGHT - 250
    draw_text_with_box(
        draw_obj, SUBTITLE_TEXT, subtitle_x, subtitle_y, font_subtitle,
        box_color=None, text_color="white", pad_x=0, pad_y=0,
        max_width=500
    )


    return bg

def variant_7(no_bg, avg_color):
    """
    Variant 7:
      - Dark background with glow effect
      - Продукт по центру с glow эффектом
      - Текст сверху и снизу в современном стиле
    """
    # 1) Создаём тёмный фон
    bg_color = darken_color(avg_color, 0.8)
    bg = Image.new("RGB", (FINAL_WIDTH, FINAL_HEIGHT), bg_color)

    # 2) Масштабируем продукт
    card_area = FINAL_WIDTH * FINAL_HEIGHT
    no_bg, _ = scale_product_to_area(
        no_bg,
        int(card_area * PRODUCT_AREA_RATIO_MIN),
        int(card_area * PRODUCT_AREA_RATIO_MAX)
    )
    w, h = no_bg.size

    product_x = (FINAL_WIDTH - w) // 2
    product_y = (FINAL_HEIGHT - h) // 2

    # Glow эффект
    glow = no_bg.convert("L").point(lambda p: p > 0 and 100).filter(ImageFilter.GaussianBlur(30))
    bg.paste(glow, (product_x - 50, product_y - 50), glow)
    bg.paste(no_bg, (product_x, product_y), no_bg)

    # 3) Текст
    draw_obj = ImageDraw.Draw(bg)
    font_title = load_font_bold(80)
    font_subtitle = load_font_regular(50)
    font_price = load_font_bold(60)

    # Сверху: Title
    title_x = (FINAL_WIDTH - 600) // 2
    title_y = 50
    draw_text_with_box(
        draw_obj, TITLE_TEXT, title_x, title_y, font_title,
        box_color=None, text_color="white", pad_x=0, pad_y=0,
        max_width=600
    )

    # Снизу: Subtitle, Price, Button
    bottom_margin = 50
    subtitle_x = (FINAL_WIDTH - 500) // 2
    subtitle_y = FINAL_HEIGHT - 250
    draw_text_with_box(
        draw_obj, SUBTITLE_TEXT, subtitle_x, subtitle_y, font_subtitle,
        box_color=None, text_color="white", pad_x=0, pad_y=0,
        max_width=500
    )



    return bg



def variant_8(no_bg, avg_color):
    """
    Variant 8:
      - Elegant gradient background
      - Продукт "парит" с тенью
      - Текст в минималистичном стиле с полупрозрачными блоками
    """
    # 1) Создаём градиентный фон
    top_color = lighten_color(avg_color, 0.8)
    bottom_color = darken_color(avg_color, 0.2)
    bg = create_linear_gradient(FINAL_WIDTH, FINAL_HEIGHT, top_color, bottom_color)

    # 2) Масштабируем продукт
    card_area = FINAL_WIDTH * FINAL_HEIGHT
    no_bg, _ = scale_product_to_area(
        no_bg,
        int(card_area * PRODUCT_AREA_RATIO_MIN),
        int(card_area * PRODUCT_AREA_RATIO_MAX)
    )
    w, h = no_bg.size

    product_x = (FINAL_WIDTH - w) // 2
    product_y = (FINAL_HEIGHT - h) // 2 - 50  # Смещаем вверх для "парящего" эффекта

    # Тень
    shadow = no_bg.convert("L").point(lambda p: p > 0 and 80).filter(ImageFilter.GaussianBlur(30))
    bg.paste(shadow, (product_x + 40, product_y + 60), shadow)
    bg.paste(no_bg, (product_x, product_y), no_bg)

    # 3) Текст
    draw_obj = ImageDraw.Draw(bg, "RGBA")
    font_title = load_font_bold(70)
    font_subtitle = load_font_regular(40)
    font_price = load_font_bold(50)

    # Title (полупрозрачный блок)
    title_bg_color = (255, 255, 255, 150)  # Полупрозрачный белый
    title_x = (FINAL_WIDTH - 600) // 2
    title_y = 50
    draw_obj.rounded_rectangle(
        [title_x - 20, title_y - 20, title_x + 600 + 20, title_y + 100],
        fill=title_bg_color, radius=20
    )
    draw_text_with_box(
        draw_obj, TITLE_TEXT, title_x, title_y, font_title,
        box_color=None, text_color="black", pad_x=0, pad_y=0,
        max_width=600
    )

    # Subtitle (полупрозрачный блок)
    subtitle_bg_color = (255, 255, 255, 120)
    subtitle_x = (FINAL_WIDTH - 500) // 2
    subtitle_y = title_y + 120
    draw_obj.rounded_rectangle(
        [subtitle_x - 20, subtitle_y - 10, subtitle_x + 500 + 20, subtitle_y + 60],
        fill=subtitle_bg_color, radius=15
    )
    draw_text_with_box(
        draw_obj, SUBTITLE_TEXT, subtitle_x, subtitle_y, font_subtitle,
        box_color=None, text_color="black", pad_x=0, pad_y=0,
        max_width=500
    )




    return bg


def variant_9(no_bg, avg_color):
    """
    Variant 9:
      - Glass morphism эффект
      - Размытый фон с полупрозрачными панелями
      - Продукт по центру с тенью
    """
    # 1) Создаём размытый фон
    base_color = lighten_color(avg_color, 0.7)
    bg = create_cloud_background(FINAL_WIDTH, FINAL_HEIGHT, base_color)
    bg = bg.filter(ImageFilter.GaussianBlur(10))  # Размываем фон

    # 2) Масштабируем продукт
    card_area = FINAL_WIDTH * FINAL_HEIGHT
    no_bg, _ = scale_product_to_area(
        no_bg,
        int(card_area * PRODUCT_AREA_RATIO_MIN),
        int(card_area * PRODUCT_AREA_RATIO_MAX)
    )
    w, h = no_bg.size

    product_x = (FINAL_WIDTH - w) // 2
    product_y = (FINAL_HEIGHT - h) // 2

    # Тень
    shadow = no_bg.convert("L").point(lambda p: p > 0 and 80).filter(ImageFilter.GaussianBlur(30))
    bg.paste(shadow, (product_x + 40, product_y + 40), shadow)
    bg.paste(no_bg, (product_x, product_y), no_bg)

    # 3) Текст на полупрозрачных панелях
    draw_obj = ImageDraw.Draw(bg, "RGBA")
    font_title = load_font_bold(70)
    font_subtitle = load_font_regular(40)
    font_price = load_font_bold(50)

    # Title (стеклянная панель)
    title_bg_color = (255, 255, 255, 120)  # Полупрозрачный белый
    title_x = (FINAL_WIDTH - 600) // 2
    title_y = 50
    draw_obj.rounded_rectangle(
        [title_x - 20, title_y - 20, title_x + 600 + 20, title_y + 100],
        fill=title_bg_color, radius=20
    )
    draw_text_with_box(
        draw_obj, TITLE_TEXT, title_x, title_y, font_title,
        box_color=None, text_color="black", pad_x=0, pad_y=0,
        max_width=600
    )

    # Subtitle (стеклянная панель)
    subtitle_bg_color = (255, 255, 255, 100)
    subtitle_x = (FINAL_WIDTH - 500) // 2
    subtitle_y = title_y + 120
    draw_obj.rounded_rectangle(
        [subtitle_x - 20, subtitle_y - 10, subtitle_x + 500 + 20, subtitle_y + 60],
        fill=subtitle_bg_color, radius=15
    )
    draw_text_with_box(
        draw_obj, SUBTITLE_TEXT, subtitle_x, subtitle_y, font_subtitle,
        box_color=None, text_color="black", pad_x=0, pad_y=0,
        max_width=500
    )

    # Price (стеклянная панель)
    price_bg_color = (255, 255, 255, 150)
    price_x = (FINAL_WIDTH - 400) // 2
    price_y = FINAL_HEIGHT - 200
    draw_obj.rounded_rectangle(
        [price_x - 20, price_y - 20, price_x + 400 + 20, price_y + 80],
        fill=price_bg_color, radius=20
    )





    return bg



def variant_10(no_bg, avg_color):
    """
    Variant 10:
      - Diagonal gradient (top-left to bottom-right)
      - Soft glow around the product
      - Текст на полупрозрачных панелях
    """
    # 1) Создаём диагональный градиент
    color1 = lighten_color(avg_color, 0.7)
    color2 = darken_color(avg_color, 0.3)
    bg = Image.new("RGB", (FINAL_WIDTH, FINAL_HEIGHT), color1)
    draw = ImageDraw.Draw(bg)

    # Рисуем диагональный градиент
    for i in range(FINAL_WIDTH + FINAL_HEIGHT):
        x = i
        y = 0
        if x > FINAL_WIDTH:
            x = FINAL_WIDTH
            y = i - FINAL_WIDTH
        t = i / (FINAL_WIDTH + FINAL_HEIGHT)
        grad_color = (
            int(color1[0] * (1 - t) + color2[0] * t),
            int(color1[1] * (1 - t) + color2[1] * t),
            int(color1[2] * (1 - t) + color2[2] * t),
        )
        draw.line([(x, y), (x - FINAL_HEIGHT, y + FINAL_HEIGHT)], fill=grad_color, width=2)

    # 2) Масштабируем продукт
    card_area = FINAL_WIDTH * FINAL_HEIGHT
    no_bg, _ = scale_product_to_area(
        no_bg,
        int(card_area * PRODUCT_AREA_RATIO_MIN),
        int(card_area * PRODUCT_AREA_RATIO_MAX)
    )
    w, h = no_bg.size

    product_x = (FINAL_WIDTH - w) // 2
    product_y = (FINAL_HEIGHT - h) // 2

    # Тень и свечение
    shadow = no_bg.convert("L").point(lambda p: p > 0 and 80).filter(ImageFilter.GaussianBlur(30))
    bg.paste(shadow, (product_x + 40, product_y + 40), shadow)
    bg.paste(no_bg, (product_x, product_y), no_bg)

    # 3) Текст на полупрозрачных панелях
    draw_obj = ImageDraw.Draw(bg, "RGBA")
    font_title = load_font_bold(70)
    font_subtitle = load_font_regular(40)
    font_price = load_font_bold(50)

    # Title (полупрозрачный блок)
    title_bg_color = (255, 255, 255, 150)  # Полупрозрачный белый
    title_x = (FINAL_WIDTH - 600) // 2
    title_y = 50
    draw_obj.rounded_rectangle(
        [title_x - 20, title_y - 20, title_x + 600 + 20, title_y + 100],
        fill=title_bg_color, radius=20
    )
    draw_text_with_box(
        draw_obj, TITLE_TEXT, title_x, title_y, font_title,
        box_color=None, text_color="black", pad_x=0, pad_y=0,
        max_width=600
    )

    # Subtitle (полупрозрачный блок)
    subtitle_bg_color = (255, 255, 255, 120)
    subtitle_x = (FINAL_WIDTH - 500) // 2
    subtitle_y = title_y + 120
    draw_obj.rounded_rectangle(
        [subtitle_x - 20, subtitle_y - 10, subtitle_x + 500 + 20, subtitle_y + 60],
        fill=subtitle_bg_color, radius=15
    )
    draw_text_with_box(
        draw_obj, SUBTITLE_TEXT, subtitle_x, subtitle_y, font_subtitle,
        box_color=None, text_color="black", pad_x=0, pad_y=0,
        max_width=500
    )



    return bg



def variant_11(no_bg, avg_color):
    """
    Variant 11:
      - Diagonal gradient (top-left to bottom-right)
      - Subtle pattern overlay
      - Текст на полупрозрачных панелях
    """
    # 1) Создаём диагональный градиент
    color1 = lighten_color(avg_color, 0.8)
    color2 = darken_color(avg_color, 0.2)
    bg = Image.new("RGB", (FINAL_WIDTH, FINAL_HEIGHT), color1)
    draw = ImageDraw.Draw(bg)

    # Рисуем диагональный градиент
    for i in range(FINAL_WIDTH + FINAL_HEIGHT):
        x = i
        y = 0
        if x > FINAL_WIDTH:
            x = FINAL_WIDTH
            y = i - FINAL_WIDTH
        t = i / (FINAL_WIDTH + FINAL_HEIGHT)
        grad_color = (
            int(color1[0] * (1 - t) + color2[0] * t),
            int(color1[1] * (1 - t) + color2[1] * t),
            int(color1[2] * (1 - t) + color2[2] * t),
        )
        draw.line([(x, y), (x - FINAL_HEIGHT, y + FINAL_HEIGHT)], fill=grad_color, width=2)

    # 2) Добавляем subtle pattern
    pattern = Image.new("RGBA", (FINAL_WIDTH, FINAL_HEIGHT), (255, 255, 255, 0))
    pattern_draw = ImageDraw.Draw(pattern)
    for i in range(0, FINAL_WIDTH + FINAL_HEIGHT, 20):
        pattern_draw.line([(i, 0), (0, i)], fill=(255, 255, 255, 10), width=2)
    bg = Image.alpha_composite(bg.convert("RGBA"), pattern).convert("RGB")

    # 3) Масштабируем продукт
    card_area = FINAL_WIDTH * FINAL_HEIGHT
    no_bg, _ = scale_product_to_area(
        no_bg,
        int(card_area * PRODUCT_AREA_RATIO_MIN),
        int(card_area * PRODUCT_AREA_RATIO_MAX)
    )
    w, h = no_bg.size

    product_x = (FINAL_WIDTH - w) // 2
    product_y = (FINAL_HEIGHT - h) // 2

    # Тень
    shadow = no_bg.convert("L").point(lambda p: p > 0 and 80).filter(ImageFilter.GaussianBlur(30))
    bg.paste(shadow, (product_x + 40, product_y + 40), shadow)
    bg.paste(no_bg, (product_x, product_y), no_bg)

    # 4) Текст на полупрозрачных панелях
    draw_obj = ImageDraw.Draw(bg, "RGBA")
    font_title = load_font_bold(70)
    font_subtitle = load_font_regular(40)
    font_price = load_font_bold(50)

    # Title (полупрозрачный блок)
    title_bg_color = (255, 255, 255, 150)  # Полупрозрачный белый
    title_x = (FINAL_WIDTH - 600) // 2
    title_y = 50
    draw_obj.rounded_rectangle(
        [title_x - 20, title_y - 20, title_x + 600 + 20, title_y + 100],
        fill=title_bg_color, radius=20
    )
    draw_text_with_box(
        draw_obj, TITLE_TEXT, title_x, title_y, font_title,
        box_color=None, text_color="black", pad_x=0, pad_y=0,
        max_width=600
    )

    # Subtitle (полупрозрачный блок)
    subtitle_bg_color = (255, 255, 255, 120)
    subtitle_x = (FINAL_WIDTH - 500) // 2
    subtitle_y = title_y + 120
    draw_obj.rounded_rectangle(
        [subtitle_x - 20, subtitle_y - 10, subtitle_x + 500 + 20, subtitle_y + 60],
        fill=subtitle_bg_color, radius=15
    )
    draw_text_with_box(
        draw_obj, SUBTITLE_TEXT, subtitle_x, subtitle_y, font_subtitle,
        box_color=None, text_color="black", pad_x=0, pad_y=0,
        max_width=500
    )

    return bg



#############################
#          MAIN
#############################

def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    files = sorted(f for f in os.listdir(INPUT_FOLDER) if os.path.isfile(os.path.join(INPUT_FOLDER, f)))
    if not files:
        print("❌ Нет файлов в папке 'inputs'!")
        return

    selected_file = files[1]
    input_path = os.path.join(INPUT_FOLDER, selected_file)
    base_name = os.path.splitext(selected_file)[0]
    result_dir = os.path.join(OUTPUT_FOLDER, base_name)
    os.makedirs(result_dir, exist_ok=True)

    print(f"Обрабатываем: {selected_file}")

    # 1) Удаляем фон
    original = Image.open(input_path).convert("RGBA")
    no_bg = remove(original)
    no_bg_path = os.path.join(result_dir, f"{base_name}_no_bg.png")
    no_bg.save(no_bg_path)
    print(f"Сохранён файл без фона: {no_bg_path}")

    # 2) Средний цвет
    arr = np.array(no_bg)
    mask = arr[:,:,3] > 0
    if np.any(mask):
        avg_color = tuple(arr[:,:,:3][mask].mean(axis=0).astype(int))
    else:
        avg_color = (128,128,128)
    print(f"Средний цвет товара: {avg_color}")

    # 3) Генерируем 5 разных вариантов
    variants = [variant_1, variant_2, variant_3, variant_4, variant_5,variant_6,variant_7,variant_8,variant_9,variant_10,variant_11]
    for i, v_func in enumerate(variants, 1):
        print(f"Генерируем вариант #{i}...")
        card_img = v_func(no_bg.copy(), avg_color)
        out_path = os.path.join(result_dir, f"{base_name}_variant_{i}.png")
        card_img.save(out_path)
        print(f" → Сохранено: {out_path}")

    print("✅ Все 9 вариантов готовы!")

if __name__ == "__main__":
    main()
