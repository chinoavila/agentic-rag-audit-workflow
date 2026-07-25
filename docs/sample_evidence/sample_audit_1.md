# Auditoría de Sistemas de Información - Empresa ACME Corp

**Fecha del Informe:** 2026-07-15  
**Auditor:** Equipo de Auditoría Interna  
**Periodo Auditado:** 2026-Q2  
**Clasificación:** Confidencial

---

## Ejecutivo

Se realizó una auditoría integral de los sistemas de información de ACME Corp durante el segundo trimestre de 2026. El alcance incluyó revisión de controles de acceso, integridad de datos, y cumplimiento normativo.

---

## Hallazgos Críticos

### 1. Control de Acceso Administrativo Débil (Severidad: ALTA)

**Descripción:**  
Se identificó que 15 usuarios cuentan con credenciales administrativas en la base de datos de producción sin revisión anual de acceso. Los registros de auditoría de base de datos muestran 4 cambios de esquema realizados por usuarios administrativos sin aprovación documentada.

**Evidencia:**
- Log de accesos: `db_audit_2026_06_30.log` líneas 1245-1340
- Usuarios administrativos sin revisión: `admin_users_2026-06-30.csv`
- Cambios de esquema no autorizados: `schema_changes_2026q2.sql` líneas 523-567

**Recomendación:**  
Implementar proceso de revisión trimestral de acceso administrativo. Requerir aprobación para cambios de esquema de producción.

---

## Hallazgos Moderados

### 2. Política de Contraseñas Desactualizada (Severidad: MEDIA)

**Descripción:**  
La política de contraseñas actual permite contraseñas de 6 caracteres y no requiere cambio periódico. 340 usuarios cuentan con contraseñas que no han sido actualizadas en más de 1 año.

**Evidencia:**
- Política actual: `password_policy_2026.txt`
- Análisis de antigüedad: `password_age_report_2026-06-30.xlsx`

---

## Cumplimiento Normativo

### SOX Compliance (Sarbanes-Oxley)

- **Hallazgo:** 2 de 8 controles de TI requeridos por SOX no cuentan con evidencia de testing trimestral.
- **Estado:** No Conforme
- **Plazo de Remediación:** 30 días

### ISO 27001

- **Hallazgo:** La política de clasificación de información fue actualizada sin comunicación formal a stakeholders.
- **Estado:** Parcialmente Conforme
- **Plazo de Remediación:** 45 días

---

## Conclusiones

ACME Corp debe tomar medidas inmediatas en el control de acceso administrativo. Los hallazgos de cumplimiento normativo son remediables dentro de 60 días si se asignan recursos adecuados.

**Clasificación General:** PARCIALMENTE CONFORME CON DEFICIENCIAS SIGNIFICATIVAS
