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
            # HTTP headers must be ASCII/Latin-1; ntfy wants non-ASCII title
            # text RFC 2047-encoded rather than sent raw (emoji would crash
            # Python's http.client otherwise).
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

        # The ticket tiers aren't on the initial page load — they appear
        # after tapping a "Get tickets" / "Reserve" style button, same as
        # in the app. Try clicking anything that looks like that button.
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

        # If we still can't find the tier text, try scrolling to trigger
        # any lazy-loaded content, then re-check once more.
        if TARGET_TIER_TEXT not in content:
            try:
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(1500)
                content = page.content()
            except Exception:
                pass

        browser.close()

    # Find the ticket card containing "Opening Reception"
    idx = content.find(TARGET_TIER_TEXT)
    if idx == -1:
        return "not_found"

    # Look at a window of text after the tier name for "Sold out"
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
        # Page structure may have changed; alert so you can check manually.
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
