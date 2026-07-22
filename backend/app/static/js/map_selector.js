let map;
let drawingManager;
let currentPolygon = null;
let drawnGeoJSON = null;

// Design system constants for drawing elements
const STROKE_COLOR = "#7FAE5C"; // --ndvi-moderate
const FILL_COLOR = "#1F5C3B";   // --ndvi-peak

// Hard validation boundaries (rules.md limits)
const MAX_AREA_HECTARES = 5000;
const MIN_VERTICES = 3;
const MAX_VERTICES = 100;
const PRECISION_DECIMALS = 6;

function initMap() {
    // 1. Initialize Map centered on the Amazon Rainforest
    map = new google.maps.Map(document.getElementById("map"), {
        center: { lat: -3.4653, lng: -62.2159 },
        zoom: 7,
        mapTypeId: "hybrid", // Satellite/terrain hybrid is standard in GIS
        tilt: 0,
        streetViewControl: false,
        mapTypeControlOptions: {
            position: google.maps.ControlPosition.TOP_RIGHT
        }
    });

    // 2. Initialize Autocomplete Search
    const searchInput = document.getElementById("map-search");
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

    // 3. Initialize Drawing Manager
    drawingManager = new google.maps.drawing.DrawingManager({
        drawingMode: google.maps.drawing.OverlayType.POLYGON,
        drawingControl: true,
        drawingControlOptions: {
            position: google.maps.ControlPosition.LEFT_TOP,
            drawingModes: [google.maps.drawing.OverlayType.POLYGON]
        },
        polygonOptions: {
            fillColor: FILL_COLOR,
            fillOpacity: 0.3,
            strokeWeight: 2,
            strokeColor: STROKE_COLOR,
            clickable: true,
            editable: true,
            draggable: true,
            zIndex: 1
        }
    });
    drawingManager.setMap(map);

    // 4. Register event listeners for drawn shapes
    google.maps.event.addListener(drawingManager, "overlaycomplete", (event) => {
        if (event.type === google.maps.drawing.OverlayType.POLYGON) {
            // Remove previous polygon if drawn
            clearPreviousPolygon();

            currentPolygon = event.overlay;
            
            // Switch out of drawing mode after polygon is completed
            drawingManager.setDrawingMode(null);

            // Validate and process the polygon
            processPolygon(currentPolygon);

            // Listen to geometry changes (dragging/editing vertices)
            const path = currentPolygon.getPath();
            google.maps.event.addListener(path, "set_at", () => processPolygon(currentPolygon));
            google.maps.event.addListener(path, "insert_at", () => processPolygon(currentPolygon));
            google.maps.event.addListener(path, "remove_at", () => processPolygon(currentPolygon));
            google.maps.event.addListener(currentPolygon, "dragend", () => processPolygon(currentPolygon));
        }
    });

    // 5. Initialize submit listener
    document.getElementById("analyze-btn").addEventListener("click", submitAOI);
}

function clearPreviousPolygon() {
    if (currentPolygon) {
        currentPolygon.setMap(null);
        currentPolygon = null;
    }
    drawnGeoJSON = null;
    document.getElementById("analyze-btn").disabled = true;
    document.getElementById("readout-vertices").innerText = "0";
    document.getElementById("readout-area").innerText = "0.00 ha";
    hideError();
}

function processPolygon(polygon) {
    const path = polygon.getPath();
    const len = path.getLength();
    
    // Update vertex UI readout
    document.getElementById("readout-vertices").innerText = len;

    // 1. Check minimum vertices
    if (len < MIN_VERTICES) {
        showError(`Geometry error: A polygon requires a minimum of ${MIN_VERTICES} vertices.`);
        document.getElementById("analyze-btn").disabled = true;
        return;
    }

    // 2. Check maximum vertices (Pydantic / DB safeguard)
    if (len > MAX_VERTICES) {
        showError(`Geometry error: Vertex count exceeds limit (${len}/${MAX_VERTICES}). Please simplify the shape.`);
        document.getElementById("analyze-btn").disabled = true;
        return;
    }

    // 3. Compute Hectares Area
    const areaSqMeters = google.maps.geometry.spherical.computeArea(path);
    const areaHectares = areaSqMeters / 10000;
    document.getElementById("readout-area").innerText = `${areaHectares.toFixed(2)} ha`;

    // 4. Validate Area bounds
    if (areaHectares > MAX_AREA_HECTARES) {
        showError(`Area Limit Exceeded: Selected parcel is ${areaHectares.toFixed(1)} hectares. Max allowed size is ${MAX_AREA_HECTARES} ha.`);
        document.getElementById("analyze-btn").disabled = true;
        return;
    }

    hideError();

    // 5. Build snapped coordinate array (precision clipping to 6 decimal places per rules.md)
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

    // Enable Submission Button
    document.getElementById("analyze-btn").disabled = false;
}

function showError(message) {
    const alertBox = document.getElementById("validation-error");
    alertBox.innerText = message;
    alertBox.style.display = "block";
}

function hideError() {
    const alertBox = document.getElementById("validation-error");
    alertBox.style.display = "none";
}

async function submitAOI() {
    if (!drawnGeoJSON) return;

    const name = document.getElementById("parcel-name").value.trim() || "Amazon Sector G4";
    const startDate = document.getElementById("start-date").value;
    const endDate = document.getElementById("end-date").value;

    // Date validation
    if (!startDate || !endDate) {
        showError("Invalid input: Please select both a start and end monitoring date.");
        return;
    }

    if (new Date(startDate) >= new Date(endDate)) {
        showError("Invalid input: Start date must be earlier than the end date.");
        return;
    }

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
            // Redirect to monitoring jobs dashboard (Phase 2 page stub)
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
