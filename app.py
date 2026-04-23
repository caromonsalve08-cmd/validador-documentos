import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime

# ── Configuración de la página ──────────────────────────────────────────────
st.set_page_config(
    page_title="Validador de Documentos",
    page_icon="✅",
    layout="wide",
)

# ── Estilos ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {font-size:1.8rem; font-weight:700; color:#1e3a5f; margin-bottom:0.2rem;}
    .sub-title  {font-size:1rem;  color:#64748b; margin-bottom:1.5rem;}
    .card-ok    {background:#dcfce7; border-left:4px solid #16a34a;
                 padding:0.7rem 1rem; border-radius:6px; margin:0.4rem 0;}
    .card-error {background:#fee2e2; border-left:4px solid #dc2626;
                 padding:0.7rem 1rem; border-radius:6px; margin:0.4rem 0;}
    .card-warn  {background:#fef9c3; border-left:4px solid #ca8a04;
                 padding:0.7rem 1rem; border-radius:6px; margin:0.4rem 0;}
    .badge-ok   {background:#16a34a; color:white; padding:2px 10px;
                 border-radius:12px; font-size:0.8rem; font-weight:600;}
    .badge-err  {background:#dc2626; color:white; padding:2px 10px;
                 border-radius:12px; font-size:0.8rem; font-weight:600;}
    .badge-warn {background:#ca8a04; color:white; padding:2px 10px;
                 border-radius:12px; font-size:0.8rem; font-weight:600;}
</style>
""", unsafe_allow_html=True)


# ── Importar validadores ─────────────────────────────────────────────────────
try:
    from validators.seguridad_social import validar_seguridad_social
    from validators.nomina import validar_nomina
    from validators.facturas import validar_factura
    VALIDADORES_OK = True
except ImportError as e:
    VALIDADORES_OK = False
    st.error(f"Error al importar validadores: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────
def mostrar_resultado(res: dict):
    """Muestra el resultado de validación de un documento."""
    estado = res.get("estado_general", "")
    archivo = res.get("archivo", "")

    if "APROBADO" in estado:
        st.markdown(f'<div class="card-ok"><b>{archivo}</b> — '
                    f'<span class="badge-ok">{estado}</span></div>',
                    unsafe_allow_html=True)
    elif "RECHAZADO" in estado:
        st.markdown(f'<div class="card-error"><b>{archivo}</b> — '
                    f'<span class="badge-err">{estado}</span></div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="card-warn"><b>{archivo}</b> — '
                    f'<span class="badge-warn">{estado}</span></div>',
                    unsafe_allow_html=True)

    with st.expander("Ver detalle de verificaciones"):
        for v in res.get("verificaciones", []):
            st.write(f"**{v['check']}**: {v['resultado']}")
            if v.get("detalle"):
                st.caption(v["detalle"])
        if res.get("errores"):
            st.error("**Errores encontrados:**\n" +
                     "\n".join(f"• {e}" for e in res["errores"]))
        if res.get("advertencias"):
            st.warning("**Advertencias:**\n" +
                       "\n".join(f"• {a}" for a in res["advertencias"]))
        datos = res.get("datos_extraidos", {})
        if datos:
            with st.expander("Ver datos extraídos del PDF"):
                for k, v in datos.items():
                    if k != "texto_completo" and k != "items" and v:
                        st.write(f"**{k}**: {v}")


def cargar_excel(archivo) -> tuple[pd.DataFrame, list]:
    """Carga un Excel y retorna el DataFrame y lista de columnas."""
    try:
        df = pd.read_excel(archivo)
        df.columns = [str(c).strip() for c in df.columns]
        return df, list(df.columns)
    except Exception as e:
        st.error(f"Error al leer Excel: {e}")
        return pd.DataFrame(), []


def resumen_resultados(resultados: list) -> dict:
    aprobados = sum(1 for r in resultados if "APROBADO" in r.get("estado_general", ""))
    rechazados = sum(1 for r in resultados if "RECHAZADO" in r.get("estado_general", ""))
    revisar = sum(1 for r in resultados if "REVISAR" in r.get("estado_general", ""))
    return {"total": len(resultados), "aprobados": aprobados,
            "rechazados": rechazados, "revisar": revisar}


# ════════════════════════════════════════════════════════════════════════════
# ENCABEZADO
# ════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="main-title">✅ Validador de Documentos</div>',
            unsafe_allow_html=True)
st.markdown('<div class="sub-title">Verificación automática de '
            'facturas, seguridad social y nómina</div>',
            unsafe_allow_html=True)

if not VALIDADORES_OK:
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# TABS PRINCIPALES
# ════════════════════════════════════════════════════════════════════════════
tab_ss, tab_nom, tab_fac, tab_reporte = st.tabs([
    "📋 Seguridad Social",
    "💰 Nómina",
    "🧾 Facturas",
    "📊 Reporte General",
])

# Almacenar resultados en session_state
if "resultados_ss" not in st.session_state:
    st.session_state.resultados_ss = []
if "resultados_nom" not in st.session_state:
    st.session_state.resultados_nom = []
if "resultados_fac" not in st.session_state:
    st.session_state.resultados_fac = []


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — SEGURIDAD SOCIAL
# ════════════════════════════════════════════════════════════════════════════
with tab_ss:
    st.subheader("Validación de Planillas de Seguridad Social")
    st.info("Verifica que la planilla esté **pagada** y que el **IBC sea igual o superior** al registrado en el Excel.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("**1. Sube los PDFs de seguridad social**")
        pdfs_ss = st.file_uploader(
            "Planillas de seguridad social (PDF)",
            type=["pdf"], accept_multiple_files=True,
            key="upload_ss"
        )

    with col2:
        st.markdown("**2. Sube el Excel de referencia**")
        excel_ss = st.file_uploader(
            "Excel con cédulas e IBC de referencia",
            type=["xlsx", "xls"],
            key="excel_ss"
        )

    df_ss = pd.DataFrame()
    cols_ss = []
    if excel_ss:
        df_ss, cols_ss = cargar_excel(excel_ss)
        if not df_ss.empty:
            st.success(f"Excel cargado: {len(df_ss)} registros, {len(cols_ss)} columnas")
            with st.expander("Vista previa del Excel"):
                st.dataframe(df_ss.head(5))

    if not df_ss.empty and cols_ss:
        st.markdown("**3. Mapea las columnas del Excel**")
        c1, c2 = st.columns(2)
        col_ced_ss = c1.selectbox("Columna de Cédula",
                                   options=cols_ss, key="col_ced_ss",
                                   index=next((i for i, c in enumerate(cols_ss)
                                               if "ced" in c.lower() or "id" in c.lower()), 0))
        col_ibc_ss = c2.selectbox("Columna de IBC / Salario",
                                   options=cols_ss, key="col_ibc_ss",
                                   index=next((i for i, c in enumerate(cols_ss)
                                               if "ibc" in c.lower() or "salario" in c.lower()), 0))

    if pdfs_ss and not df_ss.empty:
        if st.button("🔍 Validar Seguridad Social", type="primary", key="btn_ss"):
            resultados = []
            bar = st.progress(0)
            for i, pdf in enumerate(pdfs_ss):
                with st.spinner(f"Procesando {pdf.name}..."):
                    res = validar_seguridad_social(
                        pdf, df_ss,
                        col_cedula=col_ced_ss,
                        col_ibc=col_ibc_ss,
                    )
                    resultados.append(res)
                bar.progress((i + 1) / len(pdfs_ss))

            st.session_state.resultados_ss = resultados
            bar.empty()

            # Resumen
            rsm = resumen_resultados(resultados)
            m1, m2, m3 = st.columns(3)
            m1.metric("✅ Aprobados", rsm["aprobados"])
            m2.metric("❌ Rechazados", rsm["rechazados"])
            m3.metric("⚠️ Para revisar", rsm["revisar"])

            st.divider()
            for res in resultados:
                mostrar_resultado(res)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — NÓMINA
# ════════════════════════════════════════════════════════════════════════════
with tab_nom:
    st.subheader("Validación de Soportes de Nómina")
    st.info("Verifica períodos, valores no inferiores al Excel, suma de quincenas y duplicados.")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("**1. Sube los PDFs de nómina**")
        pdfs_nom = st.file_uploader(
            "Soportes de nómina / quincenas (PDF)",
            type=["pdf"], accept_multiple_files=True,
            key="upload_nom"
        )
    with col2:
        st.markdown("**2. Sube el Excel de referencia**")
        excel_nom = st.file_uploader(
            "Excel con cédulas y salarios de referencia",
            type=["xlsx", "xls"],
            key="excel_nom"
        )

    df_nom = pd.DataFrame()
    cols_nom = []
    if excel_nom:
        df_nom, cols_nom = cargar_excel(excel_nom)
        if not df_nom.empty:
            st.success(f"Excel cargado: {len(df_nom)} registros")
            with st.expander("Vista previa del Excel"):
                st.dataframe(df_nom.head(5))

    if not df_nom.empty and cols_nom:
        st.markdown("**3. Mapea las columnas**")
        c1, c2, c3 = st.columns(3)
        col_ced_nom = c1.selectbox("Columna Cédula",
                                    options=cols_nom, key="col_ced_nom",
                                    index=next((i for i, c in enumerate(cols_nom)
                                                if "ced" in c.lower() or "id" in c.lower()), 0))
        col_sal_nom = c2.selectbox("Columna Salario",
                                    options=cols_nom, key="col_sal_nom",
                                    index=next((i for i, c in enumerate(cols_nom)
                                                if "sal" in c.lower() or "salar" in c.lower()), 0))
        col_nom_nom = c3.selectbox("Columna Nombre (opcional)",
                                    options=["(ninguna)"] + cols_nom, key="col_nom_nom")

    if pdfs_nom and not df_nom.empty:
        if st.button("🔍 Validar Nómina", type="primary", key="btn_nom"):
            with st.spinner("Procesando documentos de nómina..."):
                nombre_col = None if col_nom_nom == "(ninguna)" else col_nom_nom
                resultados = validar_nomina(
                    pdfs_nom, df_nom,
                    col_cedula=col_ced_nom,
                    col_salario=col_sal_nom,
                    col_nombre=nombre_col,
                )

            st.session_state.resultados_nom = resultados

            rsm = resumen_resultados(resultados)
            m1, m2, m3 = st.columns(3)
            m1.metric("✅ Aprobados", rsm["aprobados"])
            m2.metric("❌ Rechazados", rsm["rechazados"])
            m3.metric("⚠️ Para revisar", rsm["revisar"])

            st.divider()
            for res in resultados:
                mostrar_resultado(res)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — FACTURAS
# ════════════════════════════════════════════════════════════════════════════
with tab_fac:
    st.subheader("Validación de Facturas")
    st.info("Extrae valores, fechas e ítems, y los compara contra el Excel y las orientaciones de la entidad.")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("**1. Sube los PDFs de facturas**")
        pdfs_fac = st.file_uploader(
            "Facturas en PDF",
            type=["pdf"], accept_multiple_files=True,
            key="upload_fac"
        )
    with col2:
        st.markdown("**2. Sube el Excel de referencia**")
        excel_fac = st.file_uploader(
            "Excel con proveedores y contratos",
            type=["xlsx", "xls"],
            key="excel_fac"
        )

    df_fac = pd.DataFrame()
    cols_fac = []
    if excel_fac:
        df_fac, cols_fac = cargar_excel(excel_fac)
        if not df_fac.empty:
            st.success(f"Excel cargado: {len(df_fac)} registros")
            with st.expander("Vista previa del Excel"):
                st.dataframe(df_fac.head(5))

    st.markdown("**3. Orientaciones de la entidad**")
    c1, c2 = st.columns(2)
    valor_max = c1.number_input(
        "Valor máximo por factura ($)",
        min_value=0, value=0, step=1000000,
        help="0 = sin límite"
    )
    conceptos_raw = c2.text_input(
        "Conceptos permitidos (separados por coma)",
        placeholder="alimentos, transporte, dotación",
        help="Palabras clave que deben aparecer en los ítems de la factura"
    )

    orientaciones = {
        "valor_maximo": valor_max,
        "conceptos_permitidos": [c.strip() for c in conceptos_raw.split(",")
                                   if c.strip()] if conceptos_raw else [],
    }

    col_prov = col_val_max = None
    if not df_fac.empty and cols_fac:
        st.markdown("**4. Mapea las columnas (opcional)**")
        c1, c2 = st.columns(2)
        col_prov = c1.selectbox("Columna NIT Proveedor",
                                 options=["(ninguna)"] + cols_fac, key="col_prov")
        col_val_max = c2.selectbox("Columna Valor Máximo Contrato",
                                    options=["(ninguna)"] + cols_fac, key="col_val_max")
        col_prov = None if col_prov == "(ninguna)" else col_prov
        col_val_max = None if col_val_max == "(ninguna)" else col_val_max

    if pdfs_fac:
        if st.button("🔍 Validar Facturas", type="primary", key="btn_fac"):
            resultados = []
            bar = st.progress(0)
            for i, pdf in enumerate(pdfs_fac):
                with st.spinner(f"Procesando {pdf.name}..."):
                    res = validar_factura(
                        pdf,
                        df_fac if not df_fac.empty else pd.DataFrame(),
                        col_proveedor=col_prov,
                        col_valor_max=col_val_max,
                        orientaciones=orientaciones,
                    )
                    resultados.append(res)
                bar.progress((i + 1) / len(pdfs_fac))

            st.session_state.resultados_fac = resultados
            bar.empty()

            rsm = resumen_resultados(resultados)
            m1, m2, m3 = st.columns(3)
            m1.metric("✅ Aprobados", rsm["aprobados"])
            m2.metric("❌ Rechazados", rsm["rechazados"])
            m3.metric("⚠️ Para revisar", rsm["revisar"])

            st.divider()
            for res in resultados:
                mostrar_resultado(res)


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — REPORTE GENERAL
# ════════════════════════════════════════════════════════════════════════════
with tab_reporte:
    st.subheader("📊 Reporte General de Validación")

    todos = (st.session_state.resultados_ss +
             st.session_state.resultados_nom +
             st.session_state.resultados_fac)

    if not todos:
        st.info("Realiza validaciones en las otras pestañas para ver el reporte aquí.")
    else:
        # Métricas globales
        rsm = resumen_resultados(todos)
        pct_ok = int(rsm["aprobados"] / rsm["total"] * 100) if rsm["total"] else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total documentos", rsm["total"])
        m2.metric("✅ Aprobados", rsm["aprobados"], f"{pct_ok}%")
        m3.metric("❌ Rechazados", rsm["rechazados"])
        m4.metric("⚠️ Para revisar", rsm["revisar"])

        st.divider()

        # Tabla resumen
        filas = []
        for res in todos:
            filas.append({
                "Archivo": res.get("archivo", ""),
                "Estado": res.get("estado_general", ""),
                "Errores": " | ".join(res.get("errores", [])) or "—",
                "Advertencias": " | ".join(res.get("advertencias", [])) or "—",
            })

        df_rep = pd.DataFrame(filas)
        st.dataframe(
            df_rep.style.applymap(
                lambda v: "background-color:#dcfce7" if "APROBADO" in str(v)
                else ("background-color:#fee2e2" if "RECHAZADO" in str(v)
                      else ("background-color:#fef9c3" if "REVISAR" in str(v)
                            else "")),
                subset=["Estado"]
            ),
            use_container_width=True,
            height=min(400, 40 + len(filas) * 35),
        )

        # Descargar reporte en Excel
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_rep.to_excel(writer, sheet_name="Resumen", index=False)

            # Hojas por tipo
            if st.session_state.resultados_ss:
                pd.DataFrame([{
                    "Archivo": r["archivo"],
                    "Estado": r["estado_general"],
                    "Cédula": r["datos_extraidos"].get("cedula", ""),
                    "Nombre": r["datos_extraidos"].get("nombre", ""),
                    "IBC extraído": r["datos_extraidos"].get("ibc", 0),
                    "Estado pago": r["datos_extraidos"].get("estado_pago", ""),
                    "Errores": " | ".join(r.get("errores", [])),
                } for r in st.session_state.resultados_ss]).to_excel(
                    writer, sheet_name="Seguridad Social", index=False)

            if st.session_state.resultados_nom:
                pd.DataFrame([{
                    "Archivo": r["archivo"],
                    "Estado": r["estado_general"],
                    "Cédula": r["datos_extraidos"].get("cedula", ""),
                    "Nombre": r["datos_extraidos"].get("nombre", ""),
                    "Neto pagado": r["datos_extraidos"].get("neto_pagado", 0),
                    "Quincena": r["datos_extraidos"].get("quincena", ""),
                    "Período": r["datos_extraidos"].get("periodo", ""),
                    "Errores": " | ".join(r.get("errores", [])),
                } for r in st.session_state.resultados_nom]).to_excel(
                    writer, sheet_name="Nómina", index=False)

            if st.session_state.resultados_fac:
                pd.DataFrame([{
                    "Archivo": r["archivo"],
                    "Estado": r["estado_general"],
                    "N° Factura": r["datos_extraidos"].get("numero_factura", ""),
                    "Fecha": r["datos_extraidos"].get("fecha", ""),
                    "Valor total": r["datos_extraidos"].get("valor_total", 0),
                    "Proveedor": r["datos_extraidos"].get("nombre_proveedor", ""),
                    "Errores": " | ".join(r.get("errores", [])),
                } for r in st.session_state.resultados_fac]).to_excel(
                    writer, sheet_name="Facturas", index=False)

        buf.seek(0)
        fecha_hoy = datetime.now().strftime("%Y%m%d_%H%M")
        st.download_button(
            label="⬇️ Descargar reporte en Excel",
            data=buf,
            file_name=f"Reporte_Validacion_{fecha_hoy}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        if st.button("🗑️ Limpiar todos los resultados"):
            st.session_state.resultados_ss = []
            st.session_state.resultados_nom = []
            st.session_state.resultados_fac = []
            st.rerun()
