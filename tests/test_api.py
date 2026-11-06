"""API REST: códigos HTTP 200/201, 403, 404, 409, 422 según el contrato."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import crear_app
from src.infrastructure.contenedor import construir


@pytest.fixture
def client():
    return TestClient(crear_app(construir()), headers={"X-Rol": "SUPERVISOR"})


def test_crear_apartado_201(client):
    r = client.post("/apartados", json={
        "cliente_id": "TEC-C001", "numero_serie": "SN-LAP-0001",
        "anticipo": "67.20", "fecha": "2026-11-05"})
    assert r.status_code == 201
    assert r.json()["estado"] == "ACTIVO" and r.json()["saldo"] == "268.80"
    assert r.json()["fecha_limite"] == "2026-12-05"


def test_anticipo_insuficiente_422(client):
    r = client.post("/apartados", json={
        "cliente_id": "TEC-C001", "numero_serie": "SN-LAP-0001",
        "anticipo": "67.19", "fecha": "2026-11-05"})
    assert r.status_code == 422 and "20%" in r.json()["detail"]


def test_serie_reservada_422_y_cliente_inexistente_404(client):
    body = {"cliente_id": "TEC-C001", "numero_serie": "SN-LAP-0005",
            "anticipo": "124.00", "fecha": "2026-11-05"}
    assert client.post("/apartados", json=body).status_code == 422
    assert client.post("/apartados", json={**body, "cliente_id": "X"}).status_code == 404


def test_get_apartado_200_y_404(client):
    assert client.get("/apartados/AP-0004").json()["saldo"] == "723.20"
    assert client.get("/apartados/NOPE").status_code == 404


def test_abono_y_entrega_flujo_completo(client):
    r = client.post("/apartados/AP-0004/abonos",
                    json={"monto": "723.20", "fecha": "2026-11-03"})
    assert r.status_code == 200 and r.json()["estado"] == "LIQUIDADO"
    assert client.post("/apartados/AP-0004/entrega").json()["estado"] == "ENTREGADO"


def test_entrega_sin_liquidar_409(client):
    assert client.post("/apartados/AP-0004/entrega").status_code == 409


def test_abono_excesivo_422_y_formato_invalido_422(client):
    assert client.post("/apartados/AP-0004/abonos",
                       json={"monto": "999", "fecha": "2026-11-03"}).status_code == 422
    assert client.post("/apartados/AP-0004/abonos",
                       json={"monto": "abc"}).status_code == 422


def test_vencimientos(client):
    r = client.post("/procesos/vencimientos", json={"fecha": "2026-11-06"})
    assert r.json() == {"vencidos": ["AP-0005"], "saldo_a_favor_total": "162.72"}
    assert client.get("/apartados/AP-0005").json()["estado"] == "VENCIDO"


def test_abono_a_vencido_409(client):
    client.post("/procesos/vencimientos", json={"fecha": "2026-11-06"})
    r = client.post("/apartados/AP-0005/abonos",
                    json={"monto": "10", "fecha": "2026-11-06"})
    assert r.status_code == 409


def test_venta_201_y_pago_descuadrado_422(client):
    body = {"sucursal_id": "SUC-05", "fecha": "2026-11-05",
            "lineas": [{"sku": "TEC-P002", "numero_serie": "SN-MON-0001"}],
            "pagos": [{"metodo": "EFECTIVO", "monto": "407.00"}]}
    bad = {**body, "pagos": [{"metodo": "EFECTIVO", "monto": "1.00"}]}
    assert client.post("/ventas", json=bad).status_code == 422
    r = client.post("/ventas", json=body)
    assert r.status_code == 201 and r.json()["total"] == "407.00"
    assert client.post("/ventas", json=body).status_code == 409   # ya vendida


def test_devolucion_201_403_422_404(client):
    base = {"ticket_id": "V-0001", "numero_serie": "SN-LAP-0011",
            "clave_supervisor": "SUP-001", "fecha": "2026-11-05"}
    assert client.post("/devoluciones",
                       json={**base, "clave_supervisor": ""}).status_code == 403
    assert client.post("/devoluciones",
                       json={**base, "dano_cliente": True}).status_code == 422
    assert client.post("/devoluciones",
                       json={**base, "ticket_id": "NOPE"}).status_code == 404
    r = client.post("/devoluciones", json=base)
    assert r.status_code == 201 and r.json()["monto"] == "1188.00"
    assert client.post("/devoluciones", json=base).status_code == 409


def test_devolucion_fuera_de_plazo_422(client):
    r = client.post("/devoluciones", json={
        "ticket_id": "V-0002", "numero_serie": "SN-LAP-0012",
        "clave_supervisor": "SUP-001", "fecha": "2026-11-05"})
    assert r.status_code == 422 and "15 días" in r.json()["detail"]


def test_stock_query(client):
    r = client.get("/stock", params={"sku": "TEC-P001"})
    assert r.status_code == 200
    assert sum(x["disponibles"] for x in r.json()) == 4


def test_openapi_documentado(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200 and "/apartados" in r.json()["paths"]
