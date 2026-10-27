// Fridge Chef: browser interface. Plain JavaScript, no build step.
// All model output is inserted with textContent (never innerHTML), so it can't inject markup.

const MAX_PHOTOS = 4;
const MAX_DIMENSION = 1280; // photos are shrunk in the browser before upload

const $ = (id) => document.getElementById(id);
const photoInput = $("photo-input");
const dropzone = $("dropzone");
const previews = $("previews");
const detectBtn = $("detect-btn");
const detectStatus = $("detect-status");
const ingredientsBox = $("ingredients");
const suggestBtn = $("suggest-btn");
const suggestStatus = $("suggest-status");
const results = $("results");

// Tabs are enabled only when the panels cannot fit side by side.
const compactLayout = matchMedia("(max-width: 1099px)");
const panelNames = ["ingredients", "preferences", "recipes"];
let activePanel = "ingredients";

function showPanel(name, focusTab = false) {
  activePanel = name;
  $("panel-tabs").hidden = !compactLayout.matches;
  for (const item of panelNames) {
    const panel = $(`${item}-panel`);
    const tab = $(`tab-${item}`);
    const selected = item === name;
    panel.hidden = compactLayout.matches && !selected;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (compactLayout.matches) {
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-labelledby", tab.id);
    } else {
      panel.removeAttribute("role");
      panel.setAttribute("aria-labelledby", item === "ingredients" ? "workspace-title" : item === "preferences" ? "preferences-title" : "results-title");
    }
  }
  if (focusTab) $(`tab-${name}`).focus();
}

for (const [index, name] of panelNames.entries()) {
  const tab = $(`tab-${name}`);
  tab.addEventListener("click", () => showPanel(name));
  tab.addEventListener("keydown", (event) => {
    let next;
    if (event.key === "ArrowRight") next = (index + 1) % panelNames.length;
    if (event.key === "ArrowLeft") next = (index + panelNames.length - 1) % panelNames.length;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = panelNames.length - 1;
    if (next !== undefined) {
      event.preventDefault();
      showPanel(panelNames[next], true);
    }
  });
}
compactLayout.addEventListener("change", () => {
  const focusedPanel = document.activeElement?.closest(".app-panel");
  if (focusedPanel) activePanel = focusedPanel.id.replace("-panel", "");
  showPanel(activePanel);
  // Keep keyboard focus visible when desktop tabs disappear.
  if (!compactLayout.matches && document.activeElement?.getAttribute("role") === "tab") {
    $(activePanel === "ingredients" ? "dropzone" : activePanel === "preferences" ? "diet" : "results-title").focus();
  }
});
showPanel(activePanel);

/** @type {{blob: Blob, name: string, url: string}[]} */
let photos = [];
let photoQueue = Promise.resolve();
let pendingPhotoBatches = 0;
let detecting = false;
let optionsReady = false;
let optionsLoading = false;
let suggesting = false;
const retryOptionsBtn = $("retry-options-btn");

function updateButtons() {
  detectBtn.disabled = photos.length === 0 || pendingPhotoBatches > 0 || detecting;
  suggestBtn.disabled = !optionsReady || optionsLoading || suggesting;
  retryOptionsBtn.disabled = optionsLoading;
  detectBtn.textContent = detecting ? "Detecting ingredients…" : pendingPhotoBatches ? "Preparing photos…" : "Detect ingredients";
  suggestBtn.textContent = suggesting ? "Finding recipes…" : optionsLoading ? "Loading preferences…" : "Find recipes";
  $("diet").disabled = $("cuisine").disabled = !optionsReady;
  $("photo-count").textContent = `${photos.length} / ${MAX_PHOTOS} photos`;
  results.setAttribute("aria-busy", String(suggesting));
}

// ------------------------------------------------------------- helpers
function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child) node.append(child);
  }
  return node;
}

function setStatus(node, message, kind = "") {
  node.textContent = message;
  node.className = "status" + (kind ? " " + kind : "");
}

async function api(path, options) {
  const res = await fetch(path, options);
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* non-JSON error body */
  }
  if (!res.ok) {
    let detail = data && data.detail;
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg).join(" ");
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return data;
}

// -------------------------------------------------------------- photos
async function shrinkImage(file) {
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_DIMENSION / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
    return blob || file;
  } catch (_) {
    return file; // fall back to the original if the browser can't decode it
  }
}

function addPhotos(fileList) {
  const files = Array.from(fileList).filter((f) => f.type.startsWith("image/"));
  pendingPhotoBatches += 1;
  updateButtons();
  photoQueue = photoQueue.then(async () => {
    for (const file of files) {
      if (photos.length >= MAX_PHOTOS) {
        setStatus(detectStatus, `You can add up to ${MAX_PHOTOS} photos.`, "error");
        break;
      }
      const blob = await shrinkImage(file);
      photos.push({ blob, name: file.name, url: URL.createObjectURL(blob) });
    }
  }).catch((err) => {
    setStatus(detectStatus, `Couldn't add photos: ${err.message}`, "error");
  }).finally(() => {
    pendingPhotoBatches -= 1;
    renderPreviews();
  });
  return photoQueue;
}

function renderPreviews() {
  previews.replaceChildren();
  photos.forEach((photo, index) => {
    const remove = el("button", { type: "button", "aria-label": `Remove photo ${index + 1}: ${photo.name}`, text: "×" });
    remove.addEventListener("click", () => {
      URL.revokeObjectURL(photo.url);
      photos.splice(index, 1);
      renderPreviews();
    });
    previews.append(el("div", { class: "thumb" }, [el("img", { src: photo.url, alt: `Selected photo ${index + 1}: ${photo.name}` }), remove]));
  });
  updateButtons();
}

dropzone.addEventListener("click", () => photoInput.click());

photoInput.addEventListener("change", async () => {
  setStatus(detectStatus, "");
  const files = Array.from(photoInput.files);
  photoInput.value = "";
  await addPhotos(files);
});

["dragenter", "dragover"].forEach((type) =>
  dropzone.addEventListener(type, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((type) =>
  dropzone.addEventListener(type, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => addPhotos(e.dataTransfer.files));

detectBtn.addEventListener("click", async () => {
  if (detecting || pendingPhotoBatches > 0 || photos.length === 0) return;
  const body = new FormData();
  photos.forEach((p, i) => body.append("files", p.blob, p.name || `photo-${i}.jpg`));

  detecting = true;
  updateButtons();
  setStatus(detectStatus, "Looking at your photos...", "busy");
  try {
    const { ingredients } = await api("/api/detect", { method: "POST", body });
    mergeIngredients(ingredients);
    setStatus(
      detectStatus,
      ingredients.length
        ? `Found ${ingredients.length} ingredient${ingredients.length === 1 ? "" : "s"}. Check the list below.`
        : "Couldn't spot any ingredients. Try a clearer photo or type them in."
    );
  } catch (err) {
    setStatus(detectStatus, err.message, "error");
  } finally {
    detecting = false;
    updateButtons();
  }
});

function mergeIngredients(found) {
  const existing = ingredientsBox.value.split(",").map((s) => s.trim()).filter(Boolean);
  const known = new Set(existing.map((s) => s.toLowerCase()));
  for (const item of found) {
    if (!known.has(item.toLowerCase())) {
      existing.push(item);
      known.add(item.toLowerCase());
    }
  }
  ingredientsBox.value = existing.join(", ");
}

// ------------------------------------------------------------- recipes
function renderRecipe(recipe) {
  const meta = el("div", { class: "meta" }, [
    recipe.time_minutes ? el("span", { class: "badge", text: `${recipe.time_minutes} min` }) : null,
    recipe.difficulty ? el("span", { class: "badge", text: recipe.difficulty }) : null,
  ]);

  const card = el("article", { class: "card recipe" }, [el("h3", { text: recipe.title }), meta]);

  if (recipe.uses.length) {
    card.append(el("h4", { text: "You have" }));
    card.append(el("div", { class: "chips" }, recipe.uses.map((t) => el("span", { class: "chip have", text: t }))));
  }

  if (recipe.missing.length) {
    card.append(el("h4", { text: "You're missing" }));
    card.append(el("div", { class: "chips" }, recipe.missing.map((t) => el("span", { class: "chip missing", text: t }))));
  } else {
    card.append(el("p", { class: "all-set", text: "You have everything you need!" }));
  }

  if (recipe.substitutions.length) {
    card.append(el("h4", { text: "Substitutions" }));
    card.append(
      el(
        "ul",
        { class: "subs" },
        recipe.substitutions.map((s) =>
          el("li", {}, [
            el("strong", { text: s.missing }),
            document.createTextNode(` → ${s.substitute}`),
            s.note ? el("span", { class: "note", text: s.note }) : null,
          ])
        )
      )
    );
  }

  if (recipe.steps.length) {
    card.append(el("h4", { text: "Steps" }));
    card.append(el("ol", {}, recipe.steps.map((step) => el("li", { text: step }))));
  }
  return card;
}

suggestBtn.addEventListener("click", async () => {
  if (!optionsReady || optionsLoading || suggesting) return;
  const ingredients = ingredientsBox.value.trim();
  if (!ingredients) {
    setStatus(suggestStatus, "Add some ingredients first, by photo or by typing.", "error");
    showPanel("ingredients");
    ingredientsBox.focus();
    return;
  }

  for (const id of ["max-minutes", "servings", "count"]) {
    if (!$(id).reportValidity()) {
      $(id).focus();
      return;
    }
  }

  const payload = {
    ingredients,
    diet: $("diet").value,
    cuisine: $("cuisine").value,
    max_minutes: Number($("max-minutes").value),
    servings: Number($("servings").value),
    count: Number($("count").value),
  };

  suggesting = true;
  updateButtons();
  $("recipe-count").textContent = "";
  results.replaceChildren(el("div", { class: "empty-state" }, [
    el("h3", { text: "Finding a little kitchen inspiration…" }),
    el("p", { text: "We’re matching your ingredients and preferences. This may take a moment." }),
  ]));
  setStatus(suggestStatus, "Cooking up ideas...", "busy");
  try {
    const { recipes } = await api("/api/recipes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    results.replaceChildren();
    $("recipe-count").textContent = `${recipes.length} recipe${recipes.length === 1 ? "" : "s"} for you`;
    recipes.forEach((r) => results.append(renderRecipe(r)));
    setStatus(suggestStatus, "");
    showPanel("recipes");
    results.scrollTop = 0;
    $("results-title").focus({ preventScroll: true });

  } catch (err) {
    results.replaceChildren(el("div", { class: "empty-state" }, [
      el("h3", { text: "Let’s give that another try." }),
      el("p", { text: "Your ingredients and preferences are still here. Choose Find recipes to retry." }),
    ]));
    setStatus(suggestStatus, err.message, "error");
  } finally {
    suggesting = false;
    updateButtons();
  }
});

// ------------------------------------------------------------- startup
async function loadOptions() {
  if (optionsLoading) return;
  optionsLoading = true;
  optionsReady = false;
  updateButtons();
  try {
    const { diets, cuisines } = await api("/api/options");
    if (![diets, cuisines].every((list) =>
      Array.isArray(list) && list.length > 0 && list.every((item) => typeof item === "string" && item.trim())
    )) throw new Error("Invalid options response");
    $("diet").replaceChildren(...diets.map((d) => el("option", { value: d, text: d })));
    $("cuisine").replaceChildren(...cuisines.map((c) => el("option", { value: c, text: c })));
    optionsReady = true;
    retryOptionsBtn.hidden = true;
    setStatus(suggestStatus, "");
  } catch (err) {
    retryOptionsBtn.hidden = false;
    setStatus(suggestStatus, "Couldn't load preferences. Check your connection and retry.", "error");
  } finally {
    optionsLoading = false;
    updateButtons();
  }
}

retryOptionsBtn.addEventListener("click", loadOptions);
loadOptions();
