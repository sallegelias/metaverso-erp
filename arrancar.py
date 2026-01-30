import uvicorn
import os
import time
import webbrowser
import sys

# Configuración
PUERTO = 8080 # Usamos el 8080 que es más robusto
HOST = "127.0.0.1"

def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')

def verificar_archivos():
    print("🔍 Verificando sistema...")
    
    # 1. Verificar Main
    if not os.path.exists("main.py"):
        print("❌ ERROR FATAL: No encuentro 'main.py'")
        input("Presiona Enter para salir...")
        sys.exit()
    
    # 2. Verificar Templates
    if not os.path.exists("templates"):
        print("❌ ERROR FATAL: No encuentro la carpeta 'templates'")
        input("Presiona Enter para salir...")
        sys.exit()
        
    # 3. Verificar Login
    if not os.path.exists("templates/login.html"):
        print("❌ ERROR: Falta 'templates/login.html'")
        input("Presiona Enter para salir...")
        sys.exit()

    print("✅ Archivos correctos.")

if __name__ == "__main__":
    limpiar_pantalla()
    print("========================================")
    print("   🚀 INICIANDO METAVERSO ERP v4.0")
    print("========================================")
    
    verificar_archivos()
    
    print(f"\n🌐 El servidor se abrirá en: http://{HOST}:{PUERTO}")
    print("👉 Para detenerlo, presiona CTRL + C en esta ventana.")
    print("========================================\n")
    
    # Abrir navegador automáticamente después de 2 segundos
    def abrir_navegador():
        time.sleep(2)
        webbrowser.open(f"http://{HOST}:{PUERTO}")
    
    import threading
    hilo = threading.Thread(target=abrir_navegador)
    hilo.start()
    
    # Arrancar Servidor (Forzando puerto 8080)
    try:
        uvicorn.run("main:app", host=HOST, port=PUERTO, reload=True)
    except Exception as e:
        print(f"\n❌ ERROR AL ARRANCAR: {e}")
        input("Presiona Enter para cerrar...")