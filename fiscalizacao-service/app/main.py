from fastapi import FastAPI
from app.fiscal import router as fiscal_router
from app.rabbitmq import init_rabbitmq

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_rabbitmq()

app.include_router(fiscal_router, prefix="/fiscal")