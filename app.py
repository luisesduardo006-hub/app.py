import sqlite3
from datetime import datetime
import urllib.parse
import random
import string
import os
from flask import Flask, request, render_template_string, redirect, session

app = Flask(__name__)
app.secret_key = 'clave_secreta_punto_venta'

# --- BASE DE DATOS ---
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
            conn.execute("INSERT INTO configuracion (id, nombre_negocio, direccion, min_compra, porc_desc, telefono_dueno) VALUES (1, 'MI TIENDITA PRO', 'Direccion', 0, 0, '')")
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

CSS = '''
<style>
    body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 20px; }
    .menu-box { border: 2px solid #0f0; padding: 20px; max-width: 650px; margin: auto; }
    .opcion { display: block; color: #0f0; text-decoration: none; margin: 8px 0; font-size: 1.1em; }
    .opcion:hover { background: #0f0; color: #000; }
    input, select { background: #000; color: #0f0; border: 1px solid #0f0; padding: 10px; width: 100%; margin: 5px 0; box-sizing: border-box; }
    button { background: #0f0; color: #000; border: none; padding: 12px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 10px; }
    hr { border: 0; border-top: 1px dashed #0f0; margin: 15px 0; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; color: #0f0; }
    th, td { border: 1px solid #0f0; padding: 8px; text-align: left; }
    .btn-rojo { background: #f00; color: #fff; padding: 5px; text-decoration: none; border: none; cursor: pointer; }
    .btn-volver { background: none; border: 1px solid #0f0; color: #0f0; padding: 10px; width: 100%; margin-top: 10px; cursor: pointer; font-weight: bold; display: block; text-align: center; text-decoration: none; }
    .btn-volver:hover { background: #0f0; color: #000; }
</style>
'''

@app.route('/')
def login_screen():
    session.clear()
    return f'''{CSS}
    <div class="menu-box">
        <p>===================================</p>
        <p>🔑 INICIO DE SESIÓN</p>
        <p>===================================</p>
        <form action="/verificar" method="post">
            <input type="text" name="clave" placeholder="CLAVE DE ACCESO" autofocus required>
            <button type="submit">ENTRAR</button>
        </form>
    </div>'''

@app.route('/verificar', methods=['POST'])
def verificar():
    clave = request.form.get('clave') or session.get('usuario_clave')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user and user['estado'] != "Suspendido":
        session['usuario_clave'] = clave
        db_n = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
        db = iniciar_db(db_n)
        conf = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()

        menu = f"{CSS}<div class='menu-box'><h3>--- {conf['nombre_negocio']} ---</h3><p>{user['nombre']} ({user['rango']})</p><hr>"
        if user['rango'] == 'Administrador':
            menu += f'<a class="opcion" href="/usuarios/{clave}">1. GESTIONAR DUEÑOS</a>'
        elif user['rango'] in ['Dueño', 'Trabajador']:
            menu += '<a class="opcion" href="/venta">1. REALIZAR VENTA</a>'
            menu += f'<a class="opcion" href="/inventario/{clave}">2. INVENTARIO</a>'
            menu += f'<a class="opcion" href="/pago_proveedor/{clave}">3. PAGAR PROVEEDOR</a>'
            if user['rango'] == 'Dueño':
                menu += f'<a class="opcion" href="/usuarios/{clave}">4. MIS TRABAJADORES</a>'
                menu += f'<a class="opcion" href="/config/{clave}">5. CONFIGURACIÓN</a>'
                menu += f'<a class="opcion" href="/corte/{clave}">6. CORTE DE CAJA</a>'
        menu += '<hr><a class="opcion" href="/">7. SALIR</a></div>'
        return menu
    return "Acceso denegado o cuenta suspendida."

# --- VENTAS ---

@app.route('/venta')
def vista_venta():
    clave = session.get('usuario_clave')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    
    prods = db.execute("SELECT * FROM productos WHERE stock > 0").fetchall()
    opciones = "".join([f"<option value='{p['codigo']}'>{p['nombre']} (${p['precio']} /{p['unidad']})</option>" for p in prods])
    
    carrito = session.get('carrito', [])
    total = sum(item['subtotal'] for item in carrito)
    
    tabla = "<table><tr><th>Prod</th><th>Cant</th><th>Sub</th><th>X</th></tr>"
    for i, it in enumerate(carrito):
        uni = "pz" if it['unidad'] == 'p' else "kg"
        tabla += f"<tr><td>{it['nombre']}</td><td>{it['cantidad']}{uni}</td><td>${it['subtotal']}</td><td><a href='/quitar/{i}' class='btn-rojo'>X</a></td></tr>"
    tabla += "</table>"

    return f'''{CSS}<div class="menu-box">
        <h3>🛒 CAJA</h3>
        <form action="/agregar" method="post">
            <select name="cod">{opciones}</select>
            <input type="number" step="0.1" name="cant" placeholder="Piezas o Dinero (si es kilo)" required>
            <button type="submit">AGREGAR</button>
        </form>
        {tabla}
        <h4>TOTAL: ${total}</h4>
        {f'<a href="/confirmar" class="opcion" style="background:#0f0; color:#000; text-align:center">--- FINALIZAR VENTA ---</a>' if carrito else ''}
        <br>
        <form action="/verificar" method="post">
            <input type="hidden" name="clave" value="{clave}">
            <button type="submit" class="btn-volver">VOLVER AL MENÚ</button>
        </form>
    </div>'''

@app.route('/agregar', methods=['POST'])
def agregar():
    clave = session.get('usuario_clave')
    cod, cant = request.form.get('cod'), float(request.form.get('cant'))
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    
    p = db.execute("SELECT * FROM productos WHERE codigo = ?", (cod,)).fetchone()
    if p:
        subtotal = p['precio'] * cant if p['unidad'] == 'p' else cant
        cant_stock = cant if p['unidad'] == 'p' else cant / p['precio']
        
        carrito = session.get('carrito', [])
        carrito.append({'codigo': cod, 'nombre': p['nombre'], 'cantidad': round(cant_stock, 2), 'subtotal': subtotal, 'unidad': p['unidad']})
        session['carrito'] = carrito
    return redirect('/venta')

@app.route('/quitar/<i>')
def quitar(i):
    carrito = session.get('carrito', [])
    carrito.pop(int(i))
    session['carrito'] = carrito
    return redirect('/venta')

@app.route('/confirmar')
def confirmar():
    clave = session.get('usuario_clave')
    carrito = session.get('carrito', [])
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    conf = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()
    
    total = sum(item['subtotal'] for item in carrito)
    ticket_raw = f"🧾 *TICKET: {conf['nombre_negocio']}*\\n"
    ticket_raw += f"👤 Atendió: {user['nombre']}\\n--------------------------\\n"
    
    with db:
        for it in carrito:
            db.execute("UPDATE productos SET stock = stock - ? WHERE codigo = ?", (it['cantidad'], it['codigo']))
            ticket_raw += f"• {it['nombre']}: ${it['subtotal']}\\n"
        db.execute("INSERT INTO ventas (total, pago, cambio, fecha, vendedor) VALUES (?,?,?,?,?)", (total, total, 0, datetime.now().strftime("%H:%M"), user['nombre']))
    
    ticket_raw += f"--------------------------\\n💰 *TOTAL: ${total}*"
    
    # GUARDAMOS EL TICKET TEMPORAL EN SESSION PARA MANDARLO DESPUÉS
    session['ticket_pendiente'] = ticket_raw
    session['carrito'] = [] 

    return f'''{CSS}<div class="menu-box">
        <h3>✅ VENTA COBRADA: ${total}</h3>
        <p>Introduce el número del cliente para mandar el ticket:</p>
        <form action="/enviar_ticket" method="post">
            <input type="text" name="tel_cliente" placeholder="Ej: 5512345678" required>
            <button type="submit" style="background:#0f0; color:#000">📲 ENVIAR TICKET POR WHATSAPP</button>
        </form>
        <br>
        <a href="/venta" class="btn-volver">OMITIR Y NUEVA VENTA</a>
    </div>'''

@app.route('/enviar_ticket', methods=['POST'])
def enviar_ticket():
    tel = request.form.get('tel_cliente')
    ticket = session.get('ticket_pendiente', '')
    url_wa = f"https://api.whatsapp.com/send?phone=52{tel}&text={urllib.parse.quote(ticket)}"
    return f'''<script>window.open("{url_wa}", "_blank"); window.location.href = "/venta";</script>'''

# --- EL RESTO DEL CÓDIGO (STOCK, CONFIG, GASTOS) SE MANTIENE ---

@app.route('/inventario/<clave>')
def inventario(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    prods = db.execute("SELECT * FROM productos").fetchall()
    tabla = "<table><tr><th>COD</th><th>NOM</th><th>PRE</th><th>STK</th><th>UNI</th></tr>"
    for p in prods: tabla += f"<tr><td>{p['codigo']}</td><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock']}</td><td>{p['unidad']}</td></tr>"
    tabla += "</table>"
    form = f'''<hr><form action="/add_prod" method="post"><input type="hidden" name="clave" value="{clave}"><input name="cod" placeholder="Cod"><input name="nom" placeholder="Nombre"><input type="number" step="0.1" name="pre" placeholder="Precio"><input type="number" step="0.1" name="sto" placeholder="Stock"><select name="uni"><option value="p">Pieza</option><option value="k">Kilo</option></select><button type="submit">GUARDAR</button></form>''' if user['rango'] != 'Trabajador' else ""
    return f'''{CSS}<div class="menu-box"><h3>📦 STOCK</h3>{tabla}{form}
        <form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

@app.route('/add_prod', methods=['POST'])
def add_prod():
    clave = request.form.get('clave')
    db = iniciar_db(f"tienda_{clave}.db")
    with db: db.execute("INSERT OR REPLACE INTO productos (codigo, nombre, precio, stock, min_compra, unidad) VALUES (?,?,?,?,?,?)", (request.form.get('cod'), request.form.get('nom'), request.form.get('pre'), request.form.get('sto'), 0, request.form.get('uni')))
    return redirect(f"/inventario/{clave}")

@app.route('/usuarios/<clave>')
def gestionar_usuarios(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    rango_dest = "Dueño" if user['rango'] == "Administrador" else "Trabajador"
    mi_rama = db_u.execute("SELECT * FROM usuarios WHERE creado_por = ?", (clave,)).fetchall()
    tabla = "<table><tr><th>CLAVE</th><th>NOM</th><th>EST</th><th>ACC</th></tr>"
    for u in mi_rama:
        acc = f'<td><a href="/status/{clave}/{u["clave"]}" class="btn-rojo">S/A</a></td>' if user['rango'] == "Administrador" else "<td>-</td>"
        tabla += f"<tr><td>{u['clave']}</td><td>{u['nombre']}</td><td>{u['estado']}</td>{acc}</tr>"
    return f'''{CSS}<div class="menu-box"><h3>👥 USUARIOS</h3>{tabla+"</table>"}<hr><form action="/add_user" method="post"><input type="hidden" name="admin_clave" value="{clave}"><input type="hidden" name="rango" value="{rango_dest}"><input name="nombre" placeholder="Nombre"><button type="submit">AÑADIR</button></form>
    <form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

@app.route('/status/<admin>/<target>')
def status(admin, target):
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (target,)).fetchone()
    nuevo = "Activo" if u['estado'] == "Suspendido" else "Suspendido"
    with db_u:
        db_u.execute("UPDATE usuarios SET estado = ? WHERE clave = ?", (nuevo, target))
        db_u.execute("UPDATE usuarios SET estado = ? WHERE creado_por = ?", (nuevo, target))
    return redirect(f"/usuarios/{admin}")

@app.route('/add_user', methods=['POST'])
def add_user():
    admin, nom, rango = request.form.get('admin_clave'), request.form.get('nombre'), request.form.get('rango')
    clv = f"{nom[:3].upper()}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    db_u = iniciar_db_usuarios()
    with db_u: db_u.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?,?,?,?,?)", (clv, nom, rango, admin, "Activo"))
    return f"{CSS}<div class='menu-box'>✅ CLAVE: {clv}<br><a href='/' class='btn-volver'>LOGIN</a></div>"

@app.route('/config/<clave>')
def config(clave):
    db = iniciar_db(f"tienda_{clave}.db")
    c = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()
    return f'''{CSS}<div class="menu-box"><h3>⚙️ CONFIG</h3><form action="/upd_conf" method="post"><input type="hidden" name="clave" value="{clave}"><input name="nn" value="{c['nombre_negocio']}"><input name="nt" value="{c['telefono_dueno']}"><button type="submit">GUARDAR</button></form>
    <form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

@app.route('/upd_conf', methods=['POST'])
def upd_conf():
    clave, nn, nt = request.form.get('clave'), request.form.get('nn'), request.form.get('nt')
    db = iniciar_db(f"tienda_{clave}.db")
    with db: db.execute("UPDATE configuracion SET nombre_negocio=?, telefono_dueno=? WHERE id=1", (nn, nt))
    return redirect(f"/config/{clave}")

@app.route('/pago_proveedor/<clave>')
def pago_proveedor(clave):
    return f'''{CSS}<div class="menu-box"><h3>🚚 GASTOS</h3><form action="/reg_gasto" method="post"><input type="hidden" name="clave" value="{clave}"><input name="prov" placeholder="Concepto"><input type="number" step="0.1" name="monto" placeholder="Monto"><button type="submit">PAGAR</button></form>
    <form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

@app.route('/reg_gasto', methods=['POST'])
def reg_gasto():
    clave, prov, monto = request.form.get('clave'), request.form.get('prov'), request.form.get('monto')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    with db: db.execute("INSERT INTO gastos (concepto, monto, fecha) VALUES (?, ?, ?)", (prov, monto, datetime.now().strftime("%Y-%m-%d")))
    return redirect(f"/pago_proveedor/{clave}")

@app.route('/corte/<clave>')
def corte(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['clave']}.db")
    conf = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()
    v = db.execute("SELECT SUM(total) as t FROM ventas WHERE fecha LIKE ?", (f"{datetime.now().strftime('%Y-%m-%d')}%",)).fetchone()['t'] or 0
    g = db.execute("SELECT SUM(monto) as t FROM gastos WHERE fecha LIKE ?", (f"{datetime.now().strftime('%Y-%m-%d')}%",)).fetchone()['t'] or 0
    msg = f"📊 CORTE {conf['nombre_negocio']}\\n💰 TOTAL: ${v-g}"
    url = f"https://api.whatsapp.com/send?phone=52{conf['telefono_dueno']}&text={urllib.parse.quote(msg)}"
    return f'''{CSS}<div class="menu-box"><h3>📊 CORTE</h3><p>Neto: ${v-g}</p><a href='{url}' class='opcion' target='_blank'>📲 MANDAR CORTE AL DUEÑO</a><form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

if __name__ == "__main__":
    iniciar_db_usuarios()
    iniciar_db()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
            
