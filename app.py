import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, send_file
from datetime import datetime
import io

app = Flask(__name__)
app.secret_key = 'token_seguro_mx_2026'

# --- MANEJO AUTOMÁTICO DE BASE DE DATOS ---
def get_db_connection():
    # Render usa un sistema de archivos efímero, esta ruta asegura que se cree en la raíz
    db_path = os.path.join(os.path.dirname(__file__), 'punto_venta_v4.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crea la base de datos, las tablas y el usuario inicial si no existen"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabla de Usuarios
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
    
    # Tabla de Ventas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            total REAL NOT NULL,
            dueño_id INTEGER,
            trabajador_id INTEGER
        )
    ''')
    
    # INSERTAR USUARIO MAESTRO (Si la tabla está vacía)
    # Nombre: Administrador | Clave: 2026
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (id, nombre, clave, rol) 
        VALUES (1, 'Administrador', '2026', 'admin')
    ''')
    
    conn.commit()
    conn.close()

# --- RUTA DE SALUD (PARA QUE RENDER NO DE ERROR) ---
@app.route('/health')
def health():
    return "Servidor funcionando", 200

# --- LÓGICA DE NAVEGACIÓN ---
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    clave = request.form.get('clave')
    if not clave:
        return "Introduce una clave", 400
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM usuarios WHERE clave = ?', (clave,)).fetchone()
    conn.close()
    
    if user:
        session.clear()
        session['user_id'] = user['id']
        session['nombre'] = user['nombre']
        session['rol'] = user['rol']
        session['dueño_id'] = user['dueño_id'] if user['rol'] == 'trabajador' else user['id']
        return redirect(url_for('dashboard'))
    return "Clave incorrecta", 401

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html', rol=session['rol'], nombre=session['nombre'])

# --- GENERACIÓN DE EXCEL ---
@app.route('/exportar_corte')
def exportar_corte():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    dueño_actual = session['dueño_id']
    conn = get_db_connection()
    
    # Leemos las ventas de la base de datos que se creó automáticamente
    df = pd.read_sql_query('SELECT fecha, total FROM ventas WHERE dueño_id = ?', conn, params=(dueño_actual,))
    conn.close()

    if df.empty:
        return "No hay ventas registradas para este usuario aún.", 404

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Corte de Caja')
    
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'corte_{datetime.now().strftime("%d-%m-%Y")}.xlsx'
    )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- ARRANQUE DEL SISTEMA ---
if __name__ == "__main__":
    # 1. Crear base de datos y usuario al encender
    init_db()
    # 2. Configurar puerto para Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
    
