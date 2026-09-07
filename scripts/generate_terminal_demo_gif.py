#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/generate_terminal_demo_gif.py
Generates a crisp, developer-style animated GIF simulating the real-time execution
of the RAVEN BOT X engine (ingest -> parse -> dispatch -> telemetry).
"""

import os
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_GIF = os.path.join(BASE_DIR, "docs", "assets", "terminal-demo.gif")

WIDTH = 900
HEIGHT = 400
BG_COLOR = (13, 17, 23)        # #0d1117
TITLE_BG = (22, 27, 34)        # #161b22
BORDER_COLOR = (48, 54, 61)    # #30363d
CARD_BG = (22, 27, 34)

FONT_REG_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

font_reg = ImageFont.truetype(FONT_REG_PATH, 13)
font_bold = ImageFont.truetype(FONT_BOLD_PATH, 13)
font_title = ImageFont.truetype(FONT_BOLD_PATH, 12)
font_telemetry = ImageFont.truetype(FONT_BOLD_PATH, 12)

# Colors
C_PROMPT = (121, 192, 255)     # #79c0ff
C_TEXT = (240, 246, 252)       # #f0f6fc
C_MUTED = (139, 148, 158)      # #8b949e
C_GREEN = (63, 185, 80)        # #3fb950
C_BLUE = (88, 166, 255)        # #58a6ff
C_YELLOW = (210, 153, 34)      # #d29922
C_PURPLE = (188, 140, 255)     # #bc8cff
C_ORANGE = (255, 166, 87)      # #ffa657
C_BORDER_EMERALD = (35, 134, 54)

def draw_window_frame(draw):
    # Background
    draw.rounded_rectangle([(0, 0), (WIDTH - 1, HEIGHT - 1)], radius=10, fill=BG_COLOR, outline=BORDER_COLOR, width=1)
    # Title bar
    draw.rectangle([(1, 1), (WIDTH - 2, 36)], fill=TITLE_BG)
    draw.line([(1, 36), (WIDTH - 2, 36)], fill=BORDER_COLOR, width=1)

    # Traffic light window buttons
    draw.ellipse([(16, 12), (28, 24)], fill=(255, 95, 86))
    draw.ellipse([(34, 12), (46, 24)], fill=(255, 189, 46))
    draw.ellipse([(52, 12), (64, 24)], fill=(39, 201, 63))

    # Window title
    title = "bash — raven-telecom-engine (live stream & OTP pipeline)"
    bbox = font_title.getbbox(title)
    tw = bbox[2] - bbox[0]
    draw.text(((WIDTH - tw) // 2, 12), title, font=font_title, fill=C_MUTED)

def create_frame(step, cursor_on=True):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_window_frame(draw)

    y = 62
    line_h = 32

    # Line 1: Shell prompt
    if step >= 1:
        draw.text((24, y), "obs@server:~/ivasms-bot$ ", font=font_bold, fill=C_PROMPT)
        # Typewriter effect on line 1
        cmd = "python3 main.py --stream --production"
        draw.text((24 + 195, y), cmd, font=font_reg, fill=C_TEXT)

    # Line 2: System init
    if step >= 2:
        y += line_h
        draw.text((24, y), "[2026-09-07 19:29:40]", font=font_reg, fill=C_MUTED)
        draw.text((200, y), "[System]", font=font_bold, fill=C_GREEN)
        draw.text((275, y), "SQLite session pool initialized. (0.002s)", font=font_reg, fill=(201, 209, 217))

    # Line 3: Network auth
    if step >= 3:
        y += line_h
        draw.text((24, y), "[2026-09-07 19:29:41]", font=font_reg, fill=C_MUTED)
        draw.text((200, y), "[Network]", font=font_bold, fill=C_BLUE)
        draw.text((285, y), "iVasms session authenticated. Rotating fingerprint pool active.", font=font_reg, fill=(201, 209, 217))

    # Line 4: Stream polling
    if step >= 4:
        y += line_h
        draw.text((24, y), "[2026-09-07 19:29:42]", font=font_reg, fill=C_MUTED)
        draw.text((200, y), "[Stream]", font=font_bold, fill=C_YELLOW)
        draw.text((275, y), "Polling live telecom traffic stream across 140+ countries [POLL OK]", font=font_reg, fill=(201, 209, 217))

    # Line 5: Inbound SMS
    if step >= 5:
        y += line_h
        draw.text((24, y), "[2026-09-07 19:29:43]", font=font_reg, fill=C_MUTED)
        draw.text((200, y), "[Inbound]", font=font_bold, fill=C_PURPLE)
        draw.text((285, y), 'SMS #9024: +201001234567 | "Your WhatsApp code is 482-910."', font=font_bold, fill=(230, 237, 243))

    # Line 6: Extracted OTP & Parser
    if step >= 6:
        y += line_h
        draw.text((24, y), "[2026-09-07 19:29:43]", font=font_reg, fill=C_MUTED)
        draw.text((200, y), "[Parser]", font=font_bold, fill=C_GREEN)
        draw.text((275, y), "SERVICE: WhatsApp", font=font_bold, fill=(126, 231, 135))
        draw.text((435, y), "| OTP: [", font=font_reg, fill=C_TEXT)
        draw.text((495, y), "482910", font=font_bold, fill=C_ORANGE)
        draw.text((555, y), "] | EG (+20) | Latency: ", font=font_reg, fill=C_TEXT)
        draw.text((740, y), "4.96 µs", font=font_bold, fill=C_BLUE)

    # Line 7: Telegram Dispatch
    if step >= 7:
        y += line_h
        draw.text((24, y), "[2026-09-07 19:29:43]", font=font_reg, fill=C_MUTED)
        draw.text((200, y), "[Dispatch]", font=font_bold, fill=(56, 139, 253))
        draw.text((290, y), "Broadcasted to @Raven_xx24 & Subscribers [HTTP 200 OK]", font=font_reg, fill=(201, 209, 217))

    # Line 8: Telemetry banner
    if step >= 8:
        y += line_h + 4
        draw.rounded_rectangle([(24, y), (WIDTH - 24, y + 28)], radius=4, fill=CARD_BG, outline=C_BORDER_EMERALD, width=1)
        draw.text((36, y + 6), "TELEMETRY:", font=font_telemetry, fill=C_GREEN)
        msg = "Throughput: 181,450 ops/s | p95: 7.70 µs | Queue: 0 dropped | CPU: 1.8%"
        draw.text((135, y + 6), msg, font=font_reg, fill=(201, 209, 217))

    # Next prompt cursor
    if step >= 8:
        y += line_h + 8
        draw.text((24, y), "obs@server:~/ivasms-bot$ ", font=font_bold, fill=C_PROMPT)
        if cursor_on:
            draw.rectangle([(24 + 195, y), (24 + 203, y + 14)], fill=C_TEXT)

    return img

def main():
    print("Generating frames for terminal-demo.gif...")
    frames = []
    durations = []

    # Step 1: initial shell command
    frames.append(create_frame(1, cursor_on=True))
    durations.append(900)

    # Steps 2 to 7
    for s in range(2, 8):
        frames.append(create_frame(s, cursor_on=False))
        durations.append(700)

    # Step 8: completed with telemetry banner
    for _ in range(3):
        frames.append(create_frame(8, cursor_on=True))
        durations.append(500)
        frames.append(create_frame(8, cursor_on=False))
        durations.append(500)

    # Final hold before loop
    frames.append(create_frame(8, cursor_on=True))
    durations.append(2500)

    # Save animated GIF
    frames[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True
    )
    print(f"[+] Saved animated GIF: {OUTPUT_GIF} ({os.path.getsize(OUTPUT_GIF) / 1024:.1f} KB)")

if __name__ == "__main__":
    main()
