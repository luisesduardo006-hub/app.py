import sqlite3
import os
import random
import string
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, request, redirect, session

app = Flask(__name__)
app.secret_key = 'solucion_error_500_corte_2026'

# --- MOTOR DE DATOS CORE ---
def query_db(db, query, params=(), fetch=False):
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch: return cursor.fetchall()
            conn.commit()
    except Exception as e:
        print(f"Error Crítico en {db}: {e}")
        return None # Cambiado a None para detectar errores de conexión

def init_db():
    query_db('master.db', '''CREATE TABLE IF NOT EXISTS usuarios 
               (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, creado_por TEXT, estado TEXT, vencimiento TEXT)''')
    query_db('master.db', "INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?,?,?)",
                ("ADMIN-01", "CONTROL CENTRAL", "Administrador", "SISTEMA", "Activo", "2099-12-31 23:59:59"))

def db_negocio(u):
    db = f"negocio_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"negocio_{u['clave']}.db"
    query_db(db, 'CREATE TABLE IF NOT EXISTS productos (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, stock REAL, unidad TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, fecha TEXT, vendedor TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha TEXT)')
    query_db(db, 'CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, empresa TEXT, whatsapp TEXT)')
    
    # Verificación de Configuración Inicial (Previene Error 500 en CFG)
    check_conf = query_db(db, "SELECT * FROM config WHERE id=1", fetch=True)
    if not check_conf:
        query_db(db, "INSERT INTO config (id, empresa, whatsapp) VALUES (1, 'Mi Negocio', '52')")
    return db

# --- ESTILO VISUAL ---
CSS = '''
<style>
    :root { --p: #6366f1; --s: #a855f7; --bg: #0f172a; }
    body { background: var(--bg); color: white; font-family: sans-serif; margin: 0; display: flex; justify-content: center; min-height: 100vh; padding: 20px; }
    .card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 25px; width: 100%; max-width: 400px; height: fit-content; }
    h2 { background: linear-gradient(90deg, #22d3ee, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0 0 20px; }
    input { background: rgba(0,0,0,0.3); border: 1px solid #334155; color: white; padding: 12px; width: 100%; border-radius: 10px; margin-bottom: 10px; box-sizing: border-box; }
    button { background: linear-gradient(135deg, var(--p), var(--s)); color: white; border: none; padding: 14px; width: 100%; border-radius: 10px; font-weight: bold; cursor: pointer; width: 100%; }
    .nav { display: block; text-decoration: none; color: #94a3b8; padding: 12px; border-radius: 10px; margin-bottom: 8px; background: rgba(255,255,255,0.03); text-align: center; }
    .resumen { background: rgba(0,0,0,0.2); padding: 15px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #22d3ee; }
</style>
'''

# --- RUTAS DE CONFIGURACIÓN Y CORTE (CORREGIDAS) ---

@app.route('/cfg', methods=['GET', 'POST'])
def cfg():
    if 'clv' not in session: return redirect('/')
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    
    if request.method == 'POST':
        query_db(db, "UPDATE config SET empresa=?, whatsapp=? WHERE id=1", (request.form['e'], request.form['w']))
        return redirect('/hub')
    
    # Se asegura de obtener los datos actuales para rellenar el formulario
    c = query_db(db, "SELECT * FROM config WHERE id=1", fetch=True)[0]
    return f'''{CSS}<div class="card"><h2>Ajustes</h2>
    <form method="POST">
        <label style="font-size:12px; color:#94a3b8">Nombre del Negocio:</label>
        <input name="e" value="{c['empresa']}" required>
        <label style="font-size:12px; color:#94a3b8">WhatsApp (con código de país):</label>
        <input name="w" value="{c['whatsapp']}" placeholder="Ej: 52123..." required>
        <button>GUARDAR CAMBIOS</button>
    </form>
    <a href="/hub" class="nav">Cancelar</a></div>'''

@app.route('/end')
def end():
    if 'clv' not in session: return redirect('/')
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    if u['rango'] != 'Dueño': return redirect('/hub') # Solo el dueño corta caja
    
    db = db_negocio(u)
    # Sumar todas las ventas del día
    ventas_hoy = query_db(db, "SELECT SUM(total) as total FROM ventas", fetch=True)[0]['total'] or 0
    gastos_hoy = query_db(db, "SELECT SUM(monto) as total FROM gastos", fetch=True)[0]['total'] or 0
    neto = ventas_hoy - gastos_hoy
    
    return f'''{CSS}<div class="card"><h2>Corte de Caja</h2>
    <div class="resumen">
        <p>💰 Ventas Totales: <b>${ventas_hoy}</b></p>
        <p>💸 Gastos Totales: <b>${gastos_hoy}</b></p>
        <hr style="opacity:0.1">
        <p style="font-size:18px">💵 Saldo Neto: <b>${neto}</b></p>
    </div>
    <form action="/confirm_corte" method="POST">
        <p style="font-size:11px; color:#f43f5e">⚠️ Esto borrará el historial de hoy para iniciar mañana en ceros.</p>
        <button style="background:#f43f5e">LIMPIAR CAJA Y CERRAR</button>
    </form>
    <a href="/hub" class="nav">Volver</a></div>'''

@app.route('/confirm_corte', methods=['POST'])
def confirm_corte():
    if 'clv' not in session: return redirect('/')
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    # Limpia las tablas para el nuevo día
    query_db(db, "DELETE FROM ventas")
    query_db(db, "DELETE FROM gastos")
    return redirect('/hub')

# --- RE-INCLUYO EL LOGIN PARA QUE EL CÓDIGO ESTÉ COMPLETO ---
@app.route('/')
def login():
    session.clear()
    return f'{CSS}<div class="card"><h2>Acceso</h2><form action="/auth" method="POST"><input name="c" placeholder="Clave de Acceso" required><button>ENTRAR</button></form></div>'

@app.route('/auth', methods=['POST'])
def auth():
    res = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (request.form['c'],), True)
    if not res: return redirect('/')
    u = res[0]
    session['clv'] = u['clave']
    return redirect('/hub')

@app.route('/hub')
def hub():
    if 'clv' not in session: return redirect('/')
    u = query_db('master.db', "SELECT * FROM usuarios WHERE clave=?", (session['clv'],), True)[0]
    db = db_negocio(u)
    conf = query_db(db, "SELECT * FROM config WHERE id=1", fetch=True)[0]
    html = f'{CSS}<div class="card"><h2>{conf["empresa"]}</h2>'
    if u['rango'] == 'Administrador': html += '<a href="/admin" class="nav">💎 Clientes</a>'
    else:
        html += '<a href="/pos" class="nav">🛒 Caja</a>'
        html += '<a href="/stk" class="nav">📦 Inventario</a>'
        if u['rango'] == 'Dueño':
            html += '<a href="/cfg" class="nav">⚙️ Configuración</a>'
            html += '<a href="/end" class="nav" style="color:#22d3ee">🏁 Corte de Caja</a>'
    html += '<a href="/" style="color:#f43f5e; text-decoration:none; font-size:12px; display:block; text-align:center; margin-top:10px">Salir</a></div>'
    return html

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=10000)
    
