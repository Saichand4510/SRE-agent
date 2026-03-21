import uuid
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,field_validator
import json
from langchain_core.messages import HumanMessage, AIMessage
import threading
from log_generator import main as start_log_generator
from metrics_generator import main as start_metrics_generator
from langgraph_mcp_backend1 import (
    create_chatbot
   
)
from database import create_tables,init_db,close_db
import database
from asyncpg.exceptions import UniqueViolationError
from auth import hash_password,verify_password, create_access_token,create_refresh_token,decode_token
from auth import get_current_user
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
import logging
from fastapi.middleware.cors import CORSMiddleware
import os
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
     handlers=[
        logging.FileHandler("app.log"),   # 👈 saves to file
        logging.StreamHandler()           # 👈 still prints in terminal
    ]

)

logger = logging.getLogger(__name__)




app = FastAPI(title="LangGraph MCP API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
def get_user_key(request):
    return getattr(request.state, "user", "anonymous")
limiter = Limiter(key_func=get_user_key)

app.state.limiter = limiter
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")

    response = await call_next(request)
   
    logger.info(f"Response: {response.status_code}")

    return response
@app.middleware("http")
async def add_user_to_request(request: Request, call_next):
    try:
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]  
            user = decode_token(token)

            if user:
                request.state.user = user
            else:
                request.state.user = "anonymous"
        else:
            request.state.user = "anonymous"

    except Exception:
        request.state.user = "anonymous"

    response = await call_next(request)
    return response
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests"}
    )

chatbot = None


@app.on_event("startup")
async def startup_event():
    global chatbot

    

    # Start log generator
    log_thread = threading.Thread(target=start_log_generator)
    log_thread.daemon = True
    log_thread.start()

    # Start metrics generator
    metrics_thread = threading.Thread(target=start_metrics_generator)
    metrics_thread.daemon = True
    metrics_thread.start()
    
    app.state.checkpointer_cm = AsyncPostgresSaver.from_conn_string(
         os.getenv("DATABASE_URL")
     )
    app.state.checkpointer = await app.state.checkpointer_cm.__aenter__()

    # # ✅ create chatbot
    await app.state.checkpointer.setup()
    chatbot = await create_chatbot(app.state.checkpointer)
   
  
    await init_db()          # ✅ initialize pool
    await create_tables()    # ✅ create schema   

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()    
    await app.state.checkpointer_cm.__aexit__(None, None, None)
    
# =========================
# Request / Response Models
# =========================



class ChatRequest(BaseModel):
    thread_id: str
    message: str

    @field_validator("message")
    def validate_message(cls, v):
        if len(v) > 1000:
            raise ValueError("Message too long")
        return v


class ThreadResponse(BaseModel):
    thread_id: str


class UserSignup(BaseModel):
    username: str
    password: str
class UserLogin(BaseModel):
    username: str
    password: str    
# =========================
# Utilities
# =========================



def generate_thread_id() -> str:
    return str(uuid.uuid4())


def get_config(thread_id: str):
    return {
        "configurable": {"thread_id": thread_id},
        "metadata": {"thread_id": thread_id},
        "run_name": "chat_turn",
    }



async def check_thread_owner(thread_id: str, user: str) -> bool:
    async with database.pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT username FROM threads WHERE thread_id = $1",
            thread_id
        )

    if not result:
        return False

    return result["username"] == user

@app.post("/signup")
@limiter.limit("5/minute", key_func=get_remote_address)
async def signup(request: Request, user: UserSignup):
    logger.info(f"Signup attempt: {user.username}")

    async with database.pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO users (username, password) VALUES ($1, $2)",
                user.username,
                hash_password(user.password)
            )

            logger.info(f"User created: {user.username}")
            return {"message": "User created"}

        except UniqueViolationError:
            logger.warning(f"Signup failed (user exists): {user.username}")
            raise HTTPException(status_code=400, detail="User already exists")

        except Exception as e:
            logger.error(f"Signup error: {str(e)}")
            raise HTTPException(status_code=500, detail="Signup failed")



@app.post("/login")
@limiter.limit("5/minute", key_func=get_remote_address)
async def login(request: Request, user: UserLogin):
    logger.info(f"Login attempt: {user.username}")

    async with database.pool.acquire() as conn:
        try:
            result = await conn.fetchrow(
                "SELECT password FROM users WHERE username=$1",
                user.username
            )

            if not result:
                logger.warning(f"User not found: {user.username}")
                raise HTTPException(status_code=404, detail="User not found")

            stored_password = result["password"]

            if not verify_password(user.password, stored_password):
                logger.warning(f"Invalid password attempt for user: {user.username}")
                raise HTTPException(status_code=401, detail="Invalid password")

            
            access_token = create_access_token(user.username)
            refresh_token = create_refresh_token(user.username)
            response = JSONResponse(content={"access_token": access_token})

        # 🍪 Store refresh token in cookie
            response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,   # ⚠️ True in production (HTTPS)
            samesite="lax",
            max_age=7 * 24 * 60 * 60
        )
            logger.info(f"User logged in: {user.username}")
            return response

        except HTTPException:
            raise

        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise HTTPException(status_code=500, detail="Login failed")
# =========================
# 1️⃣ Create new chat
# =========================


@app.post("/threads")
@limiter.limit("4/minute")
async def create_thread(request: Request, user: str = Depends(get_current_user)):
    logger.info(f"Creating thread for user: {user}") 
    thread_id = generate_thread_id()

    try:
        # ✅ DB insert (async + pooled)
        async with database.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO threads (thread_id, username) VALUES ($1, $2)",
                thread_id,
                user
            )

        logger.info(f"Thread stored in db: {thread_id}")

        # ✅ Initialize chatbot state (non-blocking)
        await chatbot.ainvoke(
            {"messages": []},
            config=get_config(thread_id),
        )
        logger.info(f"Thread created: {thread_id}")
        return ThreadResponse(thread_id=thread_id)

    except Exception as e:
        logger.error(f"Thread creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create thread")


# =========================
# 2️⃣ List threads
# =========================


@app.get("/threads")
@limiter.limit("2/minute")
async def list_threads(request: Request, user: str = Depends(get_current_user)):
    logger.info(f"Fetching threads for user: {user}")

    try:
        async with database.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT thread_id FROM threads WHERE username = $1",
                user
            )

        threads = [row["thread_id"] for row in rows]

        return {"threads": threads}

    except Exception as e:
        logger.error(f"Fetch threads error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch threads")


# =========================
# 3️⃣ Get conversation history
# =========================

@app.get("/threads/{thread_id}")
@limiter.limit("2/minute")
async def get_thread_messages(request:Request,thread_id: str, user: str = Depends(get_current_user)):
    try:
        logger.info(f"Fetching messages for thread: {thread_id} by user: {user}")
        if not await check_thread_owner(thread_id, user):
            logger.warning(f"Unauthorized access attempt: {thread_id} by {user}")
            raise HTTPException(status_code=403, detail="Not allowed")

        state = await chatbot.aget_state(
            config={"configurable": {"thread_id": thread_id}}
        )

        messages = state.values.get("messages", [])

        formatted = []
        for msg in messages:
            role = "assistant"
            if isinstance(msg, HumanMessage):
                role = "user"

            formatted.append({
                "role": role,
                "content": msg.content,
            })

        return {"messages": formatted}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fetch messages error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")


# =========================
# 4️⃣ Chat (STREAMING) ⭐⭐⭐
# =========================

@app.post("/chat/stream")
@limiter.limit("8/minute")
async def chat_stream(request:Request,body: ChatRequest, user: str = Depends(get_current_user)):
    if not await check_thread_owner(body.thread_id, user):
        logger.warning(f"Unauthorized chat access: {body.thread_id} by {user}")
        raise HTTPException(status_code=403, detail="Not allowed")

    CONFIG = get_config(body.thread_id)
    logger.info(f"Chat request from user: {user} on thread: {body.thread_id}")
    async def event_generator():
        try:
            
            async for event in chatbot.astream_events(
                {"messages": [HumanMessage(content=body.message)]},
                config=CONFIG,
                
            ):
                event_type = event["event"]

                if event_type == "on_tool_start":
                    yield json.dumps({
                        "type": "tool_start",
                        "name": event["name"]
                    }) + "\n"

                elif event_type == "on_tool_end":
                    yield json.dumps({
                        "type": "tool_end"
                    }) + "\n"

                elif event_type == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield json.dumps({
                            "type": "assistant",
                            "content": chunk.content
                        }) + "\n"

        except Exception:
            logger.info(f"Chat request from user: {user} on thread: {body.thread_id}")
            yield json.dumps({
                "type": "error",
                "message": "Chat failed"
            }) + "\n"

    return StreamingResponse(event_generator(), media_type="text/plain")
@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}
@app.post("/logout")
async def logout():
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie("refresh_token")
    return response

@app.post("/refresh")
async def refresh_token(request: Request):
    try:
        refresh_token = request.cookies.get("refresh_token")

        if not refresh_token:
            raise HTTPException(status_code=401, detail="No refresh token")

        username = decode_token(refresh_token, expected_type="refresh")

        new_access_token = create_access_token(username)

        return {"access_token": new_access_token}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh failed")