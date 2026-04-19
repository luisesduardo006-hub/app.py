import sqlite3
from datetime import datetime
import urllib.parse
import random
import string
import os
from flask import Flask, request, render_template_string, redirect

app = Flask(__name__)

# --- TUS FUNCIONES DE BASE DE DATOS (SIN TOCAR) ---
def iniciar_db(nombre_db='punto_venta_v4.db'):
    conn = sqlite3.connect(nombre_db)
    conn.row_factory = sqlite3.Row 
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS productos 
                     (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, 
                      stock REAL, min_compra REAL, unidad TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS ventas 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, 
                      pago REAL, cambio REAL, fecha TEXT, vendedor TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS gastos 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, 
                      monto REAL, fecha TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS configuracion 
                     (id INTEGER PRIMARY KEY, nombre_negocio TEXT, direccion TEXT, 
                      min_compra REAL, porc_desc REAL, telefono_dueno TEXT)''')
        
        res = conn.execute("SELECT COUNT(*) FROM configuracion").fetchone()
        if res[0] == 0:
            conn.execute("INSERT INTO configuracion (id, nombre_negocio, direccion, min_compra, porc_desc, telefono_dueno) VALUES (1, 'MI TIENDITA PRO', 'Direccion General', 0, 0, '')")
    return conn

def iniciar_db_usuarios():
    conn = sqlite3.connect('usuarios_sistema.db')
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                     (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, creado_por TEXT, estado TEXT)''')
        conn.execute("INSERT OR REPLACE INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?, ?, ?, ?, ?)", 
                     ("ADM-K97B", "ADMIN PRINCIPAL", "Administrador", "SISTEMA", "Activo"))
    return conn

# --- INTERFAZ VISUAL ESTILO CONSOLA ---
CSS = '''
<style>
    body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 20px; }
    .menu-box { border: 2px solid #0f0; padding: 20px; max-width: 600px; margin: auto; }
    .opcion { display: block; color: #0f0; text-decoration: none; margin: 10px 0; font-size: 1.2em; }
    .opcion:hover { background: #0f0; color: #000; }
    input { background: #000; color: #0f0; border: 1px solid #0f0; padding: 5px; width: 100%; margin-top: 10px; }
    button { background: #0f0; color: #000; border: none; padding: 10px 20px; cursor: pointer; margin-top: 10px; width: 100%; }
    hr { border: 0; border-top: 1px dashed #0f0; }
</style>
'''

@app.route('/')
def login_screen():
    return f'''{CSS}
    <div class="menu-box">
        <p>===================================</p>
        <p>🔑 INICIO DE SESIÓN</p>
        <p>===================================</p>
        <form action="/auth" method="post">
            <label>Clave de acceso:</label>
            <input type="text" name="clave" autofocus required>
            <button type="submit">ENTRAR</button>
        </form>
    </div>'''

@app.route('/auth', methods=['POST'])
def auth():
    clave = request.form['clave']
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user:
        if user['estado'] == "Suspendido":
            return f"{CSS}<div class='menu-box'>🚫 SERVICIO SUSPENDIDO. <a href='/' style='color:#0f0'>Volver</a></div>"
        
        # Aquí es donde dividimos por rangos EXACTAMENTE como tu consola
        db_nombre = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
        db = iniciar_db(db_nombre)
        conf = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()

        menu_html = f"{CSS}<div class='menu-box'><h3>--- {conf['nombre_negocio']} ---</h3><p>Usuario: {user['nombre']}</p><hr>"

        if user['rango'] == 'Administrador':
            menu_html += '''
                <a class="opcion" href="/gestion_usuarios">1. GESTIONAR DUEÑOS (TABLA)</a>
                <a class="opcion" href="/">2. SALIR</a>
            '''
        elif user['rango'] == 'Dueño':
            menu_html += f'''
                <a class="opcion" href="/venta">1. REALIZAR VENTA</a>
                <a class="opcion" href="/inventario">2. INVENTARIO (EDITAR/VER)</a>
                <a class="opcion" href="/gestion_usuarios">3. GESTIONAR MIS TRABAJADORES</a>
                <a class="opcion" href="/pago_proveedor">4. PAGAR A PROVEEDOR</a>
                <a class="opcion" href="/config">5. CONFIGURAR NEGOCIO</a>
                <a class="opcion" href="/corte">6. ENVIAR CORTE DE CAJA</a>
                <a class="opcion" href="/">7. SALIR</a>
            '''
        elif user['rango'] == 'Trabajador':
            menu_html += '''
                <a class="opcion" href="/venta">1. REALIZAR VENTA</a>
                <a class="opcion" href="/inventario">2. VER STOCK (SÓLO LECTURA)</a>
                <a class="opcion" href="/pago_proveedor">3. PAGAR A PROVEEDOR</a>
                <a class="opcion" href="/">4. SALIR</a>
            '''
        
        menu_html += "</div>"
        return menu_html
    
    return f"{CSS}<div class='menu-box'>❌ Clave incorrecta. <a href='/' style='color:#0f0'>Reintentar</a></div>"

# --- INICIO DEL SERVIDOR ---
if __name__ == "__main__":
    iniciar_db_usuarios()
    iniciar_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
