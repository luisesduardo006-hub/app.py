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
app.secret_key = 'sistema_estable_v8'

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Esto evita que el sistema se rompa si intentas entrar a una ruta sin loguearte
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
    .btn-rojo { background: #f00; color: #fff; padding: 5px 10px; text-decoration: none; font-size: 0.8em; border-radius: 3px; }
    .btn-pagar { background: #25D366; color: #000; padding: 5px 10px; text-decoration: none; font-weight: bold; font-size: 0.8em; border-radius: 3px; }
    .btn-volver { border: 1px solid #0f0; color: #0f0; padding: 12px; display: block; text-align: center; text-decoration: none; margin-top: 15px; }
    .vencido { background: #200; }
</style>
'''

# --- RUTAS DE ACCESO ---

@app.route('/')
def login_screen():
    session.clear()
    return f'''{CSS}<div class="menu-box"><h3>🔑 ACCESO AL SISTEMA</h3>
    <form action="/verificar" method="post"><input type="text" name="clave" placeholder="INGRESE SU CLAVE" autofocus required><button type="submit">ENTRAR AL PANEL</button></form></div>'''

# CORRECCIÓN PARA EL ERROR 405: Agregamos GET
@app.route('/verificar', methods=['GET', 'POST'])
def verificar():
    # Intentamos obtener la clave del formulario o de la sesión actual
    clave = request.form.get('clave') or session.get('usuario_clave')
    
    if not clave:
        return redirect('/')

    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user:
        vence_str = user['vencimiento']
        if user['rango'] == 'Trabajador':
            dueno = db_u.execute("SELECT vencimiento FROM usuarios WHERE clave = ?", (user['creado_por'],)).fetchone()
            vence_str = dueno['vencimiento']
        
        # Validar si el tiempo expiró
        try:
            v_dt = datetime.strptime(vence_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > v_dt or user['estado'] != "Activo":
                return f"{CSS}<div class='menu-box'><h2 style='color:red'>🛑 CUENTA INACTIVA</h2><p>Vencimiento: {vence_str}</p><a href='/' class='btn-volver'>VOLVER AL INICIO</a></div>"
        except: pass

        # Guardar en sesión para evitar que el 405 rompa la navegación
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
                menu += f'<a class="opcion" href="/hacer_corte_final/{clave}" onclick="return confirm(\'¿Hacer corte? Se limpiará el día y se bajará el Excel.\')">🏁 REALIZAR CORTE FINAL</a>'
        
        menu += '<hr><a class="opcion" href="/" style="color:#f00; border:1px solid #f00; text-align:center;">CERRAR SESIÓN SEGURA</a></div>'
        return menu
    return redirect('/')

# --- FUNCIONES DE ADMINISTRACIÓN ---

@app.route('/gestionar_negocios/<clave>')
def gestionar_negocios(clave):
    if not login_requerido(): return redirect('/')
    db_u = iniciar_db_usuarios()
    duenos = db_u.execute("SELECT * FROM usuarios WHERE rango = 'Dueño' ORDER BY vencimiento ASC").fetchall()
    tabla = "<table><tr><th>DUEÑO</th><th>STATUS / TIEMPO</th><th>ACCIÓN</th></tr>"
    for d in duenos:
        timer = tiempo_restante(d['vencimiento'])
        clase = 'class="vencido"' if "❌" in timer else ''
        btn_renovar = f'<a href="/renovar/{clave}/{d["clave"]}" class="btn-pagar">+30 DÍAS</a>'
        btn_susp = f'<a href="/status_cascada/{clave}/{d["clave"]}" class="btn-rojo">SWITCH</a>'
        tabla += f'<tr {clase}><td>{d["nombre"]}<br><small>{d["clave"]}</small></td><td>{d["estado"]}<br>{timer}</td><td>{btn_renovar} {btn_susp}</td></tr>'
    
    return f'''{CSS}<div class="menu-box"><h3>🏢 ADMINISTRACIÓN DE CLIENTES</h3>{tabla+"</table>"}<hr>
    <form action="/add_user" method="post"><input type="hidden" name="admin_clave" value="{clave}"><input type="hidden" name="rango" value="Dueño"><input name="nombre" placeholder="Nombre del Negocio" required><button type="submit">REGISTRAR NUEVO CLIENTE</button></form>
    <a href="/verificar" class="btn-volver">VOLVER AL PANEL</a></div>'''

@app.route('/usuarios/<clave>')
def gestionar_usuarios(clave):
    if not login_requerido(): return redirect('/')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user['rango'] == "Super Admin":
        admins = db_u.execute("SELECT * FROM usuarios WHERE rango = 'Administrador'").fetchall()
        tabla = "<table><tr><th>ADMIN</th><th>COBROS EXITO</th><th>ACCIÓN</th></tr>"
        for a in admins:
            form_ed = f'<form action="/update_counter" method="post" style="display:flex;"><input type="hidden" name="admin_clave" value="{clave}"><input type="hidden" name="target" value="{a["clave"]}"><input type="number" name="val" value="{a["reactivaciones"]}" style="width:60px;"><button type="submit">💾</button></form>'
            tabla += f'<tr><td>{a["nombre"]}</td><td>{form_ed}</td><td><a href="/borrar/{clave}/{a["clave"]}" class="btn-rojo">ELIMINAR</a></td></tr>'
        titulo, r_crear = "CONTROL DE ADMINISTRADORES", "Administrador"
    elif user['rango'] == "Dueño":
        trbs = db_u.execute("SELECT * FROM usuarios WHERE creado_por = ?", (clave,)).fetchall()
        tabla = "<table><tr><th>NOMBRE</th><th>ESTADO</th><th>ACCIÓN</th></tr>"
        for t in trbs:
            accion = f'<a href="/status_simple/{clave}/{t["clave"]}" class="btn-rojo">ESTADO</a>'
            tabla += f'<tr><td>{t["nombre"]}</td><td>{t["estado"]}</td><td>{accion}</td></tr>'
        titulo, r_crear = "GESTIÓN DE PERSONAL", "Trabajador"
    else: return redirect('/')

    return f'''{CSS}<div class="menu-box"><h3>👥 {titulo}</h3>{tabla+"</table>"}<hr>
    <form action="/add_user" method="post"><input type="hidden" name="admin_clave" value="{clave}"><input type="hidden" name="rango" value="{r_crear}"><input name="nombre" placeholder="Nombre completo" required><button type="submit">AÑADIR NUEVO</button></form>
    <a href="/verificar" class="btn-volver">VOLVER</a></div>'''

# --- PROCESO DE CORTE UNIFICADO ---

@app.route('/hacer_corte_final/<clave>')
def hacer_corte_final(clave):
    if not login_requerido(): return redirect('/')
    db_t = iniciar_db_tienda(f"tienda_{clave}.db")
    ventas = db_t.execute("SELECT * FROM ventas").fetchall()
    gastos_row = db_t.execute("SELECT sum(monto) as t FROM gastos").fetchone()
    gastos = gastos_row['t'] or 0
    total_v = sum(v['total'] for v in ventas)
    ahora_fn = datetime.now().strftime("%d-%m-%Y_%H-%M")
    
    # 1. Generación de Excel
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['REPORTE DE VENTAS DETALLADO', ahora_fn])
    writer.writerow(['ID_VENTA', 'MONTO', 'HORA', 'CAJERO'])
    for v in ventas: writer.writerow([v['id'], v['total'], v['fecha'], v['vendedor']])
    
    if not os.path.exists('cortes'): os.makedirs('cortes')
    nombre_csv = f"cortes/Corte_{clave}_{ahora_fn}.csv"
    with open(nombre_csv, 'w', encoding='utf-8-sig', newline='') as f: f.write(output.getvalue())
    
    # 2. Reseteo de tablas
    with db_t:
        db_t.execute("DELETE FROM ventas")
        db_t.execute("DELETE FROM gastos")
    
    conf = db_t.execute("SELECT * FROM configuracion WHERE id=1").fetchone()
    resumen = f"🏁 *CORTE AUTOMÁTICO*\n💰 Ventas: ${total_v}\n💸 Gastos: ${gastos}\n📈 Neto: ${total_v-gastos}\n📂 Archivo Excel generado."
    url_wa = f"https://api.whatsapp.com/send?phone={conf['telefono_dueno']}&text={urllib.parse.quote(resumen)}"
    
    return f'''{CSS}<div class="menu-box"><h3>📊 CORTE REALIZADO</h3><p>{resumen}</p>
    <a href="{url_wa}" target="_blank" class="btn-pagar">NOTIFICAR POR WHATSAPP</a><br><br>
    <a href="/descargar/{nombre_csv.replace('/','_')}" class="btn-volver" style="background:#1D7145; color:white;">📥 DESCARGAR EXCEL AHORA</a>
    <a href="/verificar" class="btn-volver">REGRESAR AL MENÚ</a></div>'''

# --- RUTAS DE ACCIONES SECUNDARIAS ---

@app.route('/add_user', methods=['POST'])
def add_user():
    adm, nom, rango = request.form['admin_clave'], request.form['nombre'], request.form['rango']
    clv = f"{rango[:3].upper()}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"
    vence = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S") if rango == 'Dueño' else "2099-12-31 23:59:59"
    with iniciar_db_usuarios() as db:
        db.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado, vencimiento) VALUES (?,?,?,?,?,?)", (clv, nom, rango, adm, "Activo", vence))
    return f"{CSS}<div class='menu-box'><h3>✅ REGISTRO ÉXITOSO</h3><p>Clave generada: <strong>{clv}</strong></p><p>Favor de guardarla, no se volverá a mostrar.</p><a href='/' class='btn-volver'>IR AL LOGIN</a></div>"

@app.route('/renovar/<admin>/<target>')
def renovar(admin, target):
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT vencimiento FROM usuarios WHERE clave = ?", (target,)).fetchone()
    actual = datetime.strptime(u['vencimiento'], "%Y-%m-%d %H:%M:%S")
    inicio = actual if actual > datetime.now() else datetime.now()
    nueva = (inicio + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    with db_u:
        db_u.execute("UPDATE usuarios SET vencimiento = ?, estado = 'Activo' WHERE clave = ?", (nueva, target))
        db_u.execute("UPDATE usuarios SET reactivaciones = reactivaciones + 1 WHERE clave = ?", (admin,))
    return redirect(f"/gestionar_negocios/{admin}")

@app.route('/update_counter', methods=['POST'])
def update_counter():
    with iniciar_db_usuarios() as db:
        db.execute("UPDATE usuarios SET reactivaciones = ? WHERE clave = ?", (request.form['val'], request.form['target']))
    return redirect(f"/usuarios/{request.form['admin_clave']}")

@app.route('/status_cascada/<admin>/<target>')
def status_cascada(admin, target):
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT estado FROM usuarios WHERE clave = ?", (target,)).fetchone()
    nuevo = "Activo" if u['estado'] == "Suspendido" else "Suspendido"
    with db_u:
        db_u.execute("UPDATE usuarios SET estado = ? WHERE clave = ?", (nuevo, target))
        db_u.execute("UPDATE usuarios SET estado = ? WHERE creado_por = ?", (nuevo, target))
    return redirect(f"/gestionar_negocios/{admin}")

@app.route('/descargar/<path_file>')
def descargar(path_file):
    return send_file(path_file.replace('_','/'), as_attachment=True)

# --- OPERACIONES DE TIENDA (VENTA E INVENTARIO) ---

@app.route('/venta')
def vista_venta():
    if not login_requerido(): return redirect('/')
    clv = session.get('usuario_clave')
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clv,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    prods = db.execute("SELECT * FROM productos WHERE stock > 0").fetchall()
    opcs = "".join([f"<option value='{p['codigo']}'>{p['nombre']} (${p['precio']})</option>" for p in prods])
    car = session.get('carrito', [])
    tabla = "<table>" + "".join([f"<tr><td>{i['n']}</td><td>x{i['c']}</td><td>${i['s']}</td></tr>" for i in car]) + "</table>"
    return f'''{CSS}<div class="menu-box"><h3>🛒 PUNTO DE VENTA</h3><form action="/add_car" method="post"><select name="cod">{opcs}</select><input type="number" step="0.1" name="cnt" placeholder="Cantidad o Dinero"><button>AÑADIR AL CARRITO</button></form>{tabla}<h4>TOTAL: ${sum(i['s'] for i in car)}</h4><a href="/cobrar" class="btn-pagar" style="font-size:1.5em; text-align:center; display:block;">💵 FINALIZAR VENTA</a><a href="/verificar" class="btn-volver">VOLVER AL MENÚ</a></div>'''

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

@app.route('/inventario/<clave>')
def inventario(clave):
    if not login_requerido(): return redirect('/')
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    prods = db.execute("SELECT * FROM productos").fetchall()
    tabla = "<table><tr><th>COD</th><th>PRODUCTO</th><th>STOCK</th></tr>" + "".join([f"<tr><td>{p['codigo']}</td><td>{p['nombre']}<br>${p['precio']}</td><td>{p['stock']} {p['unidad']}</td></tr>" for p in prods]) + "</table>"
    form = f'<hr><h4>ALTAS / MODIFICACIONES</h4><form action="/add_p" method="post"><input type="hidden" name="cl" value="{clave}"><input name="co" placeholder="Código"><input name="no" placeholder="Nombre"><input name="pr" placeholder="Precio"><input name="st" placeholder="Stock"><select name="un"><option value="p">Pieza</option><option value="k">Kilo</option></select><button>GUARDAR PRODUCTO</button></form>' if u['rango'] == 'Dueño' else ""
    return f"{CSS}<div class='menu-box'><h3>📦 INVENTARIO ACTUAL</h3>{tabla}{form}<a href='/verificar' class='btn-volver'>REGRESAR</a></div>"

@app.route('/add_p', methods=['POST'])
def add_p():
    with iniciar_db_tienda(f"tienda_{request.form['cl']}.db") as db:
        db.execute("INSERT OR REPLACE INTO productos VALUES (?,?,?,?,?)", (request.form['co'], request.form['no'], request.form['pr'], request.form['st'], request.form['un']))
    return redirect(f"/inventario/{request.form['cl']}")

@app.route('/status_simple/<admin>/<target>')
def status_simple(admin, target):
    db = iniciar_db_usuarios()
    u = db.execute("SELECT estado FROM usuarios WHERE clave=?", (target,)).fetchone()
    new = "Activo" if u['estado'] == "Suspendido" else "Suspendido"
    with db: db.execute("UPDATE usuarios SET estado=? WHERE clave=?", (new, target))
    return redirect(f"/usuarios/{admin}")

@app.route('/borrar/<admin>/<target>')
def borrar(admin, target):
    with iniciar_db_usuarios() as db: db.execute("DELETE FROM usuarios WHERE clave=?", (target,))
    return redirect(f"/usuarios/{admin}")

@app.route('/config_corte/<clave>', methods=['GET', 'POST'])
def config_corte(clave):
    if not login_requerido(): return redirect('/')
    db = iniciar_db_tienda(f"tienda_{clave}.db")
    if request.method == 'PO
