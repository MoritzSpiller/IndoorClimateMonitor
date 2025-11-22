# 🌡️ Raspberry Pi Environmental Sensor Dashboard

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)
![Chart.js](https://img.shields.io/badge/Frontend-Chart.js-FF6384.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

A lightweight, Dockerized IoT dashboard designed to run on a Raspberry Pi. It visualizes temperature, humidity, and battery data collected from local sensors using a responsive web interface.

The project uses a **Sidecar Architecture**: one container collects the data (interacting with hardware), and a separate container serves the dashboard, sharing a volume for data persistence.

## ✨ Features

* **Interactive Visualization:** Beautiful, responsive line charts using [Chart.js](https://www.chartjs.org/).
* **Dual-Axis Plot:** View Temperature and Humidity on the same graph with toggleable datasets.
* **Battery Monitoring:** Dedicated subplot for sensor battery levels.
* **Time Travel:** Select custom reference dates.
* **Flexible Ranges:** Quick-select time frames (6h, 12h, 24h, 3 Days, 7 Days, 1 Month).
* **Hover Tooltips:** Precise data inspection on hover.
* **Dockerized:** Easy deployment using Docker Compose with automatic restart policies.

---

## 📸 Screenshots

*(Add a screenshot of your dashboard here, e.g., `docs/screenshot.png`)*

---

## 🏗️ Architecture

This project runs as two separate services managed by Docker Compose:

1.  **`sensor-collector`**: A Python script running in `privileged` mode to access GPIO/I2C. It writes JSON files to a shared volume.
2.  **`web-dashboard`**: A Flask web server that reads the JSON files and serves the frontend.

The data is stored in daily JSON files to ensure lightweight file handling without needing a heavy database.

---

## 📂 Data Format & Naming Convention

The system expects data files to be stored in the `/data` directory.

### File Naming
The collector generates files using the timestamp of creation:
`sensor_YYYYMMDD_HHMMSS.json`

### JSON Structure
Each file contains an array of reading objects:
```json
[
  {
    "ts": "2025-11-20T21:40:32Z",
    "temperature_c": 18.83,
    "humidity_rh": 55.0,
    "battery_percentage": 76.0
  },
  ...
]