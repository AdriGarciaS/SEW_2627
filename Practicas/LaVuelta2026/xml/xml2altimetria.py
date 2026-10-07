# xml2altimetria.py
# -*- coding: utf-8 -*-
"""
Genera el archivo altimetria.svg con el perfil altimétrico de la etapa
a partir de etapaEsquema.xml, usando expresiones XPath para leer los datos.

Colores de los marcadores (los mismos que en etapa.kml):
    - Rojo:     salida y meta
    - Verde:    puertos de montaña
    - Azul:     sprints intermedios
    - Amarillo: puntos anónimos

@version 1.0
@author: Adriana Garcia Suarez  - UO300042
"""

import math
import sys
import xml.etree.ElementTree as ET


class PuntoPerfil:
    """Punto del perfil: distancia a la salida (km) y altitud (m)."""

    def __init__(self, nombre, distancia, altitud, tipo):
        self.nombre = nombre
        self.distancia = distancia
        self.altitud = altitud
        self.tipo = tipo


class LectorEtapa:
    """Lee etapaEsquema.xml y extrae sus datos mediante expresiones XPath."""

    ESPACIO_NOMBRES = {"uo": "http://www.uniovi.es"}

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

    def _altitud(self, nodo):
        """Devuelve la altitud (m) de un nodo con coordenadas."""
        return int(self._texto(nodo, "uo:coordenadas/uo:altitud"))

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
        """Devuelve el punto de salida (km 0)."""
        nodo = self.raiz.find("uo:salida", self.ESPACIO_NOMBRES)
        nombre = self._texto(nodo, "uo:lugar")
        return PuntoPerfil(nombre, 0.0, self._altitud(nodo), "salidaMeta")

    def meta(self):
        """Devuelve el punto de meta (km final de la etapa)."""
        nodo = self.raiz.find("uo:meta", self.ESPACIO_NOMBRES)
        nombre = self._texto(nodo, "uo:lugar")
        return PuntoPerfil(nombre, self.distancia_total(),
                           self._altitud(nodo), "salidaMeta")

    def _puntos(self, expresion_xpath, tipo):
        """Devuelve los puntos seleccionados por la expresión XPath."""
        puntos = []
        nodos = self.raiz.findall(expresion_xpath, self.ESPACIO_NOMBRES)
        for indice, nodo in enumerate(nodos, start=1):
            nodo_nombre = nodo.find("uo:nombre", self.ESPACIO_NOMBRES)
            if nodo_nombre is not None:
                nombre = nodo_nombre.text.strip()
            else:
                nombre = f"Punto {indice}"
            distancia = float(self._texto(nodo, "uo:distanciaSalida"))
            puntos.append(PuntoPerfil(nombre, distancia,
                                      self._altitud(nodo), tipo))
        return puntos

    def puertos(self):
        """Devuelve los puertos de montaña."""
        return self._puntos("uo:hitos/uo:puerto", "puerto")

    def sprints(self):
        """Devuelve los sprints intermedios."""
        return self._puntos("uo:hitos/uo:sprint", "sprint")

    def puntos_anonimos(self):
        """Devuelve los puntos anónimos."""
        return self._puntos("uo:puntos/uo:punto", "anonimo")

    def perfil(self):
        """Devuelve todos los puntos ordenados por distancia a la salida."""
        puntos = ([self.salida()] + self.puertos() + self.sprints()
                  + self.puntos_anonimos() + [self.meta()])
        return sorted(puntos, key=lambda punto: punto.distancia)


class Svg:
    """Genera un documento SVG 1.1 con elementos gráficos básicos."""

    ESPACIO_NOMBRES_SVG = "http://www.w3.org/2000/svg"

    def __init__(self, ancho, alto, titulo, descripcion):
        self.raiz = ET.Element("svg", {
            "xmlns": self.ESPACIO_NOMBRES_SVG,
            "version": "1.1",
            "width": str(ancho),
            "height": str(alto),
            "viewBox": f"0 0 {ancho} {alto}",
        })
        ET.SubElement(self.raiz, "title").text = titulo
        ET.SubElement(self.raiz, "desc").text = descripcion

    def add_rect(self, x, y, ancho, alto, relleno):
        """Añade un rectángulo."""
        ET.SubElement(self.raiz, "rect", {
            "x": str(x), "y": str(y),
            "width": str(ancho), "height": str(alto),
            "fill": relleno,
        })

    def add_polyline(self, puntos, relleno, trazo, grosor):
        """Añade una polilínea. Los puntos son una lista de pares (x, y)."""
        ET.SubElement(self.raiz, "polyline", {
            "points": " ".join(f"{x:.1f},{y:.1f}" for x, y in puntos),
            "fill": relleno,
            "stroke": trazo,
            "stroke-width": str(grosor),
            "stroke-linejoin": "round",
        })

    def add_line(self, x1, y1, x2, y2, trazo, grosor, discontinua=False):
        """Añade una línea recta, opcionalmente discontinua."""
        atributos = {
            "x1": f"{x1:.1f}", "y1": f"{y1:.1f}",
            "x2": f"{x2:.1f}", "y2": f"{y2:.1f}",
            "stroke": trazo, "stroke-width": str(grosor),
        }
        if discontinua:
            atributos["stroke-dasharray"] = "3,3"
        ET.SubElement(self.raiz, "line", atributos)

    def add_circle(self, x, y, radio, relleno):
        """Añade un círculo con borde negro."""
        ET.SubElement(self.raiz, "circle", {
            "cx": f"{x:.1f}", "cy": f"{y:.1f}", "r": str(radio),
            "fill": relleno, "stroke": "black", "stroke-width": "1",
        })

    def add_text(self, x, y, texto, tamano, anclaje="start",
                 vertical=False, negrita=False):
        """Añade un texto horizontal o vertical (girado -90 grados)."""
        atributos = {
            "x": f"{x:.1f}", "y": f"{y:.1f}",
            "font-family": "Arial, Helvetica, sans-serif",
            "font-size": str(tamano),
            "text-anchor": anclaje,
        }
        if vertical:
            atributos["transform"] = f"rotate(-90 {x:.1f} {y:.1f})"
        if negrita:
            atributos["font-weight"] = "bold"
        ET.SubElement(self.raiz, "text", atributos).text = texto

    def escribir(self, archivo_svg):
        """Escribe el documento SVG en disco con codificación UTF-8."""
        arbol = ET.ElementTree(self.raiz)
        ET.indent(arbol, space="    ")
        arbol.write(archivo_svg, encoding="UTF-8", xml_declaration=True)


class Xml2Altimetria:
    """Aplicación que convierte etapaEsquema.xml en altimetria.svg."""

    # Dimensiones del dibujo (en píxeles)
    ANCHO = 1600
    ALTO = 900
    MARGEN_IZQ = 80
    MARGEN_DER = 40
    ZONA_ETIQUETAS = 440   # espacio superior para los nombres verticales
    SEPARACION_ETIQUETAS = 13  # distancia mínima entre nombres (px)
    ALTO_PERFIL = 330      # altura del gráfico del perfil
    PASO_KM = 10           # separación de las marcas del eje horizontal
    PASO_ALTITUD = 100     # separación de las líneas horizontales

    COLOR_PUNTO = {
        "salidaMeta": "red",
        "puerto": "green",
        "sprint": "blue",
        "anonimo": "yellow",
    }

    def __init__(self, archivo_xml, archivo_svg):
        self.archivo_xml = archivo_xml
        self.archivo_svg = archivo_svg
        self.base = self.ZONA_ETIQUETAS + self.ALTO_PERFIL
        self.ancho_perfil = self.ANCHO - self.MARGEN_IZQ - self.MARGEN_DER
        self.distancia_max = 0.0
        self.altitud_max = 0

    def _x(self, distancia):
        """Convierte una distancia (km) en coordenada x del dibujo."""
        return (self.MARGEN_IZQ
                + distancia / self.distancia_max * self.ancho_perfil)

    def _y(self, altitud):
        """Convierte una altitud (m) en coordenada y del dibujo."""
        return self.base - altitud / self.altitud_max * self.ALTO_PERFIL

    def _dibujar_escalas(self, svg):
        """Dibuja la escala vertical (altitud) y la horizontal (km)."""
        for altitud in range(0, self.altitud_max + 1, self.PASO_ALTITUD):
            y = self._y(altitud)
            svg.add_line(self.MARGEN_IZQ, y, self.ANCHO - self.MARGEN_DER,
                         y, "#bbbbbb", 1, discontinua=True)
            svg.add_text(self.MARGEN_IZQ - 8, y + 4, f"{altitud} m", 12,
                         anclaje="end")

        for km in range(0, int(self.distancia_max) + 1, self.PASO_KM):
            x = self._x(km)
            svg.add_line(x, self.base, x, self.base + 8, "black", 1)
            svg.add_text(x, self.base + 24, str(km), 12, anclaje="middle")
        svg.add_text(self.ANCHO / 2, self.base + 50,
                     "Distancia desde la salida (km)", 14, anclaje="middle")

        svg.add_line(self.MARGEN_IZQ, self.base,
                     self.ANCHO - self.MARGEN_DER, self.base, "black", 2)
        svg.add_line(self.MARGEN_IZQ, self.base,
                     self.MARGEN_IZQ, self._y(self.altitud_max), "black", 2)

    def _dibujar_perfil(self, svg, perfil):
        """Dibuja la polilínea cerrada y rellena (efecto suelo)."""
        vertices = [(self._x(0), self.base)]
        vertices += [(self._x(p.distancia), self._y(p.altitud))
                     for p in perfil]
        vertices += [(self._x(self.distancia_max), self.base),
                     (self._x(0), self.base)]
        svg.add_polyline(vertices, "#f4a460", "#8b4513", 3)

    def _dibujar_etiquetas(self, svg, perfil):
        """Dibuja marcadores y nombres verticales de cada punto.

        Si dos puntos están muy próximos, el nombre del segundo se desplaza
        a la derecha para que no se solapen, y la línea discontinua lo une
        con su punto del perfil.
        """
        x_anterior = -self.SEPARACION_ETIQUETAS
        for punto in perfil:
            x = self._x(punto.distancia)
            y = self._y(punto.altitud)
            x_etiqueta = max(x, x_anterior + self.SEPARACION_ETIQUETAS)
            x_anterior = x_etiqueta
            svg.add_line(x_etiqueta, self.ZONA_ETIQUETAS - 5, x, y,
                         "#666666", 1, discontinua=True)
            svg.add_circle(x, y, 5, self.COLOR_PUNTO[punto.tipo])
            etiqueta = (f"{punto.nombre} - km {punto.distancia} "
                        f"({punto.altitud} m)")
            svg.add_text(x_etiqueta + 4, self.ZONA_ETIQUETAS - 10, etiqueta,
                         11, vertical=True)

    def _dibujar_leyenda(self, svg):
        """Dibuja la leyenda de colores en la esquina inferior."""
        leyenda = [("salidaMeta", "Salida / Meta"),
                   ("puerto", "Puerto de montaña"),
                   ("sprint", "Sprint intermedio"),
                   ("anonimo", "Punto de paso")]
        x = self.MARGEN_IZQ
        y = self.ALTO - 20
        for tipo, texto in leyenda:
            svg.add_circle(x, y - 4, 6, self.COLOR_PUNTO[tipo])
            svg.add_text(x + 12, y, texto, 13)
            x += 200

    def ejecutar(self):
        """Lee el XML, genera el SVG y lo guarda en disco."""
        lector = LectorEtapa(self.archivo_xml)
        perfil = lector.perfil()

        self.distancia_max = lector.distancia_total()
        altitud_real = max(punto.altitud for punto in perfil)
        self.altitud_max = (math.ceil(altitud_real / self.PASO_ALTITUD)
                            * self.PASO_ALTITUD)

        titulo = (f"Altimetría - Etapa {lector.numero_etapa()}: "
                  f"{lector.nombre_etapa()}")
        svg = Svg(self.ANCHO, self.ALTO, titulo,
                  "Perfil altimétrico de la etapa: altitud (m) "
                  "frente a distancia desde la salida (km)")

        svg.add_rect(0, 0, self.ANCHO, self.ALTO, "white")
        svg.add_text(self.ANCHO / 2, 30, titulo, 20, anclaje="middle",
                     negrita=True)
        self._dibujar_escalas(svg)
        self._dibujar_perfil(svg, perfil)
        self._dibujar_etiquetas(svg, perfil)
        self._dibujar_leyenda(svg)

        svg.escribir(self.archivo_svg)
        print(f"Generado {self.archivo_svg} con {len(perfil)} puntos.")


if __name__ == "__main__":
    Xml2Altimetria("etapaEsquema.xml", "altimetria.svg").ejecutar()