import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from datetime import datetime
import io

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def get_db_connection():
    # Usamos una ruta absoluta para evitar problemas en Render
    db_path = os.path.join(os.path.dirname(__file__), 'punto_venta_v4.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Tabla de usuarios (Dueños, Admin, Trabajadores)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            clave TEXT UNIQUE NOT NULL,
            rol TEXT NOT NULL,
            dueño_id INTEGER,
            negocio_nombre TEXT,
            whatsapp_reporte TEXT
        )
    ''')
    # Tabla de productos (Separados por dueño)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            stock INTEGER DEFAULT 0,
            dueño_id INTEGER,
            FOREIGN KEY(dueño_id) REFERENCES usuarios(id)
        )
    ''')
    # Tabla de ventas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            total REAL NOT NULL,
            dueño_id INTEGER,
            trabajador_id INTEGER,
            FOREIGN KEY(dueño_id) REFERENCES usuarios(id)
        )
    ''')
    conn.commit()
    conn.close()

# --- RUTAS DE SESIÓN ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    clave = request.form['clave']
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM usuarios WHERE clave = ?', (clave,)).fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user['id']
        session['nombre'] = user['nombre']
        session['rol'] = user['rol']
        session['dueño_id'] = user['dueño_id'] if user['rol'] == 'trabajador' else user['id']
        return redirect(url_for('dashboard'))
    return "Clave incorrecta", 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- DASHBOARD Y EXPORTACIÓN ---
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html', rol=session['rol'], nombre=session['nombre'])

@app.route('/exportar_corte')
def exportar_corte():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    # Solo el dueño o admin ven sus ventas
    dueño_actual = session['dueño_id']
    
    conn = get_db_connection()
    query = 'SELECT fecha, total FROM ventas WHERE dueño_id = ?'
    df = pd.read_sql_query(query, conn, params=(dueño_actual,))
    conn.close()

    if df.empty:
        return "No hay ventas registradas para este periodo."

    # Crear el Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Corte de Caja')
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'corte_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    )

# --- INICIO DEL SERVIDOR (AJUSTADO PARA RENDER) ---
if __name__ == "__main__":
    init_db()
    # Render usa la variable de entorno PORT, si no existe usa el 10000
    port = int(os.environ.get("PORT", 10000))
    # Importante: host '0.0.0.0' para que sea accesible externamente
    app.run(host='0.0.0.0', port=port)
    
