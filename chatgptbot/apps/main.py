from fastapi import FastAPI
from .routers import auth, chat, upload
from . import deps

app = FastAPI(title="ChatGPT-style API")
deps.apply_cors(app)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(upload.router)

@app.get("/health")
def health():
    return {"ok": True}

from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse(url="/docs")