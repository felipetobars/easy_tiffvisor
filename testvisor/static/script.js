// Inicializa Leaflet
document.addEventListener('DOMContentLoaded', () => {
  const map = L.map('map').setView([0, 0], 2);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 22,
    attribution: '© OpenStreetMap'
  }).addTo(map);

  let currentPath = null;
  let currentBands = { r: 1, g: 2, b: 3 };
  let currentOpacity = 1;
  let currentResampling = 'bilinear';
  let rasterBounds = null;
  let tileLayers = new Map();

  // Función para cargar un tile específico
  async function loadTile(bounds, zoom) {
    const key = `${bounds[0][0]},${bounds[0][1]},${bounds[1][0]},${bounds[1][1]}`;
    if (tileLayers.has(key)) return;

    try {
      const resp = await fetch('/load-raster-tile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: currentPath,
          bounds: bounds,
          bands: currentBands,
          zoom: zoom,
          resampling: currentResampling
        })
      });
      const data = await resp.json();
      if (data.error) throw new Error(data.error);

      const imgUrl = 'data:image/png;base64,' + data.image;
      const layer = L.imageOverlay(imgUrl, bounds, { opacity: currentOpacity }).addTo(map);
      
      // Limpiar la URL de datos después de cargar la imagen
      const img = layer.getElement();
      img.onload = () => {
        URL.revokeObjectURL(imgUrl);
      };
      
      tileLayers.set(key, layer);
    } catch (err) {
      console.error('Error loading tile:', err);
    }
  }

  // Función para limpiar tiles fuera del viewport
  function cleanupTiles() {
    const mapBounds = map.getBounds();
    const padding = 0.1;
    const paddedBounds = mapBounds.pad(padding);

    // Limpiar todos los tiles que no están en el viewport actual
    for (const [key, layer] of tileLayers.entries()) {
      const [south, west, north, east] = key.split(',').map(Number);
      const tileBounds = L.latLngBounds([south, west], [north, east]);
      
      if (!paddedBounds.intersects(tileBounds)) {
        // Remover la capa del mapa
        map.removeLayer(layer);
        // Eliminar la referencia al elemento de imagen
        if (layer.getElement()) {
          layer.getElement().src = '';
        }
        // Eliminar la capa del Map
        tileLayers.delete(key);
      }
    }
  }

  // Función para cargar tiles necesarios
  function loadVisibleTiles() {
    if (!currentPath || !rasterBounds) return;

    const mapBounds = map.getBounds();
    if (!mapBounds.intersects(rasterBounds)) return;

    const zoom = map.getZoom();
    const tileSize = 256;
    const scale = Math.pow(2, zoom);

    // Calcular la intersección de los bounds del mapa con los bounds del raster
    const sw = mapBounds.getSouthWest();
    const ne = mapBounds.getNorthEast();
    const rasterSW = rasterBounds.getSouthWest();
    const rasterNE = rasterBounds.getNorthEast();

    const bounds = L.latLngBounds(
      [Math.max(sw.lat, rasterSW.lat), Math.max(sw.lng, rasterSW.lng)],
      [Math.min(ne.lat, rasterNE.lat), Math.min(ne.lng, rasterNE.lng)]
    );

    // Calcular el tamaño de cada tile en grados
    const tileSizeDegrees = tileSize / scale;

    // Dividir el viewport en tiles, asegurando que no se superpongan
    const tiles = [];
    for (let lat = bounds.getSouth(); lat < bounds.getNorth(); lat += tileSizeDegrees) {
      for (let lng = bounds.getWest(); lng < bounds.getEast(); lng += tileSizeDegrees) {
        const tileBounds = [
          [lat, lng],
          [Math.min(lat + tileSizeDegrees, bounds.getNorth()), 
           Math.min(lng + tileSizeDegrees, bounds.getEast())]
        ];
        tiles.push(tileBounds);
      }
    }

    // Limpiar tiles existentes antes de cargar nuevos
    cleanupTiles();

    // Cargar tiles
    tiles.forEach(bounds => loadTile(bounds, zoom));
  }

  // Eventos del mapa
  map.on('moveend', () => {
    cleanupTiles();
    loadVisibleTiles();
  });

  map.on('zoomend', () => {
    cleanupTiles();
    loadVisibleTiles();
  });

  // Evento del botón de carga
  document.getElementById('load-btn').addEventListener('click', async () => {
    const path = document.getElementById('path-input').value;
    if (!path) { alert('Ingresa la ruta al archivo .tif'); return; }

    try {
      // Limpiar tiles existentes
      tileLayers.forEach(layer => map.removeLayer(layer));
      tileLayers.clear();

      // Obtener información del raster
      const resp = await fetch('/load-raster-info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path })
      });
      const data = await resp.json();
      if (data.error) throw new Error(data.error);

      // Actualizar estado
      currentPath = path;
      currentBands = {
        r: parseInt(document.getElementById('band-r').value, 10),
        g: parseInt(document.getElementById('band-g').value, 10),
        b: parseInt(document.getElementById('band-b').value, 10)
      };
      currentOpacity = parseFloat(document.getElementById('opacity').value);
      currentResampling = document.getElementById('resampling').value;
      rasterBounds = L.latLngBounds(data.bounds);

      // Ajustar rangos de los inputs de banda
      const maxBand = data.count;
      ['band-r','band-g','band-b'].forEach(id => {
        const inp = document.getElementById(id);
        inp.max = maxBand;
        if (parseInt(inp.value,10) > maxBand) inp.value = maxBand;
      });

      // Centrar mapa en el raster
      map.fitBounds(rasterBounds);
      
      // Cargar tiles iniciales
      loadVisibleTiles();

    } catch (err) {
      alert('Error: ' + err.message);
    }
  });

  // Evento para actualizar opacidad
  document.getElementById('opacity').addEventListener('input', (e) => {
    currentOpacity = parseFloat(e.target.value);
    tileLayers.forEach(layer => layer.setOpacity(currentOpacity));
  });

  // Evento para actualizar método de resampling
  document.getElementById('resampling').addEventListener('change', (e) => {
    currentResampling = e.target.value;
    // Recargar tiles con el nuevo método de resampling
    tileLayers.forEach(layer => map.removeLayer(layer));
    tileLayers.clear();
    loadVisibleTiles();
  });
});