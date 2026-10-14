# Guía y Checklist de Entregabilidad & Marco Legal para Cold Outreach

Guía práctica para garantizar que los correos de prospección lleguen a la bandeja de entrada principal (inbox) y cumplan con las normativas locales e internacionales de protección de datos.

---

## 1. Checklist Técnico de Entregabilidad

### A. Dominio Secundario Dedicado
- [ ] **Aislar el dominio principal:** Nunca realizar envíos de prospección en frío desde el dominio raíz de tu empresa (`tudominio.com`). Una eventual penalización de reputación afectaría los correos corporativos y transaccionales del día a día.
- [ ] **Adquirir dominios alternativos:** Comprar 1 o 2 dominios secundarios similares (ej. `tudominiob2b.com`, `get-tudominio.com` o `tudominioapp.com`).
- [ ] **Redirección web:** Configurar un redireccionamiento 301 del dominio secundario hacia el sitio web principal para dar confianza al prospecto que busque la URL en el navegador.

### B. Autenticación DNS Obligatoria
- [ ] **SPF (Sender Policy Framework):** Registro TXT que autoriza a los servidores de envío.  
  Ejemplo: `v=spf1 include:_spf.google.com ~all`
- [ ] **DKIM (DomainKeys Identified Mail):** Firma criptográfica con clave de 2048 bits generada por el proveedor de correo (Google Workspace, Microsoft 365, etc.) para validar que el contenido no fue manipulado.
- [ ] **DMARC (Domain-based Message Authentication):** Política de alineación SPF/DKIM.  
  Comenzar en modo monitoreo:  
  `v=DMARC1; p=none; rua=mailto:dmarc-reports@tudominiob2b.com; pct=100; sp=none; aspf=r; adkim=r`  
  *Una vez estabilizada la reputación (3-4 semanas), escalar a `p=quarantine` o `p=reject`.*
- [ ] **Custom Tracking Domain (CNAME):** Configurar un subdominio propio (ej. `track.tudominiob2b.com`) para enlaces de seguimiento, evitando dominios de rastreo compartidos que puedan estar en listas negras.
- [ ] **Registros MX válidos:** Comprobar que el dominio secundario tenga configurada la recepción de correo (los filtros antispam descartan dominios sin registros MX).

### C. Calentamiento Progresivo de Buzones (Warmup)
- [ ] **Periodo de maduración previo:** Mantener los buzones nuevos en calentamiento automatizado durante un mínimo de **14 a 21 días** antes de iniciar cualquier campaña real.
- [ ] **Régimen de calentamiento:** Iniciar con 5 correos diarios y aumentar gradualmente hasta alcanzar un volumen balanceado, simulando conversaciones humanas (aperturas, respuestas y marcados como "no es spam").
- [ ] **Warmup continuo:** Mantener el sistema de calentamiento activo al 25%-30% del volumen diario total mientras duren las campañas comerciales.

### D. Límites Diarios y Rotación de Buzones
- [ ] **Tope por buzón:** No exceder de **30 a 50 correos fríos diarios por buzón** (incluyendo seguimientos).
- [ ] **Inbox Rotation (Rotación de cuentas):** Si necesitas enviar 300 correos al día, distribúyelos entre 6 a 8 buzones distintos en 2 o 3 dominios secundarios.
- [ ] **Espaciado temporal:** Configurar un intervalo aleatorio entre envíos (mínimo de 3 a 8 minutos entre mensajes consecutivos) para evitar ráfagas instantáneas que activen filtros de spam.

### E. Verificación y Limpieza de Listas (Zero-Bounce Policy)
- [ ] **Comprobación de listas:** Verificar siempre la sintaxis y existencia de registros MX antes del cargue (incorporado en el motor de scoring del proyecto 08).
- [ ] **Umbral crítico de rebote:** Mantener la tasa de rebotes duros (*hard bounces*) estrictamente **por debajo del 2%**. Superar el 3% es la causa principal de suspensión en Google Workspace y Microsoft 365.

---

## 2. Marco Legal y Cumplimiento Normativo

### A. Colombia: Ley 1581 de 2012 y Decreto 1377 de 2013 (Habeas Data)
- **Ámbito comercial B2B:** La legislación colombiana distingue entre datos personales privados de personas naturales y datos de contacto comercial público de personas jurídicas y profesionales.
- **Canales públicos:** Los datos de contacto institucionales publicados en registros mercantiles, sitios web corporativos y directorios abiertos tienen carácter público para fines informativos y comerciales.
- **Deber de información:** En la primera comunicación debe quedar claro quién escribe, a qué empresa representa y con qué finalidad comercial.
- **Mecanismo de revocatoria / Baja:** Debe existir una opción directa, gratuita y sencilla para que el titular manifieste su deseo de no ser contactado nuevamente (ej. responder "baja"). Una vez recibida la solicitud, debe eliminarse de inmediato de la base de datos activa.

### B. Estados Unidos: CAN-SPAM Act (15 U.S.C. 7701)
- **Encabezados precisos:** La información de cabecera ("De", "Para", "Responder a" y dominio de origen) debe ser técnicamente verídica e identificar claramente al remitente.
- **Líneas de asunto transparentes:** El asunto debe guardar relación directa con el contenido del mensaje; no usar trucos engañosos (como falsos prefijos `Re:` o `Fwd:` sin comunicación previa real).
- **Identificación comercial:** Debe ser identificable como comunicación comercial o de propuesta de servicios.
- **Dirección física obligatoria:** Incluir una dirección física postal válida de la empresa en el pie del correo (puede ser oficina física o casilla postal registrada).
- **Mecanismo de Opt-Out:** Incluir un enlace o instrucción clara para darse de baja. Toda solicitud de baja debe procesarse en un plazo máximo de **10 días hábiles** y no puede compartirse ni transferirse a terceros.

### C. Unión Europea: GDPR (Reglamento UE 2016/679) y Directiva ePrivacy
- **Base jurídica (Interés Legítimo):** Para prospección B2B en la UE, la base jurídica aceptada es el **Interés Legítimo** (*Legitimate Interest*, Art. 6.1.f del GDPR).
- **Test de sopesamiento (LIA):** El servicio ofrecido debe tener una vinculación lógica, profesional y relevante con el cargo y sector del destinatario. No se admite el envío indiscriminado de servicios no afines.
- **Derecho de oposición (Art. 21 GDPR):** El prospecto tiene derecho incondicional a oponerse al tratamiento de sus datos con fines de prospección comercial directa en cualquier momento.
- **Efectividad inmediata de la baja:** El cese del contacto debe ser inmediato y definitivo. Se recomienda mantener una lista de supresión (*suppression list*) únicamente con fines de auditoría para garantizar que nunca vuelva a ser contactado.
- **Aviso de privacidad:** Incluir un enlace directo a la política de privacidad donde se informe sobre el ejercicio de derechos ARCO (Acceso, Rectificación, Cancelación y Oposición).
