"""Optional Streamlit interface (alternative to the HTML app).

Install extra dependency:  pip install streamlit
Run with:                  streamlit run streamlit_app.py
"""

import os

import streamlit as st
from anthropic import APIError
from dotenv import load_dotenv

from fridge_chef import core

load_dotenv()


def show_recipe(recipe: dict) -> None:
    meta = f"{recipe.get('time_minutes') or '?'} min  |  {recipe.get('difficulty', '')}"
    with st.expander(f"{recipe['title']}  ({meta})", expanded=True):
        if recipe["uses"]:
            st.markdown("**You have:** " + ", ".join(recipe["uses"]))
        if recipe["missing"]:
            st.markdown("**You're missing:** " + ", ".join(recipe["missing"]))
        else:
            st.success("You have everything you need!")
        if recipe["substitutions"]:
            st.markdown("**Substitutions**")
            for s in recipe["substitutions"]:
                st.markdown(f"- **{s['missing']}** -> {s['substitute']}  \n  _{s['note']}_")
        st.markdown("**Steps**")
        for i, step in enumerate(recipe["steps"], start=1):
            st.markdown(f"{i}. {step}")


st.set_page_config(page_title="Fridge Chef", page_icon="🍳")
st.title("🍳 Fridge Chef")
st.caption("Upload a photo of your fridge or type what you have. Get recipes and substitutions.")

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Ollama API key", type="password", value=os.getenv("OLLAMA_API_KEY", ""))
    diet = st.selectbox("Diet", core.DIETS)
    cuisine = st.selectbox("Cuisine", core.CUISINES)
    max_minutes = st.slider("Max cooking time (minutes)", 10, 90, 30, step=5)
    servings = st.number_input("Servings", min_value=1, max_value=10, value=2)
    count = st.slider("Number of recipes", 1, 5, 3)

if not api_key:
    st.info("Add your Ollama API key in the sidebar to begin.")
    st.stop()

client = core.make_client(api_key)

if "ingredients" not in st.session_state:
    st.session_state["ingredients"] = ""

photos = st.file_uploader(
    "Photo(s) of your fridge or pantry (optional)",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
)
if photos:
    st.image([p.getvalue() for p in photos], width=160)
    if st.button("Detect ingredients from photo(s)"):
        with st.spinner("Looking at your photos..."):
            try:
                found = core.detect_ingredients(client, [(p.getvalue(), p.type or "image/jpeg") for p in photos])
                existing = [x.strip() for x in st.session_state["ingredients"].split(",") if x.strip()]
                known = {e.lower() for e in existing}
                st.session_state["ingredients"] = ", ".join(existing + [i for i in found if i.lower() not in known])
            except (APIError, ValueError) as err:
                st.error(f"Couldn't read the photos: {err}")

st.text_area(
    "Your ingredients (comma separated)",
    key="ingredients",
    placeholder="e.g. eggs, tomato, onion, curry leaves, rice, paneer",
)

if st.button("Suggest recipes", type="primary"):
    items = st.session_state["ingredients"].strip()
    if not items:
        st.warning("Add some ingredients first, by photo or by typing.")
    else:
        with st.spinner("Cooking up ideas..."):
            try:
                for recipe in core.suggest_recipes(client, items, diet, cuisine, max_minutes, servings, count):
                    show_recipe(recipe)
            except (APIError, ValueError) as err:
                st.error(f"Something went wrong: {err}")
