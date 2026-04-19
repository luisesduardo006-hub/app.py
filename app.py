import sqlite3
import os
import random
import urllib.parse
import pandas as pd
from io import BytesIO
from datetime import datetime
from flask import Flask, request, redirect, session, send_file

app = Flask(__name__)
app.secret_key = 'SISTEMA_V11_EXCEL_REPORTS'

# --- MOTOR DE DATOS ---
def query_db(query, params=(), fetch=False):
    try:
        with sqlite3.connect('sistema_v9.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch: return cursor.fetchall()
            conn.commit()
    except Exception as e:
        return []

def init_db():
    query_db('CREATE TABLE IF NOT EXISTS usuarios (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, jefe TEXT)')
    query_db('CREATE TABLE IF NOT EXISTS productos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, precio REAL, stock REAL, unidad TEXT, dueño TEXT)')
    query_db('CREATE TABLE IF NOT EXISTS ventas (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, fecha TEXT, detalle TEXT, vendedor TEXT, dueño TEXT)')
    query_db('CREATE TABLE IF NOT EXISTS config (dueño TEXT PRIMARY KEY, empresa TEXT, whatsapp TEXT)')
    query_db('CREATE TABLE IF NOT EXISTS pagos (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha TEXT, responsable TEXT, dueño TEXT)')

CSS = '''
<style>
    :root { --p: #00d2ff; --bg: #0f172a; --card: #1e293b; }
    body { background: var(--bg); color: white; font-family: sans-serif; margin: 0; padding: 15px; display: flex; flex-direction: column; align-items: center; }
    .card { background: var(--card); border-radius: 15px; padding: 20px; width: 100%; max-width: 500px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); margin-bottom: 20px; border: 1px solid #2d3545; }
    h2 { color: var(--p); text-align:center; margin-bottom: 15px; }
    h3 { font-size: 16px; border-left: 4px solid var(--p); padding-left: 10px; margin-top: 20px; color: #94a3b8; }
    input, select { background: #0f172a; border: 1px solid #334155; color: white; padding: 12px; width: 100%; border-radius: 8px; margin-bottom: 10px; box-sizing: border-box; }
    button { background: linear-gradient(to right, #00d2ff, #3a7bd5); color: white; border: none; padding: 15px; width: 100%; border-radius: 8px; font-weight: bold; cursor: pointer; }
    table { width: 100%; border-collapse: collapse; margin-top: 5px; font-size: 11px; }
    th { text-align: left; color: #64748b; border-bottom: 1px solid #334155; padding: 5px; }
    td { padding: 8px 5px; border-bottom: 1px solid #1e293b; }
    .btn-nav { text-decoration: none; color: #94a3b8; display: block; text-align: center; padding: 10px; margin-top: 10px; background: #0f172a; border-radius: 8px; border: 1px solid #334155; font-size: 14px; }
    .btn-excel { background: #1d6f42; color: white; border: none; padding: 12px; width: 100%; border-radius: 8px; font-weight: bold; cursor: pointer; text-decoration:none; display:block; text-align:center; margin-top:10px; }
    .total-box { background: #0f172a; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 15px; border: 1px solid var(--p); }
</style>
'''

@app.route('/')
def login():
    session.clear()
    return f'{CSS}<div class="card"><h2>Acceso</h2><form action="/auth" method="POST"><input name="c" placeholder="Clave" required><button>ENTRAR</button></form></div>'

@app.route('/auth', methods=['POST'])
def auth():
    res = query_db("SELECT * FROM usuarios WHERE clave=?", (request.form['c'],), True)
    if res:
        session['clv'], session['user'], session['rango'] = res[0]['clave'], res[0]['nombre'], res[0]['rango']
        session['dueño'] = res[0]['jefe'] if res[0]['rango'] == 'Trabajador' else res[0]['clave']
        return redirect('/hub')
    return redirect('/')

@app.route('/hub')
def hub():
    if 'clv' not in session: return redirect('/')
    r = session['rango']
    c = query_db("SELECT empresa FROM config WHERE dueño=?", (session['dueño'],), True)
    empresa = c[0]['empresa'] if c else "SISTEMA"
    html = f'{CSS}<div class="card"><h2>{empresa}</h2>'
    html += '<a href="/pos" class="btn-nav" style="background:var(--p); color:black">🛒 VENTAS</a>'
    html += '<a href="/proveedores" class="btn-nav">🚚 PAGOS PROVEEDORES</a>'
    html += '<a href="/inventario" class="btn-nav">📦 PRODUCTOS</a>'
    if r == 'Dueño':
        html += '<a href="/gestion_personal" class="btn-nav">👥 PERSONAL</a>'
        html += '<a href="/corte" class="btn-nav">📊 CORTE DE CAJA</a>'
    html += '<a href="/" class="btn-nav" style="color:#f43f5e; margin-top:20px">Salir</a></div>'
    return html

# --- GENERACIÓN DE EXCEL ---
@app.route('/descargar_excel')
def descargar_excel():
    if session.get('rango') != 'Dueño': return redirect('/hub')
    
    # Obtener datos
    v_rows = query_db("SELECT fecha, detalle, vendedor, total FROM ventas WHERE dueño=?", (session['dueño'],), True)
    p_rows = query_db("SELECT fecha, concepto, responsable, monto FROM pagos WHERE dueño=?", (session['dueño'],), True)
    
    # Crear DataFrames
    df_ventas = pd.DataFrame([dict(r) for r in v_rows])
    df_pagos = pd.DataFrame([dict(r) for r in p_rows])
    
    # Guardar en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_ventas.to_excel(writer, index=False, sheet_name='Ventas')
        df_pagos.to_excel(writer, index=False, sheet_name='Pagos_Proveedores')
        
    output.seek(0)
    nombre_archivo = f"Corte_{datetime.now().strftime('%d_%m_%Y')}.xlsx"
    return send_file(output, as_attachment=True, download_name=nombre_archivo, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- CORTE DE CAJA ---
@app.route('/corte')
def corte():
    if session.get('rango') != 'Dueño': return redirect('/hub')
    v_l = query_db("SELECT * FROM ventas WHERE dueño=? ORDER BY id DESC", (session['dueño'],), True)
    p_l = query_db("SELECT * FROM pagos WHERE dueño=? ORDER BY id DESC", (session['dueño'],), True)
    t_v = sum(v['total'] for v in v_l); t_p = sum(p['monto'] for p in p_l); neto = t_v - t_p
    
    return f'''{CSS}<div class="card">
        <h2>Corte de Caja</h2>
        <div class="total-box">
            <h1 style="color:var(--p)">${neto}</h1>
            <p>Ventas: ${t_v} | Pagos: -${t_p}</p>
        </div>
        
        <a href="/descargar_excel" class="btn-excel">📊 DESCARGAR REPORTE EXCEL</a>
        
        <h3>📝 Ventas</h3>
        <table>{"".join([f"<tr><td>{v['fecha']}</td><td>{v['detalle']}</td><td>${v['total']}</td></tr>" for v in v_l])}</table>
        
        <h3>🚚 Pagos</h3>
        <table>{"".join([f"<tr><td>{p['fecha']}</td><td>{p['concepto']}</td><td>-${p['monto']}</td></tr>" for p in p_l])}</table>
        
        <form action="/reset" method="POST" onsubmit="return confirm('¿Limpiar caja?')">
            <button style="background:#f43f5e; margin-top:20px; width:100%">REINICIAR DÍA</button>
        </form>
        <a href="/hub" class="btn-nav">Volver</a></div>'''

# --- EL RESTO DEL CÓDIGO (POS, PAGOS, etc.) SE MANTIENE ---
@app.route('/proveedores')
def proveedores():
    pagos = query_db("SELECT * FROM pagos WHERE dueño=? ORDER BY id DESC", (session['dueño'],), True)
    filas = "".join([f"<tr><td>{p['concepto']}</td><td>-${p['monto']}</td><td>{p['responsable']}</td></tr>" for p in pagos])
    return f'''{CSS}<div class="card"><h2>Proveedores</h2>
        <form action="/add_pago" method="POST"><input name="con" placeholder="Concepto" required><input name="mon" type="number" step="0.01" placeholder="Monto" required><button style="background:#f59e0b">PAGAR</button></form>
        <table>{filas}</table><a href="/hub" class="btn-nav">Volver</a></div>'''

@app.route('/add_pago', methods=['POST'])
def add_pago():
    query_db("INSERT INTO pagos (concepto, monto, fecha, responsable, dueño) VALUES (?,?,?,?,?)", (request.form['con'], request.form['mon'], datetime.now().strftime("%H:%M"), session['user'], session['dueño']))
    return redirect('/proveedores')

@app.route('/pos')
def pos():
    prods = query_db("SELECT * FROM productos WHERE dueño=?", (session['dueño'],), True)
    carro = session.get('carro', [])
    total = sum(i['s'] for i in carro)
    l_bus = "".join([f'<div style="padding:8px; border-bottom:1px solid #1e293b; cursor:pointer" onclick="document.getElementById(\'pid\').value=\'{p["id"]}\'; document.getElementById(\'q\').value=\'{p["nombre"]}\'">{p["nombre"]} (${p["precio"]})</div>' for p in prods])
    return f'''{CSS}<div class="card"><h2>Caja</h2>
        <table>{"".join([f"<tr><td>{i['n']}</td><td>${i['s']}</td></tr>" for i in carro])}</table><h3>Total: ${total}</h3>
        <form action="/pagar" method="POST"><input name="tel" placeholder="WhatsApp" required><button style="background:#22c55e">COBRAR</button></form>
        <div style="margin-top:15px; border-top:1px dashed #334155; padding-top:10px">
            <input id="q" onkeyup="this.nextElementSibling.style.display='block'" placeholder="Buscar...">
            <div style="display:none; background:#0f172a">{l_bus}</div>
            <form action="/add_carro" method="POST">
                <input type="hidden" name="id" id="pid" required><input name="val" type="number" step="0.01" placeholder="Monto/Cant" required>
                <button style="background:none; border:1px solid var(--p); color:var(--p)">+ AÑADIR</button>
            </form>
        </div><a href="/hub" class="btn-nav">Volver</a></div>'''

@app.route('/add_carro', methods=['POST'])
def add_carro():
    p = query_db("SELECT * FROM productos WHERE id=?", (request.form['id'],), True)[0]
    val = float(request.form['val'])
    sub = val if p['unidad'] == 'Kg' else round(val * p['precio'], 2)
    carro = session.get('carro', []); carro.append({'id': p['id'], 'n': p['nombre'], 'c': val/p['precio'] if p['unidad']=='Kg' else val, 's': sub})
    session['carro'] = carro
    return redirect('/pos')

@app.route('/pagar', methods=['POST'])
def pagar():
    carro = session.get('carro', [])
    if not carro: return redirect('/pos')
    total = sum(i['s'] for i in carro)
    for i in carro:
        query_db("UPDATE productos SET stock = CASE WHEN stock IS NOT NULL THEN stock - ? ELSE NULL END WHERE id = ?", (i['c'], i['id']))
        query_db("INSERT INTO ventas (total, fecha, detalle, vendedor, dueño) VALUES (?,?,?,?,?)", (i['s'], datetime.now().strftime("%H:%M"), i['n'], session['user'], session['dueño']))
    session['carro'] = []
    return redirect(f"https://api.whatsapp.com/send?phone={request.form['tel']}&text=Ticket:${total}")

@app.route('/reset', methods=['POST'])
def reset():
    query_db("DELETE FROM ventas WHERE dueño=?", (session['dueño'],))
    query_db("DELETE FROM pagos WHERE dueño=?", (session['dueño'],))
    return redirect('/corte')

@app.route('/inventario')
def inventario():
    ps = query_db("SELECT * FROM productos WHERE dueño=?", (session['dueño'],), True)
    filas = "".join([f"<tr><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock'] if p['stock'] is not None else '∞'}</td></tr>" for p in ps])
    form = f'''<hr><form action="/save_prod" method="POST">
            <input name="n" placeholder="Nombre" required><input name="p" step="0.01" type="number" placeholder="Precio" required>
            <input name="s" step="0.01" type="number" placeholder="Stock"><select name="u"><option value="Pza">Pza</option><option value="Kg">Kg</option></select>
            <button>Guardar</button></form>''' if session['rango'] == 'Dueño' else ""
    return f'{CSS}<div class="card"><h2>Productos</h2><table>{filas}</table>{form}<a href="/hub" class="btn-nav">Volver</a></div>'

@app.route('/save_prod', methods=['POST'])
def save_prod():
    stock = request.form['s'] if request.form['s'] != "" else None
    query_db("INSERT INTO productos (nombre, precio, stock, unidad, dueño) VALUES (?,?,?,?,?)", (request.form['n'], request.form['p'], stock, request.form['u'], session['dueño']))
    return redirect('/inventario')

@app.route('/gestion_personal')
def gestion_personal():
    buscado = 'Dueño' if session['rango'] == 'Administrador' else 'Trabajador'
    lista = query_db("SELECT * FROM usuarios WHERE rango=? AND jefe=?", (buscado, session['clv']), True)
    filas = "".join([f"<tr><td>{u['nombre']}</td><td><code>{u['clave']}</code></td></tr>" for u in lista])
    return f'{CSS}<div class="card"><h2>Personal</h2><table>{filas}</table><hr><form action="/crear_usuario" method="POST"><input name="n" placeholder="Nombre" required><button>CREAR</button></form><a href="/hub" class="btn-nav">Volver</a></div>'

@app.route('/crear_usuario', methods=['POST'])
def crear_usuario():
    nueva_clv = f"{'DU' if session['rango'] == 'Administrador' else 'TR'}-{random.randint(1000, 9999)}"
    query_db("INSERT INTO usuarios VALUES (?,?,?,?)", (nueva_clv, request.form['n'], 'Dueño' if session['rango'] == 'Administrador' else 'Trabajador', session['clv']))
    if session['rango'] == 'Administrador': query_db("INSERT OR IGNORE INTO config VALUES (?,?,?)", (nueva_clv, request.form['n'], '52'))
    return redirect('/gestion_personal')

if __name__ == "__main__":
    init_db()
    app.run(host='0.0.0.0', port=10000)
