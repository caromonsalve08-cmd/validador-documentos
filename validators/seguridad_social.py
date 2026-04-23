import re
import pandas as pd
from utils.pdf_extractor import extraer_texto, limpiar_numero, buscar_valor


def extraer_datos_ss(archivo_pdf) -> dict:
    """Extrae datos clave de una planilla de seguridad social."""
    texto = extraer_texto(archivo_pdf)
    datos = {
        "texto_completo": texto,
        "nombre": "",
        "cedula": "",
        "ibc": 0.0,
        "periodo": "",
        "estado_pago": "",
        "eps": "",
        "pension": "",
        "arl": "",
    }

    # Cédula / identificación
    cedula = buscar_valor(texto, [
        r'(?:C[eé]dula|C\.C\.|NIT|No\.\s*Id)[:\s]+(\d[\d\.\s]+)',
        r'Identificaci[oó]n[:\s]+(\d[\d\.]+)',
    ])
    datos["cedula"] = re.sub(r'[^\d]', '', cedula)

    # Nombre
    nombre = buscar_valor(texto, [
        r'(?:Nombre|Afiliado|Empleado)[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]{4,50})',
        r'(?:Trabajador)[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]{4,50})',
    ])
    datos["nombre"] = nombre.strip()

    # IBC (Ingreso Base de Cotización)
    ibc_str = buscar_valor(texto, [
        r'IBC[:\s]+\$?\s*([\d\.,]+)',
        r'Ingreso\s+Base[:\s]+\$?\s*([\d\.,]+)',
        r'Base\s+Cotizaci[oó]n[:\s]+\$?\s*([\d\.,]+)',
    ])
    datos["ibc"] = limpiar_numero(ibc_str)

    # Período
    periodo = buscar_valor(texto, [
        r'Per[ií]odo[:\s]+(\d{4}[/\-]\d{1,2}|\d{1,2}[/\-]\d{4})',
        r'Mes[:\s]+(\w+\s+\d{4})',
        r'(?:Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre)\s+\d{4}',
    ])
    datos["periodo"] = periodo

    # Estado de pago
    if re.search(r'PAGAD[AO]|APROBAD[AO]|CANCELAD[AO]', texto, re.IGNORECASE):
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
