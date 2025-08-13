import streamlit as st
import requests

# --- Custom CSS for styling ---
st.markdown("""
<style>
body {
    background-color: #0e1117;
    color: #e0e6f0;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
.sidebar .sidebar-content {
    background-color: #161b22;
    padding: 20px;
    border-radius: 10px;
}
.chat-message {
    padding: 12px 20px;
    border-radius: 15px;
    margin: 8px 0;
    max-width: 70%;
    font-size: 16px;
    line-height: 1.4;
    white-space: pre-wrap;
}
.user-message {
    background: #1f6feb;
    color: white;
    align-self: flex-end;
    margin-left: auto;
}
.ai-message {
    background: #2d2f33;
    color: #c5c6c7;
    align-self: flex-start;
    margin-right: auto;
}
.stTextInput>div>div>input {
    background-color: #161b22 !important;
    color: white !important;
    border-radius: 10px;
    padding: 12px;
    font-size: 16px;
}
.stButton>button {
    background-color: #1f6feb;
    color: white;
    border-radius: 10px;
    padding: 10px 20px;
    font-size: 16px;
    font-weight: bold;
}
.stButton>button:hover {
    background-color: #1558b0;
}
</style>
""", unsafe_allow_html=True)

st.title("EduMentor AI Assistant 🤖")
st.sidebar.title("Settings")

# Sidebar options (customize your backend URL here)
backend_url = st.sidebar.text_input("Backend URL", value="http://127.0.0.1:5000/get")

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    if msg["sender"] == "user":
        st.markdown(f'<div class="chat-message user-message">{msg["text"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-message ai-message">{msg["text"]}</div>', unsafe_allow_html=True)

# User input form
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message here:")
    submit = st.form_submit_button("Send")

if submit and user_input:
    # Append user message
    st.session_state.messages.append({"sender": "user", "text": user_input})

    # Call backend API
    try:
        response = requests.get(backend_url, params={"msg": user_input}, timeout=10)
        response.raise_for_status()
        data = response.json()
        ai_reply = data.get("answer") or data.get("response") or "Sorry, no answer returned."
    except Exception as e:
        ai_reply = f"Error contacting backend: {e}"

    # Append AI response
    st.session_state.messages.append({"sender": "ai", "text": ai_reply})

    # Refresh chat display
    st.experimental_rerun()
