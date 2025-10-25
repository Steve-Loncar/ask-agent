# streamlit_app.py
import os
import streamlit as st
import requests
from datetime import datetime

# Config via environment variables (set these in Streamlit Secrets)
N8N_WEBHOOK = os.environ.get("N8N_WEBHOOK", "")
SHARED_SECRET = os.environ.get("N8N_SHARED_SECRET", "")

st.set_page_config(page_title="Ask Agent", layout="centered")

st.title("Ask the Perplexity Agent")
st.write("Type a question, press Ask — the app forwards to your n8n webhook and shows the answer + sources.")

if not N8N_WEBHOOK:
    st.error("N8N_WEBHOOK environment variable is not set. Set it in Streamlit secrets (see README).")
    st.stop()

# Input area
question = st.text_area("Question", value="What is the capital of France?", height=120)
col1, col2 = st.columns([1, 1])
with col1:
    max_tokens = st.number_input("Max tokens", min_value=50, max_value=2000, value=500, step=50)
with col2:
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.05)

if st.button("Ask"):
    if not question.strip():
        st.warning("Please type a question.")
    else:
        payload = {
            "question": question,
            # optional secret to help block public use of the webhook
            "secret": SHARED_SECRET,
            # optional client-side hints for your workflow
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        st.info("Sending question to agent…")
        with st.spinner("Waiting for response from n8n / Perplexity…"):
            try:
                resp = requests.post(N8N_WEBHOOK, json=payload, timeout=60)
            except requests.exceptions.RequestException as e:
                st.error(f"Request failed: {e}")
            else:
                # try parse JSON, fallback to showing raw text
                try:
                    data = resp.json()
                except ValueError:
                    st.error(f"Non-JSON response (HTTP {resp.status_code})")
                    st.code(resp.text)
                else:
                    # Basic status handling
                    if resp.status_code >= 400:
                        st.error(f"n8n returned HTTP {resp.status_code}")
                        st.json(data)
                    else:
                        # Expected shape: { "answer": "...", "sources": [...] }
                        answer = data.get("answer") or data.get("perplexity_raw") or ""
                        sources = data.get("sources") or data.get("search_results") or []

                        # Render answer
                        st.subheader("Answer")
                        st.write(answer)

                        # Optional: show raw response for debugging
                        with st.expander("Raw response JSON"):
                            st.json(data)

                        # Render sources if present
                        if isinstance(sources, list) and sources:
                            st.subheader("Sources")
                            for s in sources:
                                title = s.get("title") or s.get("url") or "source"
                                url = s.get("url") or ""
                                snippet = s.get("snippet") or s.get("summary") or ""
                                if url:
                                    st.markdown(f"- [{title}]({url})  ")
                                else:
                                    st.markdown(f"- {title}  ")
                                if snippet:
                                    st.caption(snippet)
                        else:
                            st.caption("No sources returned.")

                        # Small tools
                        st.download_button("Download full JSON", data=resp.text, file_name="response.json", mime="application/json")