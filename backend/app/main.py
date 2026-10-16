from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()  # backend/.env (git-ignored): WAIFU2X_EXE, ANTHROPIC_API_KEY, ...

from .db import init_db  # noqa: E402
from .pipeline import runner
from .routes import library, pages


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    runner.warm_up()
    runner.requeue_unfinished()
    yield


app = FastAPI(title="Manga Japanese Tutor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(library.router)
app.include_router(pages.router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}
