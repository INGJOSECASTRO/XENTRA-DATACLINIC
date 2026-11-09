from app.services.cie10 import codigo_valido, formatear_codigo
from app.services.ia import alertas_clinicas
from app.services.texto import anonimizar, normalizar


def test_formato_codigo_colombiano():
    assert formatear_codigo("i10") == "I10X"
    assert formatear_codigo("E11.9") == "E119"
    assert formatear_codigo("J00.X") == "J00X"
    assert codigo_valido("I10X") and codigo_valido("E119")
    assert not codigo_valido("I10") and not codigo_valido("XX12")


def test_normalizar():
    assert normalizar("Hipertensión Arterial!") == "hipertension arterial"


def test_anonimizar_quita_datos_personales():
    texto = "María López CC 1020304050, tel 3001234567, correo maria@mail.com refiere tos"
    limpio = anonimizar(texto, ["María", "López"])
    assert "1020304050" not in limpio and "3001234567" not in limpio
    assert "maria@mail.com" not in limpio and "López" not in limpio
    assert "tos" in limpio


def test_alertas_signos_vitales():
    alertas = alertas_clinicas({"ta_sistolica": 185, "ta_diastolica": 110, "spo2": 88, "temperatura": 38.5}, 50)
    assert any("CRISIS" in a for a in alertas)
    assert any("Saturación" in a for a in alertas)
    assert any("Fiebre" in a for a in alertas)
    assert alertas_clinicas({"ta_sistolica": 120, "ta_diastolica": 80}, 40) == []
