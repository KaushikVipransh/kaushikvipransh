"""
Contribution Constellation Generator
Fetches GitHub contribution data and renders it as an animated
star constellation SVG — each day is a star, brightness = commit count.
"""

import os
import sys
import json
import math
import random
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
USERNAME = os.environ.get("GITHUB_USERNAME", "KaushikVipransh")

GRAPHQL_QUERY = """
query($username: String!) {
  user(login: $username) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

# ── Canvas settings ────────────────────────────────────────────────────────────
W, H = 900, 300
MARGIN_X, MARGIN_Y = 24, 24
STAR_MAX_R = 5.5
STAR_MIN_R = 1.0
CONNECT_DIST = 48        # px — max distance to draw a constellation line
MAX_CONNECTIONS = 3      # max lines per star to keep it readable
LINE_OPACITY = 0.18


def fetch_contributions():
    headers = {"Authorization": f"bearer {GITHUB_TOKEN}"}
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": GRAPHQL_QUERY, "variables": {"username": USERNAME}},
        headers=headers,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    calendar = (
        data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    )
    days = []
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append(day)
    return days, calendar["totalContributions"]


def map_stars(days):
    """Convert contribution days → star coordinates + size."""
    usable_w = W - 2 * MARGIN_X
    usable_h = H - 2 * MARGIN_Y
    total = len(days)
    max_count = max((d["contributionCount"] for d in days), default=1) or 1

    stars = []
    cols = math.ceil(total / 7)

    rng = random.Random(42)  # deterministic jitter

    for i, day in enumerate(days):
        col = i // 7
        row = i % 7
        x = MARGIN_X + (col / max(cols - 1, 1)) * usable_w
        y = MARGIN_Y + (row / 6) * usable_h

        # Jitter position slightly for organic feel
        x += rng.uniform(-3, 3)
        y += rng.uniform(-2, 2)

        count = day["contributionCount"]
        ratio = math.sqrt(count / max_count) if count > 0 else 0
        r = STAR_MIN_R + ratio * (STAR_MAX_R - STAR_MIN_R)

        # Colour: dim grey → amber → red based on intensity
        if count == 0:
            color = "#1A1D24"
            opacity = 0.25
        elif ratio < 0.3:
            color = "#4A5568"   # dark steel — low activity
            opacity = 0.55 + ratio
        elif ratio < 0.65:
            color = "#A0AAB4"   # silver — medium
            opacity = 0.78
        else:
            color = "#E2E8F0"   # bright chrome — high activity
            opacity = 0.96

        stars.append({
            "x": round(x, 2),
            "y": round(y, 2),
            "r": round(r, 2),
            "color": color,
            "opacity": opacity,
            "count": count,
            "date": day["date"],
            "glow": count > 0,
        })
    return stars


def build_constellation_lines(stars):
    """Connect nearby stars with faint lines."""
    lines = []
    used = {i: 0 for i in range(len(stars))}

    for i, s in enumerate(stars):
        if s["count"] == 0:
            continue
        neighbours = []
        for j, t in enumerate(stars):
            if i == j or t["count"] == 0:
                continue
            dist = math.hypot(s["x"] - t["x"], s["y"] - t["y"])
            if dist < CONNECT_DIST:
                neighbours.append((dist, j))
        neighbours.sort()
        for dist, j in neighbours[:MAX_CONNECTIONS]:
            if used[i] >= MAX_CONNECTIONS:
                break
            lines.append((i, j, dist))
            used[i] += 1
    return lines


def anim_dur(star_idx):
    """Deterministic but varied twinkle duration per star."""
    return round(2.5 + (star_idx % 17) * 0.18, 2)


def anim_delay(star_idx):
    return round((star_idx % 23) * 0.11, 2)


def render_svg(stars, lines, total_contributions):
    parts = []

    # ── Defs: glows + gradients ────────────────────────────────────────────────
    defs = """
  <defs>
    <!-- Chrome glow (bright silver) -->
    <filter id="glow-chrome" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="3.2" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <!-- Silver glow (mid silver) -->
    <filter id="glow-silver" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="2.6" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <!-- Steel glow (dark steel) -->
    <filter id="glow-steel" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="2.0" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <!-- Background gradient -->
    <radialGradient id="bg" cx="50%" cy="50%" r="75%">
      <stop offset="0%" stop-color="#0c0f16"/>
      <stop offset="100%" stop-color="#060810"/>
    </radialGradient>
    <!-- Nebula — cool blue-gray metallic clouds -->
    <radialGradient id="nebula1" cx="30%" cy="40%" r="40%">
      <stop offset="0%" stop-color="#A0AAB4" stop-opacity="0.04"/>
      <stop offset="100%" stop-color="#0D1117" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="nebula2" cx="70%" cy="60%" r="35%">
      <stop offset="0%" stop-color="#4A5568" stop-opacity="0.05"/>
      <stop offset="100%" stop-color="#0D1117" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="nebula3" cx="55%" cy="25%" r="30%">
      <stop offset="0%" stop-color="#E2E8F0" stop-opacity="0.03"/>
      <stop offset="100%" stop-color="#0D1117" stop-opacity="0"/>
    </radialGradient>
  </defs>"""
    parts.append(defs)

    # ── Background ─────────────────────────────────────────────────────────────
    parts.append(f'  <rect width="{W}" height="{H}" fill="url(#bg)" rx="12"/>')
    parts.append(f'  <rect width="{W}" height="{H}" fill="url(#nebula1)" rx="12"/>')
    parts.append(f'  <rect width="{W}" height="{H}" fill="url(#nebula2)" rx="12"/>')
    parts.append(f'  <rect width="{W}" height="{H}" fill="url(#nebula3)" rx="12"/>')

    # ── Constellation lines ────────────────────────────────────────────────────
    for i, j, _ in lines:
        s, t = stars[i], stars[j]
        parts.append(
            f'  <line x1="{s["x"]}" y1="{s["y"]}" '
            f'x2="{t["x"]}" y2="{t["y"]}" '
            f'stroke="#A0AAB4" stroke-opacity="{LINE_OPACITY}" stroke-width="0.6"/>'
        )

    # ── Stars ──────────────────────────────────────────────────────────────────
    for idx, s in enumerate(stars):
        if s["count"] == 0:
            # tiny dim dot for days with no commits
            parts.append(
                f'  <circle cx="{s["x"]}" cy="{s["y"]}" r="{s["r"]}" '
                f'fill="{s["color"]}" opacity="{s["opacity"]}"/>'
            )
            continue

        # Determine glow filter
        if s["color"] == "#E2E8F0":
            filt = 'filter="url(#glow-chrome)"'
        elif s["color"] == "#A0AAB4":
            filt = 'filter="url(#glow-silver)"'
        else:
            filt = 'filter="url(#glow-steel)"'

        dur = anim_dur(idx)
        delay = anim_delay(idx)
        min_op = round(s["opacity"] * 0.45, 2)
        max_op = round(min(s["opacity"], 0.97), 2)

        parts.append(
            f'  <circle cx="{s["x"]}" cy="{s["y"]}" r="{s["r"]}" '
            f'fill="{s["color"]}" opacity="{max_op}" {filt}>'
            f'<animate attributeName="opacity" values="{max_op};{min_op};{max_op}" '
            f'dur="{dur}s" begin="{delay}s" repeatCount="indefinite"/>'
            f'<animate attributeName="r" values="{s["r"]};{round(s["r"]*0.82,2)};{s["r"]}" '
            f'dur="{dur}s" begin="{delay}s" repeatCount="indefinite"/>'
            f'</circle>'
        )

    # ── Label ──────────────────────────────────────────────────────────────────
    parts.append(
        f'  <text x="{W//2}" y="{H - 10}" text-anchor="middle" '
        f'font-family="monospace" font-size="10" fill="#A0AAB4" opacity="0.45">'
        f'✦ {total_contributions:,} contributions this year ✦</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">\n'
        + "\n".join(parts)
        + "\n</svg>\n"
    )
    return svg


def main():
    print(f"Fetching contributions for @{USERNAME}...")
    days, total = fetch_contributions()
    print(f"  → {total} total contributions across {len(days)} days")

    stars = map_stars(days)
    lines = build_constellation_lines(stars)
    print(f"  → {len([s for s in stars if s['count'] > 0])} active stars, {len(lines)} constellation lines")

    svg = render_svg(stars, lines, total)

    out_path = os.path.join(os.path.dirname(__file__), "..", "constellation.svg")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"  → Written to constellation.svg ✓")


if __name__ == "__main__":
    main()
