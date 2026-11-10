# Manuales de XENTRA DATACLINIC

| Manual | Para quién | Contenido |
|---|---|---|
| [01 – Manual de desarrollo](01-MANUAL-DESARROLLO.md) | Desarrolladores, líderes técnicos, interventoría, gerencia | Cómo se construyó paso a paso, normas y estándares en que se basa, por qué se tomó cada decisión, base de datos, seguridad, IA, interoperabilidad, pruebas, cómo extenderlo |
| [02 – Manual del administrador técnico](02-MANUAL-ADMINISTRADOR-TECNICO.md) | Ingeniero(a) de sistemas y usuario con rol admin | Instalación, configuración (.env completo), usuarios y roles, catálogos, integraciones (DIAN, MUV, IHCE/RDA, IA), seguridad, respaldos, monitoreo, tareas programadas, actualizaciones, solución de problemas |
| [03 – Manual de usuario](03-MANUAL-USUARIO.md) | Médicos, enfermería, estudiantes, admisiones, facturación, farmacia, laboratorio, auditores y roles técnicos | Paso a paso de cada pantalla según el rol, refrendo de estudiantes, soporte, contingencia, BI, módulos adicionales y glosario |
| [04 – Protocolos de seguridad](04-PROTOCOLOS-SEGURIDAD.md) | Dirección, oficial de seguridad, sistemas, jefes de área | Roles y por qué existen, gestión de usuarios, contraseñas y MFA, acceso a la HC, refrendo, validación de laboratorio, revisión del ledger, incidentes, respaldos, matriz de permisos, configuración y carga masiva de usuarios |

Documentos complementarios en `docs/`: normatividad (03), seguridad blockchain (04), RIPS (05), IA (06), hoja de ruta (07), análisis de mercado (10) y plan de continuidad (11).

## Versiones para imprimir o compartir

| Manual | Word (editable) | PDF |
|---|---|---|
| Desarrollo | [01-MANUAL-DESARROLLO.docx](word/01-MANUAL-DESARROLLO.docx) | [01-MANUAL-DESARROLLO.pdf](pdf/01-MANUAL-DESARROLLO.pdf) |
| Administrador técnico | [02-MANUAL-ADMINISTRADOR-TECNICO.docx](word/02-MANUAL-ADMINISTRADOR-TECNICO.docx) | [02-MANUAL-ADMINISTRADOR-TECNICO.pdf](pdf/02-MANUAL-ADMINISTRADOR-TECNICO.pdf) |
| Usuario por rol | [03-MANUAL-USUARIO.docx](word/03-MANUAL-USUARIO.docx) | [03-MANUAL-USUARIO.pdf](pdf/03-MANUAL-USUARIO.pdf) |
| Protocolos de seguridad | [04-PROTOCOLOS-SEGURIDAD.docx](word/04-PROTOCOLOS-SEGURIDAD.docx) | [04-PROTOCOLOS-SEGURIDAD.pdf](pdf/04-PROTOCOLOS-SEGURIDAD.pdf) |

Para regenerarlas después de editar los `.md` (requiere pandoc y LibreOffice):

```bash
cd docs/manuales
for f in 01-MANUAL-DESARROLLO 02-MANUAL-ADMINISTRADOR-TECNICO 03-MANUAL-USUARIO 04-PROTOCOLOS-SEGURIDAD; do
  pandoc "$f.md" -f gfm -t docx --toc --toc-depth=2 -o "word/$f.docx"
done
# El 04 lleva una matriz ancha: se convierte con el lector markdown para respetar el ancho de columnas
pandoc 04-PROTOCOLOS-SEGURIDAD.md -f markdown+task_lists-auto_identifiers+gfm_auto_identifiers --columns=60 \
  -t docx --toc --toc-depth=2 -o word/04-PROTOCOLOS-SEGURIDAD.docx
cd word && soffice --headless --convert-to pdf --outdir ../pdf *.docx
```
