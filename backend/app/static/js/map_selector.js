let map;
let vertexMarkers = [];
let previewPolyline = null;
let currentPolygon = null;
let drawnGeoJSON = null;
let vertexPoints = []; // Array of google.maps.LatLng

// Design system constants for drawing elements
const STROKE_COLOR = "#7FAE5C"; // --ndvi-moderate
const FILL_COLOR = "#1F5C3B";   // --ndvi-peak

// Hard validation boundaries (rules.md limits)
const MAX_AREA_HECTARES = 5000;
const MIN_VERTICES = 3;
const MAX_VERTICES = 100;
const PRECISION_DECIMALS = 6;

function initMap() {
    // 1. Initialize Map centered on Dhaka, Bangladesh
    map = new google.maps.Map(document.getElementById("map"), {
        center: { lat: 23.8103, lng: 90.4125 },
        zoom: 11,
        mapTypeId: "hybrid", // Satellite/terrain hybrid is standard in GIS
        tilt: 0,
        streetViewControl: false,
        disableDoubleClickZoom: true, // Disable map zoom on dblclick to allow closing polygons
        mapTypeControlOptions: {
            position: google.maps.ControlPosition.TOP_RIGHT
        }
    });

    // 2. Initialize Autocomplete Search
    const searchInput = document.getElementById("map-search");
    if (searchInput) {
        const autocomplete = new google.maps.places.Autocomplete(searchInput);
        autocomplete.bindTo("bounds", map);

        autocomplete.addListener("place_changed", () => {
            const place = autocomplete.getPlace();
            if (!place.geometry || !place.geometry.location) {
                alert("No details available for input: '" + place.name + "'");
                return;
            }

            if (place.geometry.viewport) {
                map.fitBounds(place.geometry.viewport);
            } else {
                map.setCenter(place.geometry.location);
                map.setZoom(14);
            }
        });
    }

    // 3. Register Native Map Click Listener for Polygon Drawing
    google.maps.event.addListener(map, "click", (event) => {
        if (event.latLng) {
            addVertexPoint(event.latLng);
        }
    });

    // 4. Register Double-Click Listener to Complete Polygon
    google.maps.event.addListener(map, "dblclick", (event) => {
        if (vertexPoints.length >= MIN_VERTICES) {
            completePolygon();
        }
    });

    // 5. Wire Action Buttons
    const drawBtn = document.getElementById("draw-poly-btn");
    if (drawBtn) {
        drawBtn.addEventListener("click", clearPreviousPolygon);
    }

    const clearBtn = document.getElementById("clear-poly-btn");
    if (clearBtn) {
        clearBtn.addEventListener("click", clearPreviousPolygon);
    }

    // 6. Initialize submit listener and date range validation
    const startDateInput = document.getElementById("start-date");
    const endDateInput = document.getElementById("end-date");
    if (startDateInput) startDateInput.addEventListener("change", validateDateInputs);
    if (endDateInput) endDateInput.addEventListener("change", validateDateInputs);

    document.getElementById("analyze-btn").addEventListener("click", submitAOI);
}

function addVertexPoint(latLng) {
    if (currentPolygon) {
        // Clear previous completed shape when starting a new polygon
        clearPreviousPolygon();
    }

    vertexPoints.push(latLng);

    // Create a small green circle marker at each clicked vertex
    const marker = new google.maps.Marker({
        position: latLng,
        map: map,
        icon: {
            path: google.maps.SymbolPath.CIRCLE,
            scale: 6,
            fillColor: STROKE_COLOR,
            fillOpacity: 1.0,
            strokeColor: "#FFFFFF",
            strokeWeight: 2
        }
    });

    // Clicking the 1st vertex again completes the polygon if >= 3 points exist
    if (vertexMarkers.length === 0) {
        marker.addListener("click", (e) => {
            if (vertexPoints.length >= MIN_VERTICES) {
                completePolygon();
            }
        });
    }

    vertexMarkers.push(marker);
    updateDrawingPreview();
}

function updateDrawingPreview() {
    if (previewPolyline) {
        previewPolyline.setMap(null);
    }

    if (vertexPoints.length >= 2) {
        previewPolyline = new google.maps.Polyline({
            path: vertexPoints,
            strokeColor: STROKE_COLOR,
            strokeOpacity: 0.9,
            strokeWeight: 3,
            map: map
        });
    }

    document.getElementById("readout-vertices").innerText = vertexPoints.length;

    if (vertexPoints.length >= MIN_VERTICES) {
        const areaSqMeters = google.maps.geometry.spherical.computeArea(vertexPoints);
        const areaHectares = areaSqMeters / 10000;
        document.getElementById("readout-area").innerText = `${areaHectares.toFixed(2)} ha`;

        if (areaHectares > MAX_AREA_HECTARES) {
            showError(`Area Limit Exceeded: Parcel is ${areaHectares.toFixed(1)} ha. Max allowed is ${MAX_AREA_HECTARES} ha.`);
            document.getElementById("analyze-btn").disabled = true;
        } else {
            hideError();
        }
    }
}

function completePolygon() {
    if (vertexPoints.length < MIN_VERTICES) {
        showError(`Geometry error: Polygon requires at least ${MIN_VERTICES} vertices.`);
        return;
    }

    // Clean up preview markers and line
    if (previewPolyline) {
        previewPolyline.setMap(null);
        previewPolyline = null;
    }
    vertexMarkers.forEach(m => m.setMap(null));
    vertexMarkers = [];

    // Construct final closed polygon overlay
    currentPolygon = new google.maps.Polygon({
        paths: vertexPoints,
        strokeColor: STROKE_COLOR,
        strokeOpacity: 0.9,
        strokeWeight: 2,
        fillColor: FILL_COLOR,
        fillOpacity: 0.35,
        editable: true,
        map: map
    });

    const path = currentPolygon.getPath();
    google.maps.event.addListener(path, "set_at", () => processPolygonPath(path));
    google.maps.event.addListener(path, "insert_at", () => processPolygonPath(path));
    google.maps.event.addListener(path, "remove_at", () => processPolygonPath(path));

    processPolygonPath(path);
}

function processPolygonPath(path) {
    const len = path.getLength();
    document.getElementById("readout-vertices").innerText = len;

    if (len < MIN_VERTICES) {
        showError(`Geometry error: Minimum ${MIN_VERTICES} vertices required.`);
        document.getElementById("analyze-btn").disabled = true;
        return;
    }

    if (len > MAX_VERTICES) {
        showError(`Vertex count exceeds limit (${len}/${MAX_VERTICES}).`);
        document.getElementById("analyze-btn").disabled = true;
        return;
    }

    const areaSqMeters = google.maps.geometry.spherical.computeArea(path);
    const areaHectares = areaSqMeters / 10000;
    document.getElementById("readout-area").innerText = `${areaHectares.toFixed(2)} ha`;

    if (areaHectares > MAX_AREA_HECTARES) {
        showError(`Area Limit Exceeded: Selected parcel is ${areaHectares.toFixed(1)} ha. Max allowed size is ${MAX_AREA_HECTARES} ha.`);
        document.getElementById("analyze-btn").disabled = true;
        return;
    }

    hideError();

    const coordinates = [];
    for (let i = 0; i < len; i++) {
        const latLng = path.getAt(i);
        coordinates.push([
            parseFloat(latLng.lng().toFixed(PRECISION_DECIMALS)),
            parseFloat(latLng.lat().toFixed(PRECISION_DECIMALS))
        ]);
    }

    // GeoJSON polygon loops MUST close (first and last coordinate are identical)
    coordinates.push([
        parseFloat(path.getAt(0).lng().toFixed(PRECISION_DECIMALS)),
        parseFloat(path.getAt(0).lat().toFixed(PRECISION_DECIMALS))
    ]);

    drawnGeoJSON = {
        type: "Polygon",
        coordinates: [coordinates]
    };

    document.getElementById("analyze-btn").disabled = false;
}

function clearPreviousPolygon() {
    if (currentPolygon) {
        currentPolygon.setMap(null);
        currentPolygon = null;
    }
    if (previewPolyline) {
        previewPolyline.setMap(null);
        previewPolyline = null;
    }
    vertexMarkers.forEach(m => m.setMap(null));
    vertexMarkers = [];
    vertexPoints = [];
    drawnGeoJSON = null;

    document.getElementById("analyze-btn").disabled = true;
    document.getElementById("readout-vertices").innerText = "0";
    document.getElementById("readout-area").innerText = "0.00 ha";
    hideError();
}

function validateDateInputs() {
    const startDateVal = document.getElementById("start-date").value;
    const endDateVal = document.getElementById("end-date").value;

    if (!startDateVal || !endDateVal) {
        showError("Invalid date input: Please select both a start and end monitoring date.");
        document.getElementById("analyze-btn").disabled = true;
        return false;
    }

    const startDate = new Date(startDateVal);
    const endDate = new Date(endDateVal);
    const s2MinDate = new Date("2015-06-23");

    if (startDate >= endDate) {
        showError("⚠️ Invalid Date Range: Start date must be earlier than the End date.");
        document.getElementById("analyze-btn").disabled = true;
        return false;
    }

    if (startDate < s2MinDate) {
        showWarning("ℹ️ Selected start date is before Sentinel-2 launch (June 23, 2015). The server will automatically query satellite imagery starting from 2015-06-23.");
        if (drawnGeoJSON) {
            document.getElementById("analyze-btn").disabled = false;
        }
        return true;
    }

    if (drawnGeoJSON) {
        hideError();
        document.getElementById("analyze-btn").disabled = false;
    } else {
        hideError();
    }
    return true;
}

function showError(message) {
    const alertBox = document.getElementById("validation-error");
    if (alertBox) {
        alertBox.innerText = message;
        alertBox.classList.remove("warning");
        alertBox.style.display = "block";
    }
}

function showWarning(message) {
    const alertBox = document.getElementById("validation-error");
    if (alertBox) {
        alertBox.innerText = message;
        alertBox.classList.add("warning");
        alertBox.style.display = "block";
    }
}

function hideError() {
    const alertBox = document.getElementById("validation-error");
    if (alertBox) {
        alertBox.classList.remove("warning");
        alertBox.style.display = "none";
    }
}

async function submitAOI() {
    if (!drawnGeoJSON) return;

    if (!validateDateInputs()) return;

    const name = document.getElementById("parcel-name").value.trim() || "Dhaka Forest Sector 1";
    const startDate = document.getElementById("start-date").value;
    const endDate = document.getElementById("end-date").value;

    const payload = {
        name: name,
        start_date: startDate,
        end_date: endDate,
        geometry: drawnGeoJSON
    };

    const submitBtn = document.getElementById("analyze-btn");
    submitBtn.disabled = true;
    submitBtn.innerHTML = "<span>⏳</span> Enqueueing Job...";

    try {
        const response = await fetch("/api/aoi", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok) {
            alert(`Job enqueued successfully!\nJob ID: ${data.job_id}\nStatus: ${data.status}`);
            window.location.href = "/jobs";
        } else {
            submitBtn.disabled = false;
            submitBtn.innerHTML = "<span>🚀</span> Start Automated Analysis";
            const detail = data.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : "API Submission failed.";
            showError(`Submission Failed: ${detail}`);
        }
    } catch (error) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = "<span>🚀</span> Start Automated Analysis";
        showError(`Network Connection Error: ${error.message}`);
    }
}

// Guarantee global availability for Google Maps callback
window.initMap = initMap;
