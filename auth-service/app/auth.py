from fastapi import APIRouter, HTTPException
from app.supabase_client import supabase
from app import schemas, utils
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from app.schemas import RefreshRequest

router = APIRouter()

@router.post("/register")
def register(user: schemas.UserCreate):
    existing = supabase.table("users").select("*").eq("email", user.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    hashed = utils.hash_password(user.password)
    supabase.table("users").insert({"email": user.email, "hashed_password": hashed}).execute()
    return {"msg": "Usuário criado com sucesso"}

@router.post("/login", response_model=schemas.Token)
def login(user: schemas.UserCreate):
    result = supabase.table("users").select("*").eq("email", user.email).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    db_user = result.data[0]
    if not utils.verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Senha inválida")

    token = utils.create_access_token({"sub": str(db_user["id"])})
    return {"access_token": token, "token_type": "bearer"}


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = utils.decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Token inválido")
    return payload["sub"]

@router.post("/refresh", response_model=schemas.Token)
def refresh_token(req: RefreshRequest):
    payload = utils.decode_token(req.refresh_token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    new_token = utils.create_access_token({"sub": payload["sub"]})
    return {"access_token": new_token, "token_type": "bearer"}

@router.post("/logout")
def logout():
    # Simples: não há armazenamento local. Você pode invalidar token via blacklist Redis, se quiser.
    return JSONResponse(status_code=200, content={"msg": "Logout realizado (token será naturalmente expirado)"})

@router.get("/me")
def get_me(user_id: str = Depends(get_current_user)):
    result = supabase.table("users").select("id,email").eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return result.data[0]