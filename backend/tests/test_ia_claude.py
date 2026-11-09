"""Prueba el proveedor Claude SIN llamar a internet (se simula la respuesta de la API)."""
import json
from types import SimpleNamespace

import anthropic

from app.core.config import settings
from app.core.database import SessionLocal
from app.services import ia


class _FakeMessages:
    def create(self, **kwargs):
        assert "1020304050" not in kwargs["messages"][0]["content"]  # se anonimizó
        texto = json.dumps({"sugerencias": [
            {"codigo": "I10", "confianza": 0.9, "justificacion": "Cifras tensionales elevadas"},
            {"codigo": "Z999", "confianza": 0.8, "justificacion": "código inventado"},  # no existe -> se descarta
            {"codigo": "O149", "confianza": 0.5, "justificacion": "no pertinente en hombre"},  # se descarta
        ]})
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=texto)])


class _FakeClient:
    def __init__(self, **_):
        self.beta = SimpleNamespace(messages=_FakeMessages())


def test_claude_filtra_codigos(client, monkeypatch):
    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)
    monkeypatch.setattr(settings, "IA_PROVEEDOR", "claude")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-prueba")
    with SessionLocal() as db:
        r = ia.sugerir_cie10(db, "Paciente CC 1020304050 con presión alta", sexo="H", edad=60)
    assert r["proveedor"] == "claude"
    assert [s["codigo"] for s in r["sugerencias"]] == ["I10X"]


def test_claude_falla_usa_local(client, monkeypatch):
    class Roto:
        def __init__(self, **_):
            raise anthropic.APIConnectionError(request=None)

    monkeypatch.setattr(anthropic, "Anthropic", Roto)
    monkeypatch.setattr(settings, "IA_PROVEEDOR", "claude")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-prueba")
    with SessionLocal() as db:
        r = ia.sugerir_cie10(db, "presión alta", sexo="H", edad=60)
    assert r["proveedor"] == "local"
