from fastapi import APIRouter, HTTPException
from app.schemas import VerificacaoPlaca
from app.supabase_client import supabase
from app.rabbitmq import publisher
from datetime import datetime

router = APIRouter()

@router.post("/verificar")
async def verificar(dados: VerificacaoPlaca):
    placa = dados.placa.upper()
    agora = datetime.utcnow().isoformat()

    result = supabase.table("placas_estacionadas") \
        .select("*") \
        .eq("placa", placa) \
        .gte("expira_em", agora) \
        .order("expira_em", desc=True) \
        .limit(1) \
        .execute()

    if result.data:
        return {"status": "regular", "expira_em": result.data[0]["expira_em"]}
    else:
        evento = {
            "placa": placa,
            "timestamp": agora,
            "motivo": "crédito expirado ou inexistente"
        }
        await publisher.publish_event("irregularidade.detectada", evento)
        raise HTTPException(status_code=403, detail="Placa irregular – sem crédito ativo")