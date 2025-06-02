from fastapi import APIRouter, HTTPException
from app.supabase_client import supabase
from app.schemas import RegistroPlaca
from app.rabbitmq import publisher
from datetime import datetime

router = APIRouter()

@router.post("/registrar")
async def registrar_placa(dados: RegistroPlaca):
    try:
        payload = dados.dict()
        payload["registrado_em"] = datetime.utcnow().isoformat()

        supabase.table("placas_estacionadas").insert(payload).execute()

        await publisher.publish_event("placa.registrada", payload)
        return {"msg": "Placa registrada com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
def listar_placas():
    result = supabase.table("placas_estacionadas").select("*").limit(100).execute()
    return result.data