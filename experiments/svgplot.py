"""Gráficas de líneas en SVG sin dependencias externas.

Cada serie es una lista de puntos ``(x, media, desviación)``; el eje X es
categórico (los valores de un parámetro) y cada punto lleva una barra de
error de una desviación estándar.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

COLORS = ("#1f6fb2", "#d9622b", "#2e9c5a", "#8a4fbf")
WIDTH, HEIGHT = 520, 340
LEFT, RIGHT, TOP, BOTTOM = 64, 20, 58, 56


def _nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    magnitude = 10 ** len(str(int(value))) / 10
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * magnitude:
            return step * magnitude
    return value


def line_chart(
    path: Path,
    title: str,
    x_label: str,
    y_label: str,
    categories: Sequence[str],
    series: dict[str, Sequence[tuple[float, float]]],
    y_max: float | None = None,
) -> None:
    """Escribe una gráfica de líneas con barras de error en ``path``.

    ``series`` asocia el nombre de cada serie con una lista ``(media, desv)``
    alineada con ``categories``.
    """
    top_value = max((mean + sd for points in series.values() for mean, sd in points), default=1.0)
    y_top = y_max if y_max is not None else _nice_max(top_value)
    plot_w = WIDTH - LEFT - RIGHT
    plot_h = HEIGHT - TOP - BOTTOM

    def x_pos(index: int) -> float:
        return LEFT + plot_w * (index + 0.5) / len(categories)

    def y_pos(value: float) -> float:
        return TOP + plot_h * (1 - min(max(value, 0.0), y_top) / y_top)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'font-family="sans-serif" font-size="12">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="white"/>',
        f'<text x="{WIDTH / 2}" y="22" text-anchor="middle" font-size="14" font-weight="bold">{title}</text>',
    ]
    for tick in range(5):
        value = y_top * tick / 4
        y = y_pos(value)
        label = f"{value:.0f}" if y_top >= 10 else f"{value:.2f}"
        parts.append(f'<line x1="{LEFT}" y1="{y:.1f}" x2="{WIDTH - RIGHT}" y2="{y:.1f}" stroke="#e3e3e3"/>')
        parts.append(f'<text x="{LEFT - 6}" y="{y + 4:.1f}" text-anchor="end">{label}</text>')
    for index, category in enumerate(categories):
        parts.append(f'<text x="{x_pos(index):.1f}" y="{HEIGHT - BOTTOM + 18}" text-anchor="middle">{category}</text>')
    parts.append(f'<line x1="{LEFT}" y1="{TOP + plot_h}" x2="{WIDTH - RIGHT}" y2="{TOP + plot_h}" stroke="#555"/>')
    parts.append(f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" y2="{TOP + plot_h}" stroke="#555"/>')
    parts.append(f'<text x="{LEFT + plot_w / 2}" y="{HEIGHT - 12}" text-anchor="middle">{x_label}</text>')
    parts.append(
        f'<text x="16" y="{TOP + plot_h / 2}" text-anchor="middle" '
        f'transform="rotate(-90 16 {TOP + plot_h / 2})">{y_label}</text>'
    )

    for number, (name, points) in enumerate(series.items()):
        color = COLORS[number % len(COLORS)]
        offset = (number - (len(series) - 1) / 2) * 6
        coords = [(x_pos(i) + offset, y_pos(mean)) for i, (mean, _sd) in enumerate(points)]
        parts.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2" points="'
            + " ".join(f"{x:.1f},{y:.1f}" for x, y in coords) + '"/>'
        )
        for (x, y), (mean, sd) in zip(coords, points):
            parts.append(
                f'<line x1="{x:.1f}" y1="{y_pos(mean - sd):.1f}" x2="{x:.1f}" y2="{y_pos(mean + sd):.1f}" stroke="{color}"/>'
            )
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"/>')
        legend_x = LEFT + 120 * number
        parts.append(f'<rect x="{legend_x}" y="{TOP - 24}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{legend_x + 18}" y="{TOP - 14}">{name}</text>')

    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
