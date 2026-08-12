import colorsys
import math
import random

from kitty.fast_data_types import Screen
from kitty.tab_bar import (
    DrawData,
    ExtraData,
    TabBarData,
    as_rgb,
    draw_title,
    powerline_symbols,
)
from kitty.rgb import color_from_int
from kitty.utils import color_as_int

# Distinct, readable tab colors.
PALETTE = [
    0xCC241D,  # red
    0x98971A,  # olive
    0xD79921,  # amber
    0x458588,  # teal
    0xB16286,  # magenta
    0x689D6A,  # green
    0xD65D0E,  # orange
    0x3282B8,  # blue
    0x854444,  # maroon
    0x537EC5,  # cornflower
    0x8E44AD,  # purple
    0x16A085,  # sea green
    0xC0392B,  # crimson
    0x2980B9,  # strong blue
    0xF39C12,  # gold
]

# Minimum separation from each adjacent tab color.
MIN_RGB_DISTANCE = 95.0
MIN_HUE_DISTANCE = 0.12

TAB_COLORS: dict[int, int] = {}


def _rgb_components(rgb: int) -> tuple[int, int, int]:
    return (rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF


def _rgb_distance(a: int, b: int) -> float:
    ar, ag, ab = _rgb_components(a)
    br, bg, bb = _rgb_components(b)
    return math.sqrt((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2)


def _hue_distance(a: int, b: int) -> float:
    ar, ag, ab = _rgb_components(a)
    br, bg, bb = _rgb_components(b)
    ah, _, _ = colorsys.rgb_to_hls(ar / 255.0, ag / 255.0, ab / 255.0)
    bh, _, _ = colorsys.rgb_to_hls(br / 255.0, bg / 255.0, bb / 255.0)
    return min(abs(ah - bh), 1.0 - abs(ah - bh))


def _is_too_similar(a: int, b: int) -> bool:
    return _rgb_distance(a, b) < MIN_RGB_DISTANCE or _hue_distance(a, b) < MIN_HUE_DISTANCE


def _separation_score(color: int, neighbor_colors: list[int]) -> float:
    if not neighbor_colors:
        return float('inf')
    return min(_rgb_distance(color, neighbor) + _hue_distance(color, neighbor) * 180.0
               for neighbor in neighbor_colors)


def _dim(rgb: int, factor: float) -> int:
    r, g, b = _rgb_components(rgb)
    return (int(r * factor) << 16) | (int(g * factor) << 8) | int(b * factor)


def _random_color() -> int:
    hue = random.random()
    saturation = random.uniform(0.55, 0.9)
    lightness = random.uniform(0.36, 0.5)
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return (int(red * 255) << 16) | (int(green * 255) << 8) | int(blue * 255)


def _neighbor_colors(neighbor_tabs: list[TabBarData]) -> list[int]:
    colors: list[int] = []
    for neighbor in neighbor_tabs:
        color = TAB_COLORS.get(neighbor.tab_id)
        if color is not None:
            colors.append(color)
    return colors


def _pick_distinct_color(neighbor_colors: list[int]) -> int:
    good_palette = [
        color for color in PALETTE
        if not any(_is_too_similar(color, neighbor) for neighbor in neighbor_colors)
    ]
    if good_palette:
        return random.choice(good_palette)

    ranked_palette = sorted(PALETTE, key=lambda color: _separation_score(color, neighbor_colors), reverse=True)
    if ranked_palette and _separation_score(ranked_palette[0], neighbor_colors) > 0:
        return random.choice(ranked_palette[:3])

    best_color = None
    best_score = -1.0
    for _ in range(48):
        candidate = _random_color()
        score = _separation_score(candidate, neighbor_colors)
        if score > best_score:
            best_score = score
            best_color = candidate
        if neighbor_colors and not any(_is_too_similar(candidate, neighbor) for neighbor in neighbor_colors):
            return candidate
    return best_color if best_color is not None else _random_color()


def _ensure_tab_color(tab: TabBarData, neighbor_tabs: list[TabBarData]) -> int:
    existing = TAB_COLORS.get(tab.tab_id)
    if existing is not None:
        return existing

    color = _pick_distinct_color(_neighbor_colors(neighbor_tabs))
    TAB_COLORS[tab.tab_id] = color
    return color


def _tab_bg(tab: TabBarData, neighbor_tabs: list[TabBarData]) -> int:
    color = _ensure_tab_color(tab, neighbor_tabs)
    return color if tab.is_active else _dim(color, 0.86)


ACTIVE_TAB_FG = 0xEEEEEE
INACTIVE_TAB_FG = 0x222222


def _tab_fg(tab: TabBarData, bg: int) -> int:
    if tab.is_active:
        return ACTIVE_TAB_FG
    return INACTIVE_TAB_FG


def _title_draw_data(draw_data: DrawData, tab: TabBarData, bg: int) -> DrawData:
    # draw_title uses {fmt.fg.tab} -> draw_data.tab_fg(). DrawData is immutable.
    fg = color_from_int(_tab_fg(tab, bg))
    if tab.is_active:
        return draw_data._replace(active_fg=fg)
    return draw_data._replace(inactive_fg=fg)


def _neighbor_tabs(tab: TabBarData, extra_data: ExtraData) -> list[TabBarData]:
    neighbors: list[TabBarData] = []
    if extra_data.prev_tab is not None:
        neighbors.append(extra_data.prev_tab)
    if extra_data.next_tab is not None:
        neighbors.append(extra_data.next_tab)
    return neighbors


def _draw_powerline_tab(
    draw_data: DrawData,
    title_draw_data: DrawData,
    screen: Screen,
    tab: TabBarData,
    before: int,
    max_title_length: int,
    index: int,
    is_last: bool,
    extra_data: ExtraData,
) -> int:
    tab_bg = screen.cursor.bg
    tab_fg = screen.cursor.fg
    default_bg = as_rgb(color_as_int(draw_data.default_bg))

    if extra_data.next_tab is not None:
        next_tab_bg = as_rgb(_tab_bg(extra_data.next_tab, [tab]))
        needs_soft_separator = next_tab_bg == tab_bg
    else:
        next_tab_bg = default_bg
        needs_soft_separator = False

    separator_symbol, soft_separator_symbol = powerline_symbols.get(
        draw_data.powerline_style, ('\ue0b0', '\ue0b1')
    )
    min_title_length = 1 + 2
    start_draw = 2

    if screen.cursor.x == 0:
        screen.cursor.bg = tab_bg
        screen.draw(' ')
        start_draw = 1

    screen.cursor.bg = tab_bg
    if min_title_length >= max_title_length:
        screen.draw('…')
    else:
        draw_title(title_draw_data, screen, tab, index, max_title_length)
        extra = screen.cursor.x + start_draw - before - max_title_length
        if extra > 0 and extra + 1 < screen.cursor.x:
            screen.cursor.x -= extra + 1
            screen.draw('…')

    if not needs_soft_separator:
        screen.draw(' ')
        screen.cursor.fg = tab_bg
        screen.cursor.bg = next_tab_bg
        screen.draw(separator_symbol)
    else:
        prev_fg = screen.cursor.fg
        if tab_bg == tab_fg:
            screen.cursor.fg = default_bg
        elif tab_bg != default_bg:
            c1 = draw_data.inactive_bg.contrast(draw_data.default_bg)
            c2 = draw_data.inactive_bg.contrast(draw_data.inactive_fg)
            if c1 < c2:
                screen.cursor.fg = default_bg
        screen.draw(f' {soft_separator_symbol}')
        screen.cursor.fg = prev_fg

    end = screen.cursor.x
    if end < screen.columns:
        screen.draw(' ')
    return end


def draw_tab(
    draw_data: DrawData,
    screen: Screen,
    tab: TabBarData,
    before: int,
    max_title_length: int,
    index: int,
    is_last: bool,
    extra_data: ExtraData,
) -> int:
    neighbors = _neighbor_tabs(tab, extra_data)
    bg = _tab_bg(tab, neighbors)
    fg = _tab_fg(tab, bg)

    title_draw_data = _title_draw_data(draw_data, tab, bg)
    screen.cursor.bg = as_rgb(bg)
    screen.cursor.fg = as_rgb(fg)

    return _draw_powerline_tab(
        draw_data, title_draw_data, screen, tab, before, max_title_length, index, is_last, extra_data
    )
