from fastapi import Header
from ...core.security import Subject
def current_subject(x_actor_id: str = Header("SIMULADOR"), x_actor_role: str = Header("tecnico"), x_actor_project: str = Header("GENERAL")) -> Subject:
    """Identidad simulada por cabeceras; sustituible por JWT."""
    return Subject(x_actor_id, x_actor_role, x_actor_project)
