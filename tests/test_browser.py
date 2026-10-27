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


def test_validation_and_complete_recipe_rendering(page):
    ready(page)
    requests = []
    page.route("**/api/recipes", lambda route: requests.append(route))
    page.locator("#suggest-btn").click()
    playwright.expect(page.locator("#ingredients")).to_be_focused()
    page.locator("#ingredients").fill("tomato, rice")
    page.locator("#servings").fill("0")
    page.locator("#suggest-btn").click()
    playwright.expect(page.locator("#servings")).to_be_focused()
    assert not requests
    page.locator("#servings").fill("2")
    page.locator("#suggest-btn").click()
    wait_for_route(page, requests)
    playwright.expect(page.locator("#results")).to_have_attribute("aria-busy", "true")
    requests[0].fulfill(json={"recipes": [{
        "title": "Tomato rice <script>", "time_minutes": 25, "difficulty": "Easy",
        "uses": ["tomato", "rice"], "missing": ["butter"],
        "substitutions": [{"missing": "butter", "substitute": "oil", "note": "Use a little."}],
        "steps": ["Chop tomatoes.", "Cook with rice."],
    }]})
    playwright.expect(page.locator("#recipe-count")).to_have_text("1 recipe for you")
    playwright.expect(page.locator("#results-title")).to_be_focused()
    playwright.expect(page.locator("#results")).to_have_attribute("aria-busy", "false")
    playwright.expect(page.locator(".recipe h3")).to_have_text("Tomato rice <script>")
    assert page.locator("#results script").count() == 0
    assert page.locator(".recipe ol li").count() == 2
    playwright.expect(page.locator(".chip.missing")).to_have_text("butter")
    playwright.expect(page.locator(".subs")).to_contain_text("oil")
    playwright.expect(page.locator("#ingredients")).to_have_value("tomato, rice")


def test_keyboard_upload_and_photo_count(page):
    ready(page)
    page.locator("#dropzone").focus()
    with page.expect_file_chooser() as chooser:
        page.keyboard.press("Enter")
    chooser.value.set_files({"name": "pantry.png", "mimeType": "image/png", "buffer": b"photo"})
    playwright.expect(page.locator("#photo-count")).to_have_text("1 / 4 photos")
    page.get_by_role("button", name="Remove photo 1: pantry.png").click()
    playwright.expect(page.locator("#photo-count")).to_have_text("0 / 4 photos")
    playwright.expect(page.locator("#detect-btn")).to_be_disabled()


@pytest.mark.parametrize("color_scheme", ["light", "dark"])
def test_mobile_layout_and_reduced_motion(page, color_scheme):
    page.set_viewport_size({"width": 360, "height": 800})
    page.emulate_media(color_scheme=color_scheme, reduced_motion="reduce")
    ready(page)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("#dropzone").bounding_box()["height"] >= 44
    page.locator("#detect-status").evaluate("node => node.classList.add('busy')")
    assert page.locator("#detect-status").evaluate(
        "node => getComputedStyle(node, '::before').animationName") == "none"
    page.evaluate("document.documentElement.style.fontSize = '200%'")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize("width,height", [(1440, 900), (1366, 768), (360, 800), (800, 360)])
def test_fixed_shell_and_panel_overflow(page, width, height):
    page.set_viewport_size({"width": width, "height": height})
    ready(page)
    assert page.evaluate("document.documentElement.scrollHeight <= innerHeight")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("#suggest-btn").evaluate(
        "node => getComputedStyle(node).backgroundColor") == "rgb(9, 186, 210)"
    if width < 1100:
        page.get_by_role("tab", name="Recipes", exact=True).click()
    page.locator("#results").evaluate("""node => {
        const content = document.createElement('div');
        content.style.height = '3000px';
        content.textContent = 'Long recipe details';
        node.append(content);
        node.scrollTop = 500;
    }""")
    assert page.locator("#results").evaluate("node => node.scrollTop") > 0
    page.mouse.wheel(0, 500)
    assert page.evaluate("scrollY") == 0
    assert page.evaluate("document.documentElement.scrollHeight <= innerHeight")


def test_compact_tabs_validation_generation_and_resize(page):
    page.set_viewport_size({"width": 360, "height": 800})
    ready(page)
    playwright.expect(page.get_by_role("tabpanel", name="Ingredients", exact=True)).to_be_visible()
    page.locator("#ingredients").fill("tomato, rice")
    page.get_by_role("tab", name="Ingredients", exact=True).focus()
    page.keyboard.press("ArrowRight")
    playwright.expect(page.get_by_role("tab", name="Preferences", exact=True)).to_be_focused()
    page.locator("#servings").fill("0")
    page.locator("#suggest-btn").click()
    playwright.expect(page.locator("#servings")).to_be_focused()
    page.locator("#servings").fill("2")
    held = []
    page.route("**/api/recipes", lambda route: held.append(route))
    page.locator("#suggest-btn").click()
    wait_for_route(page, held)
    held.pop().fulfill(status=502, json={"detail": "Please retry"})
    playwright.expect(page.locator("#suggest-status")).to_have_text("Please retry")
    playwright.expect(page.locator("#servings")).to_have_value("2")
    page.locator("#suggest-btn").click()
    page.wait_for_function("() => suggesting")
    wait_for_route(page, held)
    assert len(held) == 1
    held[0].fulfill(json={"recipes": [{"title": "Rice", "uses": ["rice"],
        "missing": [], "substitutions": [], "steps": ["Cook rice."]}]})
    playwright.expect(page.get_by_role("tab", name="Recipes", exact=True)).to_have_attribute("aria-selected", "true")
    playwright.expect(page.locator("#results-title")).to_be_focused()
    page.set_viewport_size({"width": 1440, "height": 900})
    playwright.expect(page.locator("#panel-tabs")).to_be_hidden()
    playwright.expect(page.locator("#ingredients-panel")).to_be_visible()
    playwright.expect(page.locator("#preferences-panel")).to_be_visible()
    page.set_viewport_size({"width": 360, "height": 800})
    page.get_by_role("tab", name="Ingredients", exact=True).click()
    playwright.expect(page.locator("#ingredients")).to_have_value("tomato, rice")
    page.locator("#ingredients").fill("")
    page.get_by_role("tab", name="Preferences", exact=True).click()
    page.locator("#suggest-btn").click()
    playwright.expect(page.locator("#ingredients")).to_be_focused()
