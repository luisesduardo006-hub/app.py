import sqlite3
from datetime import datetime
import urllib.parse
import random
import string
import csv
import os
# Se añade Flask para que prenda la web
from flask import Flask, request, render_template_string, redirect

app = Flask(__name__)

# --- INICIO Y CONFIGURACIÓN (TU CÓDIGO ORIGINAL) ---
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

def iniciar_db_usuarios(conn):
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                     (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, creado_por TEXT, estado TEXT)''')
        conn.execute("INSERT OR REPLACE INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?, ?, ?, ?, ?)", 
                     ("ADM-K97B", "ADMIN PRINCIPAL", "Administrador", "SISTEMA", "Activo"))

# --- INTERFAZ WEB (PARA REEMPLAZAR EL INPUT DE CONSOLA) ---

@app.route('/')
def login():
    # Esta es la página que pedirá la clave en lugar de la consola
    return '''
        <style>
            body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #121212; color: white; }
            form { border: 1px solid #333; padding: 20px; border-radius: 10px; background: #1e1e1e; }
            input { display: block; margin: 10px 0; padding: 10px; width: 200px; }
            button { width: 100%; padding: 10px; background: #00a8ff; border: none; color: white; cursor: pointer; }
        </style>
        <form action="/verificar" method="post">
            <h2>🔑 Acceso al Sistema</h2>
            <input type="text" name="clave" placeholder="Clave de acceso" required>
            <button type="submit">Entrar</button>
        </form>
    '''

@app.route('/verificar', methods=['POST'])
def verificar():
    clave = request.form['clave']
    db_auth = iniciar_db('usuarios_sistema.db')
    iniciar_db_usuarios(db_auth)
    
    user = db_auth.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user:
        if user['estado'] == "Suspendido":
            return "<h1>🚫 SERVICIO SUSPENDIDO. Contacte al administrador.</h1>"
        
        # Si la clave es correcta, mostramos un mensaje de éxito
        # Aquí podrías redirigir a las otras funciones de tu código
        return f'''
            <h1>✅ ¡Bienvenido, {user['nombre']}!</h1>
            <p>Rango: {user['rango']}</p>
            <p>El sistema está encendido en la web.</p>
            <hr>
            <p><i>Nota: Para usar todas las funciones (Ventas, Stock, etc.) en web, 
            se deben crear las rutas @app.route para cada una.</i></p>
        '''
    else:
        return "<h1>❌ Clave incorrecta.</h1><a href='/'>Volver a intentar</a>"

# --- INICIO DEL SERVIDOR ---
if __name__ == "__main__":
    # Esto asegura que las bases de datos existan al arrancar
    db_auth = iniciar_db('usuarios_sistema.db')
    iniciar_db_usuarios(db_auth)
    
    # Render usa el puerto 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
