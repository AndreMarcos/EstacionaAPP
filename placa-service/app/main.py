from fastapi import FastAPI
from app.placa import router as placa_router
from app.rabbitmq import init_rabbitmq

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_rabbitmq()

app.include_router(placa_router, prefix="/placa")