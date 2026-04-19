import sqlite3
from datetime import datetime, timedelta
import urllib.parse
import random
import string
import os
from flask import Flask, request, render_template_string, redirect, session

app = Flask(__name__)
app.secret_key = 'sistema_omni_v12_integridad_total'

# --- CONFIGURACIÓN DE BASES DE DATOS (ESTRUCTURA ORIGINAL) ---

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
        conn.execute('''CREATE TABLE IF NOT EXISTS configuracion 
                     (id INTEGER PRIMARY KEY, nombre_negocio TEXT, telefono_dueno TEXT, hora_corte TEXT DEFAULT '21:00')''')
        if conn.execute("SELECT COUNT(*) FROM configuracion").fetchone()[0] == 0:
            conn.execute("INSERT INTO configuracion (id, nombre_negocio, telefono_dueno) VALUES (1, 'MI TIENDA', '')")
    return conn

# --- DISEÑO Y UTILIDADES ---

CSS = '''
<style>
    body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 20px; }
    .menu-box { border: 2px solid #0f0; padding: 20px; max-width: 800px; margin: auto; box-shadow: 0 0 15px #0f0; border-radius: 5px; }
    .opcion { display: block; color: #0f0; text-decoration: none; margin: 10px 0; padding: 10px; border: 1px solid #111; }
    .opcion:hover { background: #0f0; color: #000; font-weight: bold; }
    input, select { background: #111; color: #0f0; border: 1px solid #0f0; padding: 12px; width: 100%; margin: 5px 0; box-sizing: border-box; }
    button { background: #0f0; color: #000; border: none; padding: 15px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 5px; }
    table { width: 100%; border-collapse: collapse; margin-top: 15px; }
    th, td { border: 1px solid #0f0; padding: 10px; text-align: left; }
    .clv-destaque { color: yellow; font-weight: bold; }
    .btn-volver { border: 1px solid #0f0; color: #0f0; padding: 12px; display: block; text-align: center; text-decoration: none; margin-top: 15px; }
</style>
<script>
    function buscarProducto() {
        let input = document.getElementById('search').value.toLowerCase();
        let select = document.getElementById('prod_select');
        for (let i = 0; i < select.options.length; i++) {
            let text = select.options[i].text.toLowerCase();
            select.options[i].style.display = text.includes(input) ? '' : 'none';
        }
    }
</script>
'''

# --- LÓGICA DE RUTAS ---

@app.route('/')
def login():
    session.clear()
    return f'{CSS}<div class="menu-box"><h3>🔑 ACCESO</h3><form action="/verificar" method="post"><input name="clave" placeholder="CLAVE" required autofocus><button>ENTRAR</button></form></div>'

@app.route('/verificar', methods=['POST'])
def verificar():
    clave = request.form.get('clave')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    if user:
        session['usuario_clave'] = clave
        db_n = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
        db_t = iniciar_db_tienda(db_n)
        conf = db_t.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()
        
        menu = f"{CSS}<div class='menu-box'><h3>--- {conf['nombre_negocio']} ---</h3><p>👤 {user['nombre']} | {user['rango']}</p><hr>"
        
        # Super Admin: Recuperada gestión de Dueños y Admins
        if user['rango'] == 'Super Admin':
            menu += f'<a class="opcion" href="/gestionar_negocios/{clave}">📊 GESTIONAR TODOS LOS DUEÑOS</a>'
            menu += f'<a class="opcion" href="/usuarios/{clave}">👥 GESTIONAR ADMINISTRADORES</a>'
        
        elif user['rango'] == 'Administrador':
            menu += f'<a class="opcion" href="/gestionar_negocios/{clave}">📊 GESTIONAR MIS DUEÑOS</a>'
        
        elif user['rango'] in ['Dueño', 'Trabajador']:
            menu += '<a class="opcion" href="/venta">🛒 ABRIR CAJA</a>'
            menu += f'<a class="opcion" href="/inventario/{clave}">📦 INVENTARIO</a>'
            if user['rango'] == 'Dueño':
                menu += f'<a class="opcion" href="/usuarios/{clave}">👥 GESTIONAR EMPLEADOS</a>'
        
        menu += '<hr><a class="opcion" href="/" style="color:red;">🚪 SALIR</a></div>'
        return menu
    return redirect('/')

# --- GESTIÓN DE USUARIOS (DUEÑOS Y EMPLEADOS) CON CLAVES ---

@app.route('/gestionar_negocios/<clave>')
def gestionar_negocios(clave):
    db_u = iniciar_db_usuarios()
    duenos = db_u.execute("SELECT * FROM usuarios WHERE rango = 'Dueño' ORDER BY nombre ASC").fetchall()
    tabla = "<table><tr><th>DUEÑO</th><th>CLAVE ACCESO</th><th>ESTADO</th></tr>"
    for d in duenos:
        tabla += f"<tr><td>{d['nombre']}</td><td class='clv-destaque'>{d['clave']}</td><td>{d['estado']}</td></tr>"
    return f"{CSS}<div class='menu-box'><h3>🏢 LISTA DE DUEÑOS</h3>{tabla}</table><hr><form action='/add_user' method='post'><input type='hidden' name='admin_clave' value='{clave}'><input type='hidden' name='rango' value='Dueño'><input name='nombre' placeholder='Nombre del Negocio' required><button>CREAR DUEÑO</button></form><a href='/verificar' class='btn-volver'>VOLVER</a></div>"

@app.route('/usuarios/<clave>')
def gestionar_usuarios(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    # Determinar qué tipo de usuario se gestiona según el rango del que consulta
    if user['rango'] == "Super Admin":
        items = db_u.execute("SELECT * FROM usuarios WHERE rango = 'Administrador' ORDER BY nombre ASC").fetchall()
        tipo = "Administradores"
        r_crear = "Administrador"
    else:
        items = db_u.execute("SELECT * FROM usuarios WHERE creado_por = ? ORDER BY nombre ASC", (clave,)).fetchall()
        tipo = "Empleados"
        r_crear = "Trabajador"

    tabla = "<table><tr><th>NOMBRE</th><th>CLAVE ACCESO</th><th>ESTADO</th></tr>"
    for i in items:
        tabla += f"<tr><td>{i['nombre']}</td><td class='clv-destaque'>{i['clave']}</td><td>{i['estado']}</td></tr>"
    
    return f"{CSS}<div class='menu-box'><h3>👥 GESTIÓN DE {tipo.upper()}</h3>{tabla}</table><hr><form action='/add_user' method='post'><input type='hidden' name='admin_clave' value='{clave}'><input type='hidden' name='rango' value='{r_crear}'><input name='nombre' placeholder='Nombre Completo' required><button>CREAR NUEVO</button></form><a href='/verificar' class='btn-volver'>VOLVER</a></div>"

# --- VENTA Y WHATSAPP ---

@app.route('/venta')
def vista_venta():
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
    <input type="text" id="search" placeholder="🔍 BUSCAR PRODUCTO..." onkeyup="buscarProducto()">
    <form action="/add_car" method="post">
        <select name="cod" id="prod_select" size="5" required>{opcs}</select>
        <input type="number" step="0.1" name="cnt" placeholder="CANTIDAD" required>
        <button type="submit">AÑADIR</button>
    </form>
    <h4>TOTAL: ${total}</h4>
    <a href="/cobrar_ws" class="btn-pagar" style="background:#25D366; color:white; display:block; text-align:center; padding:15px; text-decoration:none;">📱 COBRAR Y ENVIAR WHATSAPP</a>
    <a href="/verificar" class="btn-volver">VOLVER</a></div>'''

@app.route('/cobrar_ws')
def cobrar_ws():
    clv = session.get('usuario_clave')
    car = session.get('carrito', [])
    if not car: return redirect('/venta')
    
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clv,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    conf = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()
    
    # Generar texto del ticket
    ticket = f"*--- {conf['nombre_negocio']} ---*\n"
    total = 0
    with db:
        for i in car:
            db.execute("UPDATE productos SET stock = stock - ? WHERE codigo = ?", (i['c'], i['id']))
            db.execute("INSERT INTO ventas (total, fecha, vendedor) VALUES (?,?,?)", (i['s'], datetime.now().strftime("%Y-%m-%d %H:%M"), u['nombre']))
            ticket += f"• {i['n']} x{i['c']}: ${i['s']}\n"
            total += i['s']
    
    ticket += f"\n*TOTAL: ${total}*\nAtendió: {u['nombre']}"
    session['carrito'] = []
    
    # Link de WhatsApp
    ws_link = f"https://wa.me/{conf['telefono_dueno']}?text={urllib.parse.quote(ticket)}"
    return redirect(ws_link)

# --- GENERACIÓN DE CLAVES ---

@app.route('/add_user', methods=['POST'])
def add_user():
    adm, nom, rango = request.form['admin_clave'], request.form['nombre'], request.form['rango']
    pref = "DUE" if rango == "Dueño" else ("ADM" if rango == "Administrador" else "TRA")
    clv = f"{pref}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"
    with iniciar_db_usuarios() as db:
        db.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado, vencimiento) VALUES (?,?,?,?,?,?)", 
                   (clv, nom, rango, adm, "Activo", "2026-12-31 23:59:59"))
    return redirect(f"/verificar")

if __name__ == "__main__":
    iniciar_db_usuarios()
    app.run(host='0.0.0.0', port=10000)
    
