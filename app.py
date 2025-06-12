# app.py

from flask import Flask, send_file, jsonify, send_from_directory, request
from io import BytesIO
from PIL import Image
import numpy as np
from math import pi, atan, sinh
from tiffvisor.backend import GDALTileReader

app = Flask(__name__, static_folder="static", static_url_path="")
reader = GDALTileReader(raster_path="vergel_3857.tif")

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

@app.route("/metadata.json")
def metadata():
    bounds = reader.get_bounds()
    return jsonify({
        "bounds": bounds,                        # [minX, minY, maxX, maxY]
        "minzoom": 0,
        "maxzoom": 20,
        "tiles": ["/tiles/{z}/{x}/{y}.png"]
    })

@app.route("/raster-metadata")
def raster_metadata():
    return jsonify(reader.get_metadata())

@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def serve_tile(z, x, y):
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

if __name__=="__main__":
    from flask_cors import CORS
    CORS(app)  # Titiler habilita CORS por defecto
    app.run(debug=True)
