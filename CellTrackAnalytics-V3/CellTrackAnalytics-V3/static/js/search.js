document.addEventListener('DOMContentLoaded', function() {
    const basicSearchForm = document.getElementById('basicSearchForm');
    const advancedSearchForm = document.getElementById('advancedSearchForm');
    const osintSearchForm = document.getElementById('osintSearchForm');
    const searchTypeSelect = document.getElementById('advancedSearchType');
    
    // Initialize search type specific fields
    searchTypeSelect.addEventListener('change', function() {
        updateSearchFields(this.value);
    });
    
    // Basic Search Form Handler
    basicSearchForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const searchData = {
            type: document.getElementById('searchType').value,
            value: document.getElementById('searchValue').value,
            start_date: document.getElementById('startDate').value,
            end_date: document.getElementById('endDate').value
        };
        
        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(searchData)
            });
            
            const results = await response.json();
            if (!response.ok) {
                throw new Error(results.error || 'Search failed');
            }
            
            updateSearchResults(results);
        } catch (error) {
            alert('Error: ' + error.message);
        }
    });
    
    // Update search results table
    function updateSearchResults(results) {
        const tbody = document.querySelector('#searchResultsTable tbody');
        tbody.innerHTML = '';
        
        results.forEach(result => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${result.mobile_number}</td>
                <td>${result.imei || '-'}</td>
                <td>${result.tower_id}</td>
                <td>${new Date(result.timestamp).toLocaleString()}</td>
                <td>${result.duration || '-'}</td>
                <td>${result.type || '-'}</td>
                <td>${result.connected_number || '-'}</td>
                <td>${result.location.lat.toFixed(6)}, ${result.location.lng.toFixed(6)}</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="showOnMap('${result.location.lat}', '${result.location.lng}')">
                        Show on Map
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });
    }
    
    // Update search fields based on search type
    function updateSearchFields(searchType) {
        const parametersDiv = document.getElementById('searchParameters');
        let fieldsHTML = '';
        
        switch(searchType) {
            case 'common_locations':
                fieldsHTML = `
                    <div class="mb-3">
                        <label class="form-label">Minimum Locations</label>
                        <input type="number" class="form-control" min="2" value="2">
                    </div>
                `;
                break;
            case 'geo_fence':
                fieldsHTML = `
                    <div class="mb-3">
                        <button type="button" class="btn btn-secondary" onclick="openGeoFenceMap()">
                            Define Area on Map
                        </button>
                    </div>
                `;
                break;
            case 'call_duration':
                fieldsHTML = `
                    <div class="mb-3">
                        <label class="form-label">Duration Range (seconds)</label>
                        <div class="row">
                            <div class="col">
                                <input type="number" class="form-control" placeholder="Min">
                            </div>
                            <div class="col">
                                <input type="number" class="form-control" placeholder="Max">
                            </div>
                        </div>
                    </div>
                `;
                break;
        }
        
        parametersDiv.innerHTML = fieldsHTML;
    }
});

// Function to show location on map
function showOnMap(lat, lng) {
    // Implementation will use the existing map.js functionality
    if (typeof focusLocation === 'function') {
        focusLocation(lat, lng);
    }
}

// Initialize geo-fence map
let geoFenceMap;
function openGeoFenceMap() {
    const modal = new bootstrap.Modal(document.getElementById('geoFenceModal'));
    modal.show();
    
    if (!geoFenceMap) {
        geoFenceMap = L.map('geoFenceMap').setView([0, 0], 2);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(geoFenceMap);
    }
}
