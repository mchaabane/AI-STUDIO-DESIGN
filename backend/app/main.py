import re
import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app.ollama import generate, OLLAMA_MODEL
from backend.app.api.projects import router as projects_router
from backend.app.api.generation import router as generation_router


app = FastAPI(
    title="Personal Design AI",
    description="AI Designer personnel fonctionnant localement avec Ollama",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    projects_router,
    prefix="/api/projects",
    tags=["projects"],
)

app.include_router(
    generation_router,
    prefix="/api/generation",
    tags=["generation"],
)


class PromptRequest(BaseModel):
    prompt: str


def get_memory_info() -> dict:
    """
    Récupère la RAM totale et la RAM disponible sur macOS
    à partir des commandes système natives.
    """

    total_bytes = int(
        subprocess.check_output(
            ["sysctl", "-n", "hw.memsize"],
            text=True,
        ).strip()
    )

    vm_stat = subprocess.check_output(
        ["vm_stat"],
        text=True,
    )

    page_size_match = re.search(
        r"page size of (\d+) bytes",
        vm_stat,
    )

    if not page_size_match:
        raise RuntimeError("Impossible de déterminer la taille des pages mémoire.")

    page_size = int(page_size_match.group(1))

    pages = {}

    for line in vm_stat.splitlines():
        match = re.match(
            r"Pages (.+):\s+(\d+)\.",
            line,
        )

        if match:
            pages[match.group(1)] = int(match.group(2))

    available_page_names = [
        "free",
        "inactive",
        "speculative",
        "purgeable",
    ]

    available_pages = sum(
        pages.get(name, 0)
        for name in available_page_names
    )

    available_bytes = available_pages * page_size

    return {
        "model": OLLAMA_MODEL,
        "ram_total_gb": round(total_bytes / (1024 ** 3), 1),
        "ram_available_gb": round(available_bytes / (1024 ** 3), 1),
    }


@app.get("/")
def root():
    return {
        "name": "Personal Design AI",
        "status": "running",
        "version": "0.1.0",
        "model": OLLAMA_MODEL,
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "python": "connected",
        "ollama": "connected",
        "model": OLLAMA_MODEL,
    }


@app.get("/api/system")
def system_info():
    try:
        return get_memory_info()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Impossible de récupérer les informations système : {error}",
        )


@app.post("/api/chat")
async def chat(request: PromptRequest):

    if not request.prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="Le prompt ne peut pas être vide.",
        )

    try:

        response = await generate(
            request.prompt
        )

        return {
            "success": True,
            "response": response,
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Erreur Ollama : {error}",
        )
