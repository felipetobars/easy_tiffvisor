# app.py

from flask import Flask, send_file, jsonify, send_from_directory, request
from io import BytesIO
from PIL import Image
import numpy as np
from math import pi, atan, sinh
from tiffvisor.backend import GDALTileReader
import os
import tempfile
import shutil

app = Flask(__name__, static_folder="static", static_url_path="")

# Diccionario para mantener los readers activos
active_readers = {}

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

def tile_to_bbox(x, y, z):
    n = 2**z
    lon1 = x/n * 360 - 180
    lat1 = atan(sinh(pi*(1-2*y/n))) * 180/pi
    lon2 = (x+1)/n * 360 - 180
    lat2 = atan(sinh(pi*(1-2*(y+1)/n))) * 180/pi
    return (lon1, lat2, lon2, lat1)

@app.route("/upload-raster", methods=['POST'])
def upload_raster():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.lower().endswith(('.tif', '.tiff')):
        return jsonify({'error': 'File must be a GeoTIFF'}), 400

    # Crear directorio temporal único para este archivo
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    file.save(temp_path)

    try:
        # Crear nuevo reader y obtener su ID
        reader_id = str(len(active_readers))
        reader = GDALTileReader(temp_path)
        active_readers[reader_id] = {
            'reader': reader,
            'temp_dir': temp_dir,
            'temp_path': temp_path
        }

        # Obtener bounds y metadata
        bounds = reader.get_bounds()
        metadata = reader.get_metadata()

        return jsonify({
            'reader_id': reader_id,
            'bounds': bounds,
            'metadata': metadata,
            'minzoom': 0,
            'maxzoom': 20,
            'tiles': [f"/tiles/{reader_id}/{{z}}/{{x}}/{{y}}.png"]
        })

    except Exception as e:
        # Limpiar en caso de error
        shutil.rmtree(temp_dir)
        return jsonify({'error': str(e)}), 500

@app.route("/tiles/<reader_id>/<int:z>/<int:x>/<int:y>.png")
def serve_tile(reader_id, z, x, y):
    if reader_id not in active_readers:
        return jsonify({'error': 'Invalid reader ID'}), 404

    reader = active_readers[reader_id]['reader']
    bbox = tile_to_bbox(x, y, z)
    
    try:
        # Obtener las bandas seleccionadas de los parámetros de la URL
        bands = request.args.get('bands', '1,2,3')
        bands = tuple(map(int, bands.split(',')))
        
        arr = reader.tile(bbox, tile_size=256, resampling="bilinear", bands=bands)
    except Exception as e:
        app.logger.error(f"Tile fault {z}/{x}/{y}: {e}")
        arr = np.zeros((3,256,256), dtype=np.uint8)

    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(np.transpose(arr, (1,2,0)))
    buf = BytesIO(); img.save(buf, "PNG"); buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.route("/cleanup/<reader_id>", methods=['POST'])
def cleanup_reader(reader_id):
    if reader_id in active_readers:
        try:
            reader_data = active_readers[reader_id]
            # Cerrar el dataset GDAL si está abierto
            if hasattr(reader_data['reader'], '_ds') and reader_data['reader']._ds:
                reader_data['reader']._ds = None
            # Eliminar el directorio temporal
            if os.path.exists(reader_data['temp_dir']):
                shutil.rmtree(reader_data['temp_dir'])
            # Eliminar el reader del diccionario
            del active_readers[reader_id]
            return jsonify({'success': True})
        except Exception as e:
            app.logger.error(f"Error cleaning up reader {reader_id}: {str(e)}")
            return jsonify({'error': f'Error cleaning up: {str(e)}'}), 500
    return jsonify({'error': 'Invalid reader ID'}), 404

if __name__=="__main__":
    from flask_cors import CORS
    CORS(app)
    app.run(debug=True)
