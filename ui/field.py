"""Illustrative sport diagrams for the position preview."""

from html import escape

SPORT_STYLES = {"Football": "football", "Cricket": "cricket", "Basketball": "basketball"}

FIELDS = {
    "Football": (
        '<rect x="18" y="15" width="324" height="170" rx="7"/>'
        '<path d="M180 15v170M18 53h52v94H18m324-94h-52v94h52M18 77h22v46H18m324-46h-22v46h22"/>'
        '<circle cx="180" cy="100" r="27"/>',
        {"Striker": (267, 100), "Goalkeeper": (34, 101), "Midfielder": (174, 72), "Defender": (95, 125)},
    ),
    "Cricket": (
        '<ellipse cx="180" cy="100" rx="163" ry="84"/><ellipse cx="180" cy="100" rx="107" ry="57"/>'
        '<rect x="136" y="85" width="88" height="30" rx="2"/>'
        '<path d="M146 80v40m68-40v40M137 93v14m86-14v14"/>',
        {"Fast bowler": (96, 101), "Spin bowler": (128, 117), "Batter": (210, 101), "Wicketkeeper": (239, 101)},
    ),
    "Basketball": (
        '<rect x="18" y="15" width="324" height="170" rx="7"/>'
        '<path d="M180 15v170M18 75h53v50H18m324-50h-53v50h53M18 29a78 78 0 0 1 0 142m324-142a78 78 0 0 0 0 142"/>'
        '<circle cx="180" cy="100" r="22"/><circle cx="71" cy="100" r="25"/>'
        '<circle cx="289" cy="100" r="25"/><circle cx="29" cy="100" r="5"/><circle cx="331" cy="100" r="5"/>',
        {"Point guard": (204, 103), "Shooting guard": (258, 49), "Forward": (272, 147), "Center": (300, 103)},
    ),
}


def field_svg(sport, position):
    markings, positions = FIELDS[sport]
    x, y = positions[position]
    direction = -1 if x > 220 else 1
    bend = -1 if y > 110 else 1
    label = escape(f"Illustrative {sport.lower()} position map for {position}", quote=True)
    return f"""
    <svg class="cb-field-svg" viewBox="0 0 360 200" role="img" aria-label="{label}">
        <g class="cb-field-markings">{markings}</g>
        <g transform="translate({x} {y}) scale({direction} {bend})">
          <path class="cb-field-route" d="M0 0 C18 -25 42 -29 52 -12 S44 21 22 20 Q8 20 0 0 Z"/>
          <circle class="cb-field-tracer" cx="0" cy="0" r="3"/>
          <circle class="cb-field-halo" cx="0" cy="0" r="14"/>
          <circle class="cb-field-pin" cx="0" cy="0" r="6"/>
        </g>
    </svg>
    """
