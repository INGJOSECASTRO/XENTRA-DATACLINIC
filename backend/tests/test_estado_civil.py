"""Lección 5: estado civil del paciente (Res. 1995 de 1999, datos de identificación del usuario)."""
PACIENTE = {
    "tipo_documento": "CC", "numero_documento": "55667788", "primer_nombre": "Rosa",
    "primer_apellido": "Prueba", "fecha_nacimiento": "1980-01-15", "sexo": "M",
    "autoriza_tratamiento_datos": True,
}


def test_guarda_estado_civil(client, medico):
    r = client.post("/api/pacientes", json={**PACIENTE, "estado_civil": "union_libre"}, headers=medico)
    assert r.status_code == 201, r.text
    assert r.json()["estado_civil"] == "union_libre"          # se guardó y se devuelve


def test_rechaza_estado_civil_invalido(client, medico):
    r = client.post("/api/pacientes", json={**PACIENTE, "numero_documento": "55667799", "estado_civil": "complicado"},
                    headers=medico)
    assert r.status_code == 422                                   # solo valores de la lista oficial


def test_estado_civil_es_opcional(client, medico):
    r = client.post("/api/pacientes", json={**PACIENTE, "numero_documento": "55667700"}, headers=medico)
    assert r.status_code == 201 and r.json()["estado_civil"] is None
