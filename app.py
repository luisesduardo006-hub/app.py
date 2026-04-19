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
app.secret_key = 'sistema_omni_v7_final'

# --- BASES DE DATOS ---

def iniciar_db_usuarios():
    conn = sqlite3.connect('usuarios_sistema.db')
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                     (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, 
                      creado_por TEXT, estado TEXT, vencimiento TEXT, 
                      reactivaciones INTEGER DEFAULT 0)''')
        # CLAVE MAESTRA INICIAL
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
        return f"⏳ {dif.days}d {dif.seconds // 3600}h restantes"
    except: return "Sin fecha"

CSS = '''
<style>
    body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 20px; font-size: 14px; }
    .menu-box { border: 2px solid #0f0; padding: 20px; max-width: 800px; margin: auto; box-shadow: 0 0 15px #0f0; }
    .opcion { display: block; color: #0f0; text-decoration: none; margin: 10px 0; padding: 5px; border-bottom: 1px solid #111; }
    .opcion:hover { background: #0f0; color: #000; }
    input, select { background: #000; color: #0f0; border: 1px solid #0f0; padding: 10px; width: 100%; margin: 5px 0; box-sizing: border-box; }
    button { background: #0f0; color: #000; border: none; padding: 12px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 5px; }
    table { width: 100%; border-collapse: collapse; margin-top: 15px; }
    th, td { border: 1px solid #0f0; padding: 8px; text-align: left; }
    .btn-rojo { background: #f00; color: #fff; padding: 5px; text-decoration: none; font-size: 0.8em; }
    .btn-pagar { background: #25D366; color: #000; padding: 5px; text-decoration: none; font-weight: bold; font-size: 0.8em; }
    .btn-volver { border: 1px solid #0f0; color: #0f0; padding: 10px; display: block; text-align: center; text-decoration: none; margin-top: 15px; }
    .vencido { background: #300; }
</style>
'''

# --- RUTAS DE ACCESO ---

@app.route('/')
def login_screen():
    session.clear()
    return f'''{CSS}<div class="menu-box"><h3>🔑 SISTEMA CENTRAL V7</h3>
    <form action="/verificar" method="post"><input type="text" name="clave" placeholder="CLAVE DE ACCESO" autofocus required><button type="submit">ENTRAR</button></form></div>'''

@app.route('/verificar', methods=['POST'])
def verificar():
    clave = request.form.get('clave') or session.get('usuario_clave')
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user:
        # Verificación de vencimiento
        vence_str = user['vencimiento']
        if user['rango'] == 'Trabajador':
            dueno = db_u.execute("SELECT vencimiento FROM usuarios WHERE clave = ?", (user['creado_por'],)).fetchone()
            vence_str = dueno['vencimiento']
        
        if datetime.now() > datetime.strptime(vence_str, "%Y-%m-%d %H:%M:%S") or user['estado'] != "Activo":
            return f"{CSS}<div class='menu-box'><h2 style='color:red'>🛑 ACCESO BLOQUEADO</h2><p>Servicio vencido o cuenta suspendida.</p><a href='/' class='btn-volver'>VOLVER</a></div>"

        session['usuario_clave'] = clave
        db_n = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
        db_t = iniciar_db_tienda(db_n)
        conf = db_t.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()

        menu = f"{CSS}<div class='menu-box'><h3>--- {conf['nombre_negocio']} ---</h3><p>USUARIO: {user['nombre']} | RANGO: {user['rango']}</p><hr>"
        
        if user['rango'] in ['Super Admin', 'Administrador']:
            menu += f'<a class="opcion" href="/gestionar_negocios/{clave}">📊 GESTIONAR DUEÑOS (PAGOS)</a>'
            if user['rango'] == 'Super Admin':
                menu += f'<a class="opcion" href="/usuarios/{clave}">👥 CONTROL DE ADMINISTRADORES</a>'
        
        elif user['rango'] in ['Dueño', 'Trabajador']:
            menu += '<a class="opcion" href="/venta">🛒 CAJA DE COBRO</a>'
            menu += f'<a class="opcion" href="/inventario/{clave}">📦 INVENTARIO</a>'
            if user['rango'] == 'Dueño':
                menu += f'<a class="opcion" href="/usuarios/{clave}">👥 MIS EMPLEADOS</a>'
                menu += f'<a class="opcion" href="/config_corte/{clave}">⚙️ CONFIGURAR CORTE / WHATSAPP</a>'
                menu += f'<a class="opcion" href="/hacer_corte_final/{clave}" onclick="return confirm(\'¿Hacer corte? Se borrarán las ventas del día y se generará el Excel.\')">🏁 HACER CORTE DE HOY</a>'
        
        menu += '<hr><a class="opcion" href="/">🚪 SALIR</a></div>'
        return menu
    return redirect('/')

# --- RANGO: SUPER ADMIN Y ADMIN ---

@app.route('/gestionar_negocios/<clave>')
def gestionar_negocios(clave):
    db_u = iniciar_db_usuarios()
    duenos = db_u.execute("SELECT * FROM usuarios WHERE rango = 'Dueño' ORDER BY vencimiento ASC").fetchall()
    tabla = "<table><tr><th>DUEÑO</th><th>TIEMPO</th><th>ACCIÓN</th></tr>"
    for d in duenos:
        timer = tiempo_restante(d['vencimiento'])
        clase = 'class="vencido"' if "VENCIDO" in timer else ''
        btn_renovar = f'<a href="/renovar/{clave}/{d["clave"]}" class="btn-pagar">+30 DÍAS</a>'
        btn_susp = f'<a href="/status_cascada/{clave}/{d["clave"]}" class="btn-rojo">{"ACTIVAR" if d["estado"]=="Suspendido" else "SUSPENDER"}</a>'
        tabla += f'<tr {clase}><td>{d["nombre"]}<br><small>{d["clave"]}</small></td><td>{timer}</td><td>{btn_renovar} {btn_susp}</td></tr>'
    
    return f'''{CSS}<div class="menu-box"><h3>🏢 GESTIÓN GLOBAL DE DUEÑOS</h3>{tabla+"</table>"}<hr>
    <h4>REGISTRAR NUEVO DUEÑO</h4>
    <form action="/add_user" method="post"><input type="hidden" name="admin_clave" value="{clave}"><input type="hidden" name="rango" value="Dueño"><input name="nombre" placeholder="Nombre del Dueño" required><button type="submit">CREAR</button></form>
    <a href="/verificar" class="btn-volver">VOLVER</a></div>'''

@app.route('/usuarios/<clave>')
def gestionar_usuarios(clave):
    db_u = iniciar_db_usuarios()
    user = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    
    if user['rango'] == "Super Admin":
        admins = db_u.execute("SELECT * FROM usuarios WHERE rango = 'Administrador'").fetchall()
        tabla = "<table><tr><th>ADMIN</th><th>REACTIVACIONES (EDITAR)</th><th>ACCIÓN</th></tr>"
        for a in admins:
            form_ed = f'<form action="/update_counter" method="post" style="display:flex;"><input type="hidden" name="admin_clave" value="{clave}"><input type="hidden" name="target" value="{a["clave"]}"><input type="number" name="val" value="{a["reactivaciones"]}" style="width:60px;"><button type="submit">💾</button></form>'
            tabla += f'<tr><td>{a["nombre"]}</td><td>{form_ed}</td><td><a href="/borrar/{clave}/{a["clave"]}" class="btn-rojo">BORRAR</a></td></tr>'
        titulo = "CONTROL DE ADMINISTRADORES"
        r_crear = "Administrador"
    elif user['rango'] == "Dueño":
        trbs = db_u.execute("SELECT * FROM usuarios WHERE creado_por = ?", (clave,)).fetchall()
        tabla = "<table><tr><th>NOMBRE</th><th>ESTADO</th><th>ACCIÓN</th></tr>"
        for t in trbs:
            accion = f'<a href="/status_simple/{clave}/{t["clave"]}" class="btn-rojo">CAMBIAR</a>'
            tabla += f'<tr><td>{t["nombre"]}</td><td>{t["estado"]}</td><td>{accion}</td></tr>'
        titulo = "MIS TRABAJADORES"
        r_crear = "Trabajador"
    else: return redirect('/')

    return f'''{CSS}<div class="menu-box"><h3>👥 {titulo}</h3>{tabla+"</table>"}<hr>
    <form action="/add_user" method="post"><input type="hidden" name="admin_clave" value="{clave}"><input type="hidden" name="rango" value="{r_crear}"><input name="nombre" placeholder="Nombre" required><button type="submit">AÑADIR</button></form>
    <a href="/verificar" class="btn-volver">VOLVER</a></div>'''

# --- ACCIONES ---

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

@app.route('/add_user', methods=['POST'])
def add_user():
    adm, nom, rango = request.form['admin_clave'], request.form['nombre'], request.form['rango']
    clv = f"{rango[:3].upper()}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"
    vence = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S") if rango == 'Dueño' else "2099-12-31 23:59:59"
    with iniciar_db_usuarios() as db:
        db.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado, vencimiento) VALUES (?,?,?,?,?,?)", (clv, nom, rango, adm, "Activo", vence))
    return f"{CSS}<div class='menu-box'><h3>✅ REGISTRADO</h3><p>CLAVE: <strong>{clv}</strong></p><a href='/' class='btn-volver'>LOGIN</a></div>"

@app.route('/status_cascada/<admin>/<target>')
def status_cascada(admin, target):
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT estado FROM usuarios WHERE clave = ?", (target,)).fetchone()
    nuevo = "Activo" if u['estado'] == "Suspendido" else "Suspendido"
    with db_u:
        db_u.execute("UPDATE usuarios SET estado = ? WHERE clave = ?", (nuevo, target))
        db_u.execute("UPDATE usuarios SET estado = ? WHERE creado_por = ?", (nuevo, target))
    return redirect(f"/gestionar_negocios/{admin}")

# --- RANGO: DUEÑO (CORTE Y EXCEL) ---

@app.route('/config_corte/<clave>', methods=['GET', 'POST'])
def config_corte(clave):
    db = iniciar_db_tienda(f"tienda_{clave}.db")
    if request.method == 'POST':
        with db: db.execute("UPDATE configuracion SET nombre_negocio=?, telefono_dueno=?, hora_corte=? WHERE id=1", 
                           (request.form['nom'], request.form['tel'], request.form['hora']))
        return redirect('/verificar')
    conf = db.execute("SELECT * FROM configuracion WHERE id=1").fetchone()
    return f'''{CSS}<div class="menu-box"><h3>⚙️ AJUSTES</h3><form method="post">
    Nombre: <input name="nom" value="{conf['nombre_negocio']}">
    WhatsApp: <input name="tel" value="{conf['telefono_dueno']}">
    Hora Corte: <input type="time" name="hora" value="{conf['hora_corte']}">
    <button type="submit">GUARDAR</button></form></div>'''

@app.route('/hacer_corte_final/<clave>')
def hacer_corte_final(clave):
    db_t = iniciar_db_tienda(f"tienda_{clave}.db")
    ventas = db_t.execute("SELECT * FROM ventas").fetchall()
    gastos = db_t.execute("SELECT sum(monto) as t FROM gastos").fetchone()['t'] or 0
    total_v = sum(v['total'] for v in ventas)
    ahora = datetime.now().strftime("%d-%m-%Y_%H-%M")
    
    # 1. Crear Excel (.csv)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'TOTAL', 'FECHA', 'CAJERO'])
    for v in ventas: writer.writerow([v['id'], v['total'], v['fecha'], v['vendedor']])
    
    if not os.path.exists('cortes'): os.makedirs('cortes')
    ruta = f"cortes/Corte_{clave}_{ahora}.csv"
    with open(ruta, 'w', encoding='utf-8-sig', newline='') as f: f.write(output.getvalue())
    
    # 2. Limpiar Datos
    with db_t:
        db_t.execute("DELETE FROM ventas")
        db_t.execute("DELETE FROM gastos")
    
    conf = db_t.execute("SELECT * FROM configuracion WHERE id=1").fetchone()
    msg = f"🏁 *CORTE COMPLETADO*\n📅 {ahora}\n💰 Ventas: ${total_v}\n💸 Gastos: ${gastos}\n📈 Neto: ${total_v-gastos}\n📂 Excel generado."
    url_wa = f"https://api.whatsapp.com/send?phone={conf['telefono_dueno']}&text={urllib.parse.quote(msg)}"
    
    return f'''{CSS}<div class="menu-box"><h3>📊 RESULTADO DEL CORTE</h3><p>{msg}</p>
    <a href="{url_wa}" target="_blank" class="btn-pagar">MANDAR WHATSAPP</a><br><br>
    <a href="/descargar/{ruta.replace('/','_')}" class="btn-volver">DESCARGAR EXCEL</a>
    <a href="/verificar" class="btn-volver">VOLVER</a></div>'''

@app.route('/descargar/<path_file>')
def descargar(path_file):
    return send_file(path_file.replace('_','/'), as_attachment=True)

# --- OPERACIONES DE TIENDA (VENTA E INVENTARIO) ---

@app.route('/venta')
def vista_venta():
    clv = session.get('usuario_clave')
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clv,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    prods = db.execute("SELECT * FROM productos WHERE stock > 0").fetchall()
    opcs = "".join([f"<option value='{p['codigo']}'>{p['nombre']} (${p['precio']})</option>" for p in prods])
    car = session.get('carrito', [])
    tabla = "<table>" + "".join([f"<tr><td>{i['n']}</td><td>{i['c']}</td><td>${i['s']}</td></tr>" for i in car]) + "</table>"
    return f'''{CSS}<div class="menu-box"><h3>🛒 CAJA</h3><form action="/add_car" method="post"><select name="cod">{opcs}</select><input type="number" step="0.1" name="cnt" placeholder="Cant/Dinero"><button>AÑADIR</button></form>{tabla}<h4>TOTAL: ${sum(i['s'] for i in car)}</h4><a href="/cobrar" class="btn-pagar">COBRAR</a><a href="/verificar" class="btn-volver">VOLVER</a></div>'''

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
    db_u = iniciar_db_usuarios()
    u = db_u.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
    db_n = f"tienda_{u['creado_por']}.db" if u['rango'] == 'Trabajador' else f"tienda_{u['clave']}.db"
    db = iniciar_db_tienda(db_n)
    prods = db.execute("SELECT * FROM productos").fetchall()
    tabla = "<table><tr><th>COD</th><th>NOM</th><th>STOCK</th></tr>" + "".join([f"<tr><td>{p['codigo']}</td><td>{p['nombre']}</td><td>{p['stock']}</td></tr>" for p in prods]) + "</table>"
    form = f'<hr><form action="/add_p" method="post"><input type="hidden" name="cl" value="{clave}"><input name="co" placeholder="Cod"><input name="no" placeholder="Nom"><input name="pr" placeholder="Precio"><input name="st" placeholder="Stock"><select name="un"><option value="p">Pieza</option><option value="k">Kilo</option></select><button>GUARDAR</button></form>' if u['rango'] == 'Dueño' else ""
    return f"{CSS}<div class='menu-box'><h3>📦 STOCK</h3>{tabla}{form}<a href='/verificar' class='btn-volver'>VOLVER</a></div>"

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

if __name__ == "__main__":
    iniciar_db_usuarios()
    app.run(host='0.0.0.0', port=10000)
    
