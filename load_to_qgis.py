#!/usr/bin/env python3
"""
QGIS Import Script for UP Cadastral GeoJSON
Usage:
  1. Open QGIS → Plugins → Python Console
  2. Paste and run this script
  3. Or run standalone: python load_to_qgis.py --file agra_cadastral.geojson
"""
import argparse
import os
import sys
from pathlib import Path

try:
    from qgis.core import QgsProject, QgsVectorLayer, QgsFillSymbol, QgsSingleSymbolRenderer
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


def style_cadastral_layer(layer):
    """Apply a clean BhuNaksha-like style to the cadastral layer."""
    symbol = QgsFillSymbol.createSimple({
        'color': 'rgba(66, 153, 225, 40)',
        'outline_color': '#2b6cb0',
        'outline_width': '0.35'
    })
    renderer = QgsSingleSymbolRenderer(symbol)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def load_into_qgis(file_path, layer_name="UP_Cadastral"):
    if not QGIS_AVAILABLE:
        print("❌ PyQGIS not available. Run this inside QGIS Python Console.")
        sys.exit(1)

    file_path = Path(file_path).resolve()
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)

    uri = str(file_path)
    layer = QgsVectorLayer(uri, layer_name, "ogr")

    if not layer.isValid():
        print(f"❌ Failed to load layer from: {file_path}")
        sys.exit(1)

    style_cadastral_layer(layer)
    QgsProject.instance().addMapLayer(layer)

    canvas = iface.mapCanvas()
    canvas.setExtent(layer.extent())
    canvas.refresh()

    print(f"✅ Loaded '{layer_name}' with {layer.featureCount():,} features")
    print(f"   Extent: {layer.extent().toString()}")
    print(f"   CRS: {layer.crs().authid()}")


def main():
    parser = argparse.ArgumentParser(description="Load UP Cadastral GeoJSON into QGIS")
    parser.add_argument("--file", default="agra_cadastral.geojson", help="Path to GeoJSON file")
    parser.add_argument("--name", default="UP_Cadastral", help="Layer name in QGIS")
    args = parser.parse_args()

    load_into_qgis(args.file, args.name)


if __name__ == "__main__":
    main()
