return os, random, urllib.parse
from flask import Flask, render_template, request, session, redirect, jsonify
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__)
app.secret_key = 'v11_secret_2026'

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def query_db(query, args=(), one=False):
    con = sqlite3.connect('punto_venta_v11.db')
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    con.commit()
    con.close()
    return (rv[0] if rv else None) if one else rv

# Crear tablas si no existen
def init_db():
    # Usuarios (Admin, Dueños, Trabajadores)
    query_db('''CREATE TABLE IF NOT EXISTS usuarios 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, clave TEXT UNIQUE, nombre TEXT, rango TEXT, jefe TEXT)''')
    # Productos (Inventario)
    query_db('''CREATE TABLE IF NOT EXISTS productos 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT, nombre TEXT, precio REAL, stock REAL, unidad TEXT, dueño_id TEXT)''')
    # Ventas
    query_db('''CREATE TABLE IF NOT EXISTS ventas 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, detalle TEXT, total REAL, vendedor TEXT, dueño_id TEXT, fecha TIMESTAMP)''')
    # Configuración Global y Renta
    query_db('''CREATE TABLE IF NOT EXISTS config_tiendas 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, dueño_id TEXT, nombre_empresa TEXT, tel_reportes TEXT, vencimiento TEXT, estado TEXT)''')
    
    # Usuario Maestro (Tú)
    existe_admin = query_db("SELECT * FROM usuarios WHERE clave='2026'", one=True)
    if not existe_admin:
        query_db("INSERT INTO usuarios (clave, nombre, rango) VALUES ('2026', 'ADMIN MAESTRO', 'Administrador')")

init_db()

# --- LÓGICA DE CLAVES ALEATORIAS ---
def generar_clave():
    while True:
        clv = str(random.randint(1000, 9999))
        if not query_db("SELECT 1 FROM usuarios WHERE clave=?", (clv,), one=True):
            return clv

# --- RUTAS DE ACCESO ---
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    clv = request.form.get('clave')
    user = query_db("SELECT * FROM usuarios WHERE clave=?", (clv,), one=True)
    
    if user:
        session['user'] = user['nombre']
        session['rango'] = user['rango']
        session['clave'] = user['clave']
        
        if user['rango'] == 'Administrador':
            return redirect('/panel_maestro')
        
        # Aislamiento: Identificar quién es el dueño
        session['dueño_id'] = user['jefe'] if user['rango'] == 'Trabajador' else user['clave']
        
        # Cargar nombre de la empresa
        conf = query_db("SELECT nombre_empresa FROM config_tiendas WHERE dueño_id=?", (session['dueño_id'],), one=True)
        session['empresa'] = conf['nombre_empresa'] if conf else "MI NEGOCIO V11"
        
        return redirect('/hub')
    return "Clave incorrecta"

# --- MÓDULO DE VENTAS (POS) ---
@app.route('/procesar_venta', methods=['POST'])
def procesar_venta():
    datos = request.json
    carrito = datos['carrito']
    total = datos['total']
    tel_cliente = datos.get('telefono')
    dueño = session['dueño_id']

    for item in carrito:
        # Descontar stock solo si no es infinito (opcional)
        if item.get('id'):
            query_db("UPDATE productos SET stock = stock - ? WHERE id = ? AND dueño_id = ?", 
                     (item['cantidad_venta'], item['id'], dueño))

    # Guardar venta
    query_db("INSERT INTO ventas (detalle, total, vendedor, dueño_id, fecha) VALUES (?,?,?,?,?)",
             (str(carrito), total, session['user'], dueño, datetime.now()))

    # Generar link WhatsApp
    msg = f"🏪 *{session['empresa']}*\nTotal: ${total}\n¡Gracias!"
    link = f"https://wa.me/{tel_cliente}?text={urllib.parse.quote(msg)}"
    
    return jsonify({"status": "ok", "link_wa": link})
    
 # --- PANEL MAESTRO (SOLO ADMIN 2026) ---
@app.route('/panel_maestro')
def panel_maestro():
    if session.get('rango') != 'Administrador':
        return redirect('/')
    
    # Obtenemos la lista de todos los dueños y sus estadísticas
    clientes = query_db('''
        SELECT c.*, 
        (SELECT SUM(total) FROM ventas WHERE dueño_id = c.dueño_id) as ventas_totales
        FROM config_tiendas c
    ''')
    
    # Calculamos tu ganancia total (Suscripciones)
    total_rentas = query_db("SELECT COUNT(*) as total FROM config_tiendas")[0]['total'] * 450
    
    return render_template('admin.html', clientes=clientes, total_rentas=total_rentas)

@app.route('/crear_dueño', methods=['POST'])
def crear_dueño():
    if session.get('rango') != 'Administrador': return redirect('/')
    
    nombre_negocio = request.form.get('nombre').upper()
    nueva_clv = generar_clave() # Usa la función de claves aleatorias
    fecha_venc = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    
    # 1. Crear usuario Dueño
    query_db("INSERT INTO usuarios (clave, nombre, rango) VALUES (?, ?, ?)", 
             (nueva_clv, nombre_negocio, 'Dueño'))
    
    # 2. Crear su configuración inicial
    query_db("INSERT INTO config_tiendas (dueño_id, nombre_empresa, vencimiento, estado) VALUES (?, ?, ?, ?)",
             (nueva_clv, nombre_negocio, fecha_venc, 'ACTIVO'))
    
    return redirect('/panel_maestro')

@app.route('/cambiar_ley', methods=['POST'])
def cambiar_ley():
    # Aquí puedes añadir lógica para cambiar el IVA global o mensajes
    nuevo_iva = request.form.get('iva')
    # Guardar en una tabla global (puedes expandir esto después)
    return redirect('/panel_maestro')
    
@app.route('/hub')
def hub():
    if 'user' not in session: return redirect('/')
    
    # Verificamos si el dueño tiene la renta activa
    info = query_db("SELECT * FROM config_tiendas WHERE dueño_id = ?", (session['dueño_id'],), one=True)
    
    if info and info['estado'] == 'SUSPENDIDO':
        return "<h1>Cuenta Suspendida</h1><p>Contacta al administrador para reactivar.</p>"

    return render_template('hub.html', info=info)

@app.route('/usuarios')
def gestionar_usuarios():
    if session.get('rango') != 'Dueño': return redirect('/hub')
    # Solo vemos los trabajadores que pertenecen a este dueño
    empleados = query_db("SELECT * FROM usuarios WHERE jefe = ?", (session['clave'],))
    return render_template('usuarios.html', empleados=empleados)

@app.route('/crear_trabajador', methods=['POST'])
def crear_trabajador():
    nombre = request.form.get('nombre').upper()
    nueva_clv = generar_clave() # Genera clave aleatoria de 4 dígitos
    
    query_db("INSERT INTO usuarios (clave, nombre, rango, jefe) VALUES (?, ?, ?, ?)",
             (nueva_clv, nombre, 'Trabajador', session['clave']))
    
    return redirect('/usuarios')
    
@app.route('/inventario')
def inventario():
    if 'user' not in session: return redirect('/')
    # Solo mostramos los productos que pertenecen al dueño actual (AISLAMIENTO)
    productos = query_db("SELECT * FROM productos WHERE dueño_id = ?", (session['dueño_id'],))
    return render_template('inventario.html', productos=productos)

@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    nombre = request.form.get('nombre').upper()
    precio = request.form.get('precio')
    unidad = request.form.get('unidad')
    stock_input = request.form.get('stock')
    
    # Lógica de Stock Opcional: Si está vacío, se guarda como None (infinito)
    stock = float(stock_input) if stock_input and stock_input.strip() != "" else None
    
    query_db("INSERT INTO productos (nombre, precio, stock, unidad, dueño_id) VALUES (?, ?, ?, ?, ?)",
             (nombre, precio, stock, unidad, session['dueño_id']))
    
    return redirect('/inventario')
    

if __name__ == '__main__':
    app.run(debug=True)
        
