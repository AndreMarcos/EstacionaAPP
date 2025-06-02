from pydantic import BaseModel

class VerificacaoPlaca(BaseModel):
    placa: str