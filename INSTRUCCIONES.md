# ✅ Validador de Documentos – Instrucciones de uso

## ¿Qué hace esta herramienta?
Valida automáticamente tres tipos de documentos PDF comparándolos contra un Excel de referencia:
- **Seguridad Social**: verifica que esté pagada y que el IBC ≥ al Excel
- **Nómina**: verifica períodos, valores, quincenas y duplicados
- **Facturas**: verifica valores, fechas e ítems según orientaciones

---

## OPCIÓN A — Publicar GRATIS en internet (recomendado para el equipo)

### Paso 1: Crear cuenta en GitHub (gratis)
1. Ve a https://github.com y crea una cuenta
2. Crea un repositorio nuevo llamado `validador-documentos`
3. Sube todos los archivos de esta carpeta al repositorio

### Paso 2: Publicar en Streamlit Cloud (gratis)
1. Ve a https://streamlit.io/cloud
2. Inicia sesión con tu cuenta de GitHub
3. Haz clic en "New app"
4. Selecciona el repositorio `validador-documentos`
5. Archivo principal: `app.py`
6. Haz clic en "Deploy"

En 2-3 minutos tendrás un **link público** que puedes compartir con todo el equipo.

---

## OPCIÓN B — Correr en tu computador (sin internet)

### Requisitos
- Tener Python instalado (https://python.org)

### Instalación (solo la primera vez)
Abre la terminal (cmd) en la carpeta del proyecto y ejecuta:
```
pip install -r requirements.txt
```

### Ejecutar
```
streamlit run app.py
```
Se abrirá automáticamente en el navegador en http://localhost:8501

---

## Cómo usar la herramienta

### 1. Pestaña "Seguridad Social"
- Sube uno o varios PDFs de planillas de seguridad social
- Sube el Excel con las columnas: Cédula, IBC/Salario
- Selecciona qué columna es la cédula y cuál es el IBC
- Clic en "Validar"

### 2. Pestaña "Nómina"
- Sube los PDFs de soportes de nómina (pueden ser varios de la misma persona)
- Sube el Excel con Cédula y Salario de referencia
- La herramienta detecta automáticamente si son quincenas y las suma

### 3. Pestaña "Facturas"
- Sube los PDFs de facturas
- Sube el Excel con proveedores/contratos (opcional)
- Ingresa el valor máximo por factura y los conceptos permitidos
- Clic en "Validar"

### 4. Pestaña "Reporte General"
- Ve el resumen de todas las validaciones
- Descarga el reporte en Excel con semáforos por documento

---

## Estructura de archivos
```
ValidadorDocs/
├── app.py                    ← Aplicación principal
├── requirements.txt          ← Librerías necesarias
├── INSTRUCCIONES.md          ← Este archivo
├── validators/
│   ├── seguridad_social.py   ← Lógica validación SS
│   ├── nomina.py             ← Lógica validación nómina
│   └── facturas.py           ← Lógica validación facturas
└── utils/
    └── pdf_extractor.py      ← Extracción de texto PDF
```

---

## Personalización
Si necesitas ajustar las reglas de validación, los archivos clave son:
- `validators/seguridad_social.py` → reglas de IBC y pago
- `validators/nomina.py` → reglas de quincenas y salarios
- `validators/facturas.py` → reglas de facturas y proveedores
