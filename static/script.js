// static/script.js

let rasterLayer = null;
let currentBands = [1, 2, 3];
let meta = null;
let bounds = null;
let currentOpacity = 1;
let currentReaderId = null;

// 1) Inicializamos el mapa sin vista ni capas
const map = L.map('map', {
  // opcionalmente puedes desactivar la animación por defecto
  zoomSnap: 0.5
});

// Centrar en Bogotá por defecto
map.setView([4.55, -74.1], 13);

// Añadir capa base
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors',
  maxZoom: 19
}).addTo(map);

// Función para actualizar la capa del ráster
function updateRasterLayer(bands = currentBands, opacity = currentOpacity) {
  if (!meta || !bounds) return;
  
  if (rasterLayer) {
    map.removeLayer(rasterLayer);
  }
  
  const tileUrl = `${meta.tiles[0]}?bands=${bands.join(',')}`;
  
  rasterLayer = L.tileLayer(tileUrl, {
    bounds: bounds,
    minZoom: meta.minzoom,
    maxZoom: meta.maxzoom,
    tileSize: 256,
    opacity: opacity,
    attribution: 'GeoTIFF overlay'
  }).addTo(map);
}

// Función para cargar los metadatos del ráster
function loadRasterMetadata(metadata) {
  // Función para extraer información relevante de la proyección
  function getSimplifiedProjection(proj) {
    try {
      // Extraer el nombre del sistema de coordenadas
      const projcsMatch = proj.match(/PROJCS\["([^"]+)"/);
      const geogcsMatch = proj.match(/GEOGCS\["([^"]+)"/);
      
      // Buscar el último EPSG en la cadena
      const epsgMatches = [...proj.matchAll(/AUTHORITY\["EPSG","(\d+)"\]/g)];
      const lastEpsg = epsgMatches.length > 0 ? epsgMatches[epsgMatches.length - 1][1] : null;
      
      let simplified = '';
      if (projcsMatch) {
        simplified += projcsMatch[1];
      } else if (geogcsMatch) {
        simplified += geogcsMatch[1];
      }
      
      if (lastEpsg) {
        simplified += ` (EPSG:${lastEpsg})`;
      }
      
      return simplified || 'No definida';
    } catch (e) {
      return 'Error al parsear proyección';
    }
  }

  // Mostrar metadatos
  const metadataContent = document.getElementById('metadata-content');
  const simplifiedProj = getSimplifiedProjection(metadata.projection);
  
  // Calcular resolución espacial
  const gt = metadata.geotransform;
  const xRes = Math.abs(gt[1]); // Resolución en X
  const yRes = Math.abs(gt[5]); // Resolución en Y
  
  metadataContent.innerHTML = `
    <div class="metadata-item">
      <span class="metadata-label">Driver:</span> ${metadata.driver}
    </div>
    <div class="metadata-item">
      <span class="metadata-label">Tamaño:</span><br>
      Ancho: ${metadata.size[0]} px<br>
      Alto: ${metadata.size[1]} px
    </div>
    <div class="metadata-item">
      <span class="metadata-label">Resolución:</span><br>
      X: ${xRes.toFixed(2)} m/px<br>
      Y: ${yRes.toFixed(2)} m/px
    </div>
    <div class="metadata-item">
      <span class="metadata-label">Proyección:</span> 
      <div class="projection-info">
        <span class="simplified-proj">${simplifiedProj}</span>
        <button class="show-full-proj" onclick="this.parentElement.classList.toggle('expanded')">
          <span class="show-text">Ver detalles</span>
          <span class="hide-text">Ocultar detalles</span>
        </button>
        <div class="full-proj">${metadata.projection}</div>
      </div>
    </div>
    <div class="metadata-item">
      <span class="metadata-label">Bandas:</span> ${metadata.bands.length}
    </div>
  `;

  // Agregar sección del botón de zoom al final
  const zoomSection = document.createElement('div');
  zoomSection.className = 'section';
  zoomSection.innerHTML = `
    <button id="zoom-to-raster" class="zoom-button">🔍 Zoom al ráster</button>
  `;
  document.querySelector('.panel-content').appendChild(zoomSection);

  // Agregar evento para el botón de zoom
  document.getElementById('zoom-to-raster').addEventListener('click', function() {
    map.fitBounds(bounds);
  });

  // Llenar selectores de bandas
  const bandSelects = ['red-band', 'green-band', 'blue-band'];
  bandSelects.forEach((selectId, index) => {
    const select = document.getElementById(selectId);
    select.innerHTML = metadata.bands.map(band => 
      `<option value="${band.index}" ${band.index === currentBands[index] ? 'selected' : ''}>
        ${band.description} (${band.color_interpretation})
      </option>`
    ).join('');
  });
}

// Función para limpiar el estado actual
function cleanupCurrentState() {
  // Limpiar la capa del ráster
  if (rasterLayer) {
    map.removeLayer(rasterLayer);
    rasterLayer = null;
  }
  
  // Resetear variables globales
  currentBands = [1, 2, 3];
  meta = null;
  bounds = null;
  currentOpacity = 1;
  
  // Limpiar metadatos
  const metadataContent = document.getElementById('metadata-content');
  metadataContent.innerHTML = '';
  
  // Resetear selectores de bandas
  const bandSelects = ['red-band', 'green-band', 'blue-band'];
  bandSelects.forEach(selectId => {
    const select = document.getElementById(selectId);
    select.innerHTML = '';
  });
  
  // Remover botón de zoom si existe
  const zoomButton = document.getElementById('zoom-to-raster');
  if (zoomButton) {
    zoomButton.parentElement.remove();
  }

  // Ocultar botón de limpiar
  document.getElementById('clear-raster').style.display = 'none';
}

// Función para manejar la carga de un nuevo archivo desde ruta local
async function handlePathUpload(path) {
  if (!path || (!path.toLowerCase().endsWith('.tif') && !path.toLowerCase().endsWith('.tiff'))) {
    alert('Por favor, ingresa una ruta válida a un archivo GeoTIFF.');
    return;
  }

  try {
    // Limpiar estado anterior
    cleanupCurrentState();
    // Limpiar reader anterior si existe
    if (currentReaderId) {
      await fetch(`/cleanup/${currentReaderId}`, { method: 'POST' });
      currentReaderId = null;
    }
    const response = await fetch('/open-local-raster', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Error al cargar el archivo');
    }
    const data = await response.json();
    // Actualizar estado global
    currentReaderId = data.reader_id;
    meta = data;
    bounds = L.latLngBounds(
      L.latLng(data.bounds[1], data.bounds[0]),
      L.latLng(data.bounds[3], data.bounds[2])
    );
    // Actualizar vista y capas
    map.fitBounds(bounds);
    updateRasterLayer();
    loadRasterMetadata(data.metadata);
    // Mostrar botón de limpiar
    document.getElementById('clear-raster').style.display = 'block';
  } catch (error) {
    console.error('Error:', error);
    alert(error.message);
  }
}

// Configurar controles del panel
document.getElementById('toggle-panel').addEventListener('click', function() {
  const content = document.querySelector('.panel-content');
  const button = this;
  if (content.style.display === 'none') {
    content.style.display = 'block';
    button.textContent = '▼';
  } else {
    content.style.display = 'none';
    button.textContent = '▲';
  }
});

// Configurar controles de bandas
['red-band', 'green-band', 'blue-band'].forEach((selectId, index) => {
  document.getElementById(selectId).addEventListener('change', function() {
    currentBands[index] = parseInt(this.value);
    updateRasterLayer();
  });
});

// Configurar control de opacidad
document.getElementById('opacity').addEventListener('input', function() {
  const value = this.value;
  document.getElementById('opacity-value').textContent = `${value}%`;
  currentOpacity = value / 100;
  updateRasterLayer(currentBands, currentOpacity);
});

// Configurar sección colapsable de metadatos
document.querySelector('.section-header').addEventListener('click', function() {
  const content = this.nextElementSibling;
  const button = this.querySelector('.toggle-section');
  content.classList.toggle('collapsed');
  button.classList.toggle('collapsed');
});

// Configurar carga de archivos por ruta
const pathInput = document.getElementById('path-input');
const loadButton = document.getElementById('load-raster');
const clearButton = document.getElementById('clear-raster');
loadButton.addEventListener('click', () => {
  const path = pathInput.value.trim();
  handlePathUpload(path);
});

clearButton.addEventListener('click', async () => {
  // Limpiar estado actual
  cleanupCurrentState();
  // Limpiar reader anterior si existe
  if (currentReaderId) {
    await fetch(`/cleanup/${currentReaderId}`, { method: 'POST' });
    currentReaderId = null;
  }
  // Resetear la vista del mapa a Bogotá
  map.setView([4.55, -74.1], 13);
  // Limpiar el campo de ruta
  if (pathInput) pathInput.value = '';
});
