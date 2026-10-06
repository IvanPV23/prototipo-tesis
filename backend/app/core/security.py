"""ABAC mínimo: rol y proyectos autorizados del actor (atributos_abac), sin autenticación externa."""
from dataclasses import dataclass, field

from fastapi import HTTPException

WRITE_ROLES = {"tecnico", "logistica"}
READ_ROLES = {"tecnico", "logistica", "auditor"}


@dataclass(frozen=True)
class Subject:
    actor_id: str
    role: str
    projects: frozenset = field(default_factory=lambda: frozenset({"*"}))

    def in_project(self, project: str) -> bool:
        return "*" in self.projects or project in self.projects


def can_write(subject: Subject, project: str) -> bool:
    return subject.role in WRITE_ROLES and subject.in_project(project)


def can_read(subject: Subject, project: str) -> bool:
    return subject.role in READ_ROLES and subject.in_project(project)


def require_write(subject: Subject, project: str) -> None:
    if not can_write(subject, project):
        raise HTTPException(403, "Acceso denegado: escritura no autorizada")


def require_read(subject: Subject, project: str) -> None:
    if not can_read(subject, project):
        raise HTTPException(403, "Acceso denegado: lectura no autorizada")
