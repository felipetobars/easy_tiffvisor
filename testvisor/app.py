from flask import Flask, request, jsonify, render_template
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np
from PIL import Image
import io, base64
import math

app = Flask(
    __name__,
    static_folder='static',
    template_folder='templates'
)

# Cache para almacenar los valores min/max de cada raster
raster_stats = {}

# Mapeo de métodos de resampling
RESAMPLING_METHODS = {
    'nearest': Resampling.nearest,
    'bilinear': Resampling.bilinear,
    'cubic': Resampling.cubic,
    'average': Resampling.average,
    'lanczos': Resampling.lanczos,
    'mode': Resampling.mode
}

def get_raster_stats(ds, bands):
    """
    Obtiene los valores mínimos y máximos globales para las bandas especificadas.
    """
    stats = {}
    for band in bands:
        if band not in stats:
            # Leer la banda completa
            data = ds.read(band)
            # Ignorar valores nulos o inválidos
            valid_data = data[~np.isnan(data)]
            if len(valid_data) > 0:
                stats[band] = {
                    'min': float(valid_data.min()),
                    'max': float(valid_data.max())
                }
    return stats

@app.route('/')
def index():
    """
    Renderiza la página principal.

    :return: Página HTML del visualizador
    :rtype: flask.Response
    **Dependencias de la función:**
    - ninguna
    """
    return render_template('index.html')

@app.route('/load-raster-info', methods=['POST'])
def load_raster_info():
    """
    Obtiene información básica del raster sin procesar la imagen completa.
    """
    data = request.get_json()
    path = data.get('path')
    if not path:
        return jsonify({'error': 'Ruta no proporcionada'}), 400

    try:
        with rasterio.open(path) as ds:
            # Calcular transformación a EPSG:4326
            dst_crs = 'EPSG:4326'
            transform, width, height = calculate_default_transform(
                ds.crs, dst_crs, ds.width, ds.height, *ds.bounds
            )
            # Calcular bounds en lat/lng
            west, north = transform * (0, 0)
            east, south = transform * (width, height)
            bounds = [[south, west], [north, east]]
            
            # Obtener estadísticas globales para las bandas
            bands = [1, 2, 3]  # Asumimos RGB
            stats = get_raster_stats(ds, bands)
            
            # Almacenar las estadísticas en el cache
            raster_stats[path] = stats
            
            return jsonify({
                'bounds': bounds,
                'count': ds.count,
                'width': width,
                'height': height,
                'transform': list(transform)[:6],  # Convertir transform a lista para JSON
                'stats': stats,  # Incluir estadísticas en la respuesta
                'resampling_methods': list(RESAMPLING_METHODS.keys())  # Incluir métodos de resampling disponibles
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/load-raster-tile', methods=['POST'])
def load_raster_tile():
    """
    Procesa una porción específica del raster según el viewport actual.
    """
    data = request.get_json()
    path = data.get('path')
    bounds = data.get('bounds')  # [[south,west], [north,east]]
    bands = data.get('bands', {})
    zoom = data.get('zoom', 0)
    resampling_method = data.get('resampling', 'bilinear')  # Método de resampling por defecto
    
    if not path or not bounds:
        return jsonify({'error': 'Parámetros incompletos'}), 400

    try:
        with rasterio.open(path) as ds:
            # Obtener el método de resampling
            resampling = RESAMPLING_METHODS.get(resampling_method, Resampling.bilinear)
            
            # Calcular tamaño del tile basado en el zoom
            tile_size = 256  # Tamaño estándar de tile
            scale = 2 ** zoom
            
            # Convertir bounds a coordenadas de píxeles
            dst_crs = 'EPSG:4326'
            transform, width, height = calculate_default_transform(
                ds.crs, dst_crs, ds.width, ds.height, *ds.bounds
            )
            
            # Calcular índices de píxeles para el tile
            west, north = transform * (0, 0)
            east, south = transform * (width, height)
            
            # Calcular índices de píxeles para el tile actual
            x0 = int((bounds[0][1] - west) / (east - west) * width)
            y0 = int((north - bounds[1][0]) / (north - south) * height)
            x1 = int((bounds[1][1] - west) / (east - west) * width)
            y1 = int((north - bounds[0][0]) / (north - south) * height)
            
            # Asegurar que los índices estén dentro de los límites
            x0, x1 = max(0, min(x0, width)), max(0, min(x1, width))
            y0, y1 = max(0, min(y0, height)), max(0, min(y1, height))
            
            # Calcular el tamaño de salida basado en el zoom
            if zoom < 0:
                scale_factor = 2 ** abs(zoom)
                out_width = int((x1 - x0) / scale_factor)
                out_height = int((y1 - y0) / scale_factor)
            else:
                out_width = x1 - x0
                out_height = y1 - y0
            
            # Asegurar un tamaño mínimo para evitar tiles muy pequeños
            out_width = max(1, out_width)
            out_height = max(1, out_height)
            
            # Leer solo la porción visible del raster
            window = rasterio.windows.Window(x0, y0, x1-x0, y1-y0)
            
            # Procesar las bandas seleccionadas
            rgb = np.zeros((out_height, out_width, 3), np.uint8)
            
            # Obtener las estadísticas globales del raster
            stats = raster_stats.get(path, {})
            
            # Leer todas las bandas de una vez para mejor rendimiento
            band_indices = [bands.get('r', 1), bands.get('g', 1), bands.get('b', 1)]
            band_data = ds.read(band_indices, window=window, out_shape=(out_height, out_width), resampling=resampling)
            
            for idx, (band_idx, dest_channel) in enumerate(zip(band_indices, range(3))):
                # Usar los valores min/max globales para la normalización
                band_stats = stats.get(band_idx, {})
                if band_stats:
                    min_val = band_stats['min']
                    max_val = band_stats['max']
                    # Normalizar usando los valores globales
                    arr = ((band_data[idx] - min_val) / (max_val - min_val) * 255).clip(0, 255).astype(np.uint8)
                else:
                    # Fallback a normalización local si no hay estadísticas globales
                    valid_data = band_data[idx][~np.isnan(band_data[idx])]
                    if len(valid_data) > 0:
                        min_val = valid_data.min()
                        max_val = valid_data.max()
                        arr = ((band_data[idx] - min_val) / (max_val - min_val) * 255).clip(0, 255).astype(np.uint8)
                    else:
                        arr = np.zeros_like(band_data[idx], dtype=np.uint8)
                
                rgb[:, :, dest_channel] = arr
            
            # Generar PNG
            img = Image.fromarray(rgb)
            buf = io.BytesIO()
            img.save(buf, format='PNG', optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            
            return jsonify({
                'image': b64,
                'bounds': bounds
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)