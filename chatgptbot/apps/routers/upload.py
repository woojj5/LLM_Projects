from fastapi import APIRouter, UploadFile, File
from pathlib import Path, PurePath
import shutil

router = APIRouter(prefix="/files", tags=["files"])
UPLOAD_DIR = Path("./.uploads"); UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    dst = UPLOAD_DIR / PurePath(file.filename).name
    with dst.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"ok": True, "path": str(dst)}
