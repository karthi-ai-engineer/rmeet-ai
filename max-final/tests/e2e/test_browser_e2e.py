"""
Step 2 in a real browser (Edge already on the PC, via Playwright): play several people in the simulated Teams,
talk to Max, see live updates, private channel rules.
"""

import pytest
from playwright.sync_api import Browser, Page, expect, sync_playwright

TIMEOUT = 15_000


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        yield b
        b.close()


def open_as(browser: Browser, sim: str, person: str, query: str) -> Page:
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.set_default_timeout(TIMEOUT)
    page.goto(f"{sim}/?as={person}&theme=light&{query}")
    return page


def messages(page: Page, author: str | None = None):
    sel = '[data-testid="msg"]' + (f'[data-author="{author}"]' if author else "")
    return page.locator(sel)


def test_mention_in_channel_max_replies_live_for_everyone(browser, sim):
    prince = open_as(browser, sim, "prince", "channel=pp-models")
    rachitaa = open_as(browser, sim, "rachitaa", "channel=pp-models")
    max_before = messages(rachitaa, "max").count()
    prince.get_by_test_id("post-box").fill("@Max are you there?")
    prince.get_by_test_id("post-send").click()
    expect(messages(prince, "prince").filter(has_text="@Max are you there?")).to_be_visible()
    expect(messages(rachitaa).filter(has_text="@Max are you there?")).to_be_visible()  # live in another window
    expect(messages(rachitaa, "max")).to_have_count(max_before + 1)
    expect(messages(rachitaa, "max").filter(has_text="Hi Prince, I'm Max. I'm connected 👋")).to_be_visible()
    prince.close(), rachitaa.close()


def test_chat_with_max(browser, sim):
    page = open_as(browser, sim, "praga", "view=chat&chat=max-praga")
    page.get_by_test_id("chat-box").fill("hello")
    page.get_by_test_id("chat-send").click()
    expect(messages(page, "max").filter(has_text="Hi Praga, I'm Max. I'm connected 👋")).to_be_visible()
    page.close()


def test_private_channel_hidden_from_others(browser, sim):
    prince = open_as(browser, sim, "prince", "channel=pp-pricing")
    rachitaa = open_as(browser, sim, "rachitaa", "channel=pp-pricing")
    expect(prince.locator('[data-channel-id="pp-budget"]')).to_have_count(1)
    expect(rachitaa.locator('[data-channel-id="pp-pricing"]')).to_have_count(1)
    expect(rachitaa.locator('[data-channel-id="pp-budget"]')).to_have_count(0)
    prince.close(), rachitaa.close()


def test_post_survives_reload_and_reset_clears_it(browser, sim):
    page = open_as(browser, sim, "karthi", "channel=pp-general")
    page.get_by_test_id("post-box").fill("Saved for real")
    page.get_by_test_id("post-send").click()
    saved = messages(page).filter(has_text="Saved for real")
    expect(saved).to_be_visible()
    page.reload()
    expect(saved).to_be_visible()
    page.get_by_test_id("reset-world").click()
    expect(saved).to_have_count(0)
    page.close()


def test_mention_in_group_chat(browser, sim):
    praga = open_as(browser, sim, "praga", "view=chat&chat=sync")
    praga.get_by_test_id("chat-box").fill("@Max are you in this chat too?")
    praga.get_by_test_id("chat-send").click()
    expect(messages(praga, "max").filter(has_text="Hi Praga, I'm Max. I'm connected 👋")).to_be_visible()
    praga.close()


def test_plain_hello_has_no_ai_label(browser, sim):
    """Teams shows "AI generated" and 👍/👎 only when the bot marks the message; the hello isn't AI-written."""
    page = open_as(browser, sim, "prince", "view=chat&chat=max-prince")
    page.get_by_test_id("chat-box").fill("hi")
    page.get_by_test_id("chat-send").click()
    reply = messages(page, "max").filter(has_text="Hi Prince")
    expect(reply).to_be_visible()
    expect(reply.get_by_text("AI generated")).to_have_count(0)
    expect(reply.get_by_label("Helpful")).to_have_count(0)
    page.close()
