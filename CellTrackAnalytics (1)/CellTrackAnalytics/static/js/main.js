document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const loadingModal = new bootstrap.Modal(document.getElementById('loadingModal'));
    const exportBtn = document.getElementById('exportBtn');

    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('towerData');
        const file = fileInput.files[0];
        
        if (!file) {
            alert('Please select a file to upload');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            loadingModal.show();
            
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Upload failed');
            }

            // Update visualizations
            updateMap(data.patterns);
            updateChart(data.patterns);
            updateTable(data.patterns);
            
            exportBtn.disabled = false;
        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            loadingModal.hide();
        }
    });

    exportBtn.addEventListener('click', async function() {
        try {
            const response = await fetch('/export', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(window.analysisResults)
            });

            if (!response.ok) {
                throw new Error('Export failed');
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'analysis_results.xlsx';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            alert('Error exporting data: ' + error.message);
        }
    });
});

function updateTable(patterns) {
    const tbody = document.querySelector('#resultsTable tbody');
    tbody.innerHTML = '';
    
    patterns.forEach(pattern => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${pattern.mobile_number}</td>
            <td>${pattern.tower_count}</td>
            <td>${new Date(pattern.first_seen).toLocaleString()}</td>
            <td>${new Date(pattern.last_seen).toLocaleString()}</td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="showOnMap('${pattern.mobile_number}')">
                    Show on Map
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });

    window.analysisResults = patterns;
}
