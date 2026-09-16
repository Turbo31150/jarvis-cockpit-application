#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_ico.py — Fabrique icons/jarvis_cockpit.ico (multi-tailles) a partir de
icons/1_jarvis_cockpit_os.png, SANS dependance supplementaire.

Le format ICO accepte des images compressees en PNG (Vista+). On redimensionne
le PNG source avec PyQt6 (deja requis par l'application) puis on ecrit
soi-meme le conteneur ICO : en-tete + repertoire + trames PNG.

Usage :
    python icons/make_ico.py                      # PNG par defaut -> jarvis_cockpit.ico
    python icons/make_ico.py source.png cible.ico # chemins explicites

Fonctionne aussi sous Linux (mode offscreen force), mais n'y sert a rien :
l'icone .ico n'est utilisee que par les raccourcis Windows.
"""

import os
import struct
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
SOURCE_DEFAUT = os.path.join(ICI, "1_jarvis_cockpit_os.png")
CIBLE_DEFAUT = os.path.join(ICI, "jarvis_cockpit.ico")

# Tailles classiques attendues par l'Explorateur / la barre des taches.
TAILLES = (16, 24, 32, 48, 64, 128, 256)


def _trames_png(source):
    """Retourne [(taille, octets_png)] pour chaque taille de TAILLES."""
    # Pas de fenetre : on ne veut que le moteur d'images de Qt.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtCore import QBuffer, QIODevice, Qt
    from PyQt6.QtGui import QGuiApplication, QImage

    # QImage suffit en theorie, mais certaines plateformes exigent une
    # QGuiApplication avant tout usage du module image (plugins).
    _app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])

    img = QImage(source)
    if img.isNull():
        raise SystemExit(f"Image source illisible : {source}")
    img = img.convertToFormat(QImage.Format.Format_ARGB32)

    trames = []
    for taille in TAILLES:
        petite = img.scaled(
            taille, taille,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        if not petite.save(buf, "PNG"):
            raise SystemExit(f"Echec encodage PNG {taille}px")
        trames.append((taille, bytes(buf.data())))
        buf.close()
    return trames


def ecrire_ico(trames, cible):
    """Ecrit un fichier ICO dont chaque entree est une trame PNG.

    Structure (little-endian) :
      ICONDIR      : reserve(2)=0, type(2)=1, nombre(2)
      ICONDIRENTRY : largeur(1), hauteur(1), couleurs(1)=0, reserve(1)=0,
                     plans(2)=1, bpp(2)=32, taille(4), offset(4)
      puis les donnees, dans l'ordre du repertoire.
    """
    nombre = len(trames)
    en_tete = struct.pack("<HHH", 0, 1, nombre)
    offset = 6 + 16 * nombre
    repertoire = b""
    donnees = b""
    for taille, png in trames:
        # 256 se code 0 dans l'en-tete (octet unique).
        dim = 0 if taille >= 256 else taille
        repertoire += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        donnees += png
        offset += len(png)
    with open(cible, "wb") as fh:
        fh.write(en_tete + repertoire + donnees)


def verifier_ico(cible):
    """Controle minimal : en-tete coherent et trames PNG bien placees."""
    with open(cible, "rb") as fh:
        blob = fh.read()
    reserve, type_, nombre = struct.unpack_from("<HHH", blob, 0)
    if reserve != 0 or type_ != 1 or nombre == 0:
        raise SystemExit("ICO invalide : en-tete incoherent")
    for i in range(nombre):
        _w, _h, _c, _r, _p, _bpp, taille, offset = struct.unpack_from(
            "<BBBBHHII", blob, 6 + 16 * i)
        if blob[offset:offset + 8] != b"\x89PNG\r\n\x1a\n":
            raise SystemExit(f"ICO invalide : trame {i} n'est pas un PNG")
        if offset + taille > len(blob):
            raise SystemExit(f"ICO invalide : trame {i} tronquee")
    return nombre, len(blob)


def main(argv):
    source = argv[1] if len(argv) > 1 else SOURCE_DEFAUT
    cible = argv[2] if len(argv) > 2 else CIBLE_DEFAUT
    if not os.path.isfile(source):
        raise SystemExit(f"PNG source introuvable : {source}")
    trames = _trames_png(source)
    ecrire_ico(trames, cible)
    nombre, octets = verifier_ico(cible)
    print(f"OK : {cible} ({nombre} tailles, {octets} octets)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
