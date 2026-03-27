import time
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
    create_chatbot,client
   
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
# from latency_logger import log_latency
import asyncio
import hashlib
from contextlib import AsyncExitStack
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


class CheckpointerPool:
    def __init__(self, db_url: str, size: int = 5):
        self.db_url = db_url
        self.size = size
        self._checkpointers = []
        self._exit_stack = AsyncExitStack()
        self._locks = []  # 🔒 one lock per checkpointer

    async def startup(self):
        for i in range(self.size):
            cm = AsyncPostgresSaver.from_conn_string(self.db_url)
            cp = await self._exit_stack.enter_async_context(cm)
            if i==0:
             await cp.setup()
            print("Checkpointer initialized") 
            self._checkpointers.append(cp)
            self._locks.append(asyncio.Semaphore(1))  # 🔒 only 1 request at a time

    async def shutdown(self):
        print("Shutting down checkpointer pool...")
        await self._exit_stack.aclose()

    def _hash(self, key: str) -> int:
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)

    async def acquire(self, key: str):
        """
        Get a checkpointer safely (with lock)
        """
        idx = self._hash(key) % self.size
        await self._locks[idx].acquire()  # 🔒 wait if busy
        print(f"Acquired checkpointer {idx} for key: {key}")  
        return idx, self._checkpointers[idx]

    def release(self, idx: int):
        """
        Release the lock after request completes
        """
        print(f"Releasing checkpointer {idx}")
        self._locks[idx].release()
        # pass
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
    allow_origins=["https://chat-companion-07.onrender.com",
        "http://localhost:8080",],  # Or specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
def get_user_key(request):
    return getattr(request.state, "user", "anonymous")
limiter = Limiter(key_func=get_user_key)

app.state.limiter = limiter
@app.middleware("http")
async def add_user_to_request(request: Request, call_next):
    try:
        auth_header = request.headers.get("Authorization")

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]  
            print(token)
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
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")

    response = await call_next(request)
   
    logger.info(f"Response: {response.status_code}")

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




@app.on_event("startup")
async def startup_event():
   

    

    # Start log generator
    log_thread = threading.Thread(target=start_log_generator)
    log_thread.daemon = True
    log_thread.start()

    # Start metrics generator
    metrics_thread = threading.Thread(target=start_metrics_generator)
    metrics_thread.daemon = True
    metrics_thread.start()
    
    app.state.cp_pool = CheckpointerPool(
        db_url=os.getenv("DATABASE_URL"),
        size=5  # tune this
    )
    try:
      app.state.tools=await client.get_tools()
    except Exception as e:
        logger.error(f"Error fetching tools: {repr(e)}")
        app.state.tools = []
    await app.state.cp_pool.startup()
    app.state.chatbots = {}
    app.state.llm_sem = asyncio.Semaphore(2)  # 🔒 limit concurrent LLM calls
   
  
    await init_db()          # ✅ initialize pool
    await create_tables()    # ✅ create schema   

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()    
    await app.state.cp_pool.shutdown()
    
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
async def is_cp_alive(cp):
    try:
        result=await cp.conn.execute("SELECT 1")
        print(f"CP health check result: {result}")  # Debug log
        return True
    except Exception:
        return False

async def get_chatbot(app, user_id: str):
    cp_pool = app.state.cp_pool

    idx, cp = await cp_pool.acquire(user_id)

    key = idx
    tools=app.state.tools
    # 🔥 CHECK CONNECTION HEALTH
    if not await is_cp_alive(cp):
        print(f"Recreating CP {idx} while lock held")
        
        # recreate checkpointer
        cm = AsyncPostgresSaver.from_conn_string(app.state.cp_pool.db_url)
        new_cp = await app.state.cp_pool._exit_stack.enter_async_context(cm)
        await new_cp.setup()

        # replace in pool
        app.state.cp_pool._checkpointers[idx] = new_cp
        cp = new_cp

        # ❗ IMPORTANT: also update chatbot
        if key in app.state.chatbots:
            print(f"Rebinding chatbot {key} to new CP")

            # recreate chatbot ONLY when cp is dead
            app.state.chatbots[key] = await create_chatbot(cp,tools)

    # normal creation
    if key not in app.state.chatbots:
        print(f"Creating chatbot for key: {key}")
        app.state.chatbots[key] = await create_chatbot(cp,tools)

    return key, app.state.chatbots[key]

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
async def signup( user: UserSignup):
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
            secure=True,   # ⚠️ True in production (HTTPS)
            samesite="none",
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
@limiter.limit("20/minute")
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

        
      
       
        logger.info(f"Thread created: {thread_id}")
        return ThreadResponse(thread_id=thread_id)

    except Exception as e:
        logger.error(f"Thread creation failed: {repr(e)}")
        raise HTTPException(status_code=500, detail="Failed to create thread")


# =========================
# 2️⃣ List threads
# =========================


@app.get("/threads")
@limiter.limit("20/minute")
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
@limiter.limit("20/minute")
async def get_thread_messages(request:Request,thread_id: str, user: str = Depends(get_current_user)):
    idx=None
    try:
        logger.info(f"Fetching messages for thread: {thread_id} by user: {user}")
        if not await check_thread_owner(thread_id, user):
            logger.warning(f"Unauthorized access attempt: {thread_id} by {user}")
            raise HTTPException(status_code=403, detail="Not allowed")
        
        key=f"{user}:{thread_id}"
        idx, chatbot = await get_chatbot(app, key)
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
        logger.error(f"Fetch messages error: {repr(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")
    finally:
        if idx is not None:
         app.state.cp_pool.release(idx)    # 🔒 release checkpointer


# =========================
# 4️⃣ Chat (STREAMING) ⭐⭐⭐
# =========================

@app.post("/chat/stream")
@limiter.limit("20/minute")
async def chat_stream(request:Request,body: ChatRequest, user: str = Depends(get_current_user)):
    idx=None
    if not await check_thread_owner(body.thread_id, user):
        logger.warning(f"Unauthorized chat access: {body.thread_id} by {user}")
        raise HTTPException(status_code=403, detail="Not allowed")
    
    key=f"{user}:{body.thread_id}"
    idx, chatbot = await get_chatbot(app, key)
    print(f"Using checkpointer {idx} for user {user} and thread {body.thread_id}")  # Debug log
    CONFIG = get_config(body.thread_id)
    logger.info(f"Chat request from user: {user} on thread: {body.thread_id}")
    async def event_generator():
        start_time = time.time()
        first_token_time = None
        tool_start_time = None
        total_tool_time = 0

        request_id = str(uuid.uuid4())
        
        try:  
           async with app.state.llm_sem:  # 🔒 limit concurrent LLM calls 
            async for event in chatbot.astream_events(
                {"messages": [HumanMessage(content=body.message)]},
                config=CONFIG,
                
            ):
                event_type = event["event"]
                
                if event_type == "on_tool_start":
                    # print(f"Tool started: {event['name']}")  # Debug log
                    tool_start_time = time.time()
                    yield json.dumps({
                        "type": "tool_start",
                        "name": event["name"]
                    }) + "\n"
                    # yield f"data: {json.dumps({ "type": "tool_start",
                    #    "name": event["name"]})}\n\n"
                    

                elif event_type == "on_tool_end":
                    #raw_output = event.get("data", {}).get("output", "")

# extract text properly
                    # if hasattr(raw_output, "content"):
                    #       if isinstance(raw_output.content, list):
                    #                output = "\n".join(
                    #                  item.get("text", "") for item in raw_output.content if isinstance(item, dict)
                    #                     )
                    #       else:
                    #             output = str(raw_output.content)
                    # else:
                    #      output = str(raw_output)
                    # print(f"Tool ended: {event['name']} with output: {output}")  # Debug log
                    if tool_start_time:
                       total_tool_time += time.time() - tool_start_time
                    yield json.dumps({
                        "type": "tool_end"
                        # "output": output
                    }) + "\n"
                    # yield f"data: {json.dumps({ "type": "tool_end"})}\n\n"

                elif event_type == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                  #  print(f"Received chunk: {chunk.content}")  # Debug log
                    if chunk.content:
                        if first_token_time is None:
                           first_token_time = time.time()
                        yield json.dumps({
                            "type": "assistant",
                            "content": chunk.content
                        }) + "\n"
                        # print(f"Yielding chunk: {chunk.content}")  # Debug log
                       # yield f"data: {json.dumps({ 'type': 'assistant', 'content': chunk.content})}\n\n"

            end_time = time.time()    
            metrics = {
            "request_id": request_id,
            "user": user,
            "query": body.message,
            "thread_id": body.thread_id,
            "total_latency": end_time - start_time,
            "ttft": (first_token_time - start_time) if first_token_time else None,
            "tool_latency": total_tool_time,
            "llm_latency": (end_time - start_time) - total_tool_time,
            "status": "success",
        }

            # log_latency(metrics)

            # print("📊 LATENCY:", metrics)  

        except Exception as e:
            end_time = time.time()

            metrics = {
            "request_id": request_id,
            "user": user,
            "query": body.message,
            "thread_id": body.thread_id,
            "total_latency": end_time - start_time,
            "status": "failure",
            "error": str(e),
        }

            # log_latency(metrics)
            logger.error(f"Chat error: {repr(e)}")
            yield json.dumps({
                "type": "error",
                "message": "Chat failed"
        
            }) + "\n"

        finally:
            # 🔒 release checkpointer
            if idx is not None:
             app.state.cp_pool.release(idx)    

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