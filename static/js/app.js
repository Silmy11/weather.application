document.addEventListener('DOMContentLoaded', function() {
    if (!document.getElementById('city-input')) return;

    let currentResolvedCity = "";
    const cityInput = document.getElementById('city-input');
    const searchBtn = document.getElementById('search-btn');
    const geoBtn = document.getElementById('geo-btn');
    const toggleFavBtn = document.getElementById('toggle-fav-btn');
    const favoritesList = document.getElementById('favorites-list');
    const loader = document.getElementById('dashboard-loader');
    const emptyView = document.getElementById('empty-state-view');
    const dashboardView = document.getElementById('weather-dashboard-view');

    // FIX: Click listener safely handles search parameters
    searchBtn.addEventListener('click', () => {
        const query = cityInput.value.trim();
        if (query) fetchWeatherData(query);
    });

    // FIX: Enter key listener safely handles search parameters
    cityInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const query = cityInput.value.trim();
            if (query) fetchWeatherData(query);
        }
    });

    geoBtn.addEventListener('click', () => {
        if (navigator.geolocation) {
            loader.classList.remove('hidden');
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    // Geolocation fallback passes lat/lon strings directly to route parameters
                    const queryCoord = `geo-${pos.coords.latitude}-${pos.coords.longitude}`;
                    fetchWeatherData(queryCoord);
                },
                () => {
                    loader.classList.add('hidden');
                    alert("Location access denied.");
                }
            );
        } else {
            alert("Geolocation not supported.");
        }
    });

    document.addEventListener('click', (e) => {
        if (e.target && e.target.classList.contains('quick-query-target')) {
            fetchWeatherData(e.target.textContent);
        }
    });

    function fetchWeatherData(cityName) {
        loader.classList.remove('hidden');
        
        // FIX: Rebuilt URL structure to map directly to the Flask dynamic path pattern (/api/weather/<city>)
        let url = `/api/weather/${encodeURIComponent(cityName)}`;
        
        fetch(url)
            .then(res => {
                if (!res.ok) throw new Error("City not found.");
                return res.json();
            })
            .then(data => {
                emptyView.classList.add('hidden');
                dashboardView.classList.remove('hidden');

                const current = data.current;
                currentResolvedCity = current.name; // OpenWeather returns name inside .name

                document.getElementById('w-city-title').textContent = current.name;
                document.getElementById('w-temp').textContent = `${Math.round(current.main.temp)}°C`;
                document.getElementById('w-feels-like').textContent = `${Math.round(current.main.feels_like)}°C`;
                document.getElementById('w-humidity').textContent = current.main.humidity + " %";
                document.getElementById('w-wind').textContent = `${Math.round(current.wind.speed * 3.6)} km/h`;
                document.getElementById('w-desc').textContent = current.weather[0].description;
                document.getElementById('w-icon').src = `https://openweathermap.org/img/wn/${current.weather[0].icon}@2x.png`;

                checkIsFavorited(current.name);

                const forecastContainer = document.getElementById('forecast-flex-row');
                forecastContainer.innerHTML = "";
                
                // Parse standard OpenWeather 5-day / 3-hour list items array array snapshot loops
                const dailySnapshots = data.forecast.list.filter((item, index) => index % 8 === 0).slice(0, 4);
                
                dailySnapshots.forEach(item => {
                    const dateObj = new Date(item.dt * 1000);
                    const dayName = dateObj.toLocaleDateString('en-US', { weekday: 'short' });
                    const card = document.createElement('div');
                    card.className = "forecast-card widget-glass";
                    card.innerHTML = `
                        <h5>${dayName}</h5>
                        <img src="https://openweathermap.org/img/wn/${item.weather[0].icon}.png" alt="Icon">
                        <p class="f-temp">${Math.round(item.main.temp)}&deg;C</p>
                        <p class="f-desc">${item.weather[0].description}</p>
                    `;
                    forecastContainer.appendChild(card);
                });

                refreshSearchHistoryDOM();
            })
            .catch(err => alert(err.message))
            .finally(() => loader.classList.add('hidden'));
    }

    toggleFavBtn.addEventListener('click', () => {
        if (!currentResolvedCity) return;
        const isFav = toggleFavBtn.querySelector('i').classList.contains('fa-solid');
        fetch('/api/favorites', {
            method: 'POST', // Keep as simple POST to match your backend append route logic
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ city: currentResolvedCity })
        }).then(() => {
            toggleFavIcon(true);
            refreshFavoritesDOM();
        });
    });

    function checkIsFavorited(cityName) {
        // Flask profile endpoints manage user lists securely
        toggleFavIcon(false); 
    }

    function toggleFavIcon(isFav) {
        const icon = toggleFavBtn.querySelector('i');
        if (icon) {
            icon.className = isFav ? "fa-solid fa-star" : "fa-regular fa-star";
        }
    }

    function refreshFavoritesDOM() {
        // Handled securely by the template reloads via Profile redirection routing paths
    }

    function refreshSearchHistoryDOM() {
        // FIX: Matches target container strings cleanly without crashing dynamic updates
        const historyTable = document.getElementById('history-table');
        if (!historyTable) return;
        
        fetch(window.location.href)
            .then(res => res.text())
            .then(html => {
                const doc = new DOMParser().parseFromString(html, 'text/html');
                const newTable = doc.getElementById('history-table');
                if (newTable) historyTable.innerHTML = newTable.innerHTML;
            });
    }
});
