import re
import pandas as pd
from utils.pdf_extractor import extraer_texto, limpiar_numero, buscar_valor


def extraer_datos_ss(archivo_pdf) -> dict:
    """Extrae datos clave de una planilla de seguridad social (PILA Colombia)."""
    texto = extraer_texto(archivo_pdf)
    tablas = extraer_tablas(archivo_pdf)
    datos = {
        "texto_completo": texto,
        "nombre": "",
        "cedula": "",
        "ibc": 0.0,
        "periodo": "",
        "estado_pago": "",
    }

    # ── Cédula ──────────────────────────────────────────────────────────────
    cedula = buscar_valor(texto, [
        r'CC\s*[-–]?\s*(\d[\d\.]{4,})',
        r'(?:C[eé]dula|C\.C\.|NIT|Documento|No\.\s*Id)[:\s]+(?:CC)?\s*(\d[\d\.\s]{4,})',
        r'Identificaci[oó]n[:\s]+(?:CC)?\s*(\d[\d\.]{4,})',
        r'N[úu]mero\s+de\s+Identificaci[oó]n[:\s]+(\d[\d\.]+)',
    ])
    datos["cedula"] = re.sub(r'[^\d]', '', cedula)

    # ── Nombre ───────────────────────────────────────────────────────────────
    nombre = buscar_valor(texto, [
        r'(?:Raz[oó]n\s+Social|Nombre\s+Aportante|Nombre\s+o\s+Raz[oó]n)[:\s]+([A-ZÁÉÍÓÚÑ][^\n]{4,60})',
        r'(?:Nombre|Apellidos\s+y\s+Nombres)[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]{4,60})',
    ])
    datos["nombre"] = nombre.strip()

    # ── IBC (Ingreso Base de Cotización) ─────────────────────────────────────
    # Estrategia 1: buscar en texto con distintos formatos PILA
    ibc_str = buscar_valor(texto, [
        # Enlace Operativo / SuAporte: "IBC Pensión ... $ 1.800.000"
        r'IBC\s+Pensi[oó]n\s+IBC\s+Salud[^\d]+([\d\.,]+)',
        r'IBC\s+Pensi[oó]n\s*[\n\r]+\s*\$?\s*([\d\.,]+)',
        # SOI / Bancolombia: columna "IBC AFP" seguida de valor
        r'IBC\s+AFP\s+Cotizaci[oó]n[^\d]+([\d\.,]+)',
        r'IBC\s+AFP[^\d\n]{0,10}([\d\.,]{5,})',
        # Compensar: "IBC AFP" en tabla
        r'IBC\s*AFP\s+([\d\.,]{5,})',
        # Genérico IBC seguido de número grande
        r'IBC[^\d\n]{0,5}([\d\.]{7,})',
        r'Ingreso\s+Base[^\d]+([\d\.,]+)',
        r'SALARIO[:\s]+\$?\s*([\d\.,]+)',
    ])

    # Estrategia 2: buscar en tablas extraídas
    if not ibc_str or limpiar_numero(ibc_str) == 0:
        for tabla_info in tablas:
            datos_tabla = tabla_info["datos"]
            for i, fila in enumerate(datos_tabla):
                fila_str = " ".join([str(c) for c in fila if c])
                if re.search(r'IBC', fila_str, re.IGNORECASE):
                    # Buscar en la misma fila o en la siguiente
                    for c in fila:
                        v = limpiar_numero(str(c)) if c else 0
                        if v >= 800000:  # IBC mínimo Colombia
                            ibc_str = str(c)
                            break
                    if ibc_str:
                        break
                    # Buscar en fila siguiente
                    if i + 1 < len(datos_tabla):
                        for c in datos_tabla[i + 1]:
                            v = limpiar_numero(str(c)) if c else 0
                            if v >= 800000:
                                ibc_str = str(c)
                                break
                if ibc_str:
                    break

    datos["ibc"] = limpiar_numero(ibc_str)

    # ── Período ──────────────────────────────────────────────────────────────
    periodo = buscar_valor(texto, [
        r'Per[ií]odo\s+(?:Cotizaci[oó]n|Salud|Pensi[oó]n)[:\s]+(\d{4}[-/]\d{2}|\w+\s+\d{4})',
        r'Per[ií]odo\s+Cotizaci[oó]n\s+(?:Otros)?[:\s]*([\w\s]+\d{4})',
        r'MES\s+(\w+)\s+A[ÑN]O\s+(\d{4})',
        r'(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(?:de\s+)?\d{4}',
        r'Per[ií]odo\s+(?:Servicio)?[:\s]+(\w+\s+de\s+\d{4})',
    ])
    datos["periodo"] = periodo

    # ── Estado de pago ───────────────────────────────────────────────────────
    if re.search(r'PAGAD[AO]|APROBAD[AO]|CANCELAD[AO]|PAGADO\s+\d{2}', texto, re.IGNORECASE):
        datos["estado_pago"] = "PAGADO"
    elif re.search(r'PENDIENTE|NO\s+PAGAD[AO]|RECHAZAD[AO]', texto, re.IGNORECASE):
        datos["estado_pago"] = "PENDIENTE"
    else:
        datos["estado_pago"] = "NO IDENTIFICADO"

    return datos


def validar_seguridad_social(archivo_pdf, df_excel: pd.DataFrame, col_cedula: str,
                              col_ibc: str, col_nombre: str = None) -> dict:
    """
    Valida una planilla de seguridad social contra el Excel de referencia.
    Retorna un dict con resultado y detalle de cada verificación.
    """
    resultado = {
        "archivo": archivo_pdf.name if hasattr(archivo_pdf, 'name') else str(archivo_pdf),
        "estado_general": "✅ APROBADO",
        "datos_extraidos": {},
        "verificaciones": [],
        "errores": [],
        "advertencias": [],
    }

    # 1. Extraer datos del PDF
    datos = extraer_datos_ss(archivo_pdf)
    resultado["datos_extraidos"] = datos

    # 2. Verificar estado de pago
    if datos["estado_pago"] == "PAGADO":
        resultado["verificaciones"].append({
            "check": "Estado de pago",
            "resultado": "✅ PAGADO",
            "detalle": "La planilla figura como pagada"
        })
    elif datos["estado_pago"] == "PENDIENTE":
        resultado["errores"].append("Planilla NO pagada o pendiente")
        resultado["verificaciones"].append({
            "check": "Estado de pago",
            "resultado": "❌ NO PAGADO",
            "detalle": "La planilla NO está pagada"
        })
        resultado["estado_general"] = "❌ RECHAZADO"
    else:
        resultado["advertencias"].append("No se pudo confirmar el estado de pago")
        resultado["verificaciones"].append({
            "check": "Estado de pago",
            "resultado": "⚠️ NO IDENTIFICADO",
            "detalle": "No se encontró el estado de pago en el documento"
        })

    # 3. Buscar persona en Excel por cédula
    if datos["cedula"] and col_cedula in df_excel.columns:
        cedula_limpia = re.sub(r'[^\d]', '', str(datos["cedula"]))
        df_excel["_ced_temp"] = df_excel[col_cedula].astype(str).apply(
            lambda x: re.sub(r'[^\d]', '', x))
        fila = df_excel[df_excel["_ced_temp"] == cedula_limpia]

        if fila.empty:
            resultado["advertencias"].append(
                f"Cédula {datos['cedula']} no encontrada en Excel de referencia")
            resultado["verificaciones"].append({
                "check": "Persona en Excel",
                "resultado": "⚠️ NO ENCONTRADO",
                "detalle": f"La cédula {datos['cedula']} no está en el Excel"
            })
        else:
            resultado["verificaciones"].append({
                "check": "Persona en Excel",
                "resultado": "✅ ENCONTRADO",
                "detalle": f"Persona identificada en el Excel de referencia"
            })

            # 4. Verificar IBC ≥ salario en Excel
            if col_ibc in df_excel.columns and datos["ibc"] > 0:
                ibc_referencia = limpiar_numero(str(fila.iloc[0][col_ibc]))
                if datos["ibc"] >= ibc_referencia:
                    resultado["verificaciones"].append({
                        "check": "IBC vs Excel",
                        "resultado": "✅ CORRECTO",
                        "detalle": (f"IBC planilla: ${datos['ibc']:,.0f} ≥ "
                                    f"IBC referencia: ${ibc_referencia:,.0f}")
                    })
                else:
                    resultado["errores"].append(
                        f"IBC inferior al esperado: ${datos['ibc']:,.0f} < ${ibc_referencia:,.0f}")
                    resultado["verificaciones"].append({
                        "check": "IBC vs Excel",
                        "resultado": "❌ IBC INFERIOR",
                        "detalle": (f"IBC planilla: ${datos['ibc']:,.0f} — "
                                    f"Mínimo requerido: ${ibc_referencia:,.0f}")
                    })
                    resultado["estado_general"] = "❌ RECHAZADO"
            elif datos["ibc"] == 0:
                resultado["advertencias"].append("No se pudo extraer el IBC del documento")
                resultado["verificaciones"].append({
                    "check": "IBC vs Excel",
                    "resultado": "⚠️ NO EXTRAÍDO",
                    "detalle": "No se encontró el IBC en el PDF"
                })

    if resultado["errores"]:
        resultado["estado_general"] = "❌ RECHAZADO"
    elif resultado["advertencias"] and resultado["estado_general"] != "❌ RECHAZADO":
        resultado["estado_general"] = "⚠️ REVISAR"

    return resultado
