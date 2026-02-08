from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import documents, billing_notes

app = FastAPI(
    title="MedBill AI",
    description="Medical Billing Notes - CPT Code Extraction",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(billing_notes.router, prefix="/api/billing-notes", tags=["Billing Notes"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
