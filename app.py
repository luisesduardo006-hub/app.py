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
app.secret_key = 'sistema_pos_omni_v11'

# --- BASES DE DATOS (RESTAURADO) ---
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

# --- ESTILOS NEÓN Y SCRIPTS ---
CSS = '''
<style>
    body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 15px; }
    .menu-box { border: 2px solid #0f0; padding: 20px; max-width: 800px; margin: auto; box-shadow: 0 0 15px #0f0; border-radius: 5px; }
    .opcion { display: block; color: #0f0; text-decoration: none; margin: 10px 0; padding: 10px; border: 1px solid #111; border-radius: 3px; }
    .opcion:hover { background: #0f0; color: #000; font-weight: bold; }
    input, select { background: #111; color: #0f0; border: 1px solid #0f0; padding: 12px; width: 100%; margin: 5px 0; box-sizing: border-box; }
    button { background: #0f0; color: #000; border: none; padding: 15px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 5px; }
    table { width: 100%; border-collapse: collapse; margin-top: 15px; }
    th, td { border: 1px solid #0f0; padding: 10px; text-align: left; }
    .btn-rojo { background: #f00; color: #fff; padding: 5px 10px; text-decoration: none; border-radius: 3px; font-size: 0.8em; }
    .btn-pagar { background: #0f0; color: #000; padding: 5px 10px; text-decoration: none; font-weight: bold; border-radius: 3px; font-size: 0.8em; }
    .btn-volver { border: 1px solid #0f0; color: #0f0; padding: 12px; display: block; text-align: center; text-decoration: none; margin-top: 15px; }
    .search-box { background: #000; color: #0f0; border: 2px solid #0f0; padding: 10px; margin-bottom: 5px; width: 100%; font-weight: bold; }
</style>
<script>
    function filtrarProductos() {
        let input = document.getElementById('search').value.toLowerCase();
        let select = document.getElementById('prod_list');
        let options = select.options;
        for (let i = 0; i < options.length; i++) {
            let match = options[i].text.toLowerCase().includes(input);
            options[i].style.display = match ? '' : 'none';
            if (match && input !== "") options[i].selected = true;
        }
    }
</script>
'''

# --- RUTAS DE ACCESO ---
@app.route('/')
def login():
    session.clear()
    return f'{CSS}<div class="menu-box"><h3>🔑 SISTEMA DE VENTAS</h3><form action="/verificar" method="post"><input name="clave" placeholder="CLAVE DE ACCESO" autofocus required><button>ENTRAR</button></form></div>'

@app.route('/verificar', methods=['GET', 'POST'])
def verificar():
    clave = request.form.get('clave') or session.get('usuario_clave')
    if not clave: return redirect('/')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    if user:
        session['usuario_clave'] = clave
        db_n = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
        db_t = iniciar_db_tienda(db_n)
        conf = db_t.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()
        
        menu = f"{CSS}<div class='menu-box'><h3>--- {conf['nombre_negocio']} ---</h3><p>👤 {user['nombre']} | {user['rango']}</p><hr>"
        if user['rango'] in ['Super Admin', 'Administrador']:
            menu += f'<a class="opcion" href="/gestionar_negocios/{clave}">📊 CONTROL DE DUEÑOS</a>'
        elif user['rango'] in ['Dueño', 'Trabajador']:
            menu += '<a class="opcion" href="/venta">🛒 CAJA DE COBRO</a>'
            menu += f'<a class="opcion" href="/inventario/{clave}">📦 INVENTARIO</a>'
            if user['rango'] == 'Dueño':
                menu += f'<a class="opcion" href="/usuarios/{clave}">👥 EMPLEADOS</a>'
                menu += f'<a class="opcion" href="/hacer_corte_final/{clave}">🏁 REALIZAR CORTE</a>'
        menu += '<a class="opcion" href="/" style="color:red; border-color:red; margin-top:20px;">🚪 SALIR</a></div>'
        return menu
    return redirect('/')

# --- CAJA DE COBRO CON BUSCADOR Y ORDEN ---
@app.route('/venta')
def vista_venta():
    clv = session.get('usuario_clave')
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clv,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    # Ordenar por abecedario
    prods = db.execute("SELECT * FROM productos WHERE stock > 0 ORDER BY nombre ASC").fetchall()
    opcs = "".join([f"<option value='{p['codigo']}'>{p['nombre']} (${p['precio']})</option>" for p in prods])
    car = session.get('carrito', [])
    tabla = "<table>" + "".join([f"<tr><td>{i['n']}</td><td>x{i['c']}</td><td>${i['s']}</td></tr>" for i in car]) + "</table>"
    return f'''{CSS}<div class="menu-box"><h3>🛒 CAJA</h3>
    <input type="text" id="search" class="search-box" placeholder="🔍 BUSCAR..." onkeyup="filtrarProductos()">
    <form action="/add_car" method="post">
        <select name="cod" id="prod_list" size="5" required>{opcs}</select>
        <input type="number" step="0.1" name="cnt" placeholder="CANTIDAD" required>
        <button type="submit">AÑADIR</button>
    </form>
    {tabla}<h4>TOTAL: ${sum(i['s'] for i in car)}</h4>
    <a href="/cobrar" class="btn-pagar">FINALIZAR VENTA</a><a href="/verificar" class="btn-volver">VOLVER</a></div>'''

# --- GESTIÓN DE CLAVES (COMO ESTABA ANTES) ---
@app.route('/add_user', methods=['POST'])
def add_user():
    adm, nom, rango = request.form['admin_clave'], request.form['nombre'], request.form['rango']
    prefijo = "DUE" if rango == "Dueño" else ("ADM" if rango == "Administrador" else "TRA")
    # Generar clave automática
    clv = f"{prefijo}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"
    vence = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S") if rango == 'Dueño' else "2099-12-31 23:59:59"
    with iniciar_db_usuarios() as db:
        db.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado, vencimiento) VALUES (?,?,?,?,?,?)", (clv, nom, rango, adm, "Activo", vence))
    return f"{CSS}<div class='menu-box'><h3>✅ CLAVE GENERADA</h3><p>USUARIO: {nom}</p><p>CLAVE: <strong style='font-size:20px; color:yellow;'>{clv}</strong></p><a href='/verificar' class='btn-volver'>REGRESAR AL MENÚ</a></div>"

# --- OTRAS RUTAS NECESARIAS ---
@app.route('/add_car', methods=['POST'])
def add_car():
    clv = session.get('usuario_clave')
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clv,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    p = db.execute("SELECT * FROM productos WHERE codigo=?", (request.form['cod'],)).fetchone()
    if p:
        cnt = float(request.form['cnt'])
        sub = p['precio'] * cnt if p['unidad'] == 'p' else cnt
        real_cnt = cnt if p['unidad'] == 'p' else cnt / p['precio']
        car = session.get('carrito', [])
        car.append({'id': p['codigo'], 'n': p['nombre'], 'c': round(real_cnt, 2), 's': sub})
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
            db.execute("UPDATE productos SET stock = stock - ? WHERE codigo = ?", (i['c'], i['id']))
            db.execute("INSERT INTO ventas (total, fecha, vendedor) VALUES (?,?,?)", (i['s'], datetime.now().strftime("%H:%M"), u['nombre']))
    session['carrito'] = []
    return redirect('/venta')

@app.route('/inventario/<clave>')
def inventario(clave):
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    # Ordenar por abecedario
    prods = db.execute("SELECT * FROM productos ORDER BY nombre ASC").fetchall()
    tabla = "<table><tr><th>COD</th><th>PRODUCTO</th><th>STOCK</th></tr>" + "".join([f"<tr><td>{p['codigo']}</td><td>{p['nombre']} (${p['precio']})</td><td>{p['stock']} {p['unidad']}</td></tr>" for p in prods]) + "</table>"
    form = f'<hr><form action="/add_p" method="post"><input type="hidden" name="cl" value="{clave}"><input name="co" placeholder="COD"><input name="no" placeholder="PRODUCTO"><input name="pr" placeholder="PRECIO"><input name="st" placeholder="STOCK"><select name="un"><option value="p">Pieza</option><option value="k">Kilo</option></select><button>AÑADIR PRODUCTO</button></form>' if u['rango'] == 'Dueño' else ""
    return f"{CSS}<div class='menu-box'><h3>📦 INVENTARIO</h3>{tabla}{form}<a href='/verificar' class='btn-volver'>VOLVER</a></div>"

@app.route('/add_p', methods=['POST'])
def add_p():
    with iniciar_db_tienda(f"tienda_{request.form['cl']}.db") as db:
        db.execute("INSERT OR REPLACE INTO productos VALUES (?,?,?,?,?)", (request.form['co'], request.form['no'], request.form['pr'], request.form['st'], request.form['un']))
    return redirect(f"/inventario/{request.form['cl']}")

if __name__ == "__main__":
    iniciar_db_usuarios()
    app.run(host='0.0.0.0', port=10000)
    
