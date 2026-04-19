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
    .btn-whatsapp { background: #25D366; color: #fff; text-align: center; padding: 15px; text-decoration: none; display: block; font-weight: bold; border-radius: 5px; margin-top: 10px; }
    .btn-excel { background: #1D6F42; color: #fff; text-align: center; padding: 10px; text-decoration: none; display: block; margin-top: 10px; font-size: 0.9em; }
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
    return "Acceso denegado."

# --- VENTAS Y TICKET PRO ---

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
    
    tabla = "<table><tr><th>Prod</th><th>Cant</th><th>Sub</th></tr>"
    for i, it in enumerate(carrito):
        tabla += f"<tr><td>{it['nombre']}</td><td>{it['cantidad']}</td><td>${it['subtotal']}</td></tr>"
    tabla += "</table>"

    return f'''{CSS}<div class="menu-box"><h3>🛒 CAJA</h3>
        <form action="/agregar" method="post"><select name="cod">{opciones}</select>
        <input type="number" step="0.1" name="cant" placeholder="Cantidad/Dinero" required><button type="submit">AGREGAR</button></form>
        {tabla}<h4>TOTAL: ${total}</h4>
        {f'<a href="/confirmar" class="opcion" style="background:#0f0; color:#000; text-align:center">--- COBRAR ---</a>' if carrito else ''}
        <form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

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
        carrito.append({'nombre': p['nombre'], 'cantidad': round(cant_stock, 2), 'subtotal': subtotal, 'unidad': p['unidad']})
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
    
    # DISEÑO DE TICKET PRO
    ticket = f"🧾 *{conf['nombre_negocio']}* \n"
    ticket += f"📅 {ahora}\n"
    ticket += f"👤 Atendió: {user['nombre']}\n"
    ticket += "--------------------------\n"
    
    with db:
        for it in carrito:
            ticket += f"• {it['nombre']} ({it['cantidad']}): ${it['subtotal']}\n"
            db.execute("INSERT INTO ventas (total, fecha, vendedor) VALUES (?,?,?)", (it['subtotal'], ahora, user['nombre']))
    
    ticket += "--------------------------\n"
    ticket += f"💰 *TOTAL: ${total}*\n\n"
    ticket += "🙏 ¡Gracias por su compra!"
    
    session['ticket_pendiente'] = ticket
    session['carrito'] = []

    return f'''{CSS}<div class="menu-box"><h3>✅ VENTA GUARDADA</h3>
        <form action="/enviar_ticket" method="post"><input type="text" name="tel" placeholder="Número del Cliente" required>
        <button type="submit">GENERAR WHATSAPP</button></form>
        <a href="/venta" class="btn-volver">VOLVER SIN ENVIAR</a></div>'''

@app.route('/enviar_ticket', methods=['POST'])
def enviar_ticket():
    tel = request.form.get('tel')
    ticket = session.get('ticket_pendiente', '')
    url_wa = f"https://api.whatsapp.com/send?phone=52{tel}&text={urllib.parse.quote(ticket)}"
    return f'''{CSS}<div class="menu-box"><h3>🔗 LISTO</h3><a href="{url_wa}" target="_blank" class="btn-whatsapp">ENVIAR TICKET</a><br><a href="/venta" class="btn-volver">NUEVA VENTA</a></div>'''

# --- CORTE DE CAJA PRO + EXCEL ---

@app.route('/corte/<clave>')
def corte(clave):
    db = iniciar_db(f"tienda_{clave}.db")
    conf = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    
    ventas = db.execute("SELECT * FROM ventas WHERE fecha LIKE ?", (f"{fecha_hoy}%",)).fetchall()
    gastos = db.execute("SELECT * FROM gastos WHERE fecha LIKE ?", (f"{datetime.now().strftime('%Y-%m-%d')}%",)).fetchall()
    
    total_v = sum(v['total'] for v in ventas)
    total_g = sum(g['monto'] for g in gastos)
    
    # DISEÑO DE CORTE PRO
    corte_msg = f"📊 *CORTE DE CAJA: {conf['nombre_negocio']}*\n"
    corte_msg += f"📅 Fecha: {fecha_hoy}\n"
    corte_msg += "--------------------------\n"
    corte_msg += f"✅ Ventas: ${total_v}\n"
    corte_msg += f"🛑 Gastos: ${total_g}\n"
    corte_msg += "--------------------------\n"
    corte_msg += f"💵 *EFECTIVO EN CAJA: ${total_v - total_g}*\n\n"
    
    if gastos:
        corte_msg += "🚛 *DETALLE DE GASTOS:*\n"
        for g in gastos: corte_msg += f"• {g['concepto']}: ${g['monto']}\n"

    url_wa = f"https://api.whatsapp.com/send?phone=52{conf['telefono_dueno']}&text={urllib.parse.quote(corte_msg)}"
    
    return f'''{CSS}<div class="menu-box"><h3>📊 CORTE DE HOY</h3>
        <p>Ventas: ${total_v}</p><p>Gastos: ${total_g}</p><h3>TOTAL: ${total_v - total_g}</h3>
        <a href="{url_wa}" target="_blank" class="btn-whatsapp">📲 MANDAR CORTE WHATSAPP</a>
        <a href="/descargar_excel/{clave}" class="btn-excel">📥 DESCARGAR REPORTE EXCEL</a>
        <form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

@app.route('/descargar_excel/<clave>')
def descargar_excel(clave):
    db = iniciar_db(f"tienda_{clave}.db")
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    ventas = db.execute("SELECT * FROM ventas WHERE fecha LIKE ?", (f"{fecha_hoy}%",)).fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID VENTA', 'FECHA', 'VENDEDOR', 'TOTAL'])
    for v in ventas:
        writer.writerow([v['id'], v['fecha'], v['vendedor'], v['total']])
    
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), 
                     mimetype='text/csv', 
                     as_attachment=True, 
                     download_name=f'Corte_{fecha_hoy.replace("/","-")}.csv')

# --- EL RESTO DEL CÓDIGO (CONFIG, STOCK, ETC) SIGUE IGUAL ---

@app.route('/inventario/<clave>')
def inventario(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    prods = db.execute("SELECT * FROM productos").fetchall()
    tabla = "<table><tr><th>COD</th><th>NOM</th><th>PRE</th><th>STK</th></tr>"
    for p in prods: tabla += f"<tr><td>{p['codigo']}</td><td>{p['nombre']}</td><td>${p['precio']}</td><td>{p['stock']}</td></tr>"
    tabla += "</table>"
    form = f'''<hr><form action="/add_prod" method="post"><input type="hidden" name="clave" value="{clave}"><input name="cod" placeholder="Cod"><input name="nom" placeholder="Nombre"><input type="number" step="0.1" name="pre" placeholder="Precio"><input type="number" step="0.1" name="sto" placeholder="Stock"><select name="uni"><option value="p">Pieza</option><option value="k">Kilo</option></select><button type="submit">GUARDAR</button></form>''' if user['rango'] != 'Trabajador' else ""
    return f'''{CSS}<div class="menu-box"><h3>📦 STOCK</h3>{tabla}{form}<form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

@app.route('/add_prod', methods=['POST'])
def add_prod():
    clave = request.form.get('clave')
    db = iniciar_db(f"tienda_{clave}.db")
    with db: db.execute("INSERT OR REPLACE INTO productos (codigo, nombre, precio, stock, min_compra, unidad) VALUES (?,?,?,?,?,?)", (request.form.get('cod'), request.form.get('nom'), request.form.get('pre'), request.form.get('sto'), 0, request.form.get('uni')))
    return redirect(f"/inventario/{clave}")

@app.route('/config/<clave>')
def config(clave):
    db = iniciar_db(f"tienda_{clave}.db")
    c = db.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()
    return f'''{CSS}<div class="menu-box"><h3>⚙️ CONFIG</h3><form action="/upd_conf" method="post"><input type="hidden" name="clave" value="{clave}"><input name="nn" value="{c['nombre_negocio']}"><input name="nt" value="{c['telefono_dueno']}"><button type="submit">GUARDAR</button></form><form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

@app.route('/upd_conf', methods=['POST'])
def upd_conf():
    clave, nn, nt = request.form.get('clave'), request.form.get('nn'), request.form.get('nt')
    db = iniciar_db(f"tienda_{clave}.db")
    with db: db.execute("UPDATE configuracion SET nombre_negocio=?, telefono_dueno=? WHERE id=1", (nn, nt))
    return redirect(f"/config/{clave}")

@app.route('/usuarios/<clave>')
def gestionar_usuarios(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    rango_dest = "Dueño" if user['rango'] == "Administrador" else "Trabajador"
    mi_rama = db_u.execute("SELECT * FROM usuarios WHERE creado_por = ?", (clave,)).fetchall()
    tabla = "<table><tr><th>CLAVE</th><th>NOM</th><th>EST</th></tr>"
    for u in mi_rama: tabla += f"<tr><td>{u['clave']}</td><td>{u['nombre']}</td><td>{u['estado']}</td></tr>"
    return f'''{CSS}<div class="menu-box"><h3>👥 USUARIOS</h3>{tabla+"</table>"}<hr><form action="/add_user" method="post"><input type="hidden" name="admin_clave" value="{clave}"><input type="hidden" name="rango" value="{rango_dest}"><input name="nombre" placeholder="Nombre"><button type="submit">AÑADIR</button></form><form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

@app.route('/add_user', methods=['POST'])
def add_user():
    admin, nom, rango = request.form.get('admin_clave'), request.form.get('nombre'), request.form.get('rango')
    clv = f"{nom[:3].upper()}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    db_u = iniciar_db_usuarios()
    with db_u: db_u.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?,?,?,?,?)", (clv, nom, rango, admin, "Activo"))
    return f"{CSS}<div class='menu-box'>✅ CLAVE: {clv}<br><a href='/' class='btn-volver'>LOGIN</a></div>"

@app.route('/pago_proveedor/<clave>')
def pago_proveedor(clave):
    return f'''{CSS}<div class="menu-box"><h3>🚚 GASTOS</h3><form action="/reg_gasto" method="post"><input type="hidden" name="clave" value="{clave}"><input name="prov" placeholder="Concepto"><input type="number" step="0.1" name="monto" placeholder="Monto"><button type="submit">PAGAR</button></form><form action="/verificar" method="post"><input type="hidden" name="clave" value="{clave}"><button type="submit" class="btn-volver">VOLVER</button></form></div>'''

@app.route('/reg_gasto', methods=['POST'])
def reg_gasto():
    clave, prov, monto = request.form.get('clave'), request.form.get('prov'), request.form.get('monto')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db = iniciar_db(f"tienda_{user['creado_por'] if user['rango'] == 'Trabajador' else user['clave']}.db")
    with db: db.execute("INSERT INTO gastos (concepto, monto, fecha) VALUES (?, ?, ?)", (prov, monto, datetime.now().strftime("%Y-%m-%d")))
    return redirect(f"/pago_proveedor/{clave}")

if __name__ == "__main__":
    iniciar_db_usuarios()
    iniciar_db()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
    
