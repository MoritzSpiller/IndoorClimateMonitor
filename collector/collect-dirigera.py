"""Continuous logger for a Dirigera environment sensor.

What this does:
- Connects to the Hub (uses the existing token/ip from the previous file).
- Finds the environment sensor with custom name "Raumtemperatursensor".
- Reads temperature and relative humidity every 2 minutes and appends to a JSON file.
- After 24 hours (since start), creates a line plot PNG and starts a fresh cycle.
- On KeyboardInterrupt, writes final plot and exits cleanly.

Notes:
- Stores data in JSON (simple, builtin). JSON is suitable for numeric time series and is
  easy to inspect and interoperate with other tools. YAML is more human-friendly but
  adds an external dependency (PyYAML). If you prefer YAML, I can switch.
"""

import json
import os
import time
from datetime import datetime, timedelta
import tempfile
import shutil
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import dirigera

LOGGER = logging.getLogger("dirigera_logger")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def find_sensor(hub: dirigera.Hub, name: str):
    """Return the first environment sensor whose custom_name matches `name`.

    Returns the sensor object or None if not found.
    """
    try:
        sensors = hub.get_environment_sensors()
    except Exception:
        LOGGER.exception("Failed to fetch environment sensors from hub")
        return None

    for s in sensors:
        try:
            if getattr(s.attributes, "custom_name", None) == name:
                return s
        except Exception:
            continue
    return None


def read_sensor_values(sensor) -> dict:
    """Read temperature and humidity from a sensor object and return a dict.

    Example return: {"ts": "2025-11-09T12:34:56Z", "temperature_c": 21.3, "humidity_rh": 45.2}
    """
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    try:
        temp = float(sensor.attributes.current_temperature)
    except Exception:
        temp = None
    try:
        rh = float(sensor.attributes.current_r_h)
    except Exception:
        rh = None
    try:
        pwr = float(sensor.attributes.battery_percentage)
    except Exception:
        pwr = None
    return {"ts": now, "temperature_c": temp, "humidity_rh": rh, "battery_percentage": pwr}


def atomic_write_json(path: str, data):
    dname = os.path.dirname(path)
    if dname:
        os.makedirs(dname, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dname or ".", prefix=".tmp_json_", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def append_reading(path: str, reading: dict):
    # load existing or start new list
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                payload = json.load(f)
        except Exception:
            LOGGER.exception("Failed to read existing JSON, starting fresh")
            payload = []
    else:
        payload = []

    payload.append(reading)
    atomic_write_json(path, payload)


def plot_day(json_path: str, png_path: str):
    if not os.path.exists(json_path):
        LOGGER.warning("No data file to plot: %s", json_path)
        return
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except Exception:
        LOGGER.exception("Failed to load JSON for plotting")
        return

    if not data:
        LOGGER.info("Data file empty, skipping plot: %s", json_path)
        return

    times = []
    temps = []
    hums = []
    pwr = []
    for row in data:
        try:
            times.append(datetime.fromisoformat(row["ts"].replace("Z", "")))
            temps.append(row.get("temperature_c"))
            hums.append(row.get("humidity_rh"))
            pwr.append(row.get("battery_percentage"))
        except Exception:
            continue

    if not times:
        LOGGER.info("No valid timestamps in data, skipping plot")
        return

    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.plot(times, temps, color="tab:red", label="Temperature (°C)")
    ax1.set_xlabel("time")
    ax1.set_ylabel("Temperature (°C)", color="tab:red")
    ax1.tick_params(axis="y", labelcolor="tab:red")

    ax2 = ax1.twinx()
    ax2.plot(times, hums, color="tab:blue", label="Humidity (%RH)")
    ax2.set_ylabel("Relative Humidity (%)", color="tab:blue")
    ax2.tick_params(axis="y", labelcolor="tab:blue")

    fig.tight_layout()
    # save atomically
    dname = os.path.dirname(png_path)
    if dname:
        os.makedirs(dname, exist_ok=True)
    # tmp_png = png_path + ".png"
    fig.savefig(png_path)
    # plt.close(fig)
    # shutil.move(tmp_png, png_path)
    LOGGER.info("Wrote plot: %s", png_path)

    # Plot battery percentage on its own figure (filter out missing values)
    pwr_pairs = [(t, v) for t, v in zip(times, pwr) if v is not None]
    if pwr_pairs:
        pwr_times, pwr_vals = zip(*pwr_pairs)
        fig_pwr, ax_pwr = plt.subplots(figsize=(12, 4))
        ax_pwr.plot(pwr_times, pwr_vals, color="tab:red", label="Battery Percentage (%)")
        ax_pwr.set_xlabel("time")
        ax_pwr.set_ylabel("Battery Percentage (%)", color="tab:red")
        ax_pwr.tick_params(axis="y", labelcolor="tab:red")

        fig_pwr.tight_layout()
        # save atomically
        filename = os.path.basename(png_path)
        png_path_pwr = os.path.join(os.path.dirname(png_path), f"pwr_{filename}")
        fig_pwr.savefig(png_path_pwr)
        plt.close(fig_pwr)
        LOGGER.info("Wrote plot: %s", png_path_pwr)
    else:
        LOGGER.info("No battery data available, skipping battery plot")


def main_loop(
    token: str,
    ip_address: str,
    sensor_name: str = "Raumtemperatursensor",
    interval_seconds: int = 120,
    seconds_per_cycle: int = 24 * 3600,
    store_plots: bool = False,
):
    hub = dirigera.Hub(token=token, ip_address=ip_address)

    cycle_start = datetime.utcnow()
    json_path = f"data/sensor_{cycle_start.strftime('%Y%m%d_%H%M%S')}.json"
    LOGGER.info("Starting logging cycle: %s", json_path)

    # Attempt to find sensor; if not present, will retry each loop
    sensor = None

    try:
        while True:
            now = datetime.utcnow()
            if sensor is None:
                sensor = find_sensor(hub, sensor_name)
                if sensor is None:
                    LOGGER.warning("Sensor '%s' not found, retrying in %s seconds", sensor_name, interval_seconds)
                    time.sleep(interval_seconds)
                    continue

            try:
                # Fetch latest sensor object (some libraries provide live objects; re-query to be safe)
                sensor = find_sensor(hub, sensor_name) or sensor
                reading = read_sensor_values(sensor)
                append_reading(json_path, reading)
                LOGGER.info("Appended reading: %s", reading)
            except Exception:
                LOGGER.exception("Failed to read/append sensor data")

            # if cycle age >= seconds_per_cycle, produce plot and start new cycle
            if (now - cycle_start).total_seconds() >= seconds_per_cycle:
                png_path = f"plots/sensor_{cycle_start.strftime('%Y%m%d_%H%M%S')}.png"
                LOGGER.info("Cycle complete (>= %s sec). Plotting to %s", seconds_per_cycle, png_path)
                if store_plots:
                    plot_day(json_path, png_path)
                # rotate: start new files
                cycle_start = datetime.utcnow()
                json_path = f"data/sensor_{cycle_start.strftime('%Y%m%d_%H%M%S')}.json"
                LOGGER.info("Starting new cycle: %s", json_path)

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        LOGGER.info("Interrupted by user, producing final plot and exiting")
        if store_plots:
            png_path = f"plots/sensor_{cycle_start.strftime('%Y%m%d_%H%M%S')}_final.png"
            plot_day(json_path, png_path)


if __name__ == "__main__":
    # NOTE: keep same token/ip as previous code; consider moving to a config or env vars
    TOKEN = "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImVmZmI5NTkzOWYwN2YzMDAwMGIyZTM4ZjVhMzc4YjE5YzIxNmQ2NzdhOWJjNDE5MzgxMWY3YzU2MmE4MDlhODAifQ.eyJpc3MiOiIyOTNiMjk2NS0yNDM0LTRkM2MtODEyNy1kM2E5ZmYxOTllYjYiLCJ0eXBlIjoiYWNjZXNzIiwiYXVkIjoiaG9tZXNtYXJ0LmxvY2FsIiwic3ViIjoiNDc0MDU3MzItYmM5Ni00ZWVlLThlNmYtMDViZWYzNzNkZGM5IiwiaWF0IjoxNzYyNjg2MDc2LCJleHAiOjIwNzgyNjIwNzZ9.yQlkECbR3RlvEXiCCaN_dlpb59p_gCYRtEaNYiPWarZ4KvpMQVF9mE5573voECxBN_JPcGM3WETD1x-3FykiBw"
    IP = "192.168.0.32"
    # 2 minutes interval; 86400 seconds = 24 hours
    main_loop(TOKEN, IP, sensor_name="Schlafzimmersensor", interval_seconds=600, seconds_per_cycle=24 * 3600)