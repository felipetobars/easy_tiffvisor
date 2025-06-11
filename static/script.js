// static/script.js

// 1) Inicializamos el mapa sin vista ni capas
const map = L.map('map', {
  // opcionalmente puedes desactivar la animación por defecto
  zoomSnap: 0.5
});

// 2) Pedimos la configuración tipo TileJSON a nuestro Flask
fetch('/metadata.json')
  .then(response => response.json())
  .then(meta => {
    // 2.1) Creamos bounds a partir de la metadata
    const [minX, minY, maxX, maxY] = meta.bounds;
    const bounds = L.latLngBounds(
      L.latLng(minY, minX),
      L.latLng(maxY, maxX)
    );

    // 2.2) Ajustamos la vista al extent del ráster (hace zoom y centra)
    map.fitBounds(bounds);

    // 3) Añadimos la capa base (ahora que la vista ya está fijada)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19
    }).addTo(map);

    // 4) Añadimos tu capa de GeoTIFF encima
    L.tileLayer(meta.tiles[0], {
      bounds: bounds,
      minZoom: meta.minzoom,
      maxZoom: meta.maxzoom,
      tileSize: 256,
      opacity: 0.7,
      attribution: 'GeoTIFF overlay'
    }).addTo(map);
  })
  .catch(err => {
    console.error('Error cargando metadata:', err);
    // Si falla, centramos en Bogotá como fallback
    map.setView([4.55, -74.1], 13);
    // Y añadimos solo la base
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19
    }).addTo(map);
  });
