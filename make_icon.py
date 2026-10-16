"""Генерирует chem-agent.ico из растровой отрисовки колбы (совпадает с logo.svg)."""
from PIL import Image, ImageDraw

BLUE = (47, 107, 216)
WHITE = (255, 255, 255)

SS = 4  # supersample factor для сглаживания


def draw_flask(size: int) -> Image.Image:
    """Рисует колбу по мотивам logo.svg на синем фоне."""
    W = size * SS
    img = Image.new("RGBA", (W, W), BLUE)
    d = ImageDraw.Draw(img)
    s = W / 32.0  # масштаб от исходной сетки 32×32
    lw = max(3, int(2.0 * s))  # толщина линии

    # Верхняя горизонтальная планка горлышка: (12,6) -> (20,6)
    d.line([(12 * s, 6 * s), (20 * s, 6 * s)], fill=WHITE, width=lw)

    # Левая стенка: горлышко (14,6)->(14,14), затем диагональ (14,14)->(8,24)
    d.line(
        [(14 * s, 6 * s), (14 * s, 14 * s), (8 * s, 24 * s)],
        fill=WHITE, width=lw, joint="curve",
    )

    # Правая стенка: горлышко (18,6)->(18,14), затем диагональ (18,14)->(24,24)
    d.line(
        [(18 * s, 6 * s), (18 * s, 14 * s), (24 * s, 24 * s)],
        fill=WHITE, width=lw, joint="curve",
    )

    # Нижняя горизонтальная планка основания
    d.line([(8 * s, 25.5 * s), (24 * s, 25.5 * s)], fill=WHITE, width=lw)

    # Пузырёк 1: центр (14, 21), радиус 1.4
    r1 = max(2, int(1.4 * s))
    cx1, cy1 = 14 * s, 21 * s
    d.ellipse([cx1 - r1, cy1 - r1, cx1 + r1, cy1 + r1], fill=WHITE)

    # Пузырёк 2: центр (18.5, 23), радиус 1.1
    r2 = max(1, int(1.1 * s))
    cx2, cy2 = 18.5 * s, 23 * s
    d.ellipse([cx2 - r2, cy2 - r2, cx2 + r2, cy2 + r2], fill=WHITE)

    # Уменьшаем с антиалиасингом
    return img.resize((size, size), Image.LANCZOS)


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [draw_flask(s) for s in sizes]
    images[-1].save(
        "chem-agent.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    print(f"chem-agent.ico saved ({len(sizes)} sizes)")


if __name__ == "__main__":
    main()