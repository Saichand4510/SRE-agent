import uuid
import requests
import streamlit as st
import json
# =========================
# Config
# =========================
API_BASE = "https://sre-agent-wz1n.onrender.com"

# =========================== Utilities ===========================

def create_thread_api():
    r = requests.post(f"{API_BASE}/threads")
    r.raise_for_status()
    return r.json()["thread_id"]


def fetch_threads_api():
    r = requests.get(f"{API_BASE}/threads")
    r.raise_for_status()
    return r.json()["threads"]


def load_conversation_api(thread_id):
    r = requests.get(f"{API_BASE}/threads/{thread_id}")
    r.raise_for_status()
    return r.json()["messages"]


def stream_chat_api(thread_id, user_input):
    with requests.post(
        f"{API_BASE}/chat/stream",
        json={"thread_id": thread_id, "message": user_input},
        stream=True,
    ) as r:
        r.raise_for_status()

        for line in r.iter_lines(decode_unicode=True):
            if line:
                yield json.loads(line)


def reset_chat():
    thread_id = create_thread_api()
    st.session_state["thread_id"] = thread_id
    add_thread(thread_id)
    st.session_state["message_history"] = []


def add_thread(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)


# ======================= Session Initialization ===================

if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = create_thread_api()

if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = fetch_threads_api()

add_thread(st.session_state["thread_id"])

# ============================ Sidebar ============================

st.sidebar.title("LangGraph MCP Chatbot")

if st.sidebar.button("New Chat"):
    reset_chat()

st.sidebar.header("My Conversations")

for thread_id in st.session_state["chat_threads"][::-1]:
    if st.sidebar.button(str(thread_id)):
        st.session_state["thread_id"] = thread_id
        messages = load_conversation_api(thread_id)
        st.session_state["message_history"] = messages

# ============================ Main UI ============================

# Render history
for message in st.session_state["message_history"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("Type here")

# ============================ Chat ============================

if user_input:
    # Save user message
    st.session_state["message_history"].append(
        {"role": "user", "content": user_input}
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):

     status_holder = {"box": None}

     def stream_with_trace():

        for event in stream_chat_api(
            st.session_state["thread_id"], user_input
        ):

            # 🔧 Tool started
            if event["type"] == "tool_start":
                tool_name = event["name"]

                if status_holder["box"] is None:
                    status_holder["box"] = st.status(
                        f"🔧 Using `{tool_name}` …",
                        expanded=True
                    )
                else:
                    status_holder["box"].update(
                        label=f"🔧 Using `{tool_name}` …",
                        state="running",
                        expanded=True
                    )

            # ✅ Tool finished
            elif event["type"] == "tool_end":
                if status_holder["box"]:
                    status_holder["box"].update(
                        label="✅ Tool finished",
                        state="complete",
                        expanded=False
                    )

            # 🤖 Assistant token
            elif event["type"] == "assistant":
                yield event["content"]

     ai_message = st.write_stream(stream_with_trace())