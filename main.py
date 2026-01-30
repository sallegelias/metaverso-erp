import sqlite3
import json
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase  # Para archivos adjuntos
from email import encoders            # Para codificar archivos
# Importar librería para imágenes (Agréga esto arriba del todo si falta, o Python lo detectará)
from email.mime.image import MIMEImage

# ==============================================================================
# 1. IMPORTACIÓN DE LIBRERÍAS Y CONFIGURACIÓN DEL SERVIDOR
# ==============================================================================
# Asegúrate de tener instalado: pip install fastapi uvicorn jinja2 python-multipart
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

# Inicializamos la aplicación FastAPI
app = FastAPI(title="Metaverso ERP v4.0", version="4.0.0")

# --- CONFIGURACIÓN DE EMAIL (YA CONFIGURADO) ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_EMPRESA = "metaversotech.cotizaciones@gmail.com"
EMAIL_PASSWORD = "zmwfibsduckxdkme" # Clave de aplicación (ya sin espacios)

# --- SEGURIDAD: CLAVE DE SESIÓN ---
# Esta clave cifra las cookies para que nadie pueda falsificar su identidad.
# En producción, esto debería ser una variable de entorno.
app.add_middleware(SessionMiddleware, secret_key="metaverso_super_secret_key_2026_master_full_secure")

# --- CONFIGURACIÓN DE RUTAS DE ARCHIVOS (ANTI-ERRORES) ---
# Esto garantiza que el sistema encuentre las carpetas sin importar desde dónde se ejecute el script.
directorio_base = os.path.dirname(os.path.abspath(__file__))
ruta_templates = os.path.join(directorio_base, "templates")
ruta_static = os.path.join(directorio_base, "static")

# Diagnóstico de arranque en consola para verificar rutas
print(f"\n--- SISTEMA INICIANDO ---")
print(f"📂 Directorio Base: {directorio_base}")
print(f"📂 Plantillas: {ruta_templates}")
print(f"📂 Estáticos: {ruta_static}")

# Crear carpeta static si no existe para evitar crashes
if not os.path.exists(ruta_static):
    os.makedirs(ruta_static)
    print("✅ Carpeta 'static' creada automáticamente.")

# Montaje de archivos estáticos (imágenes, CSS, JS)
app.mount("/static", StaticFiles(directory=ruta_static), name="static")

# Configuración del motor de plantillas (Jinja2)
templates = Jinja2Templates(directory=ruta_templates)

# Nombre del archivo de Base de Datos SQLite
NOMBRE_DB = "metaverso_v4.db"

# --- CONFIGURACIÓN DE CORREO (Ajusta con tus datos) ---
#SMTP_SERVER = "smtp.gmail.com"
#SMTP_PORT = 587
#EMAIL_USUARIO = "tu_correo@gmail.com"
#EMAIL_PASSWORD = "tu_clave_de_aplicacion"

# ==============================================================================
# 2. BASE DE DATOS (CONEXIÓN Y ESTRUCTURA)
# ==============================================================================

def obtener_db():
    """
    Crea una conexión a la base de datos SQLite.
    row_factory permite acceder a las columnas por nombre en lugar de índice numérico.
    """
    conn = sqlite3.connect(NOMBRE_DB)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_db():
    """
    Verifica y crea todas las tablas necesarias al iniciar el programa.
    Incluye la nueva tabla 'empresas_config' para personalizar datos desde la app.
    """
    conn = obtener_db()
    cursor = conn.cursor()
    
    print("🛠️ Verificando integridad de la Base de Datos...")

    # 1. Tabla CLIENTES
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            nit TEXT,
            encargado TEXT,
            direccion TEXT,
            telefono TEXT,
            email TEXT,
            tipo TEXT
        )
    """)
    
    # 2. Tabla PROVEEDORES
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            nit TEXT,
            encargado TEXT,
            direccion TEXT,
            telefono TEXT,
            email TEXT,
            tipo TEXT
        )
    """)
    
    # 3. Tabla PRODUCTOS (Inventario con Costos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT,
            nombre TEXT,
            tipo TEXT,
            costo REAL,
            precio REAL,
            proveedor TEXT,
            imagen TEXT
        )
    """)
    
    # 4. Tabla LEVANTAMIENTOS (Ingeniería de Campo)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS levantamientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            nombre_proyecto TEXT,
            torres INTEGER,
            pisos INTEGER,
            aptos_piso INTEGER,
            total_unidades INTEGER,
            largo_m REAL,
            ancho_m REAL,
            amenidades TEXT,
            calculo_utp TEXT,
            notas TEXT
        )
    """)
    
    # 5. Tabla COTIZACIONES (Ventas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cotizaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            cliente TEXT,
            nit TEXT,
            total REAL,
            items TEXT,
            empresa_tipo TEXT,
            estado TEXT DEFAULT 'Pendiente'
        )
    """)
    
    # 6. Tabla USUARIOS (Roles y Seguridad)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password TEXT,
            rol TEXT
        )
    """)
    
    # 7. NUEVA TABLA: CONFIGURACIÓN DE EMPRESAS
    # Esta tabla permite editar los datos del PDF sin tocar el código Python
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS empresas_config (
            id TEXT PRIMARY KEY, 
            nombre TEXT, 
            nit TEXT, 
            direccion TEXT, 
            telefono TEXT, 
            email TEXT, 
            regimen TEXT, 
            tipo_regimen TEXT, 
            logo_img TEXT, 
            lema TEXT
        )
    """)

    # --- INSERCIÓN DE DATOS POR DEFECTO ---
    
    # A. Usuarios (Admin y Secretaria)
    try:
        cursor.execute("INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)", ("admin", "admin123", "admin"))
        cursor.execute("INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)", ("secre", "secre123", "asistente"))
        print("✅ Usuarios por defecto verificados.")
    except sqlite3.IntegrityError:
        pass # Ya existen

    # B. Configuración de Empresas (Si está vacía)
    verificar_empresas = cursor.execute("SELECT COUNT(*) FROM empresas_config").fetchone()[0]
    if verificar_empresas == 0:
        print("⚙️ Creando configuración de empresas por defecto...")
        # Empresa A (SAS - Régimen Común)
        cursor.execute("""
            INSERT INTO empresas_config (id, nombre, nit, direccion, telefono, email, regimen, tipo_regimen, logo_img, lema)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("A", "METAVERSO TECH S.A.S", "900.123.456-7", "Calle 100 # 20-30", "(605) 300 1234", "gerencia@metaverso.com", "IVA", "RÉGIMEN COMÚN", "logo_sas.png", "Innovación y Tecnología"))
        
        # Empresa B (Simplificado - Persona Natural)
        cursor.execute("""
            INSERT INTO empresas_config (id, nombre, nit, direccion, telefono, email, regimen, tipo_regimen, logo_img, lema)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("B", "SOLUCIONES RÁPIDAS", "1.045.678.901-2", "Carrera 50 # 80-10", "300 987 6543", "contacto@jhondoe.com", "NO_IVA", "RÉGIMEN SIMPLIFICADO", "logo_simplificado.png", "Servicio Garantizado"))

    conn.commit()
    conn.close()
    print("✅ Base de Datos inicializada correctamente.")

# Ejecutar la inicialización al arrancar el script
inicializar_db()


# ==============================================================================
# 3. HELPERS Y UTILIDADES
# ==============================================================================

def get_rol(request: Request):
    """Devuelve el rol del usuario de la sesión actual (admin o asistente)."""
    return request.session.get("rol", "asistente")

def get_usuario(request: Request):
    """Devuelve el nombre de usuario de la sesión actual."""
    return request.session.get("usuario", None)

# ==============================================================================
# 4. MÓDULO DE ENVIO DE COTIZACION POR EMAIL
# ==============================================================================

def enviar_correo_cotizacion(destinatario, cliente_nombre, id_cot, total):
    try:
        # 1. Configurar mensaje
        msg = MIMEMultipart()
        msg['From'] = EMAIL_EMPRESA
        msg['To'] = destinatario
        msg['Subject'] = f"📄 Cotización #COT-{id_cot:04d} - Metaverso Tech"

        # 2. Enlace para ver la cotización
        link_ver = f"http://127.0.0.1:8080/imprimir-cotizacion/{id_cot}"

        # 3. Cuerpo HTML Profesional
        cuerpo_html = f"""
        <html>
        <body style="font-family: 'Segoe UI', sans-serif; background-color: #f1f5f9; padding: 20px;">
            <div style="max-width: 500px; margin: auto; background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h2 style="color: #2563eb; text-align: center; margin-top: 0;">¡Hola, {cliente_nombre}!</h2>
                <p style="color: #64748b; text-align: center;">Adjuntamos la propuesta comercial solicitada.</p>
                
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 15px; margin: 20px 0;">
                    <p style="margin: 5px 0; color: #334155;"><strong>Referencia:</strong> #COT-{id_cot:04d}</p>
                    <p style="margin: 5px 0; color: #334155;"><strong>Total:</strong> $ {total:,.0f}</p>
                </div>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{link_ver}" style="background-color: #0891b2; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">
                        Ver Cotización Online
                    </a>
                </div>

                <p style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 30px;">
                    Metaverso ERP - Generado Automáticamente<br>
                    Enlace manual: {link_ver}
                </p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(cuerpo_html, 'html'))

        # 4. Enviar usando Gmail
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_EMPRESA, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True

    except Exception as e:
        print(f"❌ Error SMTP: {e}")
        return False
# ==============================================================================
# 5. MÓDULO DE AUTENTICACIÓN (LOGIN)
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """Muestra la página de inicio de sesión."""
    if not os.path.exists(os.path.join(ruta_templates, "login.html")):
        return HTMLResponse("<h1>ERROR CRÍTICO: No se encuentra 'login.html' en la carpeta templates.</h1>", status_code=500)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Procesa las credenciales enviadas por el formulario."""
    conn = obtener_db()
    cursor = conn.cursor()
    
    # Consulta segura usando parámetros para evitar inyección SQL
    user = cursor.execute("SELECT * FROM usuarios WHERE username = ? AND password = ?", (username, password)).fetchone()
    conn.close()
    
    if user:
        # Credenciales correctas: Crear sesión
        request.session["usuario"] = username
        request.session["rol"] = user["rol"]
        print(f"🔓 Login exitoso: {username}")
        return RedirectResponse(url="/dashboard", status_code=303)
    else:
        # Credenciales incorrectas
        print(f"🔒 Login fallido: {username}")
        return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciales Incorrectas"})

@app.get("/logout")
async def logout(request: Request):
    """Cierra la sesión y redirige al login."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


# ==============================================================================
# 6. MÓDULO: DASHBOARD (PANEL PRINCIPAL)
# ==============================================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Verificación de sesión
    if not request.session.get("usuario"): return RedirectResponse(url="/")
    
    conn = obtener_db()
    cursor = conn.cursor()
    
    # Obtención de métricas (Contadores)
    # Usamos try-except para robustez en caso de tablas vacías o errores de DB
    try: tc = cursor.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
    except: tc = 0
    
    try: tp = cursor.execute("SELECT COUNT(*) FROM proveedores").fetchone()[0]
    except: tp = 0
    
    try: tprod = cursor.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
    except: tprod = 0
    
    try: tlev = cursor.execute("SELECT COUNT(*) FROM levantamientos").fetchone()[0]
    except: tlev = 0
    
    try: tcot = cursor.execute("SELECT COUNT(*) FROM cotizaciones").fetchone()[0]
    except: tcot = 0
    
    # Datos para la Gráfica de Pastel (Distribución de clientes por tipo)
    resultados = cursor.execute("SELECT tipo, COUNT(*) as cantidad FROM clientes GROUP BY tipo").fetchall()
    grafica = {"Privada": 0, "Gobierno": 0, "PH": 0}
    for r in resultados:
        if r["tipo"] == "Empresa Privada": grafica["Privada"] = r["cantidad"]
        elif r["tipo"] == "Edificio Gubernamental": grafica["Gobierno"] = r["cantidad"]
        elif r["tipo"] == "Propiedad Horizontal": grafica["PH"] = r["cantidad"]
    
    conn.close()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "rol": get_rol(request), 
        "total_clientes": tc, 
        "total_proveedores": tp, 
        "total_productos": tprod, 
        "total_levantamientos": tlev, 
        "total_cotizaciones": tcot, 
        "datos_grafica": grafica
    })


# ==============================================================================
# 7. MÓDULO: GESTIÓN DE CLIENTES
# ==============================================================================

@app.get("/clientes", response_class=HTMLResponse)
async def modulo_clientes(request: Request):
    if not request.session.get("usuario"): return RedirectResponse(url="/")
    
    conn = obtener_db()
    cursor = conn.cursor()
    clientes = cursor.execute("SELECT * FROM clientes ORDER BY id DESC").fetchall()
    conn.close()
    
    return templates.TemplateResponse("clientes.html", {"request": request, "rol": get_rol(request), "clientes": clientes})

@app.post("/guardar-cliente")
async def guardar_cliente(
    id: str = Form(""), 
    nombre: str = Form(...), 
    nit: str = Form(...), 
    encargado: str = Form(...), 
    direccion: str = Form(...), 
    telefono: str = Form(...), 
    email: str = Form(...), 
    tipo: str = Form(...)
):
    conn = obtener_db()
    cursor = conn.cursor()
    
    # Estandarización a mayúsculas
    nombre = nombre.upper()
    nit = nit.upper()
    encargado = encargado.upper()
    direccion = direccion.upper()
    
    if id == "": 
        # Crear nuevo cliente
        cursor.execute("""
            INSERT INTO clientes (nombre, nit, encargado, direccion, telefono, email, tipo) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (nombre, nit, encargado, direccion, telefono, email, tipo))
    else: 
        # Actualizar existente
        cursor.execute("""
            UPDATE clientes SET nombre=?, nit=?, encargado=?, direccion=?, telefono=?, email=?, tipo=? 
            WHERE id=?
        """, (nombre, nit, encargado, direccion, telefono, email, tipo, id))
    
    conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/eliminar-cliente/{id_cliente}")
async def eliminar_cliente(request: Request, id_cliente: int):
    # Seguridad: Solo admin puede borrar
    if get_rol(request) != "admin": return RedirectResponse(url="/clientes")
    
    conn = obtener_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clientes WHERE id = ?", (id_cliente,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/clientes", status_code=303)


# ==============================================================================
# 8. MÓDULO: GESTIÓN DE PROVEEDORES
# ==============================================================================

@app.get("/proveedores", response_class=HTMLResponse)
async def modulo_proveedores(request: Request):
    if not request.session.get("usuario"): return RedirectResponse(url="/")
    
    conn = obtener_db()
    cursor = conn.cursor()
    proveedores = cursor.execute("SELECT * FROM proveedores ORDER BY id DESC").fetchall()
    conn.close()
    
    return templates.TemplateResponse("proveedores.html", {"request": request, "rol": get_rol(request), "proveedores": proveedores})

@app.post("/guardar-proveedor")
async def guardar_proveedor(
    id: str = Form(""), 
    nombre: str = Form(...), 
    nit: str = Form(...), 
    encargado: str = Form(...), 
    direccion: str = Form(...), 
    telefono: str = Form(...), 
    email: str = Form(...), 
    tipo: str = Form(...)
):
    conn = obtener_db()
    cursor = conn.cursor()
    
    nombre = nombre.upper()
    nit = nit.upper()
    encargado = encargado.upper()
    direccion = direccion.upper()
    
    if id == "": 
        cursor.execute("""
            INSERT INTO proveedores (nombre, nit, encargado, direccion, telefono, email, tipo) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (nombre, nit, encargado, direccion, telefono, email, tipo))
    else: 
        cursor.execute("""
            UPDATE proveedores SET nombre=?, nit=?, encargado=?, direccion=?, telefono=?, email=?, tipo=? 
            WHERE id=?
        """, (nombre, nit, encargado, direccion, telefono, email, tipo, id))
    
    conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/eliminar-proveedor/{id_proveedor}")
async def eliminar_proveedor(request: Request, id_proveedor: int):
    if get_rol(request) != "admin": return RedirectResponse(url="/proveedores")
    
    conn = obtener_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM proveedores WHERE id = ?", (id_proveedor,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/proveedores", status_code=303)


# ==============================================================================
# 9. MÓDULO: INVENTARIO Y PRODUCTOS
# ==============================================================================

@app.get("/productos", response_class=HTMLResponse)
async def modulo_productos(request: Request):
    if not request.session.get("usuario"): return RedirectResponse(url="/")
    
    conn = obtener_db()
    cursor = conn.cursor()
    productos = cursor.execute("SELECT * FROM productos ORDER BY id DESC").fetchall()
    proveedores = cursor.execute("SELECT nombre FROM proveedores ORDER BY nombre").fetchall()
    conn.close()
    
    return templates.TemplateResponse("productos.html", {
        "request": request, 
        "rol": get_rol(request), 
        "productos": productos, 
        "lista_proveedores": proveedores
    })

@app.post("/guardar-producto")
async def guardar_producto(
    id: str = Form(""), 
    codigo: str = Form(...), 
    nombre: str = Form(...), 
    tipo: str = Form(...), 
    costo: str = Form(...), 
    precio: str = Form(...), 
    proveedor: str = Form(...), 
    imagen: str = Form("")
):
    conn = obtener_db()
    cursor = conn.cursor()
    
    codigo = codigo.upper()
    nombre = nombre.upper()
    
    if id == "": 
        cursor.execute("""
            INSERT INTO productos (codigo, nombre, tipo, costo, precio, proveedor, imagen) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (codigo, nombre, tipo, costo, precio, proveedor, imagen))
    else: 
        cursor.execute("""
            UPDATE productos SET codigo=?, nombre=?, tipo=?, costo=?, precio=?, proveedor=?, imagen=? 
            WHERE id=?
        """, (codigo, nombre, tipo, costo, precio, proveedor, imagen, id))
    
    conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/eliminar-producto/{id_producto}")
async def eliminar_producto(request: Request, id_producto: int):
    if get_rol(request) != "admin": return RedirectResponse(url="/productos")
    
    conn = obtener_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM productos WHERE id = ?", (id_producto,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/productos", status_code=303)


# ==============================================================================
# 10. MÓDULO: LEVANTAMIENTO (INGENIERÍA)
# ==============================================================================

@app.get("/caracterizacion", response_class=HTMLResponse)
async def modulo_caracterizacion(request: Request):
    if not request.session.get("usuario"): return RedirectResponse(url="/")
    
    conn = obtener_db()
    cursor = conn.cursor()
    levs = cursor.execute("SELECT * FROM levantamientos ORDER BY id DESC").fetchall()
    clientes = cursor.execute("SELECT nombre FROM clientes ORDER BY nombre").fetchall()
    
    # Parseo de JSON para las amenidades (ej: Piscina, Gym)
    levantamientos = []
    for l in levs:
        item = dict(l)
        try: item['lista_amenidades'] = json.loads(l['amenidades'])
        except: item['lista_amenidades'] = []
        levantamientos.append(item)
        
    conn.close()
    return templates.TemplateResponse("caracterizacion.html", {
        "request": request, 
        "rol": get_rol(request), 
        "levantamientos": levantamientos, 
        "lista_clientes": clientes
    })

@app.post("/guardar-levantamiento")
async def guardar_levantamiento(
    id: str = Form(""), 
    cliente: str = Form(...), 
    nombre_proyecto: str = Form(...), 
    torres: int = Form(0), 
    pisos: int = Form(0), 
    aptos_piso: int = Form(0), 
    largo_m: float = Form(0.0), 
    ancho_m: float = Form(0.0), 
    amenidades_json: str = Form("[]"), 
    calculo_utp: str = Form(""), 
    notas: str = Form("")
):
    total = torres * pisos * aptos_piso
    conn = obtener_db()
    cursor = conn.cursor()
    
    if id == "": 
        cursor.execute("""
            INSERT INTO levantamientos (cliente, nombre_proyecto, torres, pisos, aptos_piso, total_unidades, largo_m, ancho_m, amenidades, calculo_utp, notas) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cliente, nombre_proyecto.upper(), torres, pisos, aptos_piso, total, largo_m, ancho_m, amenidades_json, calculo_utp, notas))
    else: 
        cursor.execute("""
            UPDATE levantamientos SET cliente=?, nombre_proyecto=?, torres=?, pisos=?, aptos_piso=?, total_unidades=?, largo_m=?, ancho_m=?, amenidades=?, calculo_utp=?, notas=? 
            WHERE id=?
        """, (cliente, nombre_proyecto.upper(), torres, pisos, aptos_piso, total, largo_m, ancho_m, amenidades_json, calculo_utp, notas, id))
    
    conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/eliminar-levantamiento/{id_lev}")
async def eliminar_levantamiento(request: Request, id_lev: int):
    if get_rol(request) != "admin": return RedirectResponse(url="/caracterizacion")
    conn = obtener_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM levantamientos WHERE id = ?", (id_lev,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/caracterizacion", status_code=303)


# ==============================================================================
# 11. MÓDULO: COTIZACIONES (VENTAS) - ACTUALIZADO CON DB CONFIG
# ==============================================================================

@app.get("/cotizaciones", response_class=HTMLResponse)
async def modulo_cotizaciones(request: Request):
    if not request.session.get("usuario"): return RedirectResponse(url="/")
    
    conn = obtener_db()
    cursor = conn.cursor()
    
    historial = cursor.execute("SELECT * FROM cotizaciones ORDER BY id DESC").fetchall()
    clientes = cursor.execute("SELECT * FROM clientes ORDER BY nombre").fetchall()
    productos_db = cursor.execute("SELECT * FROM productos ORDER BY nombre").fetchall()
    
    # 🌟 AQUÍ ESTÁ EL CAMBIO: Leemos la configuración de la empresa DESDE LA DB
    empresa_a = cursor.execute("SELECT * FROM empresas_config WHERE id='A'").fetchone()
    empresa_b = cursor.execute("SELECT * FROM empresas_config WHERE id='B'").fetchone()
    
    productos_json = []
    for p in productos_db: 
        productos_json.append({"nombre": p["nombre"], "costo": p["costo"], "precio": p["precio"], "codigo": p["codigo"]})
        
    conn.close()
    return templates.TemplateResponse("cotizaciones.html", {
        "request": request, 
        "rol": get_rol(request),
        "cotizaciones": historial, 
        "lista_clientes": clientes, 
        "productos_json": json.dumps(productos_json),
        "empresa_a": empresa_a, 
        "empresa_b": empresa_b
    })

# ==============================================================================
# 12. GUARDAR COTIZACIÓN EN BD (ACTUALIZADO CON EMAIL)
# ==============================================================================
@app.post("/guardar-cotizacion")
async def guardar_cotizacion(
    fecha: str = Form(...), 
    cliente_info: str = Form(...),  # En el HTML se llama "cliente_info"
    nit: str = Form(...),
    items_json: str = Form(...), 
    empresa_tipo: str = Form(...),
    email_destino: str = Form("")   # <--- AQUI RECIBIMOS EL EMAIL DEL FORMULARIO
):
    conn = obtener_db()
    cursor = conn.cursor()
    
    # Procesar totales
    items = json.loads(items_json)
    
    # Limpiamos el subtotal de cualquier formato raro antes de sumar
    subtotal = sum([float(str(i['subtotal']).replace('$','').replace('.','').replace(',','')) for i in items])
    total = subtotal * 1.19 if empresa_tipo == "A" else subtotal

    # --- GUARDAR EN DB (CON EL CAMPO EMAIL) ---
    # Nota: Si tu DB se acaba de actualizar, ahora ya acepta la columna 'email'
    try:
        cursor.execute("""
            INSERT INTO cotizaciones (fecha, cliente, nit, total, items, empresa_tipo, email)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (fecha, cliente_info, nit, total, items_json, empresa_tipo, email_destino))
    except Exception as e:
        # Si falla (por si acaso), intentamos guardar sin email para no perder los datos
        print(f"⚠️ Alerta: Guardando sin email por error de DB: {e}")
        cursor.execute("""
            INSERT INTO cotizaciones (fecha, cliente, nit, total, items, empresa_tipo)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (fecha, cliente_info, nit, total, items_json, empresa_tipo))
    
    conn.commit()
    conn.close()

    print(f"✅ Cotización guardada para {cliente_info} (Email: {email_destino})")

    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/eliminar-cotizacion/{id_cot}")
async def eliminar_cotizacion(request: Request, id_cot: int):
    if get_rol(request) != "admin": return RedirectResponse(url="/cotizaciones")
    conn = obtener_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cotizaciones WHERE id = ?", (id_cot,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/cotizaciones", status_code=303)


# ==============================================================================
# 13. IMPRESIÓN PDF (LECTURA DINÁMICA DE CONFIGURACIÓN)
# ==============================================================================

@app.get("/imprimir-cotizacion/{id_cot}", response_class=HTMLResponse)
async def imprimir_cotizacion(request: Request, id_cot: int):
    # Inicializamos la conexión fuera del try para que el finally pueda cerrarla
    conn = obtener_db()
    cursor = conn.cursor()
    
    try:
        # 1. Obtener la cotización
        cot = cursor.execute("SELECT * FROM cotizaciones WHERE id = ?", (id_cot,)).fetchone()
        
        if not cot:
            conn.close()
            return HTMLResponse("<h3>❌ Error: Cotización no encontrada en la base de datos.</h3>", status_code=404)

        # 2. Procesar los Ítems (Compatibilidad total con nombres de variables)
        try:
            items_crudos = json.loads(cot["items"])
        except Exception:
            items_crudos = [] # Evita que el sistema explote si el JSON está mal formado

        items_procesados = []
        for item in items_crudos:
            # Extraer precio/unitario limpiando posibles caracteres no numéricos
            raw_p = item.get('precio') or item.get('unitario') or 0
            if isinstance(raw_p, str):
                # Quitamos $, puntos de mil y comas para que float() no falle
                val_p = raw_p.replace('$', '').replace('.', '').replace(',', '').strip()
            else:
                val_p = raw_p
            
            # Extraer subtotal del ítem
            raw_st = item.get('subtotal') or 0
            if isinstance(raw_st, str):
                val_st = raw_st.replace('$', '').replace('.', '').replace(',', '').strip()
            else:
                val_st = raw_st

            # Construir el objeto limpio para la plantilla
            items_procesados.append({
                "producto": item.get('producto', 'Sin descripción'),
                "precio": float(val_p) if val_p else 0.0,
                "cantidad": int(item.get('cantidad', 1)),
                "subtotal": float(val_st) if val_st else 0.0
            })

        # 3. Configuración de Empresa y Estilos
        # Si no hay tipo de empresa (datos viejos), asumimos 'A' (SAS)
        tipo_e = cot["empresa_tipo"] if ("empresa_tipo" in cot.keys() and cot["empresa_tipo"]) else "A"
        
        empresa_data = cursor.execute("SELECT * FROM empresas_config WHERE id=?", (tipo_e,)).fetchone()
        
        # Diccionario de estilos visuales para Tailwind
        estilos_map = {
            "A": {"color_borde": "border-blue-600", "color_texto": "text-blue-800", "tema": "SAS"},
            "B": {"color_borde": "border-green-600", "color_texto": "text-green-800", "tema": "INDIVIDUAL"}
        }
        estilo = estilos_map.get(tipo_e, estilos_map["A"])

        # 4. Renderizado Final
        return templates.TemplateResponse("imprimir.html", {
            "request": request, 
            "cot": cot, 
            "items": items_procesados, 
            "empresa": empresa_data,
            "estilo": estilo
        })

    except Exception as e:
        # Log del error en la terminal para que sepas qué pasó exactamente
        print(f"DEBUG ERROR: {str(e)}")
        return HTMLResponse(f"<h3>⚠️ Error Crítico en el Servidor</h3><p>{str(e)}</p>", status_code=500)
    
    finally:
        # Garantizamos que la conexión siempre se cierre, pase lo que pase
        if conn:
            conn.close()

# ==============================================================================
# 14. MÓDULO: INFORMES BI (INTELIGENCIA DE NEGOCIOS)
# ==============================================================================

@app.get("/informes", response_class=HTMLResponse)
async def modulo_informes(request: Request):
    if not request.session.get("usuario"): return RedirectResponse(url="/")
    rol = get_rol(request)
    
    # Seguridad: Solo Admin
    if rol != "admin": return RedirectResponse(url="/dashboard")

    conn = obtener_db()
    cursor = conn.cursor()
    
    # 1. Total Vendido por Empresa
    ventas_sas = cursor.execute("SELECT SUM(total) FROM cotizaciones WHERE empresa_tipo = 'A'").fetchone()[0] or 0
    ventas_simpl = cursor.execute("SELECT SUM(total) FROM cotizaciones WHERE empresa_tipo = 'B'").fetchone()[0] or 0
    
    # 2. Top Clientes
    top_clientes = cursor.execute("""
        SELECT cliente, COUNT(*) as compras, SUM(total) as volumen 
        FROM cotizaciones 
        GROUP BY cliente 
        ORDER BY volumen DESC 
        LIMIT 5
    """).fetchall()
    
    conn.close()
    
    return templates.TemplateResponse("informes.html", {
        "request": request, 
        "rol": rol, 
        "ventas_sas": ventas_sas, 
        "ventas_simpl": ventas_simpl, 
        "top_clientes": top_clientes
    })


# ==============================================================================
# 15. MÓDULO: CONFIGURACIÓN (EDITAR DATOS DE EMPRESA)
# ==============================================================================

@app.get("/configuracion", response_class=HTMLResponse)
async def modulo_configuracion(request: Request):
    # Seguridad: Solo Admin y Logueado
    if not request.session.get("usuario") or get_rol(request) != "admin": 
        return RedirectResponse(url="/dashboard")
    
    conn = obtener_db()
    cursor = conn.cursor()
    
    # Cargar datos actuales para mostrarlos en los inputs
    empresa_a = cursor.execute("SELECT * FROM empresas_config WHERE id='A'").fetchone()
    empresa_b = cursor.execute("SELECT * FROM empresas_config WHERE id='B'").fetchone()
    conn.close()
    
    return templates.TemplateResponse("configuracion.html", {
        "request": request, 
        "rol": "admin", 
        "empresa_a": empresa_a, 
        "empresa_b": empresa_b
    })

@app.post("/guardar-configuracion")
async def guardar_configuracion(
    nombre_a: str = Form(...), nit_a: str = Form(...), dir_a: str = Form(...), 
    tel_a: str = Form(...), email_a: str = Form(...), lema_a: str = Form(...),
    nombre_b: str = Form(...), nit_b: str = Form(...), dir_b: str = Form(...), 
    tel_b: str = Form(...), email_b: str = Form(...), lema_b: str = Form(...)
):
    conn = obtener_db(); cursor = conn.cursor()
    
    # Actualizar A
    cursor.execute("""
        UPDATE empresas_config 
        SET nombre=?, nit=?, direccion=?, telefono=?, email=?, lema=? 
        WHERE id='A'
    """, (nombre_a, nit_a, dir_a, tel_a, email_a, lema_a))
    
    # Actualizar B
    cursor.execute("""
        UPDATE empresas_config 
        SET nombre=?, nit=?, direccion=?, telefono=?, email=?, lema=? 
        WHERE id='B'
    """, (nombre_b, nit_b, dir_b, tel_b, email_b, lema_b))
    
    conn.commit()
    conn.close()
    
    print("✅ Configuración actualizada.")
    # Este return pertenece a guardar_configuracion
    return RedirectResponse(url="/dashboard", status_code=303)


# --- (NUEVO) CAMBIO DE CONTRASEÑA ---
@app.post("/cambiar-clave")
async def cambiar_clave(request: Request, usuario_objetivo: str = Form(...), nueva_clave: str = Form(...)):
    # Solo Admin puede cambiar claves
    if get_rol(request) != "admin": 
        return RedirectResponse(url="/dashboard")
    
    conn = obtener_db(); cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET password = ? WHERE username = ?", (nueva_clave, usuario_objetivo))
    conn.commit(); conn.close()
    
    print(f"✅ Contraseña actualizada para: {usuario_objetivo}")
    
    # Este return pertenece a cambiar_clave (te devuelve a config para que veas que no hubo error)
    return RedirectResponse(url="/configuracion", status_code=303)


# ==============================================================================
# 16. MÓDULO: EMAIL RESPONSIVE (MÓVIL PERFECTO) + BOTÓN FUNCIONAL
# ==============================================================================

@app.get("/enviar-email/{id}")
async def enviar_email_automatico(id: int):
    conn = obtener_db()
    cursor = conn.cursor()

    # 1. Buscar datos
    cot = cursor.execute("SELECT * FROM cotizaciones WHERE id = ?", (id,)).fetchone()
    conn.close()

    if not cot:
        return "❌ Error: Cotización no encontrada."

    destinatario = cot['email'] 
    if not destinatario:
        return f"⚠️ Error: El cliente {cot['cliente']} no tiene email."

    # 2. Generar filas
    items = json.loads(cot['items'])
    filas_html = ""
    
    # Colores alternados suaves
    color_par = "#ffffff"
    color_impar = "#f8fafc"

    for i, item in enumerate(items):
        precio_fmt = "{:,.0f}".format(float(item['precio']))
        subtotal_fmt = "{:,.0f}".format(float(item['subtotal']))
        
        bg_color = color_par if i % 2 == 0 else color_impar
        
        filas_html += f"""
        <tr style="background-color: {bg_color}; border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 10px 8px; font-size: 13px; color: #334155; line-height: 1.4;">
                <span style="font-weight: 600; display: block; color: #1e293b;">{item['producto']}</span>
            </td>
            <td style="padding: 10px 4px; text-align: center; font-size: 13px; color: #64748b;">{item['cantidad']}</td>
            <td style="padding: 10px 8px; text-align: right; font-size: 13px; color: #64748b; white-space: nowrap;">$ {precio_fmt}</td>
            <td style="padding: 10px 8px; text-align: right; font-size: 13px; font-weight: bold; color: #0f172a; white-space: nowrap;">$ {subtotal_fmt}</td>
        </tr>
        """

    total_fmt = "{:,.0f}".format(cot['total'])
    fecha_fmt = cot['fecha']

    # 3. Diseño Responsive (CSS optimizado para Gmail móvil)
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            /* Reset y base */
            body {{ margin: 0; padding: 0; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f1f5f9; }}
            table {{ border-spacing: 0; border-collapse: collapse; }}
            
            /* Contenedor Principal */
            .wrapper {{ width: 100%; table-layout: fixed; background-color: #f1f5f9; padding-bottom: 40px; }}
            .webkit {{ max-width: 600px; background-color: #ffffff; margin: 0 auto; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
            
            /* Header */
            .header {{ background-color: #0f172a; padding: 30px 20px; text-align: center; }}
            .header img {{ max-width: 160px; height: auto; display: block; margin: 0 auto; }}
            
            /* Contenido */
            .content {{ padding: 25px 20px; }}
            .title {{ font-size: 20px; font-weight: 800; color: #0f172a; margin: 0 0 10px 0; }}
            .text {{ font-size: 14px; color: #475569; line-height: 1.6; margin: 0 0 20px 0; }}
            
            /* Info Box */
            .info-box {{ background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 25px; font-size: 13px; color: #334155; }}
            
            /* Tabla Responsive */
            .table-container {{ width: 100%; overflow-x: auto; }}
            .data-table {{ width: 100%; max-width: 100%; }}
            .data-table th {{ background-color: #334155; color: #ffffff; padding: 10px 8px; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; text-align: right; }}
            .data-table th:first-child {{ text-align: left; border-radius: 6px 0 0 0; }}
            .data-table th:last-child {{ border-radius: 0 6px 0 0; }}
            
            /* Total */
            .total-area {{ background-color: #0f172a; color: white; padding: 20px; margin-top: 20px; border-radius: 8px; text-align: right; }}
            .total-label {{ font-size: 12px; text-transform: uppercase; opacity: 0.8; }}
            .total-value {{ font-size: 24px; font-weight: bold; margin-top: 5px; }}
            
            /* Botón Funcional */
            .btn-container {{ text-align: center; margin-top: 30px; }}
            .btn {{ background-color: #2563eb; color: #ffffff !important; padding: 14px 28px; border-radius: 50px; text-decoration: none; font-weight: bold; font-size: 14px; display: inline-block; box-shadow: 0 4px 6px rgba(37, 99, 235, 0.3); }}
            
            /* Footer */
            .footer {{ background-color: #f1f5f9; padding: 20px; text-align: center; color: #94a3b8; font-size: 11px; }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="webkit">
                <div class="header">
                    <img src="cid:logo_empresa" alt="Metaverso ERP">
                </div>

                <div class="content">
                    <h1 class="title">Hola, {cot['cliente']}</h1>
                    <p class="text">Adjuntamos el detalle de su cotización solicitada. Los precios incluyen impuestos aplicables según el régimen.</p>

                    <div class="info-box">
                        <strong>N° Cotización:</strong> {id}<br>
                        <strong>Fecha Emisión:</strong> {fecha_fmt}
                    </div>

                    <table class="data-table">
                        <thead>
                            <tr>
                                <th style="text-align: left;">Descripción</th>
                                <th style="text-align: center;">Cant.</th>
                                <th>Unit.</th>
                                <th>Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filas_html}
                        </tbody>
                    </table>

                    <div class="total-area">
                        <div class="total-label">Total a Pagar</div>
                        <div class="total-value">$ {total_fmt} COP</div>
                    </div>

                    <div class="btn-container">
                        <a href="mailto:{EMAIL_EMPRESA}?subject=Consulta sobre Cotización #{id}&body=Hola, quisiera aprobar esta cotización o tengo una duda..." class="btn">
                            📩 Responder / Aprobar
                        </a>
                    </div>
                </div>

                <div class="footer">
                    Generado por Metaverso ERP 4.0<br>
                    Barranquilla, Colombia
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    # 4. Configuración Técnica
    msg = MIMEMultipart("related")
    msg['From'] = EMAIL_EMPRESA
    msg['To'] = destinatario
    msg['Subject'] = f"Cotización #{id} | {cot['cliente']}"

    # Adjuntar HTML
    msg.attach(MIMEText(html_content, "html"))

    # Adjuntar Logo
    try:
        with open("static/logo_sas.png", "rb") as f:
            img_data = f.read()
        img = MIMEImage(img_data)
        img.add_header('Content-ID', '<logo_empresa>')
        img.add_header('Content-Disposition', 'inline', filename="logo_sas.png")
        msg.attach(img)
    except:
        pass # Si falla el logo, se envía sin él

    # 5. Enviar
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_EMPRESA, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ Correo Responsive enviado a: {destinatario}")
        # AQUI ESTA EL CAMBIO: Agregamos "?mensaje=enviado" a la URL
        return RedirectResponse(url="/dashboard?mensaje=enviado", status_code=303)
    except Exception as e:
        print(f"❌ Error: {e}")
        return f"Error: {e}"
    # ==============================================================================
# 14. MÓDULO: ADMINISTRACIÓN (ELIMINAR Y RESETEAR CONSECUTIVO)
# ==============================================================================

# A. ELIMINAR UNA COTIZACIÓN
@app.get("/eliminar-cotizacion/{id}")
async def eliminar_cotizacion(id: int):
    conn = obtener_db()
    cursor = conn.cursor()
    
    # Borramos la cotización
    cursor.execute("DELETE FROM cotizaciones WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    print(f"🗑️ Cotización #{id} eliminada.")
    # Volvemos al dashboard avisando que se borró
    return RedirectResponse(url="/cotizaciones?mensaje=eliminado", status_code=303)


# B. RESETEAR SISTEMA (BORRA TODO Y INICIA EN 10001)
# ¡CUIDADO! Esto borra todas las cotizaciones y pone el contador en 10000.
@app.get("/resetear-consecutivo")
async def resetear_consecutivo():
    conn = obtener_db()
    cursor = conn.cursor()
    
    # 1. Borrar todas las cotizaciones existentes (Limpieza)
    cursor.execute("DELETE FROM cotizaciones")
    
    # 2. Reiniciar el contador interno de SQLite
    # Primero verificamos si existe la tabla de secuencia
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='cotizaciones'")
    
    # 3. Insertar el inicio en 10000 (para que la siguiente sea 10001)
    cursor.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('cotizaciones', 10000)")
    
    conn.commit()
    conn.close()
    
    print("⚠️ SISTEMA RESETEADO: El contador iniciará en 10,001")
    return RedirectResponse(url="/cotizaciones?mensaje=reseteado", status_code=303)