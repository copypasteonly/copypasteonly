"""Generate dark_mode.svg and light_mode.svg from config.toml and ASCII art files."""

from __future__ import annotations

import datetime
import tomllib
from html import escape
from pathlib import Path

from dateutil import relativedelta


def load_config(config_path: Path = Path("config.toml")) -> dict:
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def dot_fill(key_len: int, value_len: int, target_width: int) -> str:
    """Calculate dot-fill string for a dot-justified line.

    Full line is: `. ` + key + `:` + dot_fill + value = (2 + target_width) chars.
    So: dot_count = target_width - key_len - 1(colon) - value_len - 2(spaces around dots).
    """
    dot_count = target_width - key_len - 1 - value_len - 2
    if dot_count <= 0:
        return " "
    return " " + "." * dot_count + " "


def stats_dot_fill(length: int, value_len: int) -> str:
    """Calculate dot-fill for stats elements (matches today.py's justify_format)."""
    just_len = max(0, length - value_len)
    if just_len == 0:
        return ""
    if just_len == 1:
        return " "
    if just_len == 2:
        return ". "
    return " " + "." * just_len + " "


def compute_age(birth_year: int, birth_month: int, birth_day: int) -> str:
    birthday = datetime.datetime(birth_year, birth_month, birth_day)
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)
    s = lambda n: "s" if n != 1 else ""
    parts = f"{diff.years} year{s(diff.years)}, {diff.months} month{s(diff.months)}, {diff.days} day{s(diff.days)}"
    if diff.months == 0 and diff.days == 0:
        parts += " 🎂"
    return parts


def em_dash_separator(title: str, target_width: int) -> str:
    """Build a section header separator line.

    Total line width = target_width + 2 (matching `. ` prefix width of content lines).
    Format: title + ` -` + N×`—` + `-—-`
    """
    total_width = target_width + 2
    n = total_width - len(title) - 5  # 5 = len(" -") + len("-—-")
    return f" -{'—' * n}-—-"


def xml_escape(text: str) -> str:
    """Escape only the XML-required characters: &, <, >. Not quotes."""
    return escape(text, quote=False)


def render_ascii_art(art_path: Path, x: int, y_start: int, line_height: int) -> tuple[str, int]:
    """Read ASCII art file and return tspan lines. Returns (svg_fragment, next_y)."""
    lines = art_path.read_text().splitlines()
    parts = []
    y = y_start
    for line in lines:
        parts.append(f'<tspan x="{x}" y="{y}">{xml_escape(line)}</tspan>')
        y += line_height
    return "\n".join(parts), y


def render_profile_line(x: int, y: int, key_display: str, value: str,
                        target_width: int, element_id: str | None = None) -> str:
    """Render a dot-justified profile/contact line."""
    dots = dot_fill(len(key_display), len(value), target_width)

    # Build key tspan(s) — handle dotted keys like "Languages.Programming"
    if "." in key_display:
        key_parts = key_display.split(".")
        key_html = ".".join(f'<tspan class="key">{p}</tspan>' for p in key_parts)
    else:
        key_html = f'<tspan class="key">{key_display}</tspan>'

    # Build dots and value tspans with optional IDs
    dots_attrs = ' class="cc"'
    value_attrs = ' class="value"'
    if element_id:
        dots_attrs += f' id="{element_id}_dots"'
        value_attrs += f' id="{element_id}"'

    return (
        f'<tspan x="{x}" y="{y}" class="cc">. </tspan>'
        f'{key_html}:'
        f'<tspan{dots_attrs}>{dots}</tspan>'
        f'<tspan{value_attrs}>{xml_escape(value)}</tspan>'
    )


def render_blank_line(x: int, y: int) -> str:
    return f'<tspan x="{x}" y="{y}" class="cc">. </tspan>'


def build_svg(config: dict, theme: str) -> str:
    layout = config["layout"]
    colors = config["colors"][theme]
    tw = layout["target_width"]
    x = layout["content_x"]
    lh = layout["line_height"]

    # Age calculation
    user = config["user"]
    age_value = compute_age(user["birth_year"], user["birth_month"], user["birth_day"])

    # --- SVG header and styles ---
    svg = f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="{layout['width']}px" height="{layout['height']}px" font-size="{layout['font_size']}px">
<style>
@font-face {{
src: local('Consolas'), local('Consolas Bold');
font-family: 'ConsolasFallback';
font-display: swap;
-webkit-size-adjust: 109%;
size-adjust: 109%;
}}
.key {{fill: {colors['key']};}}
.value {{fill: {colors['value']};}}
.addColor {{fill: {colors['add']};}}
.delColor {{fill: {colors['delete']};}}
.cc {{fill: {colors['dots']};}}
text, tspan {{white-space: pre;}}
</style>
<rect width="{layout['width']}px" height="{layout['height']}px" fill="{colors['background']}" rx="{layout['corner_radius']}"/>"""

    # --- ASCII art ---
    art_path = Path(config["ascii_art"][theme])
    ascii_svg, _ = render_ascii_art(art_path, layout["ascii_x"], 30, lh)
    svg += f'\n<text x="{layout["ascii_x"]}" y="30" fill="{colors["text"]}" class="ascii">\n{ascii_svg}\n</text>'

    # --- Content section ---
    content_lines = []
    y = 30

    # Username header
    username = config["user"]["username"]
    separator = em_dash_separator(username, tw)
    content_lines.append(f'<tspan x="{x}" y="{y}">{xml_escape(username)}</tspan>{separator}')
    y += lh

    # Profile section — plain string values first
    profile = config["profile"]
    for key, value in profile.items():
        if isinstance(value, dict):
            continue  # handle nested tables after plain values
        if value == "auto":
            # Uptime — auto-calculated with IDs for dynamic updating
            content_lines.append(render_profile_line(x, y, "Uptime", age_value, tw, "age_data"))
        else:
            content_lines.append(render_profile_line(x, y, key, value, tw))
        y += lh

    # Nested profile groups (Languages, Hobbies, etc.)
    for group_name, group_dict in profile.items():
        if not isinstance(group_dict, dict):
            continue
        # Blank separator before group
        content_lines.append(render_blank_line(x, y))
        y += lh
        for sub_key, sub_value in group_dict.items():
            display_key = f"{group_name}.{sub_key}"
            content_lines.append(render_profile_line(x, y, display_key, sub_value, tw))
            y += lh

    # --- Contact section ---
    y += lh  # gap before section header
    contact_title = "- Contact"
    separator = em_dash_separator(contact_title, tw)
    content_lines.append(f'<tspan x="{x}" y="{y}">{contact_title}</tspan>{separator}')
    y += lh

    contact = config["contact"]
    for key, value in contact.items():
        if isinstance(value, list):
            for item in value:
                content_lines.append(render_profile_line(x, y, key, item, tw))
                y += lh
        else:
            content_lines.append(render_profile_line(x, y, key, value, tw))
            y += lh

    # --- GitHub Stats section ---
    y += lh  # gap before section header
    stats_title = "- GitHub Stats"
    separator = em_dash_separator(stats_title, tw)
    content_lines.append(f'<tspan x="{x}" y="{y}">{stats_title}</tspan>{separator}')
    y += lh

    # Stats line 1: Repos {Contributed} | Stars
    repo_dots = stats_dot_fill(6, 1)
    star_dots = stats_dot_fill(14, 1)
    content_lines.append(
        f'<tspan x="{x}" y="{y}" class="cc">. </tspan>'
        f'<tspan class="key">Repos</tspan>:'
        f'<tspan class="cc" id="repo_data_dots">{repo_dots}</tspan>'
        f'<tspan class="value" id="repo_data">0</tspan>'
        f' {{<tspan class="key">Contributed</tspan>: '
        f'<tspan class="value" id="contrib_data">0</tspan>'
        f'}} | '
        f'<tspan class="key">Stars</tspan>:'
        f'<tspan class="cc" id="star_data_dots">{star_dots}</tspan>'
        f'<tspan class="value" id="star_data">0</tspan>'
    )
    y += lh

    # Stats line 2: Commmits | Followers (note: 3 m's preserved)
    commit_dots = stats_dot_fill(22, 1)
    follower_dots = stats_dot_fill(10, 1)
    content_lines.append(
        f'<tspan x="{x}" y="{y}" class="cc">. </tspan>'
        f'<tspan class="key">Commmits</tspan>:'
        f'<tspan class="cc" id="commit_data_dots">{commit_dots}</tspan>'
        f'<tspan class="value" id="commit_data">0</tspan>'
        f' | '
        f'<tspan class="key">Followers</tspan>:'
        f'<tspan class="cc" id="follower_data_dots">{follower_dots}</tspan>'
        f'<tspan class="value" id="follower_data">0</tspan>'
    )
    y += lh

    # Stats line 3: Lines of Code on GitHub (additions++, deletions--)
    loc_dots = stats_dot_fill(9, 1)
    loc_del_dots = stats_dot_fill(7, 1)
    content_lines.append(
        f'<tspan x="{x}" y="{y}" class="cc">. </tspan>'
        f'<tspan class="key">Lines of Code on GitHub</tspan>:'
        f'<tspan class="cc" id="loc_data_dots">{loc_dots}</tspan>'
        f'<tspan class="value" id="loc_data">0</tspan>'
        f' ( '
        f'<tspan class="addColor" id="loc_add">0</tspan>'
        f'<tspan class="addColor">++</tspan>'
        f', '
        f'<tspan id="loc_del_dots">{loc_del_dots}</tspan>'
        f'<tspan class="delColor" id="loc_del">0</tspan>'
        f'<tspan class="delColor">--</tspan>'
        f' )'
    )

    # Assemble content text block
    svg += f'\n<text x="{x}" y="30" fill="{colors["text"]}">'
    svg += "\n" + "\n".join(content_lines)
    svg += "\n</text>"
    svg += "\n</svg>"

    return svg


def main() -> None:
    config = load_config()
    for theme in ("dark", "light"):
        svg_content = build_svg(config, theme)
        output_path = Path(config["output"][theme])
        output_path.write_text(svg_content, encoding="utf-8")
        print(f"Generated {output_path}")


if __name__ == "__main__":
    main()
