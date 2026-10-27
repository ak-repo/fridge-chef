"""Browser regressions. See docs/WORKFLOW.md for the optional browser setup."""

from pathlib import Path
from time import monotonic

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
OPTIONS = {"diets": ["No restriction", "Vegan"], "cuisines": ["Any", "Indian (any)"]}


@pytest.fixture
def page():
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page()

        def serve(route):
            path = route.request.url.split("http://fridge.test", 1)[1]
            files = {"/": ("static/index.html", "text/html"),
                     "/static/app.js": ("static/app.js", "text/javascript"),
                     "/static/style.css": ("static/style.css", "text/css")}
            if path in files:
                file, mime = files[path]
                route.fulfill(body=(ROOT / file).read_text(), content_type=mime)
            else:
                route.abort()

        page.route("http://fridge.test/**", serve)
        yield page
        browser.close()


def wait_for_route(page, routes):
    deadline = monotonic() + 5
    while not routes and monotonic() < deadline:
        page.wait_for_timeout(10)
    assert routes, "Expected intercepted request"


def ready(page):
    page.route("**/api/options", lambda route: route.fulfill(json=OPTIONS))
    page.goto("http://fridge.test/")
    playwright.expect(page.locator("#suggest-btn")).to_be_enabled()


def add_files(page, count):
    page.evaluate("""(count) => addPhotos(Array.from({length: count}, (_, i) =>
        new File(['photo'], `photo-${i}.png`, {type: 'image/png'})))""", count)


def test_overlapping_photo_additions_are_serialized(page):
    ready(page)
    page.evaluate("""() => {
        window.releaseImages = [];
        window.createImageBitmap = () => new Promise((resolve, reject) => releaseImages.push(reject));
        const file = () => new File(['photo'], 'photo.png', {type: 'image/png'});
        window.batches = Promise.all([addPhotos([file(), file(), file()]), addPhotos([file(), file(), file()])]);
    }""")
    playwright.expect(page.locator("#detect-btn")).to_be_disabled()
    for index in range(4):
        page.wait_for_function("n => releaseImages.length > n", arg=index)
        page.evaluate("n => releaseImages[n](new Error('use original'))", index)
    page.evaluate("() => batches")
    assert page.locator("#previews .thumb").count() == 4
    playwright.expect(page.locator("#detect-btn")).to_be_enabled()


@pytest.mark.parametrize("success", [True, False])
def test_detection_stays_locked_during_preview_changes(page, success):
    ready(page)
    add_files(page, 2)
    held = []
    page.route("**/api/detect", lambda route: held.append(route))
    page.locator("#detect-btn").click()
    page.wait_for_function("() => detecting")
    page.locator("#previews button").first.click()
    add_files(page, 1)
    playwright.expect(page.locator("#detect-btn")).to_be_disabled()
    page.locator("#detect-btn").dispatch_event("click")
    wait_for_route(page, held)
    assert len(held) == 1
    if success:
        held[0].fulfill(json={"ingredients": ["tomato"]})
    else:
        held[0].fulfill(status=502, json={"detail": "Try again"})
    playwright.expect(page.locator("#detect-btn")).to_be_enabled()
    if success:
        playwright.expect(page.locator("#ingredients")).to_have_value("tomato")
    else:
        playwright.expect(page.locator("#detect-status")).to_have_text("Try again")


def test_options_failure_retry_and_recipe_request_state(page):
    held = []
    requests = []
    page.route("**/api/options", lambda route: held.append(route))
    page.route("**/api/recipes", lambda route: requests.append(route))
    page.goto("http://fridge.test/")
    playwright.expect(page.locator("#suggest-btn")).to_be_disabled()
    page.locator("#ingredients").fill("tomato")
    page.locator("#suggest-btn").dispatch_event("click")
    assert not requests
    wait_for_route(page, held)
    held.pop().fulfill(status=503, json={"detail": "Offline"})
    playwright.expect(page.locator("#retry-options-btn")).to_be_visible()
    playwright.expect(page.locator("#suggest-btn")).to_be_disabled()
    page.locator("#retry-options-btn").click()
    page.wait_for_function("() => optionsLoading")
    playwright.expect(page.locator("#retry-options-btn")).to_be_disabled()
    wait_for_route(page, held)
    held.pop().fulfill(json=OPTIONS)
    playwright.expect(page.locator("#suggest-btn")).to_be_enabled()
    playwright.expect(page.locator("#retry-options-btn")).to_be_hidden()
    page.locator("#suggest-btn").click()
    page.wait_for_function("() => suggesting")
    page.locator("#suggest-btn").dispatch_event("click")
    wait_for_route(page, requests)
    assert len(requests) == 1
    assert requests[0].request.post_data_json["diet"] == "No restriction"
    page.evaluate("() => { void loadOptions(); }")
    wait_for_route(page, held)
    held.pop().fulfill(json=OPTIONS)
    page.wait_for_function("() => !optionsLoading")
    playwright.expect(page.locator("#suggest-btn")).to_be_disabled()
    requests[0].fulfill(status=502, json={"detail": "Try again"})
    playwright.expect(page.locator("#suggest-btn")).to_be_enabled()
