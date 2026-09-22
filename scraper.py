import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

URL = "https://contratacion.aena.es/contratacion/principal?portal=licitaciones"

CABECERA = {
    "User-Agent": "Mozilla/5.0 SALNES-ROT-Licitaciones/1.0"
}

# Palabras relacionadas directamente con trabajos que puede realizar SALNES ROT
PALABRAS_INTERES = [
    "rotulacion", "rotulación", "rotulo", "rótulo", "rotulos", "rótulos",
    "señaletica", "señalética", "señalizacion", "señalización", "señales",
    "carteleria", "cartelería", "cartel", "carteles",
    "vinilo", "vinilos", "vinilado",
    "impresion", "impresión", "impresion digital", "impresión digital",
    "gran formato",
    "letras corporeas", "letras corpóreas", "corporeas", "corpóreas",
    "luminoso", "luminosos", "rotulo luminoso", "rótulo luminoso",
    "fachada", "fachadas",
    "directorio", "directorios",
    "placa", "placas", "panel", "paneles",
    "lona", "lonas",
    "metacrilato",
    "aluminio compuesto",
    "revestimiento",
    "publicidad",
    "soportes graficos", "soportes gráficos",
    "elementos graficos", "elementos gráficos",
    "serigrafia", "serigrafía",
    "pictograma", "pictogramas",
    "identificacion", "identificación",
    "imagen corporativa",
    "grafica", "gráfica", "graficas", "gráficas",
    "decoracion", "decoración",
    "adhesivo", "adhesivos",
    "banderola", "banderolas",
    "monolito", "monolitos",
    "señal direccional", "señales direccionales",
    "señal informativa", "señales informativas",
    "señal de seguridad", "señales de seguridad",
    "señal fotoluminiscente", "fotoluminiscente",
    "marcaje", "marcajes",
    "grafismo", "grafismos"

def es_recomendada(texto):
    texto = texto.lower()
    return any(palabra.lower() in texto for palabra in PALABRAS_INTERES)


def limpiar(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


def principal():
    respuesta = requests.get(
        URL,
        headers=CABECERA,
        timeout=40
    )
    respuesta.raise_for_status()

    soup = BeautifulSoup(respuesta.text, "html.parser")

    tablas = soup.find_all("table")
    tabla_objetivo = None

    for tabla in tablas:
        texto = limpiar(tabla.get_text(" ", strip=True)).lower()

        if "expediente" in texto and (
            "fecha límite" in texto
            or "fecha limite" in texto
            or "título" in texto
            or "titulo" in texto
        ):
            tabla_objetivo = tabla
            break

    if tabla_objetivo is None:
        raise RuntimeError(
            "No se encontró la tabla de licitaciones de AENA"
        )

    elementos = []

    for fila in tabla_objetivo.find_all("tr"):
        celdas = fila.find_all(["td", "th"])

        if len(celdas) < 4:
            continue

        valores = [
            limpiar(celda.get_text(" ", strip=True))
            for celda in celdas
        ]

        texto_fila = " | ".join(valores)

        if "expediente" in texto_fila.lower():
            continue

        enlace = fila.find("a", href=True)

        url = ""
        if enlace:
            url = urljoin(URL, enlace.get("href"))

        # Adaptación a la estructura actual de la tabla de AENA
        identificacion = valores[0] if len(valores) > 0 else ""
        titulo = valores[1] if len(valores) > 1 else ""
        lugar = valores[2] if len(valores) > 2 else ""
        cantidad = valores[3] if len(valores) > 3 else ""
        estimado = valores[4] if len(valores) > 4 else ""
        fecha_limite = valores[-1] if valores else ""

        texto_interes = " ".join([
            identificacion,
            titulo,
            lugar,
            texto_fila
        ])

        recomendado = es_recomendada(texto_interes)

        elementos.append({
            "identificacion": identificacion,
            "titulo": titulo,
            "lugar": lugar,
            "cantidad": cantidad,
            "estimado": estimado,
            "fecha_limite": fecha_limite,
            "url": url,
            "fuente": "AENA",
            "recomendada": recomendado
        })

    # Evitar duplicados
    unicos = []
    vistos = set()

    for elemento in elementos:
        clave = (
            elemento["identificacion"],
            elemento["titulo"],
            elemento["url"]
        )

        if clave not in vistos:
            vistos.add(clave)
            unicos.append(elemento)

    resultado = {
        "actualizado": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "fuente": URL,
        "total": len(unicos),
        "recomendadas": sum(
            1 for elemento in unicos
            if elemento["recomendada"]
        ),
        "elementos": unicos
    }

    with open("datos.json", "w", encoding="utf-8") as archivo:
        json.dump(
            resultado,
            archivo,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"Actualización terminada: "
        f"{len(unicos)} licitaciones / "
        f"{resultado['recomendadas']} recomendadas"
    )


if _name_ == "_main_":
    principal()
