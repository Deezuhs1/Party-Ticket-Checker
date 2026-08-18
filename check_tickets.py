#!/usr/bin/env python3
"""
Monitors the Shotgun 'Sela V Presents: Chapter 1' ticket page and sends a
free push notification to your phone the moment the "WE BEGIN (Opening
Reception)" tier stops showing "Sold out".

Notifications are sent via ntfy.sh (no account needed):
  1. Install the "ntfy" app (iOS App Store / Google Play), or just use
     https://ntfy.sh/<your-topic> in a browser.
  2. Pick a random, hard-to-guess topic name (e.g. "donw-sela-v-8f2k")
     and subscribe to it in the app.
  3. Set that same name as the NTFY_TOPIC value below (or as a GitHub
     Actions secret/variable — see the workflow file).

This script is read-only: it never attempts to purchase, log in, or
submit anything. It just checks the public page and alerts you so you
can grab the ticket yourself.
"""

import os
import re
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

EVENT_URL = "https://shotgun.live/en/events/chapter-1"
TARGET_TIER_TEXT = "Opening Reception"  # substring to find the right ticket card
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "REPLACE_ME_WITH_YOUR_TOPIC")


def send_notification(title: str, message: str) -> None:
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        headers={
            "Title": "=?UTF-8?B?" + __import__("base64").b64encode(title.encode("utf-8")).decode("ascii") + "?=",
            "Priority": "urgent",
            "Tags": "rotating_light",
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=15)


def check_reception_tier() -> str:
    """Returns 'sold_out', 'available', or 'not_found'."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(EVENT_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)

        clicked = False
        for pattern in [
            r"get tickets?", r"buy tickets?", r"reserve", r"tickets?",
        ]:
            try:
                locator = page.get_by_text(re.compile(pattern, re.IGNORECASE)).first
                if locator.is_visible(timeout=2000):
                    locator.click(timeout=3000)
                    clicked = True
                    break
            except Exception:
                continue

        if clicked:
            page.wait_for_timeout(2500)

        content = page.content()

        if TARGET_TIER_TEXT not in content:
            try:
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(1500)
                content = page.content()
            except Exception:
                pass

        # Always save a screenshot for debugging — lets us see exactly
        # what the automated browser is looking at.
        try:
            page.screenshot(path="debug_screenshot.png", full_page=True)
        except Exception:
            pass

        browser.close()

    idx = content.find(TARGET_TIER_TEXT)
    if idx == -1:
        return "not_found"

    window = content[idx: idx + 1500]
    if re.search(r"sold\s*out", window, re.IGNORECASE):
        return "sold_out"
    return "available"


def main() -> None:
    status = check_reception_tier()
    print(f"Status: {status}")

    if status == "available":
        send_notification(
            "🎟️ Reception ticket OPEN!",
            "Opening Reception tickets are no longer sold out — grab one now: "
            + EVENT_URL,
        )
        print("Notification sent.")
    elif status == "not_found":
        send_notification(
            "⚠️ Ticket checker needs a look",
            "Couldn't find the Opening Reception tier on the page — "
            "the site may have changed. Check manually: " + EVENT_URL,
        )
        print("Tier not found — sent a heads-up notification.")
    else:
        print("Still sold out, no notification sent.")


if __name__ == "__main__":
    main()
