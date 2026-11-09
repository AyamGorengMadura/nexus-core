import psutil
import threading
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SystemMonitor")

class SystemMonitor:
    def __init__(self, check_interval=45):
        self.check_interval = check_interval
        self.cpu_threshold = 90.0
        self.ram_threshold = 90.0
        self.battery_threshold = 20.0
        self.cooldown = 300  # 5 minutes cooldown for alerts
        self.last_alert_time = 0
        self.running = False
        self._monitor_thread = None

    def get_stats(self):
        """Returns current system statistics."""
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
        battery_pct = battery.percent if battery else None

        return {
            "cpu": cpu,
            "ram": ram,
            "battery": battery_pct,
            "timestamp": datetime.now().isoformat()
        }

    def check_for_alerts(self, stats):
        """Checks if any stats exceed thresholds and returns an alert message if so."""
        now = time.time()
        if now - self.last_alert_time < self.cooldown:
            return None

        alerts = []
        if stats["cpu"] > self.cpu_threshold:
            alerts.append("Woi, laptop lu mau meledak, matiin dulu game-nya!")
        if stats["ram"] > self.ram_threshold:
            alerts.append("RAM lu udah mau penuh nih, tutup tab Chrome yang gak kepake!")
        if stats["battery"] is not None and stats["battery"] < self.battery_threshold:
            alerts.append("Batre lu sekarat, colokin charger-nya sekarang!")

        if alerts:
            self.last_alert_time = now
            return " ".join(alerts)

        return None

    def monitor_loop(self, callback):
        """Main polling loop."""
        self.running = True
        while self.running:
            try:
                stats = self.get_stats()
                alert = self.check_for_alerts(stats)
                if alert:
                    callback(alert)
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in system monitor loop: {e}")
                time.sleep(self.check_interval)

    def start(self, callback):
        """Starts the monitoring thread."""
        self._monitor_thread = threading.Thread(target=self.monitor_loop, args=(callback,), daemon=True)
        self._monitor_thread.start()
        logger.info("System Monitor started.")

    def stop(self):
        """Stops the monitoring thread."""
        self.running = False
        if self._monitor_thread:
            self._monitor_thread.join()
        logger.info("System Monitor stopped.")

def get_current_time_info():
    """Returns the current time and date in a natural format."""
    now = datetime.now()
    return now.strftime("%A, %d %B %Y, %H:%M:%S")
