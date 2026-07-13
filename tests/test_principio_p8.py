from backend.app.core.security import Subject, can_read, can_write
from .conftest import write_json, log, now

def test_p8_abac_por_proyecto_y_rol(output_dir):
    tecnico_a=Subject("TEC-A","tecnico","PROY-A"); tecnico_b=Subject("TEC-B","tecnico","PROY-B"); auditor=Subject("AUDITOR","auditor","PROY-A")
    assert can_write(tecnico_a,"PROY-A")
    assert not can_write(tecnico_b,"PROY-A") and not can_write(auditor,"PROY-A")
    assert can_read(auditor,"PROY-A")
    log(output_dir, "test_p8.log", ["INFO: Acceso denegado: TEC-B intenta escribir en PROY-A (proyecto no autorizado)", "INFO: Acceso denegado: AUDITOR intenta escribir (rol sin permiso)", "INFO: Acceso permitido: AUDITOR consulta auditoría en PROY-A"])
    write_json(output_dir / "seguridad.json", {"test":"P8 - ABAC","fecha":now(),"intentos":3,"intentos_denegados":2,"intentos_permitidos":1,"politicas_aplicadas":["proyecto_autorizado","rol_escritura"],"estado":"APROBADO"})
