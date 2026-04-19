import sqlite3
from datetime import datetime
import urllib.parse
import random
import string
import os
import csv
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
    body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 20px; line-height: 1.2; }
    .menu-box { border: 2px solid #0f0; padding: 20px; max-width: 650px; margin: auto; }
    .opcion { display: block; color: #0f0; text-decoration: none; margin: 8px 0; font-size: 1.1em; }
    .opcion:hover { background: #0f0; color: #000; }
    input, select { background: #000; color: #0f0; border: 1px solid #0f0; padding: 8px; width: 100%; margin: 5px 0; box-sizing: border-box; }
    button { background: #0f0; color: #000; border: none; padding: 12px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 10px; }
    hr { border: 0; border-top: 1px dashed #0f0; margin: 15px 0; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; color: #0f0; }
    th, td { border: 1px solid #0f0; padding: 8px; text-align: left; }
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
    clave = request.form.get('clave')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user:
        if user['estado'] == "Suspendido":
            return f"{CSS}<div class='menu-box'>🚫 SERVICIO SUSPENDIDO. <a href='/' style='color:#0f0'>Volver</a></div>"
        
        db_nombre = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
        db = iniciar_db(db_nombre)
        conf = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()

        menu_html = f"{CSS}<div class='menu-box'><h3>--- {conf['nombre_negocio']} ---</h3><p>Usuario: {user['nombre']} | Rango: {user['rango']}</p><hr>"

        if user['rango'] == 'Administrador':
            menu_html += f'''<a class="opcion" href="/usuarios/{clave}">1. GESTIONAR DUEÑOS (TABLA)</a><a class="opcion" href="/">2. SALIR</a>'''
        elif user['rango'] == 'Dueño':
            menu_html += f'''
                <a class="opcion" href="/venta/{clave}">1. REALIZAR VENTA</a>
                <a class="opcion" href="/inventario/{clave}">2. INVENTARIO (EDITAR/VER)</a>
                <a class="opcion" href="/usuarios/{clave}">3. GESTIONAR MIS TRABAJADORES</a>
                <a class="opcion" href="/pago_proveedor/{clave}">4. PAGAR A PROVEEDOR</a>
                <a class="opcion" href="/config/{clave}">5. CONFIGURAR NEGOCIO</a>
                <a class="opcion" href="/corte/{clave}">6. ENVIAR CORTE DE CAJA</a>
                <a class="opcion" href="/">7. SALIR</a>'''
        elif user['rango'] == 'Trabajador':
            menu_html += f'''
                <a class="opcion" href="/venta/{clave}">1. REALIZAR VENTA</a>
                <a class="opcion" href="/inventario/{clave}">2. VER STOCK (SÓLO LECTURA)</a>
                <a class="opcion" href="/pago_proveedor/{clave}">3. PAGAR A PROVEEDOR</a>
                <a class="opcion" href="/">4. SALIR</a>'''
        
        menu_html += "</div>"
        return menu_html
    return f"{CSS}<div class='menu-box'>❌ Clave incorrecta. <a href='/' style='color:#0f0'>Reintentar</a></div>"

# --- FUNCIONES DE GESTIÓN DE USUARIOS ---
@app.route('/usuarios/<clave>')
def gestionar_usuarios(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    rango_a_gestionar = "Dueño" if user['rango'] == "Administrador" else "Trabajador"
    mi_rama = db_u.execute("SELECT * FROM usuarios WHERE creado_por = ?", (clave,)).fetchall()
    tabla = "<table><tr><th>CLAVE</th><th>NOMBRE</th><th>ESTADO</th></tr>"
    for u in mi_rama:
        tabla += f"<tr><td>{u['clave']}</td><td>{u['nombre']}</td><td>{u['estado']}</td></tr>"
    tabla += "</table>"
    return f'''{CSS}<div class="menu-box"><h3>--- GESTIÓN DE {rango_a_gestionar.upper()}S ---</h3>{tabla}<hr>
    <form action="/add_user" method="post"><input type="hidden" name="admin_clave" value="{clave}"><input type="hidden" name="rango" value="{rango_a_gestionar}">
    <input name="nombre" placeholder="Nombre" required><button type="submit">REGISTRAR</button></form>
    <br><form action="/auth" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" style="background:none;color:#0f0;border:1px solid #0f0;width:auto;">VOLVER</button></form></div>'''

@app.route('/add_user', methods=['POST'])
def add_user():
    admin_clave, nom, rango = request.form.get('admin_clave'), request.form.get('nombre'), request.form.get('rango')
    nueva_c = f"{nom[:3].upper()}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    db_u = iniciar_db_usuarios()
    with db_u: db_u.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?,?,?,?,?)", (nueva_c, nom, rango, admin_clave, "Activo"))
    return f"{CSS}<div class='menu-box'>✅ CLAVE GENERADA: {nueva_c}<br><form action='/auth' method='post'><input type='hidden' name='clave' value='{admin_clave}'><button type='submit'>CONTINUAR</button></form></div>"

# --- INVENTARIO ---
@app.route('/inventario/<clave>')
def inventario(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    prods = db.execute("SELECT * FROM productos").fetchall()
    tabla = "<table><tr><th>ID</th><th>NOMBRE</th><th>PRECIO</th><th>STOCK</th></tr>"
    for p in prods: tabla += f"<tr><td>{p['codigo']}</td><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock']}</td></tr>"
    tabla += "</table>"
    form_add = f'''<hr><form action="/add_prod" method="post"><input type="hidden" name="clave" value="{clave}"><input name="cod" placeholder="Código" required><input name="nom" placeholder="Nombre" required><input type="number" step="0.1" name="pre" placeholder="Precio" required><input type="number" step="0.1" name="sto" placeholder="Stock" required><select name="uni"><option value="p">Pieza</option><option value="k">Kilo</option></select><button type="submit">GUARDAR</button></form>''' if user['rango'] != 'Trabajador' else ""
    return f"{CSS}<div class='menu-box'><h3>📦 INVENTARIO</h3>{tabla}{form_add}<br><form action='/auth' method='post'><input type='hidden' name='clave' value='{clave}'><button type='submit' style='background:none;color:#0f0;border:1px solid #0f0;width:auto;'>VOLVER</button></form></div>"

@app.route('/add_prod', methods=['POST'])
def add_prod():
    clave = request.form.get('clave')
    db = iniciar_db(f"tienda_{clave}.db")
    with db: db.execute("INSERT OR REPLACE INTO productos (codigo, nombre, precio, stock, min_compra, unidad) VALUES (?,?,?,?,?,?)", (request.form.get('cod'), request.form.get('nom'), request.form.get('pre'), request.form.get('sto'), 0, request.form.get('uni')))
    return redirect(f"/inventario/{clave}", code=307)

# --- VENTAS ---
@app.route('/venta/<clave>')
def venta(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    prods = db.execute("SELECT * FROM productos WHERE stock > 0").fetchall()
    opciones = "".join([f"<option value='{p['codigo']}'>{p['nombre']} (${p['precio']})</option>" for p in prods])
    return f'''{CSS}<div class="menu-box"><h3>🛒 CAJA</h3><form action="/procesar_venta" method="post"><input type="hidden" name="clave" value="{clave}"><select name="cod">{opciones}</select><input type="number" step="0.1" name="cant" placeholder="Cantidad / Dinero" required><button type="submit">VENDER</button></form><br><form action='/auth' method='post'><input type='hidden' name='clave' value='{clave}'><button type='submit' style='background:none;color:#0f0;border:1px solid #0f0;width:auto;'>VOLVER</button></form></div>'''

@app.route('/procesar_venta', methods=['POST'])
def procesar_venta():
    clave, cod, cant = request.form.get('clave'), request.form.get('cod'), float(request.form.get('cant'))
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    p = db.execute("SELECT * FROM productos WHERE codigo = ?", (cod,)).fetchone()
    if p:
        total = p['precio'] * cant if p['unidad'] == 'p' else cant
        desc = cant if p['unidad'] == 'p' else cant / p['precio']
        with db:
            db.execute("UPDATE productos SET stock = stock - ? WHERE codigo = ?", (desc, cod))
            db.execute("INSERT INTO ventas (total, pago, cambio, fecha, vendedor) VALUES (?,?,?,?,?)", (total, total, 0, datetime.now().strftime("%Y-%m-%d %H:%M"), user['nombre']))
        return f"{CSS}<div class='menu-box'>✅ VENTA: ${total}<br><form action='/auth' method='post'><input type='hidden' name='clave' value='{clave}'><button type='submit'>CONTINUAR</button></form></div>"
    return "Error"

# --- GASTOS Y PROVEEDORES ---
@app.route('/pago_proveedor/<clave>')
def pago_proveedor(clave):
    return f'''{CSS}<div class="menu-box"><h3>🚚 PAGO A PROVEEDOR</h3><form action="/reg_gasto" method="post"><input type="hidden" name="clave" value="{clave}"><input name="prov" placeholder="Proveedor / Concepto" required><input type="number" step="0.1" name="monto" placeholder="Monto $" required><button type="submit">REGISTRAR PAGO</button></form></div>'''

@app.route('/reg_gasto', methods=['POST'])
def reg_gasto():
    clave, prov, monto = request.form.get('clave'), request.form.get('prov'), request.form.get('monto')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    with db: db.execute("INSERT INTO gastos (concepto, monto, fecha) VALUES (?, ?, ?)", (prov, monto, datetime.now().strftime("%Y-%m-%d %H:%M")))
    return f"{CSS}<div class='menu-box'>✅ GASTO REGISTRADO.<form action='/auth' method='post'><input type='hidden' name='clave' value='{clave}'><button type='submit'>VOLVER</button></form></div>"

# --- CORTE DE CAJA ---
@app.route('/corte/<clave>')
def corte(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['clave']}.db")
    conf = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    v = db.execute("SELECT SUM(total) as t FROM ventas WHERE fecha LIKE ?", (f"{fecha_hoy}%",)).fetchone()['t'] or 0
    g = db.execute("SELECT SUM(monto) as t FROM gastos WHERE fecha LIKE ?", (f"{fecha_hoy}%",)).fetchone()['t'] or 0
    total = v - g
    msg = f"📊 *CORTE: {conf['nombre_negocio']}*\\n✅ Ventas: ${v}\\n💸 Gastos: ${g}\\n💰 TOTAL: ${total}"
    url_wa = f"https://api.whatsapp.com/send?phone=52{conf['telefono_dueno']}&text={urllib.parse.quote(msg)}"
    return f"{CSS}<div class='menu-box'><h3>📊 CORTE DEL DÍA</h3><p>Ventas: ${v}</p><p>Gastos: ${g}</p><h4>TOTAL: ${total}</h4><hr><a href='{url_wa}' class='opcion' target='_blank'>📲 ENVIAR POR WHATSAPP</a><br><form action='/auth' method='post'><input type='hidden' name='clave' value='{clave}'><button type='submit'>VOLVER</button></form></div>"

# --- CONFIGURACIÓN ---
@app.route('/config/<clave>')
def config(clave):
    db = iniciar_db(f"tienda_{clave}.db")
    c = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()
    return f'''{CSS}<div class="menu-box"><h3>⚙️ CONFIGURACIÓN</h3><form action="/upd_conf" method="post"><input type="hidden" name="clave" value="{clave}"><label>Nombre Negocio:</label><input name="nn" value="{c['nombre_negocio']}"><label>Teléfono (WhatsApp):</label><input name="nt" value="{c['telefono_dueno']}"><button type="submit">GUARDAR</button></form></div>'''

@app.route('/upd_conf', methods=['POST'])
def upd_conf():
    clave, nn, nt = request.form.get('clave'), request.form.get('nn'), request.form.get('nt')
    db = iniciar_db(f"tienda_{clave}.db")
    with db: db.execute("UPDATE configuracion SET nombre_negocio=?, telefono_dueno=? WHERE id=1", (nn, nt))
    return redirect(f"/auth", code=307)

if __name__ == "__main__":
    iniciar_db_usuarios()
    iniciar_db()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
