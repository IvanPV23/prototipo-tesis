"""ABAC mínimo: proyecto y capacidad de escritura, sin autenticación externa."""
from dataclasses import dataclass
from fastapi import HTTPException

@dataclass(frozen=True)
class Subject:
    actor_id: str
    role: str
    project: str

def can_write(subject: Subject, project: str) -> bool:
    return subject.role == "tecnico" and subject.project == project

def can_read(subject: Subject, project: str) -> bool:
    return subject.role in {"tecnico", "auditor"} and subject.project == project

def require_write(subject: Subject, project: str) -> None:
    if not can_write(subject, project): raise HTTPException(403, "Acceso denegado: escritura no autorizada")

def require_read(subject: Subject, project: str) -> None:
    if not can_read(subject, project): raise HTTPException(403, "Acceso denegado: lectura no autorizada")
