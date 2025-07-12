from flask import Flask, render_template, request
from flask_socketio import SocketIO
from ping3 import ping
import time
from datetime import datetime, timedelta
from collections import deque
from colorama import Fore, Style
import sys
import os
from tabulate import tabulate

# Inicialización
app = Flask(__name__)
app.logger.disabled = True
import logging
log = logging.getLogger('werkzeug')
log.disabled = True

socketio = SocketIO(app, logger=False, engineio_logger=False)
background_task_started = False

# Configuración
HISTORY_LENGTH = 15
DEVICE_HISTORY = {}
DEVICE_INCIDENTS = {}

class Incident:
    def __init__(self, start_time):
        self.start_time = start_time
        self.end_time = None
        self.duration = None

    def close(self, end_time):
        self.end_time = end_time
        self.duration = end_time - self.start_time

    def to_dict(self):
        return {
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else None,
            'duration': str(self.duration) if self.duration else None
        }

DEVICES = [
    # Plantilla para dispositivos: {"name": "Nombre", "type": "Tipo", "ip": "IP", "building": "Edificio", "location": "Ubicación"}
    
    # ================================================
    # ================================================
    # SECRETARIA CENTRAL
    # ================================================
    # ================================================

    {"name": "Firewall", "type": "SWITCH", "ip": "192.168.99.1", "building": "Secretaría Central", "location": "Secretaría Central"},
    {"name": "Switch Secretaria", "type": "SWITCH", "ip": "192.168.99.211", "building": "Secretaría Central", "location": "Secretaría Central"},
    
    # ================================================
    # ================================================
    # ESO
    # ================================================
    # ================================================

    # ================================================
    # PLANTA 1
    # ================================================

    {"name": "Switch ESO Planta 1", "type": "SWITCH", "ip": "192.168.99.0", "building": "ESO", "location": "Planta 1"},
    {"name": "Impresora ESO Dep. Cien.", "type": "IMPRESORA", "ip": "192.168.80.15", "building": "ESO", "location": "Planta 1"},

    # ================================================
    # PLANTA 0
    # ================================================
 
    {"name": "Switch ESO Planta 0", "type": "SWITCH", "ip": "192.168.99.201", "building": "ESO", "location": "Planta 0"},
    {"name": "Impresora ESO Secretaria", "type": "IMPRESORA", "ip": "192.168.80.12", "building": "ESO", "location": "Planta 0"},
    {"name": "Impresora ESO Dep. Hum.", "type": "IMPRESORA", "ip": "192.168.80.17", "building": "ESO", "location": "Planta 0"},

    # ================================================
    # PLANTA -1
    # ================================================

    {"name": "Switch ESO Planta -1", "type": "SWITCH", "ip": "192.168.99.204", "building": "ESO", "location": "Planta -1"},

]

# Inicializar historial
for device in DEVICES:
    DEVICE_HISTORY[device['ip']] = deque(maxlen=HISTORY_LENGTH)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def check_device(device):
    try:
        response_time = ping(device["ip"], timeout=1)
        current_time = datetime.now()
        
        if response_time is not None:
            status = "online"
            ms = f"{response_time*1000:.1f}"
            uptime_status = 1
            
            if device['ip'] in DEVICE_INCIDENTS and DEVICE_INCIDENTS[device['ip']][-1].end_time is None:
                DEVICE_INCIDENTS[device['ip']][-1].close(current_time)
        else:
            status = "offline"
            ms = "-"
            uptime_status = 0
            
            if device['ip'] not in DEVICE_INCIDENTS:
                DEVICE_INCIDENTS[device['ip']] = []
            if not DEVICE_INCIDENTS[device['ip']] or DEVICE_INCIDENTS[device['ip']][-1].end_time is not None:
                DEVICE_INCIDENTS[device['ip']].append(Incident(current_time))
    except Exception:
        status = "offline"
        ms = "-"
        uptime_status = 0
    
    # Actualizar historial
    if device['ip'] not in DEVICE_HISTORY:
        DEVICE_HISTORY[device['ip']] = deque(maxlen=HISTORY_LENGTH)
    DEVICE_HISTORY[device['ip']].append({
        'timestamp': current_time,
        'status': uptime_status
    })

    # Calcular uptime
    history = list(DEVICE_HISTORY[device['ip']])
    uptime_24h = sum(1 for entry in history if entry['status'] == 1) / len(history) * 100 if history else 0

    # Incidente actual
    current_incident = None
    if device['ip'] in DEVICE_INCIDENTS and DEVICE_INCIDENTS[device['ip']]:
        last_incident = DEVICE_INCIDENTS[device['ip']][-1]
        if last_incident.end_time is None:
            current_incident = {
                'start_time': last_incident.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'duration': str(current_time - last_incident.start_time)
            }

    uptime_history = [{
        'timestamp': entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
        'status': entry['status']
    } for entry in history]

    return {
        "type": device["type"],
        "name": device["name"],
        "status": status,
        "building": device["building"],
        "location": device["location"],
        "latency": ms,
        "ip": device["ip"],
        "uptime_history": uptime_history,
        "uptime_24h": uptime_24h,
        "current_incident": current_incident
    }

def check_connections():
    """Comprueba la conectividad mostrando barra de progreso"""
    results = []
    total = len(DEVICES)
    max_width = 50
    
    print(f"{Fore.CYAN}Comprobando {total} dispositivos:{Style.RESET_ALL}")
    print("[", end="")
    
    for i, device in enumerate(DEVICES, 1):
        try:
            response_time = ping(device["ip"])
            if response_time is not None:
                status = Fore.GREEN + "✓" + Style.RESET_ALL
                ms = f"{response_time*1000:.1f} ms"
            else:
                status = Fore.RED + "✗" + Style.RESET_ALL
                ms = "-"
        except Exception:
            status = Fore.RED + "✗" + Style.RESET_ALL
            ms = "-"
        
        results.append([device["name"], device["type"], device["ip"], status, ms])
        
        # Barra de progreso
        progress = int((i / total) * max_width)
        bar = "=" * progress + " " * (max_width - progress)
        percent = int((i / total) * 100)
        sys.stdout.write(f"\r[{bar}] {percent}%")
        sys.stdout.flush()
    
    print("\n")
    return results

# Rutas Flask
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/esquema')
def esquema():
    return render_template('esquema/index.html')

@app.route('/device/<ip>')
def device_details(ip):
    device = next((d for d in DEVICES if d['ip'] == ip), None)
    if not device:
        return "Dispositivo no encontrado", 404
    device_status = check_device(device)
    return render_template('device_details.html', device=device_status)

# WebSocket
@socketio.on('connect')
def handle_connect():
    global background_task_started
    current_time = datetime.now().strftime("%H:%M:%S")
    
    print(f"{Fore.CYAN}Cliente conectado. Iniciando comprobación...{Style.RESET_ALL}")
    
    # Enviar progreso inicial
    socketio.emit('progress', {'value': 0, 'device': 'Iniciando...'})
    
    devices_status = []
    total = len(DEVICES)
    
    def check_devices():
        for i, device in enumerate(DEVICES, 1):
            # Enviar progreso antes de comprobar el dispositivo
            progress = int(((i-1) / total) * 100)
            socketio.emit('progress', {
                'value': progress,
                'device': f'Comprobando {device["name"]}...'
            })
            
            # Comprobar dispositivo
            status = check_device(device)
            devices_status.append(status)
            
            # Enviar progreso después de comprobar
            progress = int((i / total) * 100)
            socketio.emit('progress', {
                'value': progress,
                'device': f'Comprobado {device["name"]}: {status["status"]}'
            })
            
            # Log en consola
            print(f"Comprobado {device['name']}: {status['status']} ({progress}%)")
        
        # Enviar datos finales
        socketio.emit('devices_data', {'time': current_time, 'devices': devices_status})
    
    # Iniciar la comprobación en un hilo separado
    socketio.start_background_task(check_devices)
    
    if not background_task_started:
        socketio.start_background_task(update_status)
        background_task_started = True

def update_status():
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            devices_status = [check_device(device) for device in DEVICES]
            socketio.emit('devices_data', {'time': current_time, 'devices': devices_status})
            time.sleep(60)
        except Exception as e:
            print(f"\n{Fore.RED}Error in update_status: {e}{Style.RESET_ALL}")

# Modo consola
def console_monitor():
    print(f"{Fore.CYAN}=== CheckNet ==={Style.RESET_ALL}")
    print("Presiona Ctrl+C para detener\n")

    try:
        while True:
            clear_screen()
            print(f"{Fore.CYAN}=== Monitor de Red ==={Style.RESET_ALL}")
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"Hora actual: {current_time}\n")
            
            results = check_connections()
            headers = ["Nombre", "Tipo", "IP", "Estado", "Latencia"]
            print(tabulate(results, headers=headers, tablefmt="grid"))
            print("-" * 50)

            time.sleep(5)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Monitoreo finalizado{Style.RESET_ALL}")

if __name__ == '__main__':
    # Ejecutar en modo web o consola según argumentos
    if len(sys.argv) > 1 and sys.argv[1] == 'console':
        console_monitor()
    else:
        print("\nCheckNet - Monitor de Red")
        print("Running on http://127.0.0.1:5000")
        print("Press CTRL+C to quit\n")
        socketio.run(app, debug=False)