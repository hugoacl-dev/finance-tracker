from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional

class Transacao(BaseModel):
    Descricao: str = Field(min_length=1)
    Valor: float
    Cartao: str
    Titular: str = "Sistema"
    Categoria: str = "Outros"
    Tipo: Literal["debito", "credito"] = "debito"
    Perfil: Optional[str] = None
    is_dupe: Optional[bool] = False
    dest_profile: Optional[str] = None
    
    @field_validator("Cartao", mode="before")
    @classmethod
    def format_cartao(cls, v):
        s = str(v).strip()
        if s.isdigit():
            return s.zfill(4)
        return s
        
    @field_validator("Valor", mode="before")
    @classmethod
    def format_valor(cls, v):
        if isinstance(v, str):
            s = v.strip().replace("R$", "").replace(" ", "")
            if "," in s:
                s = s.replace(".", "").replace(",", ".")
            try:
                return float(s)
            except ValueError:
                return 0.0
        return float(v)
