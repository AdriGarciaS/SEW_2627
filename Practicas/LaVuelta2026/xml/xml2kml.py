# xml2kml.py
# -*- coding: utf-8 -*-
"""
Genera el archivo etapa.kml con la planimetría de la etapa a partir
de etapaEsquema.xml, usando expresiones XPath para leer los datos.

Colores de los marcadores:
    - Rojo:     salida y meta
    - Verde:    puertos de montaña
    - Azul:     sprints intermedios
    - Amarillo: puntos anónimos

@version 1.0
@author: Adriana Garcia Suarez UO300042
"""

import sys
import xml.etree.ElementTree as ET


class Punto:
    """Punto geográfico de la etapa (salida, meta, hito o punto anónimo)."""

    def __init__(self, nombre, longitud, latitud, altitud, distancia, tipo):
        self.nombre = nombre
        self.longitud = longitud
        self.latitud = latitud
        self.altitud = altitud
        self.distancia = distancia
        self.tipo = tipo

    def coordenadas(self):
        """Devuelve las coordenadas en formato KML (lon,lat,alt)."""
        return f"{self.longitud},{self.latitud},{self.altitud}"


class LectorEtapa:
    """Lee etapaEsquema.xml y extrae sus datos mediante expresiones XPath."""

    ESPACIO_NOMBRES = {"uo": "http://www.uniovi.es"}
    MAX_PUNTOS_ANONIMOS = 30

    def __init__(self, archivo_xml):
        try:
            self.raiz = ET.parse(archivo_xml).getroot()
        except IOError:
            print("No se encuentra el archivo", archivo_xml)
            sys.exit(1)
        except ET.ParseError:
            print("Error procesando el archivo XML =", archivo_xml)
            sys.exit(1)

    def _texto(self, nodo, expresion_xpath):
        """Devuelve el texto del nodo seleccionado por la expresión XPath."""
        return nodo.find(expresion_xpath, self.ESPACIO_NOMBRES).text.strip()

    def _crear_punto(self, nodo, nombre, distancia, tipo):
        """Crea un Punto leyendo las coordenadas del nodo con XPath."""
        return Punto(
            nombre,
            self._texto(nodo, "uo:coordenadas/uo:longitud"),
            self._texto(nodo, "uo:coordenadas/uo:latitud"),
            self._texto(nodo, "uo:coordenadas/uo:altitud"),
            distancia,
            tipo,
        )

    def nombre_etapa(self):
        """Devuelve el nombre de la etapa."""
        return self._texto(self.raiz, "uo:nombre")

    def numero_etapa(self):
        """Devuelve el número de la etapa (atributo del elemento raíz)."""
        return self.raiz.get("numero")

    def distancia_total(self):
        """Devuelve la longitud total de la etapa en km."""
        return float(self._texto(self.raiz, "uo:distancia"))

    def salida(self):
        """Devuelve el punto de salida de la etapa."""
        nodo = self.raiz.find("uo:salida", self.ESPACIO_NOMBRES)
        nombre = "Salida: " + self._texto(nodo, "uo:lugar")
        return self._crear_punto(nodo, nombre, 0.0, "salidaMeta")

    def meta(self):
        """Devuelve el punto de meta de la etapa."""
        nodo = self.raiz.find("uo:meta", self.ESPACIO_NOMBRES)
        nombre = "Meta: " + self._texto(nodo, "uo:lugar")
        distancia = self.distancia_total()
        return self._crear_punto(nodo, nombre, distancia, "salidaMeta")

    def _hitos(self, expresion_xpath, prefijo, tipo):
        """Devuelve los hitos (puertos o sprints) seleccionados por XPath."""
        hitos = []
        for nodo in self.raiz.findall(expresion_xpath, self.ESPACIO_NOMBRES):
            nombre = prefijo + self._texto(nodo, "uo:nombre")
            distancia = float(self._texto(nodo, "uo:distanciaSalida"))
            hitos.append(self._crear_punto(nodo, nombre, distancia, tipo))
        return hitos

    def puertos(self):
        """Devuelve los puertos de montaña de la etapa."""
        return self._hitos("uo:hitos/uo:puerto", "Puerto: ", "puerto")

    def sprints(self):
        """Devuelve los sprints intermedios de la etapa."""
        return self._hitos("uo:hitos/uo:sprint", "Sprint: ", "sprint")

    def puntos_anonimos(self):
        """Devuelve los puntos anónimos (el nombre es opcional)."""
        puntos = []
        nodos = self.raiz.findall("uo:puntos/uo:punto", self.ESPACIO_NOMBRES)
        for indice, nodo in enumerate(nodos, start=1):
            nodo_nombre = nodo.find("uo:nombre", self.ESPACIO_NOMBRES)
            if nodo_nombre is not None:
                nombre = nodo_nombre.text.strip()
            else:
                nombre = f"Punto {indice}"
            distancia = float(self._texto(nodo, "uo:distanciaSalida"))
            punto = self._crear_punto(nodo, nombre, distancia, "anonimo")
            puntos.append(punto)
        if len(puntos) > self.MAX_PUNTOS_ANONIMOS:
            print(f"Aviso: hay {len(puntos)} puntos anónimos "
                  f"(máximo recomendado: {self.MAX_PUNTOS_ANONIMOS}).")
        return puntos


class Kml:
    """Genera un documento KML 2.2 con marcadores y líneas."""

    ESPACIO_NOMBRES_KML = "http://www.opengis.net/kml/2.2"
    ICONO = "http://maps.google.com/mapfiles/kml/pushpin/wht-pushpin.png"

    def __init__(self, nombre_documento):
        self.raiz = ET.Element("kml", xmlns=self.ESPACIO_NOMBRES_KML)
        self.documento = ET.SubElement(self.raiz, "Document")
        ET.SubElement(self.documento, "name").text = nombre_documento

    def add_estilo_icono(self, identificador, color, escala):
        """Añade un estilo de marcador. El color va en formato aabbggrr."""
        estilo = ET.SubElement(self.documento, "Style", id=identificador)
        icon_style = ET.SubElement(estilo, "IconStyle")
        ET.SubElement(icon_style, "color").text = color
        ET.SubElement(icon_style, "scale").text = str(escala)
        icono = ET.SubElement(icon_style, "Icon")
        ET.SubElement(icono, "href").text = self.ICONO

    def add_estilo_linea(self, identificador, color, ancho):
        """Añade un estilo de línea. El color va en formato aabbggrr."""
        estilo = ET.SubElement(self.documento, "Style", id=identificador)
        line_style = ET.SubElement(estilo, "LineStyle")
        ET.SubElement(line_style, "color").text = color
        ET.SubElement(line_style, "width").text = str(ancho)

    def add_placemark(self, nombre, descripcion, coordenadas, estilo):
        """Añade un marcador (Point) con el estilo indicado."""
        placemark = ET.SubElement(self.documento, "Placemark")
        ET.SubElement(placemark, "name").text = nombre
        ET.SubElement(placemark, "description").text = descripcion
        ET.SubElement(placemark, "styleUrl").text = "#" + estilo
        punto = ET.SubElement(placemark, "Point")
        ET.SubElement(punto, "altitudeMode").text = "clampToGround"
        ET.SubElement(punto, "coordinates").text = coordenadas

    def add_line_string(self, nombre, lista_coordenadas, estilo):
        """Añade una línea (LineString) que se adapta al relieve."""
        placemark = ET.SubElement(self.documento, "Placemark")
        ET.SubElement(placemark, "name").text = nombre
        ET.SubElement(placemark, "styleUrl").text = "#" + estilo
        linea = ET.SubElement(placemark, "LineString")
        ET.SubElement(linea, "extrude").text = "1"
        ET.SubElement(linea, "tessellate").text = "1"
        ET.SubElement(linea, "altitudeMode").text = "clampToGround"
        ET.SubElement(linea, "coordinates").text = "\n".join(lista_coordenadas)

    def escribir(self, archivo_kml):
        """Escribe el documento KML en disco con codificación UTF-8."""
        arbol = ET.ElementTree(self.raiz)
        ET.indent(arbol, space="    ")
        arbol.write(archivo_kml, encoding="UTF-8", xml_declaration=True)


class Xml2Kml:
    """Aplicación que convierte etapaEsquema.xml en etapa.kml."""

    # Colores KML en formato aabbggrr (alfa, azul, verde, rojo)
    ROJO = "ff0000ff"
    VERDE = "ff00ff00"
    AZUL = "ffff0000"
    AMARILLO = "ff00ffff"
    NARANJA = "ff0080ff"

    ESTILOS = {
        "salidaMeta": ("estiloSalidaMeta", ROJO, 1.3),
        "puerto": ("estiloPuerto", VERDE, 1.1),
        "sprint": ("estiloSprint", AZUL, 1.1),
        "anonimo": ("estiloAnonimo", AMARILLO, 0.8),
    }

    def __init__(self, archivo_xml, archivo_kml):
        self.archivo_xml = archivo_xml
        self.archivo_kml = archivo_kml

    def _descripcion(self, punto):
        """Genera la descripción que se muestra al pulsar un marcador."""
        return (f"Km {punto.distancia} desde la salida. "
                f"Altitud: {punto.altitud} m")

    def ejecutar(self):
        """Lee el XML, genera el KML y lo guarda en disco."""
        lector = LectorEtapa(self.archivo_xml)
        titulo = f"Etapa {lector.numero_etapa()}: {lector.nombre_etapa()}"

        kml = Kml(titulo)
        for identificador, color, escala in self.ESTILOS.values():
            kml.add_estilo_icono(identificador, color, escala)
        kml.add_estilo_linea("estiloRuta", self.NARANJA, 4)

        puntos = ([lector.salida()] + lector.puertos() + lector.sprints()
                  + lector.puntos_anonimos() + [lector.meta()])

        # La ruta une todos los puntos ordenados por distancia a la salida
        ruta = sorted(puntos, key=lambda punto: punto.distancia)
        kml.add_line_string("Recorrido de la etapa",
                            [punto.coordenadas() for punto in ruta],
                            "estiloRuta")

        for punto in puntos:
            estilo = self.ESTILOS[punto.tipo][0]
            kml.add_placemark(punto.nombre, self._descripcion(punto),
                              punto.coordenadas(), estilo)

        kml.escribir(self.archivo_kml)
        print(f"Generado {self.archivo_kml} con {len(puntos)} puntos.")


if __name__ == "__main__":
    Xml2Kml("etapaEsquema.xml", "etapa.kml").ejecutar()