let patternChart;

function updateChart(patterns) {
    const ctx = document.getElementById('patternChart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (patternChart) {
        patternChart.destroy();
    }

    // Process data for visualization
    const towerCounts = patterns.map(p => p.tower_count);
    const labels = patterns.map(p => p.mobile_number);

    // Create new chart
    patternChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Number of Towers Visited',
                data: towerCounts,
                backgroundColor: '#2C3E50',
                borderColor: '#34495E',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Tower Count'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Mobile Number'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Tower Visit Patterns by Mobile Number'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Towers visited: ${context.raw}`;
                        }
                    }
                }
            }
        }
    });
}
