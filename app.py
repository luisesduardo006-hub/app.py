import sqlite3
from datetime import datetime, timedelta
import urllib.parse
import random
import string
import os
import csv
import io
from flask import Flask, request, render_template_string, redirect, session, send_file

app = Flask(__name__)
app.secret_key = 'sistema_estable_v8_corregido'

# --- CONFIGURACIÓN DE SEGURIDAD ---
def login_requerido():
    return session.get('usuario_clave') is not None

# --- BASES DE DATOS ---

def iniciar_db_usuarios():
    conn = sqlite3.connect('usuarios_sistema.db')
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                     (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, 
                      creado_por TEXT, estado TEXT, vencimiento TEXT, 
                      reactivaciones INTEGER DEFAULT 0)''')
        conn.execute("INSERT OR REPLACE INTO usuarios (clave, nombre, rango, creado_por, estado, vencimiento, reactivaciones) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                     ("ROOT-XYZ7", "SUPER ADMIN", "Super Admin", "SISTEMA", "Activo", "2099-12-31 23:59:59", 0))
    return conn

def iniciar_db_tienda(nombre_db):
    conn = sqlite3.connect(nombre_db)
    conn.row_factory = sqlite3.Row 
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS productos 
                     (codigo TEXT PRIMARY KEY, nombre TEXT, precio REAL, stock REAL, unidad TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS ventas 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL, fecha TEXT, vendedor TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS gastos 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, concepto TEXT, monto REAL, fecha TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS configuracion 
                     (id INTEGER PRIMARY KEY, nombre_negocio TEXT, telefono_dueno TEXT, hora_corte TEXT DEFAULT '21:00')''')
        
        if conn.execute("SELECT COUNT(*) FROM configuracion").fetchone()[0] == 0:
            conn.execute("INSERT INTO configuracion (id, nombre_negocio, telefono_dueno) VALUES (1, 'MI TIENDA', '')")
    return conn

# --- UTILIDADES ---

def tiempo_restante(fecha_vence_str):
    try:
        vence = datetime.strptime(fecha_vence_str, "%Y-%m-%d %H:%M:%S")
        ahora = datetime.now()
        dif = vence - ahora
        if dif.total_seconds() <= 0: return "❌ VENCIDO"
        return f"⏳ {dif.days}d {dif.seconds // 3600}h"
    except: return "S/N"

CSS = '''
<style>
    body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 20px; font-size: 14px; }
    .menu-box { border: 2px solid #0f0; padding: 20px; max-width: 800px; margin: auto; box-shadow: 0 0 15px #0f0; border-radius: 5px; }
    .opcion { display: block; color: #0f0; text-decoration: none; margin: 10px 0; padding: 8px; border-bottom: 1px solid #111; border-radius: 3px; }
    .opcion:hover { background: #0f0; color: #000; font-weight: bold; }
    input, select { background: #111; color: #0f0; border: 1px solid #0f0; padding: 12px; width: 100%; margin: 5px 0; box-sizing: border-box; }
    button { background: #0f0; color: #000; border: none; padding: 15px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 5px; text-transform: uppercase; }
    table { width: 100%; border-collapse: collapse; margin-top: 15px; }
    th, td { border: 1px solid #0f0; padding: 10px; text-align: left; }
    .clv-destaque { color: yellow; font-weight: bold; }
    .btn-rojo { background: #f00; color: #fff; padding: 5px 10px; text-decoration: none; font-size: 0.8em; border-radius: 3px; }
    .btn-pagar { background: #25D366; color: #000; padding: 5px 10px; text-decoration: none; font-weight: bold; font-size: 0.8em; border-radius: 3px; }
    .btn-volver { border: 1px solid #0f0; color: #0f0; padding: 12px; display: block; text-align: center; text-decoration: none; margin-top: 15px; }
    .vencido { background: #200; }
</style>
<script>
    function buscarProd() {
        let input = document.getElementById('search').value.toLowerCase();
        let select = document.getElementById('prod_select');
        for (let i = 0; i < select.options.length; i++) {
            let text = select.options[i].text.toLowerCase();
            select.options[i].style.display = text.includes(input) ? '' : 'none';
        }
    }
</script>
'''

# --- RUTAS DE ACCESO ---

@app.route('/')
def login_screen():
    session.clear()
    return f'''{CSS}<div class="menu-box"><h3>🔑 ACCESO AL SISTEMA</h3>
    <form action="/verificar" method="post"><input type="text" name="clave" placeholder="INGRESE SU CLAVE" autofocus required><button type="submit">ENTRAR AL PANEL</button></form></div>'''

@app.route('/verificar', methods=['GET', 'POST'])
def verificar():
    clave = request.form.get('clave') or session.get('usuario_clave')
    if not clave: return redirect('/')

    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user:
        vence_str = user['vencimiento']
        if user['rango'] == 'Trabajador':
            dueno = db_u.execute("SELECT vencimiento FROM usuarios WHERE clave = ?", (user['creado_por'],)).fetchone()
            vence_str = dueno['vencimiento']
        
        try:
            v_dt = datetime.strptime(vence_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > v_dt or user['estado'] != "Activo":
                return f"{CSS}<div class='menu-box'><h2 style='color:red'>🛑 CUENTA INACTIVA</h2><p>Vencimiento: {vence_str}</p><a href='/' class='btn-volver'>VOLVER AL INICIO</a></div>"
        except: pass

        session['usuario_clave'] = clave
        db_n = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
        db_t = iniciar_db_tienda(db_n)
        conf = db_t.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()

        menu = f"{CSS}<div class='menu-box'><h3>--- {conf['nombre_negocio']} ---</h3><p>👤 {user['nombre']} | 🏷️ {user['rango']}</p><hr>"
        
        if user['rango'] in ['Super Admin', 'Administrador']:
            menu += f'<a class="opcion" href="/gestionar_negocios/{clave}">📊 GESTIONAR PAGOS DUEÑOS</a>'
            if user['rango'] == 'Super Admin':
                menu += f'<a class="opcion" href="/usuarios/{clave}">👥 CONTROL DE ADMINS</a>'
        
        elif user['rango'] in ['Dueño', 'Trabajador']:
            menu += '<a class="opcion" href="/venta">🛒 ABRIR CAJA DE COBRO</a>'
            menu += f'<a class="opcion" href="/inventario/{clave}">📦 CONSULTAR INVENTARIO</a>'
            if user['rango'] == 'Dueño':
                menu += f'<a class="opcion" href="/usuarios/{clave}">👥 GESTIÓN DE EMPLEADOS</a>'
                menu += f'<a class="opcion" href="/config_corte/{clave}">⚙️ CONFIGURACIÓN DE CORTE</a>'
                menu += f'<a class="opcion" href="/hacer_corte_final/{clave}" onclick="return confirm(\'¿Hacer corte?\')">🏁 REALIZAR CORTE FINAL</a>'
        
        menu += '<hr><a class="opcion" href="/" style="color:#f00; border:1px solid #f00; text-align:center;">CERRAR SESIÓN SEGURA</a></div>'
        return menu
    return redirect('/')

@app.route('/gestionar_negocios/<clave>')
def gestionar_negocios(clave):
    if not login_requerido(): return redirect('/')
    db_u = iniciar_db_usuarios()
    duenos = db_u.execute("SELECT * FROM usuarios WHERE rango = 'Dueño' ORDER BY vencimiento ASC").fetchall()
    tabla = "<table><tr><th>DUEÑO</th><th>CLAVE</th><th>STATUS</th><th>ACCIÓN</th></tr>"
    for d in duenos:
        timer = tiempo_restante(d['vencimiento'])
        clase = 'class="vencido"' if "❌" in timer else ''
        tabla += f'<tr {clase}><td>{d["nombre"]}</td><td class="clv-destaque">{d["clave"]}</td><td>{timer}</td><td><a href="/renovar/{clave}/{d["clave"]}" class="btn-pagar">+30D</a> <a href="/status_cascada/{clave}/{d["clave"]}" class="btn-rojo">SW</a></td></tr>'
    return f"{CSS}<div class='menu-box'><h3>🏢 CLIENTES</h3>{tabla}</table><hr><form action='/add_user' method='post'><input type='hidden' name='admin_clave' value='{clave}'><input type='hidden' name='rango' value='Dueño'><input name='nombre' placeholder='Nombre Negocio' required><button type='submit'>REGISTRAR</button></form><a href='/verificar' class='btn-volver'>VOLVER</a></div>"

@app.route('/usuarios/<clave>')
def gestionar_usuarios(clave):
    if not login_requerido(): return redirect('/')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    if user['rango'] == "Super Admin":
        items = db_u.execute("SELECT * FROM usuarios WHERE rango = 'Administrador'").fetchall()
        titulo, r_crear = "ADMINISTRADORES", "Administrador"
    else:
        items = db_u.execute("SELECT * FROM usuarios WHERE creado_por = ?", (clave,)).fetchall()
        titulo, r_crear = "PERSONAL", "Trabajador"

    tabla = "<table><tr><th>NOMBRE</th><th>CLAVE</th><th>ACCIÓN</th></tr>"
    for i in items:
        tabla += f'<tr><td>{i["nombre"]}</td><td class="clv-destaque">{i["clave"]}</td><td><a href="/status_simple/{clave}/{i["clave"]}" class="btn-rojo">ESTADO</a></td></tr>'
    return f"{CSS}<div class='menu-box'><h3>👥 {titulo}</h3>{tabla}</table><hr><form action='/add_user' method='post'><input type='hidden' name='admin_clave' value='{clave}'><input type='hidden' name='rango' value='{r_crear}'><input name='nombre' placeholder='Nombre' required><button type='submit'>AÑADIR</button></form><a href='/verificar' class='btn-volver'>VOLVER</a></div>"

@app.route('/venta')
def vista_venta():
    if not login_requerido(): return redirect('/')
    clv = session.get('usuario_clave')
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clv,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    prods = db.execute("SELECT * FROM productos WHERE stock > 0 ORDER BY nombre ASC").fetchall()
    opcs = "".join([f"<option value='{p['codigo']}'>{p['nombre']} (${p['precio']})</option>" for p in prods])
    car = session.get('carrito', [])
    total = sum(i['s'] for i in car)
    return f'''{CSS}<div class="menu-box"><h3>🛒 CAJA</h3>
    <input type="text" id="search" placeholder="🔍 BUSCAR..." onkeyup="buscarProd()">
    <form action="/add_car" method="post"><select name="cod" id="prod_select" size="5">{opcs}</select><input type="number" step="0.1" name="cnt" placeholder="CANTIDAD"><button>AÑADIR</button></form>
    <h4>TOTAL: ${total}</h4><a href="/cobrar" class="btn-pagar" style="display:block; text-align:center;">💵 FINALIZAR VENTA</a><a href="/verificar" class="btn-volver">VOLVER</a></div>'''

@app.route('/add_car', methods=['POST'])
def add_car():
    clv = session.get('usuario_clave')
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clv,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    p = db.execute("SELECT * FROM productos WHERE codigo=?", (request.form['cod'],)).fetchone()
    if p:
        cnt = float(request.form['cnt'] or 1)
        sub = p['precio']*cnt if p['unidad']=='p' else cnt
        real_cnt = cnt if p['unidad']=='p' else cnt/p['precio']
        car = session.get('carrito', [])
        car.append({'id':p['codigo'], 'n':p['nombre'], 'c':round(real_cnt,2), 's':sub})
        session['carrito'] = car
    return redirect('/venta')

@app.route('/cobrar')
def cobrar():
    clv = session.get('usuario_clave')
    car = session.get('carrito', [])
    if not car: return redirect('/venta')
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clv,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    with db:
        for i in car:
            db.execute("UPDATE productos SET stock=stock-? WHERE codigo=?", (i['c'], i['id']))
            db.execute("INSERT INTO ventas (total, fecha, vendedor) VALUES (?,?,?)", (i['s'], datetime.now().strftime("%H:%M"), u['nombre']))
    session['carrito'] = []
    return redirect('/venta')

@app.route('/add_user', methods=['POST'])
def add_user():
    adm, nom, rango = request.form['admin_clave'], request.form['nombre'], request.form['rango']
    pref = rango[:3].upper()
    clv = f"{pref}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"
    vence = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S") if rango == 'Dueño' else "2099-12-31 23:59:59"
    with iniciar_db_usuarios() as db:
        db.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado, vencimiento) VALUES (?,?,?,?,?,?)", (clv, nom, rango, adm, "Activo", vence))
    return f"{CSS}<div class='menu-box'><h3>✅ CLAVE: {clv}</h3><a href='/verificar' class='btn-volver'>CONTINUAR</a></div>"

@app.route('/status_simple/<admin>/<target>')
def status_simple(admin, target):
    db = iniciar_db_usuarios()
    u = db.execute("SELECT estado FROM usuarios WHERE clave=?", (target,)).fetchone()
    new = "Activo" if u['estado'] == "Suspendido" else "Suspendido"
    with db: db.execute("UPDATE usuarios SET estado=? WHERE clave=?", (new, target))
    return redirect(f"/usuarios/{admin}")

@app.route('/status_cascada/<admin>/<target>')
def status_cascada(admin, target):
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT estado FROM usuarios WHERE clave = ?", (target,)).fetchone()
    nuevo = "Activo" if u['estado'] == "Suspendido" else "Suspendido"
    with db_u:
        db_u.execute("UPDATE usuarios SET estado = ? WHERE clave = ?", (nuevo, target))
        db_u.execute("UPDATE usuarios SET estado = ? WHERE creado_por = ?", (nuevo, target))
    return redirect(f"/gestionar_negocios/{admin}")

@app.route('/renovar/<admin>/<target>')
def renovar(admin, target):
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT vencimiento FROM usuarios WHERE clave = ?", (target,)).fetchone()
    actual = datetime.strptime(u['vencimiento'], "%Y-%m-%d %H:%M:%S")
    inicio = actual if actual > datetime.now() else datetime.now()
    nueva = (inicio + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    with db_u:
        db_u.execute("UPDATE usuarios SET vencimiento = ?, estado = 'Activo' WHERE clave = ?", (nueva, target))
    return redirect(f"/gestionar_negocios/{admin}")

@app.route('/inventario/<clave>')
def inventario(clave):
    if not login_requerido(): return redirect('/')
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    prods = db.execute("SELECT * FROM productos ORDER BY nombre ASC").fetchall()
    tabla = "<table><tr><th>COD</th><th>PRODUCTO</th><th>STOCK</th></tr>" + "".join([f"<tr><td>{p['codigo']}</td><td>{p['nombre']} (${p['precio']})</td><td>{p['stock']} {p['unidad']}</td></tr>" for p in prods]) + "</table>"
    form = f'<hr><form action="/add_p" method="post"><input type="hidden" name="cl" value="{clave}"><input name="co" placeholder="Código"><input name="no" placeholder="Nombre"><input name="pr" placeholder="Precio"><input name="st" placeholder="Stock"><select name="un"><option value="p">Pieza</option><option value="k">Kilo</option></select><button>GUARDAR</button></form>' if u['rango'] == 'Dueño' else ""
    return f"{CSS}<div class='menu-box'><h3>📦 INVENTARIO</h3>{tabla}{form}<a href='/verificar' class='btn-volver'>VOLVER</a></div>"

@app.route('/add_p', methods=['POST'])
def add_p():
    with iniciar_db_tienda(f"tienda_{request.form['cl']}.db") as db:
        db.execute("INSERT OR REPLACE INTO productos VALUES (?,?,?,?,?)", (request.form['co'], request.form['no'], request.form['pr'], request.form['st'], request.form['un']))
    return redirect(f"/inventario/{request.form['cl']}")

if __name__ == "__main__":
    iniciar_db_usuarios()
    app.run(host='0.0.0.0', port=10000)
                
