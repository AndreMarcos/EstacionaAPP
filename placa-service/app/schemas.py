from pydantic import BaseModel
from typing import Optional

class RegistroPlaca(BaseModel):
    placa: str
    zona: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    expira_em: str  
