"""Specifications: cada regla por separado y combinadas con AND/OR/NOT."""
from datetime import date

import pytest

from src.domain.devolucion import (
    ISupervisorAuthDomainService,
    PoliticaDevolucionDomainService,
)
from src.domain.errores import NoAutorizado, ReglaNegocioViolada
from src.domain.especificaciones import (
    DEVOLUCION_ELEGIBLE,
    PUEDE_APARTAR,
    AnticipoMinimoSpec,
    ClienteActivoSpec,
    DanoClienteSpec,
    DentroDePlazoSpec,
    EmpaqueCompletoSpec,
    LimiteApartadosSpec,
    SerieDisponibleSpec,
    SolicitudApartado,
    SolicitudDevolucion,
)
from src.domain.item_serie import EstadoSerie
from src.domain.valores import MontoMonetario

M = MontoMonetario.de


def solicitud(**kw):
    base = dict(cliente_activo=True, total=M("1000.00"), anticipo=M("200.00"),
                apartados_activos_cliente=0, estado_serie=EstadoSerie.DISPONIBLE)
    return SolicitudApartado(**{**base, **kw})


def devolucion(**kw):
    base = dict(fecha_venta=date(2026, 10, 1), hoy=date(2026, 10, 10),
                empaque_original=True, accesorios_completos=True,
                dano_cliente=False)
    return SolicitudDevolucion(**{**base, **kw})


def test_apartar_caso_feliz():
    assert PUEDE_APARTAR.se_cumple(solicitud())


@pytest.mark.parametrize("spec, kw", [
    (ClienteActivoSpec(), dict(cliente_activo=False)),
    (AnticipoMinimoSpec(), dict(anticipo=M("199.99"))),
    (AnticipoMinimoSpec(), dict(anticipo=M("1000.01"))),
    (LimiteApartadosSpec(), dict(apartados_activos_cliente=3)),
    (SerieDisponibleSpec(), dict(estado_serie=EstadoSerie.RESERVADO)),
])
def test_cada_regla_de_apartar_falla_sola(spec, kw):
    s = solicitud(**kw)
    assert not spec.se_cumple(s)
    assert not PUEDE_APARTAR.se_cumple(s)


def test_limite_de_apartados_frontera_2_si_3_no():
    assert LimiteApartadosSpec().se_cumple(solicitud(apartados_activos_cliente=2))
    assert not LimiteApartadosSpec().se_cumple(solicitud(apartados_activos_cliente=3))


def test_composicion_or_y_not():
    s = solicitud(cliente_activo=False)
    assert (ClienteActivoSpec() | AnticipoMinimoSpec()).se_cumple(s)  # OR
    assert (~ClienteActivoSpec()).se_cumple(s)                         # NOT
    assert not (ClienteActivoSpec() & AnticipoMinimoSpec()).se_cumple(s)


def test_devolucion_plazo_frontera_dia_15_si_16_no():
    d15 = devolucion(hoy=date(2026, 10, 16))
    d16 = devolucion(hoy=date(2026, 10, 17))
    assert DentroDePlazoSpec().se_cumple(d15)
    assert not DentroDePlazoSpec().se_cumple(d16)


@pytest.mark.parametrize("kw", [
    dict(empaque_original=False), dict(accesorios_completos=False),
    dict(dano_cliente=True), dict(hoy=date(2026, 11, 30))])
def test_devolucion_no_elegible(kw):
    assert not DEVOLUCION_ELEGIBLE.se_cumple(devolucion(**kw))


def test_devolucion_elegible_y_specs_individuales():
    d = devolucion()
    assert DEVOLUCION_ELEGIBLE.se_cumple(d)
    assert EmpaqueCompletoSpec().se_cumple(d)
    assert not DanoClienteSpec().se_cumple(d)


# ---------- PoliticaDevolucionDomainService ----------
class _Auth(ISupervisorAuthDomainService):
    def validar(self, clave):
        return clave == "SUP-OK"


def autorizar(clave, **kw):
    return PoliticaDevolucionDomainService(_Auth()).autorizar(
        "V-1", "SN-0001", M("100.00"), devolucion(**kw), clave)


def test_politica_autoriza_con_supervisor_valido():
    nota, evento = autorizar("SUP-OK")
    assert nota.monto == M("100.00") and nota.autorizada_por == "SUP-OK"
    assert evento.nombre == "DevolucionAutorizadaEvent"


@pytest.mark.parametrize("clave", ["", "SUP-MAL"])
def test_politica_exige_supervisor(clave):
    with pytest.raises(NoAutorizado):
        autorizar(clave)


def test_politica_rechaza_por_regla_antes_de_pedir_supervisor():
    with pytest.raises(ReglaNegocioViolada, match="daño imputable"):
        autorizar("", dano_cliente=True)    # sin clave: rechaza por política


def test_politica_informa_todos_los_motivos():
    with pytest.raises(ReglaNegocioViolada) as e:
        autorizar("SUP-OK", empaque_original=False, hoy=date(2026, 12, 1))
    assert "plazo" in str(e.value) and "empaque" in str(e.value)
