<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Geoestimation Predictions</title>
    
    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
        }
        
        header {
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        h1 {
            font-size: 28px;
            margin-bottom: 5px;
        }
        
        .subtitle {
            font-size: 14px;
            color: #bdc3c7;
        }
        
        #map {
            height: calc(100vh - 80px);
            width: 100%;
        }
        
        .info-box {
            position: absolute;
            top: 100px;
            right: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
            max-width: 250px;
        }
        
        .info-box h3 {
            margin-bottom: 10px;
            color: #2c3e50;
            font-size: 16px;
        }
        
        .info-box p {
            font-size: 13px;
            color: #666;
            line-height: 1.5;
        }
        
        .marker-true {
            background-color: #27ae60;
        }
        
        .marker-predicted {
            background-color: #e74c3c;
        }
    </style>
</head>
<body>
    <header>
        <h1>🌍 Geoestimation Predictions</h1>
        <p class="subtitle">Visualisierung von Bildlokalisierungs-Vorhersagen</p>
    </header>
    
    <div id="map"></div>
    
    <div class="info-box">
        <h3>📍 Über dieses Projekt</h3>
        <p>Diese Karte zeigt Predictions eines Geoestimation-Modells, das Bildlokalisierungen vorhersagt.</p>
        <p style="margin-top: 10px;">
            <span style="color: #27ae60;">●</span> Tatsächlicher Standort<br>
            <span style="color: #e74c3c;">●</span> Vorhergesagter Standort
        </p>
    </div>
    
    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    
    <script>
        // Initialisiere die Karte
        const map = L.map('map').setView([20, 0], 2);
        
        // Füge OpenStreetMap Tiles hinzu
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18,
        }).addTo(map);
        
        // Beispiel-Funktion zum Hinzufügen von Predictions
        function addPrediction(trueLat, trueLng, predLat, predLng, imageName = "") {
            // Marker für tatsächlichen Standort (grün)
            const trueMarker = L.circleMarker([trueLat, trueLng], {
                radius: 8,
                fillColor: "#27ae60",
                color: "#ffffff",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(map);
            
            // Marker für vorhergesagten Standort (rot)
            const predMarker = L.circleMarker([predLat, predLng], {
                radius: 8,
                fillColor: "#e74c3c",
                color: "#ffffff",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(map);
            
            // Verbindungslinie zwischen beiden Punkten
            const line = L.polyline([[trueLat, trueLng], [predLat, predLng]], {
                color: '#3498db',
                weight: 2,
                opacity: 0.6,
                dashArray: '5, 10'
            }).addTo(map);
            
            // Berechne Distanz in km
            const distance = map.distance([trueLat, trueLng], [predLat, predLng]) / 1000;
            
            // Popup-Inhalt
            const popupContent = `
                <b>${imageName || 'Prediction'}</b><br>
                Distanz: ${distance.toFixed(2)} km<br>
                <small>Tatsächlich: ${trueLat.toFixed(4)}, ${trueLng.toFixed(4)}<br>
                Vorhersage: ${predLat.toFixed(4)}, ${predLng.toFixed(4)}</small>
            `;
            
            trueMarker.bindPopup(popupContent);
            predMarker.bindPopup(popupContent);
            line.bindPopup(popupContent);
        }
        
        // Beispiel-Predictions (später durch echte Daten ersetzen)
        addPrediction(48.8566, 2.3522, 48.9, 2.4, "Bild 1 - Paris");
        addPrediction(40.7128, -74.0060, 40.8, -74.1, "Bild 2 - New York");
        addPrediction(51.5074, -0.1278, 51.6, -0.2, "Bild 3 - London");
        
        console.log("Karte geladen! Verwende addPrediction(trueLat, trueLng, predLat, predLng, imageName) um neue Predictions hinzuzufügen.");
    </script>
</body>
</html>