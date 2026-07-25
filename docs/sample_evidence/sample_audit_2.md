# Auditoría de Seguridad de Datos - División Financiera

**Fecha del Informe:** 2026-06-20  
**Auditor:** Especialista de Seguridad de Información  
**Periodo Auditado:** 2026-Q2  
**Clasificación:** Confidencial - Uso Interno Solamente

---

## Resumen Ejecutivo

Auditoría de seguridad enfocada en sistemas de la División Financiera, incluyendo bases de datos de clientes, información transaccional y controles de encriptación.

---

## Controles de Encriptación

### Datos en Tránsito

**Hallazgo:** Todos los servicios cuentan con TLS 1.2 o superior.  
**Estado:** ✓ CONFORME

### Datos en Reposo

**Hallazgo:** 85% de bases de datos cuentan con encriptación AES-256. 3 instancias heredadas no están encriptadas.  
**Servidor Afectado:**
- `fin-db-legacy-01`: 2.4 GB de datos sin encriptación
- `fin-db-legacy-02`: 1.8 GB de datos sin encriptación
- `reports-archive-01`: 450 MB de archivos sin encriptación

**Severidad:** CRÍTICA  
**Plazo de Remediación:** 15 días

---

## Acceso a Información Sensible

### Personal Autorizado

Se revisaron 127 usuarios con acceso a información de cliente (PII). Se encontró:

- 98 usuarios: acceso justificado
- 19 usuarios: acceso justificado pero requiere reevaluación (cambios de rol)
- 10 usuarios: **acceso no autorizado o no justificado**

**Recomendación Inmediata:** Desactivar acceso para 10 usuarios dentro de 48 horas.

---

## Cumplimiento PCI DSS (Datos de Tarjeta de Crédito)

| Control | Estado | Observaciones |
|---------|--------|--------------|
| Firewalls configurados | ✓ Conforme | Última revisión: 2026-06-15 |
| Encriptación en tránsito | ✓ Conforme | TLS 1.3 en producción |
| Cambio de contraseña por defecto | ⚠ Parcial | 2 servidores aún por procesar |
| Logs de acceso auditados | ✓ Conforme | Retención: 90 días |
| Política de acceso documentada | ✗ No Conforme | Falta formalización de matriz RACI |

---

## Evidencia de Pruebas Penetración

Se realizó prueba de penetración externa limitada (Scope: API Gateway).

**Vulnerabilidades Encontradas:**
1. **SQL Injection (Baja):** Endpoint `/api/transactions?filter=` vulnerable a SQL injection. Remediado en versión 2.3.1
2. **Información Disclosure (Media):** Error 500 expone stack traces. Se requiere review de error handling.

---

## Próximos Pasos

1. Remediación de encriptación de datos en reposo (CRÍTICA)
2. Revisión de acceso de usuarios de PII (ALTA)
3. Formalización de documentación PCI DSS (MEDIA)

**Fecha Próxima Auditoría:** 2026-09-15
