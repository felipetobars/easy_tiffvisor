# 🗺️ EASY-TIFFVISOR
*Visualizador GeoTIFF en Flask + Leaflet*

Este proyecto es un visor web ligero y rápido que permite explorar archivos GeoTIFF georreferenciados usando una interfaz moderna basada en Leaflet. Ideal para visualizar imágenes satelitales o aéreas sobre mapas base.

(¡AÚN EN DESARROLLO!) 

---

## 🚀 Características

- 📡 Soporte para imágenes **GeoTIFF georreferenciadas**
- 🧭 Compatible con mapas base como **OpenStreetMap**
- 🎯 Renderizado de tiles en tiempo real con **GDAL**
- ⚡ Servidor ligero en **Flask**

---

## 📁 Estructura del proyecto
```
tiffvisor/
├── app.py # Servidor Flask
├── backend.py # Lectura de tiles con GDAL
├── static/
│ ├── index.html # Interfaz principal con Leaflet
│ ├── style.css # Estilos
│ └── script.js # Lógica del visor
├── test.tif # Archivo GeoTIFF a visualizar
├── README.md # Este archivo :)
└──LICENCE
```

## ⚙️ Requisitos

- Python 3.9+
- GDAL (con bindings de Python)
- Flask
- Pillow
- NumPy

Instalación con `conda` (recomendado):

```bash
conda create -n tiffvisor python=3.10
conda activate tiffvisor
conda install gdal flask numpy pillow
```
## 🖥️ Uso
1. Asegúrate de tener tu archivo GeoTIFF reproyectado a EPSG:3857.

    Ejecuta el servidor:

    ```bash
    python app.py
    ```
2. Abre tu navegador en:

    ```bash
    http://127.0.0.1:5000
    ```
¡Listo! Podrás explorar tu raster sobre el mapa base de Leaflet.


## 📝 Pendientes provisionales
📌 Selector de ráster desde el navegador

🖼️ Renderizado de canales individuales (R, G, B, NDVI…)

🧩 Carga de GeoTIFFs grandes mediante VRT

