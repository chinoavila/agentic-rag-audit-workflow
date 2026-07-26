# Informe de Auditoría

Plantilla estándar del proyecto (`template_id=auditoria_estandar`). Los únicos fragmentos que
la tool `generate_report` puede completar son los placeholders `{{...}}` de abajo: todo lo
demás (encabezados, esta tabla) es estructura fija y se copia tal cual al renderizado
(`app/reports/templates.py::render_template`, spec-012).

| Campo | Valor |
|---|---|
| Tipo de informe | Auditoría estándar |
| Plantilla | auditoria_estandar |

## Resumen Ejecutivo

{{resumen_ejecutivo}}

## Detalle de Hallazgos

{{hallazgos_detalle}}

## Recomendaciones

{{recomendaciones}}

---

*Informe generado automáticamente a partir de hallazgos registrados en el caso de auditoría.
Toda afirmación de la narrativa de arriba cita su evidencia de origen (spec-001), y este
documento requiere aprobación humana explícita antes de publicarse (spec-006).*
