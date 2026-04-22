from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.auth import create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, get_password_hash
from backend.models.user import User
from pydantic import BaseModel

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    profile_image_url: str | None = None
    bio: str | None = None

class SetupRootRequest(BaseModel):
    username: str
    password: str

@router.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).filter(User.username == form_data.username))
    user = result.scalars().first()
    
    from backend.core.auth import verify_password
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/auth/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/auth/setup-root")
async def setup_root_admin(request: SetupRootRequest, db: AsyncSession = Depends(get_db)):
    # Check if any ADMIN exists
    result = await db.execute(select(User).filter(User.role == "admin").limit(1))
    if result.scalars().first() is not None:
        raise HTTPException(status_code=400, detail="A root administrator already exists.")
    
    hashed_password = get_password_hash(request.password)
    new_admin = User(
        username=request.username,
        hashed_password=hashed_password,
        role="admin"
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    return {"message": "Root admin created successfully"}
