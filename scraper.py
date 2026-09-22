import json
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


URL = "https://contratacion.aena.es/contratacion/principal?portal=licitaciones"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
}


# Palabras relacionadas con los trabajos de SALNES ROT
PALABRAS_INTERES = [
    "rotulacion",
    "rotulación",
    "rotulo",
    "rótulo",
    "rotulos",
    "rótulos",
    "señaletica",
    "señalética",
    "señalizacion",
    "señalización",
    "señales",
    "carteleria",
    "cartelería",
    "cartel",
    "carteles",
    "vinilo",
    "vinilos",
    "vinilado",
    "impresion",
    "impresión",
    "impresion digital",
    "impresión digital",
    "gran formato",
    "letras corporeas",
    "letras corpóreas",
    "corporeas",
    "corpóreas",
    "luminoso",
    "luminosos",
    "rotulo luminoso",
    "rótulo luminoso",
    "fachada",
    "fachadas",
    "directorio",
    "directorios",
    "placa",
    "placas",
    "panel",
    "paneles",
    "lona",
    "lonas",
    "metacrilato",
    "aluminio compuesto",
    "revestimiento",
    "publicidad",
    "soportes graficos",
    "soportes gráficos",
    "identificacion",
    "identificación",
    "imagen corporativa",
    "grafica",
    "gráfica",
    "graficas",
    "gráficas",
    "decoracion",
    "decoración",
    "adhesivo",
    "adhesivos",
    "banderola",
    "banderolas",
    "monolito",
    "monolitos",
    "señal direccional",
    "señales direccionales",
    "señal informativa",
    "señales informativas",
    "señal de seguridad",
    "señales de seguridad",
    "señal fotoluminiscente",
    "fotoluminiscente",
    "marcaje",
    "marcajes",
    "grafismo",
    "grafismos",
]


def limpiar(texto):
    """Limpia espacios y saltos de línea."""
    if texto is None:
        return ""
    return re.sub(r"\s+", " ", texto).strip()


def es_recomendada(texto):
    """Indica si una licitación contiene trabajos de interés."""
    texto = limpiar(texto).lower()
    return any(palabra.lower() in texto for palabra in PALABRAS_INTERES)


def obtener_texto(celda):
    """Obtiene texto limpio de una celda HTML."""
    return limpiar(celda.get_text(" ", strip=True))


def buscar_tabla_licitaciones(soup):
    """
    Busca la tabla que contiene las licitaciones.
    Se intenta identificarla por palabras habituales de sus cabeceras.
    """
    tablas = soup.find_all("table")

    for tabla in tablas:
        texto = limpiar(tabla.get_text(" ", strip=True)).lower()

        indicadores = [
            "expediente",
            "fecha límite",
            "fecha limite",
            "título",
            "titulo",
        ]

        if any(indicador in texto for indicador in indicadores):
            return tabla

    return None


def extraer_licitaciones(tabla):
    """Extrae las licitaciones de la tabla encontrada."""
    elementos = []

    filas = tabla.find_all("tr")

    for fila in filas:
        celdas = fila.find_all(["td", "th"])

        if len(celdas) < 2:
            continue

        valores = [obtener_texto(celda) for celda in celdas]

        texto_fila = " | ".join(valores)

        # Evitar la cabecera de la tabla
        if "expediente" in texto_fila.lower() and (
            "fecha" in texto_fila.lower()
            or "título" in texto_fila.lower()
            or "titulo" in texto_fila.lower()
        ):
            continue

        enlace = fila.find("a", href=True)

        url_licitacion = ""
        if enlace:
            url_licitacion = urljoin(URL, enlace.get("href", ""))

        # Adaptación flexible a la estructura de AENA
        identificacion = valores[0] if len(valores) > 0 else ""
        titulo = valores[1] if len(valores) > 1 else ""
        lugar = valores[2] if len(valores) > 2 else ""
        cantidad = valores[3] if len(valores) > 3 else ""
        estimado = valores[4] if len(valores) > 4 else ""
        fecha_limite = valores[-1] if len(valores) > 1 else ""

        # Si el enlace tiene un texto más descriptivo, usarlo como título
        if enlace:
            texto_enlace = limpiar(enlace.get_text(" ", strip=True))
            if texto_enlace and len(texto_enlace) > len(titulo):
                titulo = texto_enlace

        texto_interes = " ".join(
            [
                identificacion,
                titulo,
                lugar,
                cantidad,
                estimado,
                texto_fila,
            ]
        )

        recomendado = es_recomendada(texto_interes)

        # No guardar filas completamente vacías
        if not identificacion and not titulo:
            continue

        elementos.append(
            {
                "identificacion": identificacion,
                "titulo": titulo,
                "lugar": lugar,
                "cantidad": cantidad,
                "estimado": estimado,
                "fecha_limite": fecha_limite,
                "url": url_licitacion,
                "fuente": "AENA",
                "recomendada": recomendado,
            }
        )

    return elementos


def eliminar_duplicados(elementos):
    """Elimina resultados duplicados."""
    unicos = []
    vistos = set()

    for elemento in elementos:
        clave = (
            elemento.get("identificacion", ""),
            elemento.get("titulo", ""),
            elemento.get("url", ""),
        )

        if clave not in vistos:
            vistos.add(clave)
            unicos.append(elemento)

    return unicos


def principal():
    print("Buscando licitaciones de AENA...")

    respuesta = requests.get(
        URL,
        headers=HEADERS,
        timeout=40,
    )

    respuesta.raise_for_status()

    soup = BeautifulSoup(respuesta.text, "html.parser")

    tabla = buscar_tabla_licitaciones(soup)

    if tabla is None:
        raise RuntimeError(
            "No se encontro la tabla de licitaciones de AENA. "
            "La estructura de la pagina puede haber cambiado."
        )

    elementos = extraer_licitaciones(tabla)
    unicos = eliminar_duplicados(elementos)

    recomendadas = [
        elemento
        for elemento in unicos
        if elemento.get("recomendada")
    ]

    resultado = {
        "actualizado": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "fuente": URL,
        "total": len(unicos),
        "recomendadas": len(recomendadas),
        "elementos": unicos,
    }

    with open("datos.json", "w", encoding="utf-8") as archivo:
        json.dump(
            resultado,
            archivo,
            ensure_ascii=False,
            indent=2,
        )

    print("Actualizacion terminada.")
    print(f"{len(unicos)} licitaciones encontradas.")
    print(f"{len(recomendadas)} licitaciones recomendadas.")


if __name__ == "__main__":
    principal()
