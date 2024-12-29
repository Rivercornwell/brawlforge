function searchCommander() {
    const searchQuery = document.getElementById('commander-search').value;
    const resultsList = document.getElementById('commander-results');

    // Clear previous results
    resultsList.innerHTML = '';

    if (searchQuery.length < 2) {
        return; // Don't make request if the query is too short
    }

    fetch(`/search-commander?q=${searchQuery}`)
        .then(response => response.json())
        .then(data => {
            // Check if data is empty
            if (data.length === 0) {
                resultsList.innerHTML = '<li>No commanders found</li>';
                return;
            }

            // Populate the results
            data.forEach(commander => {
                const listItem = document.createElement('li');
                listItem.textContent = commander.name;
                listItem.onclick = function() {
                    document.getElementById('commander-search').value = commander.name; // Set selected commander
                    resultsList.innerHTML = ''; // Clear results after selection
                };
                resultsList.appendChild(listItem);
            });
        })
        .catch(error => {
            console.error('Error fetching commanders:', error);
        });
}
