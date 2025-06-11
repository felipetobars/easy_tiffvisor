# test_backend.py

from backend import GDALTileReader
from matplotlib import pyplot as plt
import numpy as np

reader = GDALTileReader("data/vergel.tif")

bounds = reader.get_bounds()
print("Bounds de la imagen:", bounds)

bbox = reader.get_center_bbox(size_deg=0.002)
print("BBOX centrado:", bbox)

tile = reader.tile(bbox, tile_size=256)

# Visualización
plt.imshow(np.transpose(tile, (1, 2, 0)))
plt.title("Tile centrado en EPSG:4326")
plt.axis("off")
plt.show()
