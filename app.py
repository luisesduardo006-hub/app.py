import sqlite3
from datetime import datetime
import urllib.parse
import random
import string
import os
import csv
import io
from flask import Flask, request, render_template_string, redirect, session, send_file

app = Flask(__name__)
app.secret_key = 'clave_secreta_punto_venta_v5'

# --- BASE DE DATOS ---
def iniciar_db(nombre_db='punto_venta_v5.db'):
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
            conn.execute("INSERT INTO configuracion (id, nombre_negocio, direccion, min_compra, porc_desc, telefono_dueno) VALUES (1, 'NUEVO NEGOCIO', 'Direccion', 0, 0, '')")
    return conn

def iniciar_db_usuarios():
    conn = sqlite3.connect('usuarios_sistema.db')
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                     (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, creado_por TEXT, estado TEXT)''')
        # CLAVE MAESTRA
        conn.execute("INSERT OR REPLACE INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?, ?, ?, ?, ?)", 
                     ("ROOT-XYZ7", "SUPER ADMIN", "Super Admin", "SISTEMA", "Activo"))
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
    table { width: 100%; border-collapse: collapse; margin-top: 10px; color: #0f0; font-size: 0.9em; }
    th, td { border: 1px solid #0f0; padding: 8px; text-align: left; }
    .btn-rojo { background: #f00; color: #fff; padding: 5px; text-decoration: none; border: none; cursor: pointer; border-radius: 3px; }
    .btn-gris { background: #444; color: #fff; padding: 5px; text-decoration: none; border: none; cursor: pointer; border-radius: 3px; }
    .btn-volver { background: none; border: 1px solid #0f0; color: #0f0; padding: 10px; width: 100%; margin-top: 10px; cursor: pointer; font-weight: bold; display: block; text-align: center; text-decoration: none; }
</style>
'''

@app.route('/')
def login_screen():
    session.clear()
    return f'''{CSS}
    <div class="menu-box">
        <p>===================================</p>
        <p>🔑 LOGIN CENTRALIZADO V5</p>
        <p>===================================</p>
        <form action="/verificar" method="post">
            <input type="text" name="clave" placeholder="CLAVE DE ACCESO" autofocus required>
            <button type="submit">ENTRAR AL SISTEMA</button>
        </form>
    </div>'''

@app.route('/verificar', methods=['POST'])
def verificar():
    clave = request.form.get('clave') or session.get('usuario_clave')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user and user['estado'] == "Activo":
        session['usuario_clave'] = clave
        # Los trabajadores usan la DB de su dueño, los demás la suya propia
        db_n = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
        db = iniciar_db(db_n)
        conf = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()

        menu = f"{CSS}<div class='menu-box'><h3>--- {conf['nombre_negocio']} ---</h3><p>USUARIO: {user['nombre']} | RANGO: {user['rango']}</p><hr>"
        
        if user['rango'] == 'Super Admin':
            menu += f'<a class="opcion" href="/usuarios/{clave}">1. GESTIONAR ADMINISTRADORES (BORRAR)</a>'
            menu += f'<a class="opcion" href="/gestionar_negocios/{clave}">2. GESTIONAR TODOS LOS DUEÑOS</a>'
        
        elif user['rango'] == 'Administrador':
            menu += f'<a class="opcion" href="/gestionar_negocios/{clave}">1. GESTIONAR TODOS LOS DUEÑOS</a>'
            
        elif user['rango'] in ['Dueño', 'Trabajador']:
            menu += '<a class="opcion" href="/venta">1. CAJA DE COBRO</a>'
            menu += f'<a class="opcion" href="/inventario/{clave}">2. VER INVENTARIO</a>'
            menu += f'<a class="opcion" href="/pago_proveedor/{clave}">3. REGISTRAR GASTO</a>'
            if user['rango'] == 'Dueño':
                menu += f'<a class="opcion" href="/usuarios/{clave}">4. GESTIONAR EMPLEADOS</a>'
                menu += f'<a class="opcion" href="/config/{clave}">5. AJUSTES DE TIENDA</a>'
                menu += f'<a class="opcion" href="/corte/{clave}">6. CORTE DE CAJA</a>'
        
        menu += '<hr><a class="opcion" href="/">🚪 CERRAR SESIÓN</a></div>'
        return menu
    return f"{CSS}<div class='menu-box'><p style='color:red'>⚠️ ACCESO DENEGADO (CLAVE INVÁLIDA O CUENTA SUSPENDIDA)</p><a href='/' class='btn-volver'>REINTENTAR</a></div>"

# --- GESTIÓN DE DUEÑOS (TODOS LOS ADMINS VEN TODO) ---
@app.route('/gestionar_negocios/<clave>')
def gestionar_negocios(clave):
    db_u = iniciar_db_usuarios()
    # Todos los administradores ven a todos los dueños
    duenos = db_u.execute("SELECT * FROM usuarios WHERE rango = 'Dueño'").fetchall()
    
    tabla = "<table><tr><th>CLAVE</th><th>NOMBRE</th><th>ESTADO</th><th>ACCIÓN CASCADA</th></tr>"
    for d in duenos:
        accion = f'<a href="/status_cascada/{clave}/{d["clave"]}" class="btn-rojo">{"SUSPENDER RAMA" if d["estado"]=="Activo" else "ACTIVAR RAMA"}</a>'
        tabla += f"<tr><td>{d['clave']}</td><td>{d['nombre']}</td><td>{d['estado']}</td><td>{accion}</td></tr>"
    
    return f'''{CSS}<div class="menu-box"><h3>🏢 GESTIÓN GLOBAL DE DUEÑOS</h3>{tabla+"</table>"}<hr>
    <form action="/add_user" method="post"><input type="hidden" name="admin_clave" value="{clave}"><input type="hidden" name="rango" value="Dueño"><input name="nombre" placeholder="Nombre del nuevo Dueño" required><button type="submit">CREAR NUEVO NEGOCIO</button></form>
    <form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER AL MENÚ</button></form></div>'''

# --- GESTIÓN DE ADMINS (SOLO SUPER ADMIN) Y TRABAJADORES (SOLO DUEÑOS) ---
@app.route('/usuarios/<clave>')
def gestionar_usuarios(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user['rango'] == "Super Admin":
        rango_a_crear, titulo = "Administrador", "ADMINISTRADORES DEL SISTEMA"
        mi_rama = db_u.execute("SELECT * FROM usuarios WHERE rango = 'Administrador'").fetchall()
    elif user['rango'] == "Dueño":
        rango_a_crear, titulo = "Trabajador", "MIS TRABAJADORES"
        mi_rama = db_u.execute("SELECT * FROM usuarios WHERE creado_por = ?", (clave,)).fetchall()
    else: return redirect('/')

    tabla = "<table><tr><th>CLAVE</th><th>NOMBRE</th><th>ESTADO</th><th>ACCIÓN</th></tr>"
    for u in mi_rama:
        if user['rango'] == "Super Admin":
            # Botón BORRAR para Administradores
            accion = f'<a href="/borrar/{clave}/{u["clave"]}" class="btn-rojo" onclick="return confirm(\'¿Eliminar administrador permanentemente?\')">BORRAR</a>'
        else:
            # Botón SUSPENDER independiente para Trabajadores
            accion = f'<a href="/status_simple/{clave}/{u["clave"]}" class="btn-gris">{"SUSPENDER" if u["estado"]=="Activo" else "ACTIVAR"}</a>'
        
        tabla += f"<tr><td>{u['clave']}</td><td>{u['nombre']}</td><td>{u['estado']}</td><td>{accion}</td></tr>"
    
    return f'''{CSS}<div class="menu-box"><h3>👥 {titulo}</h3>{tabla+"</table>"}<hr>
    <form action="/add_user" method="post"><input type="hidden" name="admin_clave" value="{clave}"><input type="hidden" name="rango" value="{rango_a_crear}"><input name="nombre" placeholder="Nombre completo" required><button type="submit">AÑADIR NUEVO</button></form>
    <form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

# --- ACCIONES DE ESTADO ---

@app.route('/status_cascada/<admin>/<target>')
def status_cascada(admin, target):
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (target,)).fetchone()
    nuevo_estado = "Activo" if u['estado'] == "Suspendido" else "Suspendido"
    with db_u:
        # Suspende al dueño
        db_u.execute("UPDATE usuarios SET estado = ? WHERE clave = ?", (nuevo_estado, target))
        # Suspende a todos sus trabajadores (toda la rama)
        db_u.execute("UPDATE usuarios SET estado = ? WHERE creado_por = ?", (nuevo_estado, target))
    return redirect(f"/gestionar_negocios/{admin}")

@app.route('/status_simple/<admin>/<target>')
def status_simple(admin, target):
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (target,)).fetchone()
    nuevo_estado = "Activo" if u['estado'] == "Suspendido" else "Suspendido"
    with db_u:
        db_u.execute("UPDATE usuarios SET estado = ? WHERE clave = ?", (nuevo_estado, target))
    return redirect(f"/usuarios/{admin}")

@app.route('/borrar/<admin>/<target>')
def borrar(admin, target):
    db_u = iniciar_db_usuarios()
    with db_u:
        db_u.execute("DELETE FROM usuarios WHERE clave = ?", (target,))
    return redirect(f"/usuarios/{admin}")

@app.route('/add_user', methods=['POST'])
def add_user():
    admin, nom, rango = request.form.get('admin_clave'), request.form.get('nombre'), request.form.get('rango')
    prefijo = "ADM" if rango == "Administrador" else "DUE" if rango == "Dueño" else "TRB"
    clv = f"{prefijo}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"
    db_u = iniciar_db_usuarios()
    with db_u: 
        db_u.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?,?,?,?,?)", 
                     (clv, nom, rango, admin, "Activo"))
    return f"{CSS}<div class='menu-box'><h3>✅ REGISTRO EXITOSO</h3><p>CLAVE GENERADA: <strong>{clv}</strong></p><hr><a href='/' class='btn-volver'>VOLVER AL LOGIN</a></div>"

# --- FUNCIONES OPERATIVAS (CAJA, INVENTARIO, ETC.) ---

@app.route('/venta')
def vista_venta():
    clave = session.get('usuario_clave')
    if not clave: return redirect('/')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    prods = db.execute("SELECT * FROM productos WHERE stock > 0").fetchall()
    opciones = "".join([f"<option value='{p['codigo']}'>{p['nombre']} (${p['precio']})</option>" for p in prods])
    carrito = session.get('carrito', [])
    total = sum(item['subtotal'] for item in carrito)
    tabla = "<table><tr><th>Producto</th><th>Cant.</th><th>Subtotal</th></tr>"
    for it in carrito:
        tabla += f"<tr><td>{it['nombre']}</td><td>{it['cantidad']}</td><td>${it['subtotal']}</td></tr>"
    return f'''{CSS}<div class="menu-box"><h3>🛒 CAJA DE VENTAS</h3><form action="/agregar" method="post"><select name="cod">{opciones}</select><input type="number" step="0.1" name="cant" placeholder="Cantidad / Dinero" required><button type="submit">AÑADIR</button></form>{tabla+"</table>"}<h4>TOTAL: ${total}</h4><a href="/confirmar" class="opcion" style="background:#0f0; color:#000; text-align:center; padding:10px;">--- COBRAR ---</a><form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

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
        carrito.append({'codigo': cod, 'nombre': p['nombre'], 'cantidad': round(cant_stock, 2), 'subtotal': subtotal})
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
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    ticket = f"🧾 *{conf['nombre_negocio']}*\n📅 {ahora}\n👤 Atendió: {user['nombre']}\n"
    ticket += "--------------------------\n"
    with db:
        for it in carrito:
            db.execute("UPDATE productos SET stock = stock - ? WHERE codigo = ?", (it['cantidad'], it['codigo']))
            db.execute("INSERT INTO ventas (total, fecha, vendedor) VALUES (?,?,?)", (it['subtotal'], ahora, user['nombre']))
            ticket += f"• {it['nombre']}: ${it['subtotal']}\n"
    ticket += f"--------------------------\n💰 *TOTAL: ${total}*"
    session['ticket_pendiente'] = ticket
    session['carrito'] = [] 
    return f'''{CSS}<div class="menu-box"><h3>✅ VENTA REGISTRADA</h3><form action="/enviar_ticket" method="post"><input type="text" name="tel" placeholder="Número WhatsApp Cliente" required><button type="submit">ENVIAR TICKET</button></form></div>'''

@app.route('/enviar_ticket', methods=['POST'])
def enviar_ticket():
    tel, ticket = request.form.get('tel'), session.get('ticket_pendiente', '')
    url_wa = f"https://api.whatsapp.com/send?phone=52{tel}&text={urllib.parse.quote(ticket)}"
    return f'''{CSS}<div class="menu-box"><h3>🔗 LISTO</h3><a href="{url_wa}" target="_blank" class="btn-volver" style="background:#25D366; color:#fff;">ENVIAR POR WHATSAPP</a><br><a href="/venta" class="btn-volver">NUEVA VENTA</a></div>'''

@app.route('/inventario/<clave>')
def inventario(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    prods = db.execute("SELECT * FROM productos").fetchall()
    tabla = "<table><tr><th>COD</th><th>NOMBRE</th><th>PRECIO</th><th>STOCK</th></tr>"
    for p in prods:
        tabla += f"<tr><td>{p['codigo']}</td><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock']}</td></tr>"
    
    form = ""
    if user['rango'] == 'Dueño':
        form = f'''<hr><form action="/add_prod" method="post"><input type="hidden" name="clave" value="{clave}"><input name="cod" placeholder="Código"><input name="nom" placeholder="Nombre"><input type="number" step="0.1" name="pre" placeholder="Precio"><input type="number" step="0.1" name="sto" placeholder="Stock"><select name="uni"><option value="p">Pieza</option><option value="k">Kilo/Dinero</option></select><button type="submit">GUARDAR PRODUCTO</button></form>'''
    
    return f'''{CSS}<div class="menu-box"><h3>📦 INVENTARIO</h3>{tabla+"</table>"}{form}<form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

@app.route('/add_prod', methods=['POST'])
def add_prod():
    clave = request.form.get('clave')
    db = iniciar_db(f"tienda_{clave}.db")
    with db:
        db.execute("INSERT OR REPLACE INTO productos (codigo, nombre, precio, stock, min_compra, unidad) VALUES (?,?,?,?,?,?)", 
                   (request.form.get('cod'), request.form.get('nom'), request.form.get('pre'), request.form.get('sto'), 0, request.form.get('uni')))
    return redirect(f"/inventario/{clave}")

# --- INICIO ---
if __name__ == "__main__":
    iniciar_db_usuarios()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
                
