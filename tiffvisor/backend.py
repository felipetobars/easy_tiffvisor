# tiffvisor/backend.py

import os
import threading
from typing import Tuple, Union
import numpy as np
from osgeo import gdal, gdal_array, osr

gdal.UseExceptions()

class GDALTileReader:
    def __init__(self, raster_path: str):
        self.raster_path = raster_path
        self._lock = threading.Lock()
        self._ensure_overviews()

    def _ensure_overviews(self):
        """Borra .ovr corruptos y (re)genera pirámides."""
        ovr = self.raster_path + ".ovr"
        if os.path.exists(ovr):
            os.remove(ovr)
        ds = gdal.Open(self.raster_path, gdal.GA_Update)
        ds.BuildOverviews("AVERAGE", [2, 4, 8, 16, 32])
        ds = None

    def tile(self,
         bbox: Tuple[float, float, float, float],
         tile_size: int = 256,
         resampling: str = "bilinear",
         bands: Tuple[int, int, int] = (1, 2, 3)
        ) -> np.ndarray:
        """
        Devuelve un array (bands, tile_size, tile_size) para el bbox dado.
        """
        with self._lock:
            ds = gdal.Open(self.raster_path, gdal.GA_ReadOnly)
            gt = ds.GetGeoTransform()

            # Invertir GeoTransform y descomponer coeficientes
            inv = gdal.InvGeoTransform(gt)

            # Soportar bounding box de mercantile
            if hasattr(bbox, "west"):
                xmin, ymin, xmax, ymax = bbox.west, bbox.south, bbox.east, bbox.north
            else:
                xmin, ymin, xmax, ymax = bbox

            # Reproyectar bbox de EPSG:4326 al CRS del raster
            src = osr.SpatialReference()
            src.ImportFromEPSG(4326)
            dst = osr.SpatialReference()
            dst.ImportFromWkt(ds.GetProjection())
            transform = osr.CoordinateTransformation(src, dst)
            xmin, ymin, _ = transform.TransformPoint(xmin, ymin)
            xmax, ymax, _ = transform.TransformPoint(xmax, ymax)

            # Convertir bbox reproyectado a ventana de píxeles (usando splat)
            px0, py0 = gdal.ApplyGeoTransform(inv, xmin, ymax)
            px1, py1 = gdal.ApplyGeoTransform(inv, xmax, ymin)

            # Clamp
            px0, px1 = sorted((int(px0), int(px1)))
            py0, py1 = sorted((int(py0), int(py1)))
            px0 = max(0, px0); py0 = max(0, py0)
            px1 = min(ds.RasterXSize, px1); py1 = min(ds.RasterYSize, py1)
            wx, hy = px1 - px0, py1 - py0

            # Si fuera de bounds → tile negro
            if wx <= 0 or hy <= 0:
                dtype = gdal_array.GDALTypeCodeToNumericTypeCode(
                    ds.GetRasterBand(bands[0]).DataType
                )
                return np.zeros((len(bands), tile_size, tile_size), dtype=dtype)

            # Resampling
            resmap = {
                "nearest": gdal.GRIORA_NearestNeighbour,
                "bilinear": gdal.GRIORA_Bilinear,
                "cubic": gdal.GRIORA_Cubic,
                "average": gdal.GRIORA_Average
            }[resampling]

            raw = ds.ReadRaster(
                px0, py0, wx, hy,
                tile_size, tile_size,
                band_list=[int(b) for b in bands],
                resample_alg=resmap
            )

            dtype = gdal_array.GDALTypeCodeToNumericTypeCode(
                ds.GetRasterBand(bands[0]).DataType
            )
            arr = np.frombuffer(raw, dtype=dtype)
            return arr.reshape((len(bands), tile_size, tile_size))

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """
        Devuelve (minLon, minLat, maxLon, maxLat) en EPSG:4326.
        """
        ds = gdal.Open(self.raster_path, gdal.GA_ReadOnly)
        gt = ds.GetGeoTransform()
        w, h = ds.RasterXSize, ds.RasterYSize

        src = osr.SpatialReference()
        src.ImportFromWkt(ds.GetProjection())
        dst = osr.SpatialReference()
        dst.ImportFromEPSG(4326)
        transform = osr.CoordinateTransformation(src, dst)

        lons, lats = [], []
        for px, py in [(0, 0), (w, 0), (0, h), (w, h)]:
            x = gt[0] + px * gt[1] + py * gt[2]
            y = gt[3] + px * gt[4] + py * gt[5]
            lon, lat, _ = transform.TransformPoint(x, y)
            lons.append(lon)
            lats.append(lat)

        return (min(lons), min(lats), max(lons), max(lats))

    def get_center_bbox(self, size_deg: float = 0.002) -> Tuple[float, float, float, float]:
        """
        Devuelve un bbox pequeño centrado en la imagen.

        :param size_deg: tamaño del bbox en grados (ancho y alto)
        :type size_deg: float
        :return: bbox centrado
        :rtype: Tuple[float, float, float, float]
        """
        minx, miny, maxx, maxy = self.get_bounds()
        cx = (minx + maxx) / 2
        cy = (miny + maxy) / 2
        half = size_deg / 2
        return (cx - half, cy - half, cx + half, cy + half)

    def get_metadata(self) -> dict:
        """
        Devuelve los metadatos del ráster incluyendo información de las bandas.
        """
        ds = gdal.Open(self.raster_path, gdal.GA_ReadOnly)
        metadata = {
            "driver": ds.GetDriver().ShortName,
            "size": [ds.RasterXSize, ds.RasterYSize],
            "projection": ds.GetProjection(),
            "geotransform": ds.GetGeoTransform(),
            "bands": []
        }
        
        for i in range(ds.RasterCount):
            band = ds.GetRasterBand(i + 1)
            band_info = {
                "index": i + 1,
                "type": gdal.GetDataTypeName(band.DataType),
                "no_data_value": band.GetNoDataValue(),
                "color_interpretation": gdal.GetColorInterpretationName(band.GetColorInterpretation()),
                "description": band.GetDescription() or f"Band {i + 1}"
            }
            metadata["bands"].append(band_info)
            
        return metadata
