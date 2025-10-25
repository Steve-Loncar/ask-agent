# streamlit_app.py
import os
import streamlit as st
import requests
from datetime import datetime

# Config via environment variables
N8N_WEBHOOK = os.environ.get("N8N_WEBHOOK", "")
SHARED_SECRET = os.environ.get("N8N_SHARED_SECRET", "")

st.set_page_config(page_title="Ask Agent", layout="centered")
st.title("Ask the Agent (Perplexity via n8n)")

st.markdown(
    "This app forwards your question to an n8n webhook which calls Perplexity. "
    "The app then displays a short answer plus a list of sources."
)

if not N8N_WEBHOOK:
    st.error("N8N_WEBHOOK is not set. Add it to Streamlit Secrets (see README).")
    st.stop()

# UI controls
question = st.text_area("Question", value="What is the capital of France?", height=140)
col1, col2 = st.columns([1, 1])
with col1:
    max_tokens = st.number_input("Max tokens", min_value=50, max_value=2000, value=500, step=50)
with col2:
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.05)

submit = st.button("Ask")

def safe_coerce_sources(raw):
    """
    Accept many shapes and return a list of source objects or strings.
    - If raw is a list: return as-is
    - If raw is a dict: return [raw]
    - If raw is a string: return [raw]
    - If None/other: return []
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return [raw]
    # fallback: strings or other scalars
    return [raw]

def render_source(s):
    """
    Return (title, url, snippet) for a source entry s that may be:
      - dict with keys title/url/snippet (or similar)
      - a plain string (likely a URL or short description)
    """
    try:
        if isinstance(s, dict):
            title = s.get("title") or s.get("name") or s.get("url") or s.get("snippet") or "source"
            url = s.get("url") or s.get("link") or ""
            snippet = s.get("snippet") or s.get("summary") or ""
        else:
            # s is probably a string (URL or title)
            text = str(s)
            if text.startswith("http://") or text.startswith("https://"):
                url = text
                title = text
                snippet = ""
            else:
                title = text
                url = ""
                snippet = ""
        return title, url, snippet
    except Exception:
        # Defensive fallback to avoid crashing the app UI
        return ("source", "", "")

if submit:
    if not question.strip():
        st.warning("Please type a question.")
    else:
        payload = {
            "question": question,
            "secret": SHARED_SECRET,
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        st.info("Sending question to n8n…")
        with st.spinner("Waiting for response…"):
            try:
                r = requests.post(N8N_WEBHOOK, json=payload, timeout=60)
            except requests.exceptions.RequestException as e:
                st.error(f"Request to n8n failed: {e}")
                r = None

            if r is None:
                st.stop()

            # Try parse JSON safely
            try:
                data = r.json()
            except ValueError:
                st.error(f"n8n returned non-JSON (HTTP {r.status_code})")
                st.code(r.text)
                st.stop()

            if r.status_code >= 400:
                st.error(f"n8n returned HTTP {r.status_code}")
                st.json(data)
                st.stop()

            # Extract usable fields with fallbacks
            answer = data.get("answer") or data.get("body", {}).get("answer") or ""
            raw_sources = data.get("sources") or data.get("search_results") or data.get("body", {}).get("search_results") or []

            # Coerce into list
            sources = safe_coerce_sources(raw_sources)

            # Render UI
            st.subheader("Answer")
            st.write(answer)

            if isinstance(sources, list) and sources:
                st.subheader("Sources")
                for s in sources:
                    title, url, snippet = render_source(s)
                    if url:
                        st.markdown(f"- [{title}]({url})")
                    else:
                        st.markdown(f"- {title}")
                    if snippet:
                        st.caption(snippet)
            else:
                st.caption("No sources returned.")

            # Optional: raw JSON download and expand for debugging
            st.download_button("Download full response (JSON)", data=r.text,
                               file_name="n8n_response.json", mime="application/json")
            with st.expander("Raw response JSON"):
                st.json(data)