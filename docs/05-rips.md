# 5. RIPS (Resolución 2275 de 2023)

## 5.1 ¿Qué son?

Los **Registros Individuales de Prestación de Servicios de Salud (RIPS)** reportan cada servicio prestado.
Con la Resolución 2275 de 2023 pasaron de archivos planos a **JSON**, y son **soporte obligatorio de la
factura electrónica de venta (FEV)** en salud. El JSON se envía junto con la factura al **Mecanismo Único de
Validación (MUV)** del Ministerio de Salud, que devuelve un **Código Único de Validación (CUV)**.

## 5.2 Flujo en XENTRA

1. El profesional **firma** la atención (solo se facturan atenciones cerradas).
2. Facturación entra a **RIPS / Facturación**, selecciona las atenciones y escribe el número de la factura.
3. **Generar y validar**: el sistema arma el JSON y revisa errores (diagnóstico principal, formato CIE-10,
   sexo, DIVIPOLA, atención firmada…).
4. **Descargar JSON** (solo si no hay errores).
5. Se envía al MUV con la factura (manual hoy; automático en la fase 1 de la hoja de ruta).

## 5.3 Estructura generada

```json
{
  "numDocumentoIdObligado": "900000000",
  "numFactura": "FEV1001",
  "tipoNota": null,
  "numNota": null,
  "usuarios": [{
    "tipoDocumentoIdentificacion": "CC",
    "numDocumentoIdentificacion": "79888777",
    "tipoUsuario": "04",
    "fechaNacimiento": "1958-11-02",
    "codSexo": "H",
    "codPaisResidencia": "170",
    "codMunicipioResidencia": "05001",
    "codZonaTerritorialResidencia": "02",
    "incapacidad": "NO",
    "consecutivo": 1,
    "codPaisOrigen": "170",
    "servicios": {
      "consultas": [{
        "codPrestador": "110010000001",
        "fechaInicioAtencion": "2026-11-09 13:10",
        "numAutorizacion": null,
        "codConsulta": "890201",
        "modalidadGrupoServicioTecSal": "01",
        "grupoServicios": "01",
        "codServicio": 328,
        "finalidadTecnologiaSalud": "44",
        "causaMotivoAtencion": "38",
        "codDiagnosticoPrincipal": "I10X",
        "codDiagnosticoRelacionado1": "R51X",
        "codDiagnosticoRelacionado2": null,
        "codDiagnosticoRelacionado3": null,
        "tipoDiagnosticoPrincipal": "01",
        "tipoDocumentoIdentificacion": "CC",
        "numDocumentoIdentificacion": "52123456",
        "vrServicio": 45000,
        "conceptoRecaudo": "05",
        "valorPagoModerador": 0,
        "numFEVPagoModerador": null,
        "consecutivo": 1
      }],
      "procedimientos": [ ... ]
    }
  }]
}
```

El código está en `backend/app/services/rips.py`.

## 5.4 Antes de producción (importante)

1. **Tablas de referencia**: los valores por defecto (`finalidadTecnologiaSalud`, `causaMotivoAtencion`,
   `modalidadGrupoServicioTecSal`, `grupoServicios`, `codServicio`, `conceptoRecaudo`, `tipoUsuario`) deben
   validarse contra las tablas vigentes publicadas en **SISPRO** (web.sispro.gov.co → Tablas de referencia).
   Lo ideal es cargarlas como catálogos y mostrarlas como listas desplegables (fase 1).
2. **Validar en el ambiente de pruebas del MUV** con facturas reales de prueba antes de facturar.
3. **Servicios faltantes**: urgencias, hospitalización, recién nacidos, medicamentos y otros servicios.
4. **Notas crédito/débito y ajustes** (`tipoNota`, `numNota`) ya están en el JSON, falta el flujo completo.
5. **Hora local**: las fechas se convierten a hora de Colombia (`ZONA_HORARIA=America/Bogota`).
