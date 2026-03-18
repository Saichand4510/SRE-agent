import uuid
import requests
import streamlit as st
import json
# =========================
# Config
# =========================
API_BASE = "https://sre-agent-wz1n.onrender.com"

# 🔐 AUTH HELPERS (NEW)
# =========================

def get_headers():
    return {
        "Authorization": f"Bearer {st.session_state.token}"
    }
def handle_response(r):
    try:
        data = r.json()
       
    except:
        data = {}

    # 🔐 401 - Unauthorized
    if r.status_code == 401:
        msg = data.get("detail", "")

        if msg == "Token expired":
            st.warning("Session expired. Please login again.")
            st.session_state.token = None
            st.session_state.clear()
            st.rerun()
        else:
            st.warning("Authentication failed")

        

    # 🚫 403 - Forbidden
    elif r.status_code == 403:
        st.error(data.get("detail", "You are not allowed to perform this action"))
        

    # ❌ 400 - Bad Request
    elif r.status_code == 400:
        st.warning(data.get("detail", "Invalid request"))
    

    # 🔍 404 - Not Found
    elif r.status_code == 404:
        st.warning(data.get("detail", "Resource not found"))
        

    # 🚦 429 - Rate Limit
    elif r.status_code == 429:
        st.warning(data.get("detail","Too many requests. Please wait and try again."))
    elif r.status_code == 422:
        errors = data.get("detail", [])
       
        if errors and isinstance(errors, list):
           msg = errors[0].get("msg", "Invalid input")
        else:
            msg = "Invalid input"

        st.warning(msg)    

    # 🔥 500+ - Server Error
    elif r.status_code >= 500:
        st.error("Server error. Please try again later.")
    

    # ❓ Any other unexpected
    elif r.status_code != 200:
        st.error(data.get("detail", "Something went wrong"))
    
      
        

    return data
# =========================== Utilities ===========================

def create_thread_api():
    r = requests.post(f"{API_BASE}/threads",headers=get_headers())
    data = handle_response(r)
    if "detail" in data:
        return None

    return data["thread_id"]

    
    


def fetch_threads_api():
    r = requests.get(f"{API_BASE}/threads",headers=get_headers())
    data = handle_response(r)
    if "detail" in data:
        return []

    return data["threads"]


def load_conversation_api(thread_id):
    r = requests.get(f"{API_BASE}/threads/{thread_id}",headers=get_headers())
    data = handle_response(r)
    if "detail" in  data:
        return []

    return data["messages"]


def stream_chat_api(thread_id, user_input):
    try:
        with requests.post(
            f"{API_BASE}/chat/stream",
            headers=get_headers(),
            json={"thread_id": thread_id, "message": user_input},
            stream=True,
        ) as r:

            # 🔐 Handle HTTP errors BEFORE streaming
            if r.status_code != 200:
                handle_response(r)
                
                return

            for line in r.iter_lines(decode_unicode=True):
                if line:
                    yield json.loads(line)

    except Exception:
        st.error("Network error. Please try again.")

# =========================
# 🔐 LOGIN UI (NEW)
# =========================

if "token" not in st.session_state:
    st.session_state.token = None

if not st.session_state.token:

    st.title("SRE Chatbot")

    auth_mode = st.radio("Select Option", ["Login", "Sign Up"])

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    # ----------------------
    # SIGN UP
    # ----------------------
    if auth_mode == "Sign Up":
        if st.button("Create Account"):
            res = requests.post(
                f"{API_BASE}/signup",
                json={"username": username, "password": password}
            )

            data = res.json()

            if "message" in data:
                st.success("Account created! Please login.")
            else:
                st.error(data.get("error", "Signup failed"))

    # ----------------------
    # LOGIN
    # ----------------------
    else:
        if st.button("Login"):
          try:
            r = requests.post(
            f"{API_BASE}/login",
            json={"username": username, "password": password}
           )

            data = handle_response(r)

            if "detail" in data:
              
              st.stop() # error already shown

        # ✅ success
            
            st.session_state.token = data["access_token"]
            st.success("Login successful")
            st.rerun()

          except Exception:
             st.error("Login request failed. Check network.")

    st.stop()
def reset_chat():
    thread_id = create_thread_api()
    if thread_id!=None:
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
# 🔐 Logout button (NEW)
if st.sidebar.button("Logout"):
    st.session_state.token = None
    st.session_state.clear()
    st.rerun()
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
    try:
        # ✅ Save user message
        st.session_state["message_history"].append(
            {"role": "user", "content": user_input}
        )

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):

            status_holder = {"box": None}

            def stream_with_trace():
                try:
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

                        # 🤖 Assistant streaming
                        elif event["type"] == "assistant":
                            yield event["content"]

                        # ❌ Backend error
                        elif event["type"] == "error":
                            st.error(event["message"])
                            return  # 🔥 STOP STREAM

                except Exception:
                    st.error("Streaming failed")
                    return

            # ✅ Keep inside try
            ai_message = st.write_stream(stream_with_trace())

            # ✅ Save assistant response
            if ai_message:
                st.session_state["message_history"].append(
                    {"role": "assistant", "content": ai_message}
                )

    except Exception:
        st.error("Something went wrong while sending message")