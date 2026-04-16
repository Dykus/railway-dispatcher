from PIL import Image, ImageDraw, ImageFont
import os

# Список стандартных размеров для ICO
sizes = [16, 24, 32, 48, 64, 128, 256]
images = []

# Попробуем найти системный шрифт с эмодзи (Windows)
font_paths = [
    "seguiemj.ttf",          # Segoe UI Emoji
    "C:\\Windows\\Fonts\\seguiemj.ttf",
    "C:\\Windows\\Fonts\\seguiemj.TTF",
    "segoeui.ttf",
    "C:\\Windows\\Fonts\\segoeui.ttf"
]

font = None
for path in font_paths:
    try:
        font = ImageFont.truetype(path, size=10)
        break
    except:
        pass

if font is None:
    print("⚠️ Не найден шрифт с эмодзи, будет использован стандартный (без эмодзи).")
    font = ImageFont.load_default()

for size in sizes:
    # Создаём прозрачный квадрат
    img = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Устанавливаем размер шрифта чуть меньше размера иконки
    font_size = int(size * 0.8)
    try:
        # Пытаемся создать шрифт нужного размера
        for path in font_paths:
            try:
                font = ImageFont.truetype(path, size=font_size)
                break
            except:
                pass
    except:
        font = ImageFont.load_default()

    text = "🚂"
    # Вычисляем размер текста
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (size - w) // 2
    y = (size - h) // 2

    # Рисуем текст (эмодзи) с поддержкой цвета
    draw.text((x, y), text, font=font, embedded_color=True)

    images.append(img)

# Сохраняем как ICO с несколькими размерами
# Pillow сохранит все переданные изображения в один ICO-файл
images[0].save(
    'icon.ico',
    format='ICO',
    sizes=[(s, s) for s in sizes],
    append_images=images[1:]
)

print("✅ icon.ico создан с размерами:", sizes)