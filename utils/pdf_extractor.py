import pdfplumber
import re
from datetime import datetime


def extraer_texto(archivo_pdf) -> str:
    """Extrae todo el texto de un PDF."""
    texto = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            t = pagina.extract_text()
            if t:
                texto += t + "\n"
    return texto


def extraer_tablas(archivo_pdf) -> list:
    """Extrae todas las tablas de un PDF."""
    tablas = []
    with pdfplumber.open(archivo_pdf) as pdf:
        for i, pagina in enumerate(pdf.pages):
            for tabla in pagina.extract_tables():
                if tabla:
                    tablas.append({"pagina": i + 1, "datos": tabla})
    return tablas


def limpiar_numero(texto: str) -> float:
    """Convierte texto con formato de número (1.234.567,89) a float."""
    if not texto:
        return 0.0
    texto = str(texto).strip()
    # Formato colombiano: puntos como miles, coma como decimal
    texto = re.sub(r'[^\d,.]', '', texto)
    if ',' in texto and '.' in texto:
        if texto.rfind(',') > texto.rfind('.'):
            texto = texto.replace('.', '').replace(',', '.')
        else:
            texto = texto.replace(',', '')
    elif ',' in texto:
        texto = texto.replace(',', '.')
    try:
        return float(texto)
    except:
        return 0.0


def buscar_valor(texto: str, patrones: list) -> str:
    """Busca un valor en el texto usando una lista de patrones regex."""
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                return match.group(1).strip()
            except IndexError:
                return match.group(0).strip()
    return ""


def buscar_fecha(texto: str) -> str:
    """Busca la primera fecha válida en el texto."""
    patrones = [
        r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})',
        r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})',
        r'(\d{1,2})\s+de\s+\w+\s+de\s+(\d{4})',
    ]
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            return match.group(0)
    return ""
