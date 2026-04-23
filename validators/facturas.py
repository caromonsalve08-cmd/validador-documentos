import re
import pandas as pd
from utils.pdf_extractor import extraer_texto, extraer_tablas, limpiar_numero, buscar_valor, buscar_fecha


def extraer_datos_factura(archivo_pdf) -> dict:
    """Extrae datos clave de una factura en PDF."""
    texto = extraer_texto(archivo_pdf)
    tablas = extraer_tablas(archivo_pdf)

    datos = {
        "texto_completo": texto,
        "numero_factura": "",
        "fecha": "",
        "nit_proveedor": "",
        "nombre_proveedor": "",
        "valor_total": 0.0,
        "subtotal": 0.0,
        "iva": 0.0,
        "items": [],
    }

    # Número de factura
    num = buscar_valor(texto, [
        r'(?:Factura|Fac\.|No\.|N[úu]mero)[:\s#]+([A-Z\-\d]+)',
        r'FACTURA\s+(?:DE\s+VENTA\s+)?N[°oO\.]+\s*([A-Z\-\d]+)',
    ])
    datos["numero_factura"] = num

    # Fecha
    datos["fecha"] = buscar_fecha(texto)

    # NIT proveedor
    nit = buscar_valor(texto, [
        r'NIT[:\s]+(\d[\d\.\-]+)',
        r'Nit[:\s]+(\d[\d\.\-]+)',
    ])
    datos["nit_proveedor"] = re.sub(r'[^\d]', '', nit)

    # Nombre proveedor (primera línea grande del documento)
    nombre = buscar_valor(texto, [
        r'^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s&\.]{5,60}(?:S\.A\.S?|LTDA|S\.A|E\.S\.P\.?)?)',
        r'(?:Proveedor|Empresa|Razón\s+Social)[:\s]+([A-ZÁÉÍÓÚÑ][^\n]{4,60})',
    ])
    datos["nombre_proveedor"] = nombre.strip()

    # Valor total
    total_str = buscar_valor(texto, [
        r'TOTAL\s+(?:A\s+PAGAR|FACTURA|GENERAL)?[:\s]+\$?\s*([\d\.,]+)',
        r'(?:Gran\s+)?Total[:\s]+\$?\s*([\d\.,]+)',
        r'VALOR\s+TOTAL[:\s]+\$?\s*([\d\.,]+)',
    ])
    datos["valor_total"] = limpiar_numero(total_str)

    # Subtotal
    sub_str = buscar_valor(texto, [
        r'Subtotal[:\s]+\$?\s*([\d\.,]+)',
        r'SUBTOTAL[:\s]+\$?\s*([\d\.,]+)',
    ])
    datos["subtotal"] = limpiar_numero(sub_str)

    # IVA
    iva_str = buscar_valor(texto, [
        r'IVA[:\s]+\$?\s*([\d\.,]+)',
        r'(?:19|5)\s*%[:\s]+\$?\s*([\d\.,]+)',
    ])
    datos["iva"] = limpiar_numero(iva_str)

    # Items (de tablas extraídas)
    items_encontrados = []
    for tabla_info in tablas:
        for fila in tabla_info["datos"]:
            if fila and any(fila):
                fila_limpia = [str(c).strip() if c else "" for c in fila]
                if any(c for c in fila_limpia):
                    items_encontrados.append(fila_limpia)
    datos["items"] = items_encontrados[:20]  # máximo 20 ítems

    return datos


def validar_factura(archivo_pdf, df_excel: pd.DataFrame,
                    col_proveedor: str = None,
                    col_valor_max: str = None,
                    col_concepto: str = None,
                    orientaciones: dict = None) -> dict:
    """
    Valida una factura contra el Excel y las orientaciones de la entidad.
    """
    resultado = {
        "archivo": archivo_pdf.name if hasattr(archivo_pdf, 'name') else str(archivo_pdf),
        "estado_general": "✅ APROBADO",
        "datos_extraidos": {},
        "verificaciones": [],
        "errores": [],
        "advertencias": [],
    }

    if orientaciones is None:
        orientaciones = {}

    # 1. Extraer datos
    datos = extraer_datos_factura(archivo_pdf)
    resultado["datos_extraidos"] = datos

    # 2. Verificar que tiene datos básicos
    if not datos["numero_factura"]:
        resultado["advertencias"].append("No se extrajo número de factura")
    else:
        resultado["verificaciones"].append({
            "check": "Número de factura",
            "resultado": "✅ ENCONTRADO",
            "detalle": f"Factura N° {datos['numero_factura']}"
        })

    if not datos["fecha"]:
        resultado["advertencias"].append("No se extrajo fecha de la factura")
    else:
        resultado["verificaciones"].append({
            "check": "Fecha",
            "resultado": "✅ ENCONTRADO",
            "detalle": f"Fecha: {datos['fecha']}"
        })

    if datos["valor_total"] == 0:
        resultado["advertencias"].append("No se extrajo el valor total")
        resultado["verificaciones"].append({
            "check": "Valor total",
            "resultado": "⚠️ NO EXTRAÍDO",
            "detalle": "No se encontró el valor total en el PDF"
        })
    else:
        resultado["verificaciones"].append({
            "check": "Valor total",
            "resultado": "✅ ENCONTRADO",
            "detalle": f"Valor: ${datos['valor_total']:,.0f}"
        })

    # 3. Valor máximo por orientaciones
    valor_max = orientaciones.get("valor_maximo", 0)
    if valor_max > 0 and datos["valor_total"] > 0:
        if datos["valor_total"] <= valor_max:
            resultado["verificaciones"].append({
                "check": "Valor vs límite",
                "resultado": "✅ DENTRO DEL LÍMITE",
                "detalle": f"${datos['valor_total']:,.0f} ≤ límite ${valor_max:,.0f}"
            })
        else:
            resultado["errores"].append(
                f"Valor supera el límite: ${datos['valor_total']:,.0f} > ${valor_max:,.0f}")
            resultado["verificaciones"].append({
                "check": "Valor vs límite",
                "resultado": "❌ SUPERA LÍMITE",
                "detalle": f"${datos['valor_total']:,.0f} > límite ${valor_max:,.0f}"
            })
            resultado["estado_general"] = "❌ RECHAZADO"

    # 4. Verificar proveedor en Excel
    if col_proveedor and col_proveedor in df_excel.columns and datos["nit_proveedor"]:
        nit_limpio = re.sub(r'[^\d]', '', datos["nit_proveedor"])
        df_excel["_nit_temp"] = df_excel[col_proveedor].astype(str).apply(
            lambda x: re.sub(r'[^\d]', '', x))
        fila = df_excel[df_excel["_nit_temp"] == nit_limpio]

        if not fila.empty:
            resultado["verificaciones"].append({
                "check": "Proveedor",
                "resultado": "✅ REGISTRADO",
                "detalle": f"NIT {datos['nit_proveedor']} está en el Excel de referencia"
            })
            # Verificar valor máximo del Excel
            if col_valor_max and col_valor_max in df_excel.columns:
                valor_ref = limpiar_numero(str(fila.iloc[0][col_valor_max]))
                if valor_ref > 0 and datos["valor_total"] > valor_ref:
                    resultado["errores"].append(
                        f"Valor supera el máximo del contrato: "
                        f"${datos['valor_total']:,.0f} > ${valor_ref:,.0f}")
                    resultado["verificaciones"].append({
                        "check": "Valor vs contrato",
                        "resultado": "❌ SUPERA CONTRATO",
                        "detalle": (f"Factura: ${datos['valor_total']:,.0f} — "
                                    f"Máximo contrato: ${valor_ref:,.0f}")
                    })
                    resultado["estado_general"] = "❌ RECHAZADO"
        else:
            resultado["advertencias"].append(
                f"NIT {datos['nit_proveedor']} no encontrado en Excel")
            resultado["verificaciones"].append({
                "check": "Proveedor",
                "resultado": "⚠️ NO REGISTRADO",
                "detalle": f"NIT {datos['nit_proveedor']} no está en el Excel"
            })

    # 5. Verificar ítems según orientaciones
    conceptos_permitidos = orientaciones.get("conceptos_permitidos", [])
    if conceptos_permitidos and datos["items"]:
        texto_items = " ".join([" ".join(item) for item in datos["items"]]).lower()
        items_ok = any(c.lower() in texto_items for c in conceptos_permitidos)
        if items_ok:
            resultado["verificaciones"].append({
                "check": "Conceptos permitidos",
                "resultado": "✅ CORRECTO",
                "detalle": "Los ítems corresponden a conceptos autorizados"
            })
        else:
            resultado["advertencias"].append(
                "No se identificaron conceptos autorizados en los ítems")
            resultado["verificaciones"].append({
                "check": "Conceptos permitidos",
                "resultado": "⚠️ REVISAR ÍTEMS",
                "detalle": "No se encontraron los conceptos esperados"
            })

    if resultado["errores"]:
        resultado["estado_general"] = "❌ RECHAZADO"
    elif resultado["advertencias"] and resultado["estado_general"] == "✅ APROBADO":
        resultado["estado_general"] = "⚠️ REVISAR"

    return resultado
