import streamlit as st

st.set_page_config(page_title="Chat2SQL", layout="wide")

st.title("💬 Chat2SQL")

# Session state to store messages
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! How can I help you?"}
    ]

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input box (ChatGPT style)
if prompt := st.chat_input("Type your message..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Call local FastAPI endpoint instead of echo
    import httpx

    try:
        with httpx.Client(timeout=900.0) as client:
            res = client.post(
                "http://127.0.0.1:8000/v1/query/text/",
                json={"query": prompt},
                headers={"Content-Type": "application/json"},
            )
            res.raise_for_status()
            response = res.text

            # If response is JSON object, try to take generated_text or body
            try:
                parsed = res.json()
                if isinstance(parsed, dict) and "generated_text" in parsed:
                    response = parsed["generated_text"]
                elif isinstance(parsed, str):
                    response = parsed
            except Exception:
                pass
    except Exception as err:
        response = f"Error calling backend: {err}"

    # Add assistant response
    st.session_state.messages.append({"role": "assistant", "content": response})

    with st.chat_message("assistant"):
        st.markdown(response)
