from fastapi import Header

from ...core.security import Subject


def current_subject(x_actor_id: str = Header("SIMULADOR"), x_actor_role: str = Header("tecnico"),
                    x_actor_projects: str = Header("*")) -> Subject:
    """Identidad simulada por cabeceras; sustituible por JWT con los mismos atributos."""
    projects = frozenset(p.strip() for p in x_actor_projects.split(",") if p.strip())
    return Subject(x_actor_id, x_actor_role, projects)
