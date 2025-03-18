let map;
let markers = [];
let markerCluster;
let heatmapLayer;
let pathLayer;
let currentView = 'markers'; // markers, heatmap, or path

document.addEventListener('DOMContentLoaded', function() {
    // Initialize the map
    map = L.map('map').setView([0, 0], 2);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    // Initialize marker cluster group
    markerCluster = L.markerClusterGroup({
        chunkedLoading: true,
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: true,
        zoomToBoundsOnClick: true
    });

    // Add view control
    const viewControl = L.control({position: 'topright'});
    viewControl.onAdd = function() {
        const div = L.DomUtil.create('div', 'leaflet-control leaflet-bar view-control');
        div.innerHTML = `
            <button onclick="changeView('markers')" class="btn btn-sm btn-light active" data-view="markers">
                <i data-feather="map-pin"></i>
            </button>
            <button onclick="changeView('heatmap')" class="btn btn-sm btn-light" data-view="heatmap">
                <i data-feather="activity"></i>
            </button>
            <button onclick="changeView('path')" class="btn btn-sm btn-light" data-view="path">
                <i data-feather="navigation"></i>
            </button>
        `;
        return div;
    };
    viewControl.addTo(map);

    // Initialize feather icons in control
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
});

function updateMap(patterns) {
    // Clear existing layers
    clearLayers();

    // Process data for different visualizations
    const heatmapData = [];
    const pathData = [];

    patterns.forEach(pattern => {
        if (pattern.movement_path && pattern.movement_path.length > 0) {
            // Create markers
            pattern.movement_path.forEach(([lat, lng], index) => {
                const marker = L.marker([lat, lng], {
                    title: pattern.mobile_number
                }).bindPopup(createPopupContent(pattern, index));

                markerCluster.addLayer(marker);
                markers.push(marker);

                // Add point to heatmap data
                heatmapData.push([lat, lng, 1]); // intensity of 1 for each point
            });

            // Store path data
            pathData.push({
                coords: pattern.movement_path,
                mobile: pattern.mobile_number
            });
        }
    });

    // Initialize heatmap layer
    heatmapLayer = L.heatLayer(heatmapData, {
        radius: 25,
        blur: 15,
        maxZoom: 10,
        max: 1.0,
        gradient: {0.4: 'blue', 0.65: 'lime', 1: 'red'}
    });

    // Create path layers with animation
    pathLayer = L.layerGroup();
    pathData.forEach(path => {
        const polyline = L.polyline(path.coords, {
            color: '#E74C3C',
            weight: 3,
            opacity: 0.7,
            smoothFactor: 1
        }).bindTooltip(path.mobile);

        // Add arrow decorations
        const decorator = L.polylineDecorator(polyline, {
            patterns: [
                {offset: '5%', repeat: '10%', symbol: L.Symbol.arrowHead({
                    pixelSize: 10,
                    polygon: false,
                    pathOptions: {stroke: true, color: '#E74C3C'}
                })}
            ]
        });

        pathLayer.addLayer(polyline);
        pathLayer.addLayer(decorator);
    });

    // Show default view
    changeView(currentView);

    // Fit map bounds
    if (markers.length > 0) {
        const group = L.featureGroup(markers);
        map.fitBounds(group.getBounds());
    }
}

function changeView(view) {
    currentView = view;
    clearLayers();

    // Update control buttons
    document.querySelectorAll('.view-control button').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-view') === view) {
            btn.classList.add('active');
        }
    });

    switch(view) {
        case 'markers':
            map.addLayer(markerCluster);
            break;
        case 'heatmap':
            map.addLayer(heatmapLayer);
            break;
        case 'path':
            map.addLayer(pathLayer);
            break;
    }
}

function clearLayers() {
    markers.forEach(marker => markerCluster.removeLayer(marker));
    map.removeLayer(markerCluster);
    if (heatmapLayer) map.removeLayer(heatmapLayer);
    if (pathLayer) map.removeLayer(pathLayer);
}

function createPopupContent(pattern, index) {
    return `
        <div class="popup-content">
            <strong>Mobile: ${pattern.mobile_number}</strong><br>
            Location ${index + 1} of ${pattern.movement_path.length}<br>
            First seen: ${new Date(pattern.first_seen).toLocaleString()}<br>
            Last seen: ${new Date(pattern.last_seen).toLocaleString()}<br>
            Total towers: ${pattern.tower_count}
        </div>
    `;
}

function showOnMap(mobileNumber) {
    const pattern = window.analysisResults.find(p => p.mobile_number === mobileNumber);
    if (pattern && pattern.movement_path.length > 0) {
        const bounds = L.latLngBounds(pattern.movement_path);
        map.fitBounds(bounds);

        // Highlight the selected pattern's markers
        markers.forEach(marker => {
            if (marker.getPopup() && 
                marker.getPopup().getContent().includes(mobileNumber)) {
                marker.openPopup();
            }
        });
    }
}

function focusLocation(lat, lng) {
    map.setView([lat, lng], 15);
    markers.forEach(marker => {
        const mLat = marker.getLatLng().lat;
        const mLng = marker.getLatLng().lng;
        if (mLat === lat && mLng === lng) {
            marker.openPopup();
        }
    });
}