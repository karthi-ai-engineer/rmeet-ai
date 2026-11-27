"""Step 3 in a real browser: Thirdwave's world (history, names, files, privacy). The day is pinned to Fri 27 Nov 2026."""

import httpx
from playwright.sync_api import expect

from tests.e2e.conftest import messages, open_as


def test_history_with_full_names_and_sliding_dates(browser, sim):
    page = open_as(browser, sim, "prince", "channel=pp-models")
    kickoff = messages(page, "prince").filter(has_text="Kick-off for the Raptor X9")
    expect(kickoff).to_contain_text("launch on Fri 8 Jan")
    expect(page.get_by_text("Kenji Mori").first).to_be_visible()
    expect(messages(page).filter(has_text="moves from Fri 8 Jan to Fri 15 Jan")).to_be_visible()
    page.close()


def test_files_tab_with_versions(browser, sim):
    page = open_as(browser, sim, "praga", "channel=pr-suppliers&tab=files")
    row = page.locator('[data-testid="file-row"][data-file-name="Parts prices.xlsx"]')
    expect(row).to_contain_text("v2")
    row.click()
    expect(page.get_by_test_id("file-preview")).to_be_visible()
    expect(page.locator('[data-testid="file-version"]')).to_have_count(2)
    page.close()


def test_private_world_stays_private(browser, sim):
    page = open_as(browser, sim, "rachitaa", "channel=pp-pricing")
    expect(page.locator('[data-channel-id="pp-pricing"]')).to_have_count(1)
    expect(page.locator('[data-channel-id="pp-budget"]')).to_have_count(0)
    page.close()
    assert httpx.get(f"{sim}/api/files/gpu-budget", params={"as": "rachitaa"}).status_code == 403
    assert httpx.get(f"{sim}/api/files/gpu-budget", params={"as": "prince"}).status_code == 200


def test_reset_brings_the_same_world_back(browser, sim):
    before = httpx.get(f"{sim}/api/channels/pp-models/threads", params={"as": "prince"}).json()
    httpx.post(f"{sim}/api/messages", json={"as": "prince", "kind": "channel", "where": "pp-models", "text": "temp"})
    httpx.post(f"{sim}/api/reset", json={})
    assert httpx.get(f"{sim}/api/channels/pp-models/threads", params={"as": "prince"}).json() == before
