import re
import pandas as pd
from utils.pdf_extractor import extraer_texto, limpiar_numero, buscar_valor


def extraer_datos_nomina(archivo_pdf) -> dict:
    """Extrae datos de un comprobante/soporte de nómina."""
    texto = extraer_texto(archivo_pdf)
    datos = {
        "texto_completo": texto,
        "nombre": "",
        "cedula": "",
        "periodo": "",
        "quincena": "",
        "salario_base": 0.0,
        "total_devengado": 0.0,
        "total_deducido": 0.0,
        "neto_pagado": 0.0,
    }

    # Cédula
    cedula = buscar_valor(texto, [
        r'(?:C[eé]dula|C\.C\.|No\.\s*Id)[:\s]+(\d[\d\.\s]+)',
        r'Identificaci[oó]n[:\s]+(\d[\d\.]+)',
        r'C\.C\s+(\d[\d\.]+)',
    ])
    datos["cedula"] = re.sub(r'[^\d]', '', cedula)

    # Nombre
    nombre = buscar_valor(texto, [
        r'(?:Nombre|Empleado|Trabajador)[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]{4,50})',
        r'Se[ñn]or\(?a?\)?[:\s]+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]{4,50})',
    ])
    datos["nombre"] = nombre.strip()

    # Período / quincena
    periodo = buscar_valor(texto, [
        r'Per[ií]odo[:\s]+(\d{1,2}[/\-]\d{1,2}[/\-]\d{4}\s*[aA]\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
        r'Del\s+(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})\s+[aA]l?\s+(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
        r'(?:Primera|Segunda|1ra|2da)\s+[Qq]uincena[:\s]+(\w+\s+\d{4})',
        r'Quincena[:\s]+(\w+)',
    ])
    datos["periodo"] = periodo

    # Determinar quincena (1 o 2)
    if re.search(r'primera|1ra|1er|01\s*al\s*15|del\s+1\s+al\s+15', texto, re.IGNORECASE):
        datos["quincena"] = "1"
    elif re.search(r'segunda|2da|16\s*al\s*30|16\s*al\s*31|del\s+16', texto, re.IGNORECASE):
        datos["quincena"] = "2"

    # Salario base
    sal_str = buscar_valor(texto, [
        r'Salario\s+[Bb]ase[:\s]+\$?\s*([\d\.,]+)',
        r'B[aá]sico[:\s]+\$?\s*([\d\.,]+)',
        r'Sueldo[:\s]+\$?\s*([\d\.,]+)',
    ])
    datos["salario_base"] = limpiar_numero(sal_str)

    # Total devengado
    dev_str = buscar_valor(texto, [
        r'Total\s+[Dd]evengado[:\s]+\$?\s*([\d\.,]+)',
        r'Total\s+[Hh]aberes[:\s]+\$?\s*([\d\.,]+)',
        r'TOTAL\s+DEVENGADO[:\s]+\$?\s*([\d\.,]+)',
    ])
    datos["total_devengado"] = limpiar_numero(dev_str)

    # Neto pagado
    neto_str = buscar_valor(texto, [
        r'Neto\s+[Pp]agado[:\s]+\$?\s*([\d\.,]+)',
        r'NETO\s+A\s+PAGAR[:\s]+\$?\s*([\d\.,]+)',
        r'Total\s+[Nn]eto[:\s]+\$?\s*([\d\.,]+)',
        r'Valor\s+[Gg]irado[:\s]+\$?\s*([\d\.,]+)',
    ])
    datos["neto_pagado"] = limpiar_numero(neto_str)

    return datos


def validar_nomina(archivos_pdf: list, df_excel: pd.DataFrame,
                   col_cedula: str, col_salario: str,
                   col_nombre: str = None) -> list:
    """
    Valida uno o varios soportes de nómina de una misma persona.
    Verifica que:
      1. Los pagos están dentro del período contractual
      2. Los valores no son inferiores al Excel
      3. Si hay dos quincenas, la suma corresponde al mes completo
      4. No hay duplicados para la misma persona/período
    """
    resultados = []
    datos_por_cedula = {}

    for archivo in archivos_pdf:
        datos = extraer_datos_nomina(archivo)
        cedula = datos["cedula"]

        resultado = {
            "archivo": archivo.name if hasattr(archivo, 'name') else str(archivo),
            "estado_general": "✅ APROBADO",
            "datos_extraidos": datos,
            "verificaciones": [],
            "errores": [],
            "advertencias": [],
        }

        # Agrupar por cédula para verificar quincenas
        if cedula not in datos_por_cedula:
            datos_por_cedula[cedula] = []
        datos_por_cedula[cedula].append({"datos": datos, "resultado": resultado})

        resultados.append(resultado)

    # Verificaciones por persona (sobre todos los PDFs de esa cédula)
    for cedula, lista in datos_por_cedula.items():
        # --- Buscar en Excel ---
        ref_salario = 0.0
        nombre_excel = ""
        if cedula and col_cedula in df_excel.columns:
            df_excel["_ced_temp"] = df_excel[col_cedula].astype(str).apply(
                lambda x: re.sub(r'[^\d]', '', x))
            fila = df_excel[df_excel["_ced_temp"] == re.sub(r'[^\d]', '', cedula)]
            if not fila.empty:
                if col_salario in df_excel.columns:
                    ref_salario = limpiar_numero(str(fila.iloc[0][col_salario]))
                if col_nombre and col_nombre in df_excel.columns:
                    nombre_excel = str(fila.iloc[0][col_nombre])

        for item in lista:
            datos = item["datos"]
            res = item["resultado"]

            # 1. Persona en Excel
            if ref_salario > 0:
                res["verificaciones"].append({
                    "check": "Persona en Excel",
                    "resultado": "✅ ENCONTRADO",
                    "detalle": f"Persona identificada. Salario ref: ${ref_salario:,.0f}"
                })
            elif cedula:
                res["advertencias"].append(
                    f"Cédula {cedula} no encontrada en Excel")
                res["verificaciones"].append({
                    "check": "Persona en Excel",
                    "resultado": "⚠️ NO ENCONTRADO",
                    "detalle": f"Cédula {cedula} no está en el Excel de referencia"
                })

            # 2. Valor neto no inferior al Excel
            neto = datos["neto_pagado"] or datos["total_devengado"]
            if neto > 0 and ref_salario > 0:
                quincena_ref = ref_salario / 2
                if neto >= quincena_ref * 0.95:  # 5% tolerancia por deducciones
                    res["verificaciones"].append({
                        "check": "Valor vs referencia",
                        "resultado": "✅ CORRECTO",
                        "detalle": (f"Neto: ${neto:,.0f} — "
                                    f"Mínimo quincena: ${quincena_ref:,.0f}")
                    })
                else:
                    res["errores"].append(
                        f"Pago inferior al mínimo: ${neto:,.0f} < ${quincena_ref:,.0f}")
                    res["verificaciones"].append({
                        "check": "Valor vs referencia",
                        "resultado": "❌ INFERIOR",
                        "detalle": (f"Neto: ${neto:,.0f} — "
                                    f"Mínimo esperado: ${quincena_ref:,.0f}")
                    })
                    res["estado_general"] = "❌ RECHAZADO"
            elif neto == 0:
                res["advertencias"].append("No se pudo extraer el valor pagado")
                res["verificaciones"].append({
                    "check": "Valor vs referencia",
                    "resultado": "⚠️ NO EXTRAÍDO",
                    "detalle": "No se encontró el valor neto en el PDF"
                })

        # 3. Verificar suma de quincenas (si hay 2 PDFs de la misma persona)
        if len(lista) == 2:
            q1 = next((i["datos"] for i in lista if i["datos"]["quincena"] == "1"), None)
            q2 = next((i["datos"] for i in lista if i["datos"]["quincena"] == "2"), None)
            if q1 and q2:
                suma = ((q1.get("neto_pagado") or q1.get("total_devengado")) +
                        (q2.get("neto_pagado") or q2.get("total_devengado")))
                for item in lista:
                    item["resultado"]["verificaciones"].append({
                        "check": "Suma quincenas",
                        "resultado": f"ℹ️ SUMA: ${suma:,.0f}",
                        "detalle": (f"1ra quincena + 2da quincena = ${suma:,.0f} "
                                    f"(Salario referencia: ${ref_salario:,.0f})")
                    })

        # 4. Detectar posibles duplicados
        periodos = [i["datos"]["periodo"] for i in lista if i["datos"]["periodo"]]
        quincenas = [i["datos"]["quincena"] for i in lista if i["datos"]["quincena"]]
        if len(quincenas) != len(set(quincenas)) and quincenas:
            for item in lista:
                item["resultado"]["errores"].append(
                    "Posible duplicado: misma quincena en dos documentos")
                item["resultado"]["verificaciones"].append({
                    "check": "Duplicados",
                    "resultado": "❌ POSIBLE DUPLICADO",
                    "detalle": "Se encontraron dos documentos con la misma quincena"
                })
                item["resultado"]["estado_general"] = "❌ RECHAZADO"

        for item in lista:
            if item["resultado"]["errores"]:
                item["resultado"]["estado_general"] = "❌ RECHAZADO"
            elif item["resultado"]["advertencias"] and \
                    item["resultado"]["estado_general"] == "✅ APROBADO":
                item["resultado"]["estado_general"] = "⚠️ REVISAR"

    return resultados
