import json
import re
import time
import unicodedata
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# =========================================================
# CONFIGURACION
# =========================================================

URL_MAYOR = (
    "https://contratacion.aena.es/contratacion/"
    "principal?portal=licitaciones"
)

URL_MENOR = (
    "https://contratacion.aena.es/contratacion/"
    "ecompras/pedidos/pedidos"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}


# =========================================================
# PALABRAS DE INTERES PARA SALNES ROT
# =========================================================

PALABRAS_ALTA = {
    "rotulacion": 100,
    "rotulo": 90,
    "rotulos": 90,
    "senaletica": 100,
    "senalizacion": 95,
    "senalizaciones": 95,
    "carteleria": 95,
    "cartel": 70,
    "carteles": 75,
    "vinilo": 90,
    "vinilos": 90,
    "vinilado": 90,
    "impresion digital": 95,
    "gran formato": 100,
    "letras corporeas": 100,
    "corporeas": 95,
    "rotulo luminoso": 100,
    "luminoso": 85,
    "luminosos": 85,
    "imagen corporativa": 90,
    "soportes graficos": 90,
    "grafismo": 85,
    "grafismos": 85,
    "placa informativa": 85,
    "placas informativas": 85,
    "directorio": 85,
    "directorios": 85,
    "banderola": 85,
    "banderolas": 85,
    "monolito": 85,
    "monolitos": 85,
    "fotoluminiscente": 90,
    "pictograma": 90,
    "pictogramas": 90,
    "senal direccional": 95,
    "senales direccionales": 95,
    "senal informativa": 95,
    "senales informativas": 95,
    "senal de seguridad": 90,
    "senales de seguridad": 90,
    "marcaje": 70,
    "marcajes": 70,
    "adhesivo": 65,
    "adhesivos": 65,
    "lona impresa": 90,
    "lonas impresas": 90,
    "publicidad": 65,
    "identificacion": 70,
}


PALABRAS_MEDIA = {
    "fachada": 40,
    "fachadas": 40,
    "revestimiento": 35,
    "revestimientos": 35,
    "metacrilato": 45,
    "aluminio compuesto": 45,
    "decoracion": 35,
    "acondicionamiento": 30,
    "adecuacion": 30,
    "reforma": 25,
    "reformas": 25,
    "remodelacion": 25,
    "rehabilitacion": 25,
    "mobiliario": 20,
    "pintura": 25,
    "mampara": 20,
    "mamparas": 20,
    "mostrador": 20,
    "mostradores": 20,
    "carpinteria": 15,
    "equipamiento": 15,
}


# =========================================================
# FUNCIONES GENERALES
# =========================================================

def limpiar(texto):
    if texto is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(texto)
    ).strip()


def normalizar(texto):
    texto = limpiar(texto).lower()

    texto = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )

    return texto


def calcular_prioridad(texto):
    texto = normalizar(texto)

    puntuacion = 0
    coincidencias = []

    for palabra, puntos in PALABRAS_ALTA.items():
        if palabra in texto:
            puntuacion += puntos
            coincidencias.append(palabra)

    for palabra, puntos in PALABRAS_MEDIA.items():
        if palabra in texto:
            puntuacion += puntos
            coincidencias.append(palabra)

    # Evitar que varias variantes de la misma palabra
    # produzcan puntuaciones exageradas.
    puntuacion = min(puntuacion, 500)

    if puntuacion >= 70:
        prioridad = "ALTA"
    elif puntuacion >= 20:
        prioridad = "MEDIA"
    else:
        prioridad = "BAJA"

    return puntuacion, prioridad, coincidencias


def obtener_texto(celda):
    return limpiar(
        celda.get_text(
            " ",
            strip=True
        )
    )


# =========================================================
# LOCALIZAR TABLA DE LICITACIONES
# =========================================================

def buscar_tabla_licitaciones(soup):
    tablas = soup.find_all("table")

    mejor_tabla = None
    mejor_puntuacion = 0

    for tabla in tablas:
        texto = normalizar(
            tabla.get_text(
                " ",
                strip=True
            )
        )

        puntuacion = 0

        indicadores = [
            "expediente",
            "titulo",
            "fecha limite",
            "importe",
            "licitacion",
        ]

        for indicador in indicadores:
            if indicador in texto:
                puntuacion += 1

        filas = tabla.find_all("tr")

        if len(filas) >= 2:
            puntuacion += 1

        if puntuacion > mejor_puntuacion:
            mejor_puntuacion = puntuacion
            mejor_tabla = tabla

    return mejor_tabla


# =========================================================
# EXTRAER LICITACIONES DE UNA TABLA
# =========================================================

def extraer_licitaciones(tabla, url_base, tipo):
    elementos = []

    if tabla is None:
        return elementos

    filas = tabla.find_all("tr")

    for fila in filas:
        celdas = fila.find_all("td")

        if len(celdas) < 2:
            continue

        valores = [
            obtener_texto(celda)
            for celda in celdas
        ]

        texto_fila = " | ".join(valores)

        if not texto_fila.strip():
            continue

        enlaces = fila.find_all(
            "a",
            href=True
        )

        url_licitacion = ""

        if enlaces:
            # Preferimos el enlace que tenga texto.
            enlace_elegido = enlaces[0]

            for enlace in enlaces:
                if limpiar(
                    enlace.get_text(
                        " ",
                        strip=True
                    )
                ):
                    enlace_elegido = enlace
                    break

            url_licitacion = urljoin(
                url_base,
                enlace_elegido.get(
                    "href",
                    ""
                )
            )

        # Detectar expediente.
        identificacion = ""

        patron_expediente = re.search(
            r"\b[A-ZÁÉÍÓÚÑ]{2,10}"
            r"[-/]"
            r"[A-Z0-9.-]+"
            r"[-/]"
            r"20\d{2}\b",
            texto_fila,
            re.IGNORECASE
        )

        if patron_expediente:
            identificacion = (
                patron_expediente
                .group(0)
                .strip()
            )

        # Si no se detecta por patrón,
        # buscamos una celda corta con formato similar.
        if not identificacion:
            for valor in valores:
                valor_normal = valor.strip()

                if (
                    len(valor_normal) <= 40
                    and re.search(
                        r"\d",
                        valor_normal
                    )
                    and (
                        "-" in valor_normal
                        or "/" in valor_normal
                    )
                ):
                    identificacion = valor_normal
                    break

        # Buscar el mejor título.
        titulo = ""

        candidatos = []

        for valor in valores:
            valor_limpio = limpiar(valor)

            if (
                len(valor_limpio) >= 12
                and valor_limpio != identificacion
            ):
                candidatos.append(valor_limpio)

        # Los títulos suelen ser uno de los textos
        # más descriptivos de la fila.
        if candidatos:
            titulo = max(
                candidatos,
                key=len
            )

        # Si existe un enlace con texto descriptivo,
        # puede ser mejor título.
        for enlace in enlaces:
            texto_enlace = limpiar(
                enlace.get_text(
                    " ",
                    strip=True
                )
            )

            if (
                len(texto_enlace) >= 12
                and len(texto_enlace) > len(titulo)
            ):
                titulo = texto_enlace

        if not titulo:
            titulo = texto_fila

        puntuacion, prioridad, coincidencias = (
            calcular_prioridad(
                titulo + " " + texto_fila
            )
        )

        # Intentar localizar una fecha límite.
        fecha_limite = ""

        fechas = re.findall(
            r"\b\d{1,2}"
            r"[/-]"
            r"\d{1,2}"
            r"[/-]"
            r"\d{2,4}\b",
            texto_fila
        )

        if fechas:
            # Normalmente la última fecha de la fila
            # corresponde al límite.
            fecha_limite = fechas[-1]

       # Intentar obtener lugar, importe y valor estimado
lugar = ""
cantidad = ""
estimado = ""

for valor in valores:
    valor_limpio = limpiar(valor)

    # Detectar importes en euros
    if "€" in valor_limpio or "EUR" in valor_limpio.upper():
        if not cantidad:
            cantidad = valor_limpio
        elif not estimado and valor_limpio != cantidad:
            estimado = valor_limpio

# Intentar detectar el lugar a partir de las columnas
for valor in valores:
    valor_limpio = limpiar(valor)

    if (
        valor_limpio
        and valor_limpio != identificacion
        and valor_limpio != titulo
        and valor_limpio != cantidad
        and valor_limpio != estimado
        and valor_limpio != fecha_limite
        and len(valor_limpio) < 100
    ):
        lugar = valor_limpio
        break

        elementos.append(
            {
                "identificacion": identificacion,
                "titulo": titulo,
                "lugar": lugar,
                "cantidad": cantidad,
                "estimado": estimado,
                "fecha_limite": fecha_limite,
                "url": url_licitacion,
                "fuente": tipo,
                "recomendada": prioridad in (
                    "ALTA",
                    "MEDIA",
                ),
                "prioridad": prioridad,
                "puntuacion": puntuacion,
                "coincidencias": coincidencias,
            }
        )

    return elementos


# =========================================================
# PAGINACION
# =========================================================

def buscar_siguiente(soup, url_actual):
    """
    Busca el enlace real de 'Siguiente' dentro de la
    página, evitando inventar la paginación de AENA.
    """

    candidatos = soup.find_all(
        "a",
        href=True
    )

    for enlace in candidatos:
        texto = normalizar(
            enlace.get_text(
                " ",
                strip=True
            )
        )

        titulo = normalizar(
            enlace.get("title", "")
        )

        aria = normalizar(
            enlace.get(
                "aria-label",
                ""
            )
        )

        conjunto = (
            texto
            + " "
            + titulo
            + " "
            + aria
        )

        if (
            "siguiente" in conjunto
            or conjunto.strip() == "next"
        ):
            href = enlace.get(
                "href",
                ""
            )

            if href and not href.lower().startswith(
                "javascript:"
            ):
                return urljoin(
                    url_actual,
                    href
                )

    return None


# =========================================================
# RECORRER LICITACIONES MAYORES
# =========================================================

def obtener_mayores(session):
    print(
        "Buscando licitaciones AENA "
        "de cuantia mayor..."
    )

    elementos = []
    visitadas = set()

    url_actual = URL_MAYOR

    pagina = 1

    while url_actual:
        if url_actual in visitadas:
            break

        visitadas.add(url_actual)

        print(
            f"Procesando pagina {pagina}..."
        )

        respuesta = session.get(
            url_actual,
            timeout=40
        )

        respuesta.raise_for_status()

        soup = BeautifulSoup(
            respuesta.text,
            "html.parser"
        )

        tabla = buscar_tabla_licitaciones(
            soup
        )

        if tabla is None:
            print(
                "No se encontro tabla "
                f"en pagina {pagina}."
            )
            break

        nuevos = extraer_licitaciones(
            tabla,
            url_actual,
            "AENA Mayor"
        )

        if not nuevos:
            break

        elementos.extend(nuevos)

        siguiente = buscar_siguiente(
            soup,
            url_actual
        )

        if (
            not siguiente
            or siguiente in visitadas
        ):
            break

        url_actual = siguiente

        pagina += 1

        # Pequeña pausa para no cargar el servidor.
        time.sleep(0.7)

    print(
        f"{len(elementos)} registros mayores "
        "recogidos antes de eliminar duplicados."
    )

    return elementos


# =========================================================
# LICITACIONES MENORES
# =========================================================

def obtener_menores(session):
    print(
        "Buscando contratos AENA "
        "de cuantia menor..."
    )

    elementos = []
    visitadas = set()

    # Esta URL abre el listado de licitaciones menores.
    url_actual = (
        URL_MENOR
        + "?accion=LICITACIONES"
        + "&paginaActual=1"
    )

    pagina = 1

    while url_actual:
        if url_actual in visitadas:
            break

        visitadas.add(url_actual)

        try:
            respuesta = session.get(
                url_actual,
                timeout=40
            )

            respuesta.raise_for_status()

        except requests.RequestException as error:
            print(
                "No se pudieron consultar "
                "los contratos menores:"
            )
            print(error)
            break

        soup = BeautifulSoup(
            respuesta.text,
            "html.parser"
        )

        tabla = buscar_tabla_licitaciones(
            soup
        )

        if tabla is None:
            print(
                "No se encontro tabla de "
                "contratos menores."
            )
            break

        nuevos = extraer_licitaciones(
            tabla,
            url_actual,
            "AENA Menor"
        )

        if not nuevos:
            break

        elementos.extend(nuevos)

        siguiente = buscar_siguiente(
            soup,
            url_actual
        )

        if not siguiente:
            break

        if siguiente in visitadas:
            break

        url_actual = siguiente
        pagina += 1

        time.sleep(0.7)

    print(
        f"{len(elementos)} registros menores "
        "recogidos antes de eliminar duplicados."
    )

    return elementos


# =========================================================
# ELIMINAR DUPLICADOS
# =========================================================

def eliminar_duplicados(elementos):
    unicos = []
    vistos = set()

    for elemento in elementos:
        identificacion = normalizar(
            elemento.get(
                "identificacion",
                ""
            )
        )

        titulo = normalizar(
            elemento.get(
                "titulo",
                ""
            )
        )

        if identificacion:
            clave = identificacion
        else:
            clave = titulo

        if not clave:
            continue

        if clave not in vistos:
            vistos.add(clave)
            unicos.append(elemento)

    return unicos


# =========================================================
# ORDENAR POR INTERES PARA SALNES ROT
# =========================================================

def ordenar_por_interes(elementos):
    return sorted(
        elementos,
        key=lambda elemento: (
            -elemento.get(
                "puntuacion",
                0
            ),
            elemento.get(
                "titulo",
                ""
            ).lower(),
        )
    )


# =========================================================
# PROGRAMA PRINCIPAL
# =========================================================

def principal():
    print(
        "===================================="
    )
    print(
        "SALNES ROT - LICITACIONES AENA"
    )
    print(
        "===================================="
    )

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    # Abrir primero AENA para crear cookies/sesion.
    try:
        inicio = session.get(
            URL_MAYOR,
            timeout=40
        )

        inicio.raise_for_status()

    except requests.RequestException as error:
        raise RuntimeError(
            "No se pudo conectar con AENA."
        ) from error

    mayores = obtener_mayores(
        session
    )

    menores = obtener_menores(
        session
    )

    todos = mayores + menores

    unicos = eliminar_duplicados(
        todos
    )

    ordenados = ordenar_por_interes(
        unicos
    )

    recomendadas = [
        elemento
        for elemento in ordenados
        if elemento.get(
            "recomendada"
        )
    ]

    altas = [
        elemento
        for elemento in ordenados
        if elemento.get(
            "prioridad"
        ) == "ALTA"
    ]

    medias = [
        elemento
        for elemento in ordenados
        if elemento.get(
            "prioridad"
        ) == "MEDIA"
    ]

    resultado = {
        "actualizado": (
            datetime.now()
            .strftime(
                "%d/%m/%Y %H:%M"
            )
        ),
        "fuente": URL_MAYOR,
        "total": len(ordenados),
        "recomendadas": len(
            recomendadas
        ),
        "prioridad_alta": len(
            altas
        ),
        "prioridad_media": len(
            medias
        ),
        "elementos": ordenados,
    }

    with open(
        "datos.json",
        "w",
        encoding="utf-8"
    ) as archivo:
        json.dump(
            resultado,
            archivo,
            ensure_ascii=False,
            indent=2
        )

    print()
    print(
        "Actualizacion terminada."
    )
    print(
        f"TOTAL: {len(ordenados)}"
    )
    print(
        f"PRIORIDAD ALTA: {len(altas)}"
    )
    print(
        f"PRIORIDAD MEDIA: {len(medias)}"
    )
    print(
        f"RECOMENDADAS: {len(recomendadas)}"
    )


if __name__ == "__main__":
    principal()
