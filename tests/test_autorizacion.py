"""Seguridad de negocio: matriz rol x acción (E6) y su aplicación en la API."""
from itertools import product

import pytest
from fastapi.testclient import TestClient

from src.api.main import crear_app
from src.domain.autorizacion import Accion, Rol, exigir, puede
from src.domain.errores import NoAutenticado, NoAutorizado
from src.infrastructure.contenedor import construir

A, R = Accion, Rol
# Oráculo independiente del código: quién PUEDE hacer qué (BRD p.11-12).
ESPERADO = {
    A.CONSULTAR_STOCK: {R.VENDEDOR, R.CAJERO, R.SUPERVISOR, R.ALMACEN, R.ADMINISTRADOR},
    A.CONSULTAR_APARTADO: {R.VENDEDOR, R.CAJERO, R.SUPERVISOR, R.ADMINISTRADOR},
    A.CREAR_APARTADO: {R.VENDEDOR, R.CAJERO, R.SUPERVISOR},
    A.REGISTRAR_ABONO: {R.CAJERO, R.SUPERVISOR},
    A.ENTREGAR_APARTADO: {R.CAJERO, R.ALMACEN, R.SUPERVISOR},
    A.PROCESAR_VENTA: {R.CAJERO, R.SUPERVISOR},
    A.PROCESAR_DEVOLUCION: {R.CAJERO, R.SUPERVISOR},
    A.PROCESAR_VENCIMIENTOS: {R.SISTEMA, R.SUPERVISOR, R.ADMINISTRADOR},
}


@pytest.mark.parametrize("rol, accion", list(product(Rol, Accion)))
def test_matriz_rol_accion(rol, accion):
    assert puede(rol, accion) == (rol in ESPERADO[accion])


def test_el_oraculo_cubre_todas_las_acciones():
    assert set(ESPERADO) == set(Accion)


def test_exigir_distingue_401_de_403():
    with pytest.raises(NoAutenticado):
        exigir(None, A.CONSULTAR_STOCK)
    with pytest.raises(NoAutenticado):
        exigir("HACKER", A.CONSULTAR_STOCK)
    with pytest.raises(NoAutorizado):
        exigir("ALMACEN", A.PROCESAR_VENTA)
    assert exigir("CAJERO", A.PROCESAR_VENTA) == Rol.CAJERO


def cliente(rol=None):
    headers = {"X-Rol": rol} if rol else {}
    return TestClient(crear_app(construir()), headers=headers)


def test_api_sin_rol_401_y_rol_desconocido_401():
    assert cliente().get("/stock").status_code == 401
    assert cliente("HACKER").get("/stock").status_code == 401


@pytest.mark.parametrize("rol, ruta, metodo, body, status", [
    ("ALMACEN", "/ventas", "post", {"sucursal_id": "S", "lineas": [], "pagos": []}, 403),
    ("VENDEDOR", "/apartados/AP-0004/abonos", "post", {"monto": "1"}, 403),
    ("CAJERO", "/procesos/vencimientos", "post", {}, 403),
    ("VENDEDOR", "/devoluciones", "post",
     {"ticket_id": "V-0001", "numero_serie": "SN-LAP-0011"}, 403),
    ("CLIENTE", "/stock", "get", None, 403),
    ("VENDEDOR", "/stock", "get", None, 200),
    ("SISTEMA", "/procesos/vencimientos", "post", {"fecha": "2026-11-05"}, 200),
])
def test_api_aplica_la_matriz(rol, ruta, metodo, body, status):
    c = cliente(rol)
    r = c.get(ruta) if metodo == "get" else c.post(ruta, json=body)
    assert r.status_code == status


def test_vendedor_puede_apartar():
    r = cliente("VENDEDOR").post("/apartados", json={
        "cliente_id": "TEC-C001", "numero_serie": "SN-LAP-0001",
        "anticipo": "67.20", "fecha": "2026-11-05"})
    assert r.status_code == 201


def test_cajero_con_rol_valido_aun_necesita_clave_de_supervisor():
    """Autenticación (rol) != autorización (firma del Supervisor)."""
    body = {"ticket_id": "V-0001", "numero_serie": "SN-LAP-0011",
            "fecha": "2026-11-05", "clave_supervisor": ""}
    c = cliente("CAJERO")
    assert c.post("/devoluciones", json=body).status_code == 403
    assert c.post("/devoluciones",
                  json={**body, "clave_supervisor": "SUP-001"}).status_code == 201


def test_supervisor_inactivo_no_autoriza_ni_con_rol_cajero():
    body = {"ticket_id": "V-0001", "numero_serie": "SN-LAP-0011",
            "fecha": "2026-11-05", "clave_supervisor": "SUP-002"}
    assert cliente("CAJERO").post("/devoluciones", json=body).status_code == 403
