document.addEventListener('DOMContentLoaded', function() {
    if (!document.getElementById('city-input')) return;

    let currentResolvedCity = "";
    const cityInput = document.getElementById('city-input');
    const searchBtn = document.getElementById('search-btn');
    const geoBtn = document.getElementById('geo-btn');
    const toggleFavBtn = document.getElementById('toggle-fav-btn');
    const favoritesList = document.getElementById('favorites-list');
    const historyList = document.getElementById('history-list');
    const loader = document.getElementById('dashboard-loader');
    const emptyView = document.getElementById('empty-state-view');
    const dashboardView = document.getElementById('weather-dashboard-view');

    searchBtn.addEventListener('click', () => {
        const query = cityInput.value.trim();
        if (query) fetchWeatherData({ city: query });
    });

    cityInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const query = cityInput.value.trim();
            if (query) fetchWeatherData({ city: query });
        }
    });

    geoBtn.addEventListener('click', () => {
        if (navigator.geolocation) {
            loader.classList.remove('hidden');
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    fetchWeatherData({ lat: pos.coords.latitude, lon: pos.coords.longitude });
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
            fetchWeatherData({ city: e.target.textContent });
        }
    });

    function fetchWeatherData(params) {
        loader.classList.remove('hidden');
        let url = '/api/weather?' + new URLSearchParams(params).toString();
        
        fetch(url)
            .then(res => {
                if (!res.ok) throw new Error("City not found.");
                return res.json();
            })
            .then(data => {
                emptyView.classList.add('hidden');
                dashboardView.classList.remove('hidden');

                const current = data.current;
                currentResolvedCity = current.city;

                document.getElementById('w-city-title').textContent = current.city;
                document.getElementById('w-temp').textContent = current.temp;
                document.getElementById('w-feels-like').textContent = current.feels_like;
                document.getElementById('w-humidity').textContent = current.humidity + " %";
                document.getElementById('w-wind').textContent = current.wind_speed + " m/s";
                document.getElementById('w-pressure').textContent = current.pressure + " hPa";
                document.getElementById('w-visibility').textContent = current.visibility + " km";
                document.getElementById('w-desc').textContent = current.description;
                document.getElementById('w-icon').src = `https://openweathermap.org/img/wn/${current.icon}@2x.png`;
                document.getElementById('w-sun-bounds').innerHTML = `Rise: ${current.sunrise} | Set: ${current.sunset}`;
                
                const aqiLabels = ["Good", "Fair", "Moderate", "Poor", "Very Poor"];
                document.getElementById('w-aqi').textContent = `${current.aqi} - ${aqiLabels[current.aqi - 1] || 'Unknown'}`;

                checkIsFavorited(current.city);

                const forecastContainer = document.getElementById('forecast-flex-row');
                forecastContainer.innerHTML = "";
                data.forecast.forEach(item => {
                    const card = document.createElement('div');
                    card.className = "forecast-card widget-glass";
                    card.innerHTML = `
                        <h5>${item.day}</h5>
                        <p class="f-date">${item.date}</p>
                        <img src="https://openweathermap.org/img/wn/${item.icon}.png" alt="Icon">
                        <p class="f-temp">${item.temp}&deg;C</p>
                        <p class="f-desc">${item.description}</p>
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
            method: isFav ? 'DELETE' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ city: currentResolvedCity })
        }).then(() => {
            toggleFavIcon(!isFav);
            refreshFavoritesDOM();
        });
    });

    function checkIsFavorited(cityName) {
        fetch('/api/favorites')
            .then(res => res.json())
            .then(favs => {
                toggleFavIcon(favs.some(c => c.toLowerCase() === cityName.toLowerCase()));
            });
    }

    function toggleFavIcon(isFav) {
        toggleFavBtn.querySelector('i').className = isFav ? "fa-solid fa-star" : "fa-regular fa-star";
    }

    function refreshFavoritesDOM() {
        fetch('/api/favorites')
            .then(res => res.json())
            .then(favs => {
                favoritesList.innerHTML = favs.length ? "" : '<p class="empty-text">No favorited locations yet.</p>';
                favs.forEach(city => {
                    const li = document.createElement('li');
                    li.innerHTML = `<span class="quick-query-target">${city}</span><button class="btn-remove-fav" data-city="${city}">&times;</button>`;
                    favoritesList.appendChild(li);
                });
            });
    }

    favoritesList.addEventListener('click', (e) => {
        if (e.target && e.target.classList.contains('btn-remove-fav')) {
            e.stopPropagation();
            const targetCity = e.target.getAttribute('data-city');
            fetch('/api/favorites', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ city: targetCity })
            }).then(() => {
                if(currentResolvedCity.toLowerCase() === targetCity.toLowerCase()) toggleFavIcon(false);
                refreshFavoritesDOM();
            });
        }
    });

    function refreshSearchHistoryDOM() {
        fetch(window.location.href)
            .then(res => res.text())
            .then(html => {
                const doc = new DOMParser().parseFromString(html, 'text/html');
                document.getElementById('history-list').innerHTML = doc.getElementById('history-list').innerHTML;
            });
    }
});
