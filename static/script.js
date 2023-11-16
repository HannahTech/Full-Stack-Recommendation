document.getElementById('searchForm').addEventListener('submit', function(event) {
    event.preventDefault();

    var searchInput = document.getElementById('searchInput').value;

    var progressContainer = document.getElementById('progress-container');
    progressContainer.style.display = 'block';

    var resultsContainer = document.getElementById('results');
    resultsContainer.innerHTML = '';

    var source = new EventSource('/search', { withCredentials: true });

    source.onmessage = function(event) {
        var lines = event.data.trim().split('\n');
        lines.forEach(line => {
            if (line.startsWith('data:')) {
                var progress = parseInt(line.substr(5));
                var progressDiv = document.getElementById('progress');
                progressDiv.style.width = progress + '%';
            } else {
                try {
                    var jsonData = JSON.parse(line.substr(5));
                    console.log(jsonData);
                } catch (error) {
                    console.error('Error parsing JSON:', error);
                }
            }
        });
    };
});
