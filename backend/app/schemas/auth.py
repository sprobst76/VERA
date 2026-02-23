from pydantic import BaseModel, EmailStr, field_validator
import uuid


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_name: str
    tenant_slug: str
    state: str = "BW"
    registration_secret: str = ""

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Passwort muss mindestens 8 Zeichen lang sein")
        return v


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str
