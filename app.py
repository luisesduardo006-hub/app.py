import sqlite3
from datetime import datetime
import urllib.parse
import webbrowser
import random
import string
import csv
import os

# --- INICIO Y CONFIGURACIÓN ---
def iniciar_db(nombre_db='punto_venta_v4.db'):
    conn = sqlite3.connect(nombre_db)
    conn.row_factory = sqlite3.Row 
    with conn:
        # Limpieza de datos (Borra el contenido de las tablas si existen)
        conn.execute("DROP TABLE IF EXISTS productos")
        conn.execute("DROP TABLE IF EXISTS ventas")
        conn.execute("DROP TABLE IF EXISTS gastos")
        conn.execute("DROP TABLE IF EXISTS configuracion")
        
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
        
        cursor = conn.execute("PRAGMA table_info(ventas)")
        columnas_ventas = [info[1] for info in cursor.fetchall()]
        if "vendedor" not in columnas_ventas:
            conn.execute("ALTER TABLE ventas ADD COLUMN vendedor TEXT")

        cursor = conn.execute("PRAGMA table_info(configuracion)")
        columnas_config = [info[1] for info in cursor.fetchall()]
        if "telefono_dueno" not in columnas_config:
            conn.execute("ALTER TABLE configuracion ADD COLUMN telefono_dueno TEXT")

        res = conn.execute("SELECT COUNT(*) FROM configuracion").fetchone()
        if res[0] == 0:
            conn.execute("INSERT INTO configuracion (id, nombre_negocio, direccion, min_compra, porc_desc, telefono_dueno) VALUES (1, 'MI TIENDITA PRO', 'Direccion General', 0, 0, '')")
    return conn

def obtener_config(conn):
    return conn.execute("SELECT * FROM configuracion WHERE id = 1").fetchone()

def leer_float(prompt, error_msg="❌ Valor inválido."):
    while True:
        try:
            val = input(prompt)
            return float(val) if val else 0.0
        except ValueError:
            print(error_msg)

# --- MÓDULO DE GESTIÓN DE USUARIOS ---
def iniciar_db_usuarios(conn):
    with conn:
        # Limpieza de usuarios
        conn.execute("DROP TABLE IF EXISTS usuarios")
        conn.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                     (clave TEXT PRIMARY KEY, nombre TEXT, rango TEXT, creado_por TEXT, estado TEXT)''')
        conn.execute("INSERT OR REPLACE INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?, ?, ?, ?, ?)", 
                     ("ADM-K97B", "ADMIN PRINCIPAL", "Administrador", "SISTEMA", "Activo"))

def gestionar_usuarios(conn, usuario_activo):
    while True:
        rango_a_gestionar = "Dueño" if usuario_activo['rango'] == "Administrador" else "Trabajador"
        print(f"\n--- PANEL DE GESTIÓN: {rango_a_gestionar.upper()}S ---")
        print(f"{'CLAVE':<12} | {'NOMBRE':<15} | {'ESTADO':<10}")
        print("-" * 45)
        mi_rama = conn.execute("SELECT * FROM usuarios WHERE creado_por = ?", (usuario_activo['clave'],)).fetchall()
        for u in mi_rama:
            print(f"{u['clave']:<12} | {u['nombre']:<15} | {u['estado']:<10}")
        
        print(f"\n1. Registrar {rango_a_gestionar} | 2. Eliminar | 3. Suspender/Activar | 4. Volver")
        op = input("Selecciona una opción: ")
        if op == '1':
            nom = input(f"Nombre del {rango_a_gestionar}: ").strip()
            if not nom: continue
            sufijo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            nueva_c = f"{nom[:3].upper()}-{sufijo}"
            with conn:
                conn.execute("INSERT INTO usuarios (clave, nombre, rango, creado_por, estado) VALUES (?,?,?,?,?)",
                             (nueva_c, nom, rango_a_gestionar, usuario_activo['clave'], "Activo"))
            print(f"✅ Registrado con éxito: {nom}. CLAVE: {nueva_c}")
        elif op == '2':
            c_eliminar = input("Introduce la clave a eliminar: ").strip()
            check = conn.execute("SELECT 1 FROM usuarios WHERE clave = ? AND creado_por = ?", (c_eliminar, usuario_activo['clave'])).fetchone()
            if check:
                with conn: conn.execute("DELETE FROM usuarios WHERE clave = ?", (c_eliminar,))
                print("🗑️ Usuario eliminado.")
            else:
                print("❌ Sin permiso o no existe.")
        elif op == '3':
            c_susp = input("Introduce la clave a Suspender/Activar: ").strip()
            u = conn.execute("SELECT estado FROM usuarios WHERE clave = ? AND creado_por = ?", (c_susp, usuario_activo['clave'])).fetchone()
            if u:
                nuevo_estado = "Suspendido" if u['estado'] == "Activo" else "Activo"
                with conn: conn.execute("UPDATE usuarios SET estado = ? WHERE clave = ?", (nuevo_estado, c_susp))
                print(f"✅ Estado cambiado a: {nuevo_estado}")
            else: print("❌ Usuario no encontrado.")
        elif op == '4': break

# --- GESTIÓN DE INVENTARIO ---
def gestionar_stock(conn, usuario_activo):
    while True:
        print(f"\n{'📦 CONTROL DE INVENTARIO':^45}")
        filas = conn.execute("SELECT * FROM productos").fetchall()
        for p in filas:
            u = "kg" if p['unidad'] == 'k' else "pz"
            print(f"ID:{p['codigo']:<4} | {p['nombre'][:12]:<12} | ${p['precio']:>6.2f} | {p['stock']:>6.2f} {u}")
        if usuario_activo['rango'] == 'Trabajador':
            input("\n[VISTA DE TRABAJADOR] Enter para salir...")
            break
        print("\n1. Agregar/Editar Producto | 2. Borrar Producto | 3. Volver")
        op = input("Selecciona: ")
        if op == '3': break
        elif op == '1':
            cod, nom = input("ID/Código: "), input("Nombre: ")
            pre, uni, sto = leer_float("Precio: "), input("Unidad (p/k): ").lower(), leer_float("Stock: ")
            with conn: conn.execute("INSERT OR REPLACE INTO productos (codigo, nombre, precio, stock, min_compra, unidad) VALUES (?,?,?,?,?,?)", (cod, nom, pre, sto, 0, uni))
        elif op == '2':
            cod = input("ID a eliminar: ")
            with conn: conn.execute("DELETE FROM productos WHERE codigo = ?", (cod,))

# --- VENTAS ---
def realizar_venta(conn, user):
    carrito = []
    conf = obtener_config(conn)
    while True:
        total_v = sum(item['subtotal'] for item in carrito)
        print(f"\n{conf['nombre_negocio']} | CAJA: {user['nombre']}")
        print(f"TOTAL: ${total_v:.2f}")
        op = input("\n[ID] Agregar | [c] Cobrar | [s] Salir: ").strip()
        if op.lower() == 's': break
        if op.lower() == 'c':
            if not carrito: continue
            pago = leer_float(f"¿Con cuánto pagan? (Total ${total_v:.2f}): $")
            if pago >= total_v:
                cambio = pago - total_v
                fecha_v = datetime.now().strftime("%Y-%m-%d %H:%M")
                with conn:
                    for it in carrito:
                        conn.execute("UPDATE productos SET stock = stock - ? WHERE codigo = ?", (it['cant'], it['cod']))
                    conn.execute("INSERT INTO ventas (total, pago, cambio, fecha, vendedor) VALUES (?,?,?,?,?)", 
                                  (total_v, pago, cambio, fecha_v, user['nombre']))
                print(f"✅ VENTA EXITOSA. CAMBIO: ${cambio:.2f}")
                
                tel_c = input("\n📱 ¿Enviar ticket por WhatsApp? (Número 10 dígitos o Enter para saltar): ").strip()
                if tel_c:
                    ticket = f"🧾 *TICKET: {conf['nombre_negocio']}*\n📅 {fecha_v}\n" + "━"*15 + "\n"
                    for i in carrito:
                        u = "kg" if i['tipo'] == 'k' else "pz"
                        ticket += f"• {i['nombre']} ({i['cant']:.2f} {u}) - ${i['subtotal']:.2f}\n"
                    ticket += "━"*15 + f"\n💰 *TOTAL: ${total_v:.2f}*\n💵 Pago: ${pago:.2f}\n🪙 Cambio: ${cambio:.2f}\n"
                    ticket += "\n🙏 ¡Gracias por su compra!"
                    webbrowser.open(f"https://api.whatsapp.com/send?phone=52{tel_c}&text={urllib.parse.quote(ticket)}")
                break
        else:
            p = conn.execute("SELECT * FROM productos WHERE codigo = ? OR nombre LIKE ?", (op, f"{op}%")).fetchone()
            if p:
                if p['unidad'] == 'k':
                    monto = leer_float(f"¿Dinero de {p['nombre']}?: $")
                    carrito.append({'cod': p['codigo'], 'nombre': p['nombre'], 'cant': monto/p['precio'], 'subtotal': monto, 'tipo': 'k'})
                else:
                    cant = leer_float(f"¿Piezas de {p['nombre']}?: ")
                    carrito.append({'cod': p['codigo'], 'nombre': p['nombre'], 'cant': cant, 'subtotal': cant * p['precio'], 'tipo': 'p'})

# --- PAGOS A PROVEEDORES ---
def pago_proveedor(conn):
    print("\n--- REGISTRO DE PAGO A PROVEEDOR ---")
    prov = input("Nombre del Proveedor / Concepto: ").strip()
    if not prov: return
    monto = leer_float("Monto pagado: $")
    with conn: 
        conn.execute("INSERT INTO gastos (concepto, monto, fecha) VALUES (?, ?, ?)", 
                    (prov, monto, datetime.now().strftime("%Y-%m-%d %H:%M")))
    print(f"✅ Gasto de ${monto:.2f} registrado correctamente.")

# --- CORTE DE CAJA ---
def enviar_corte_whatsapp(conn, conf):
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    ventas = conn.execute("SELECT total FROM ventas WHERE fecha LIKE ?", (f"{fecha_hoy}%",)).fetchall()
    gastos = conn.execute("SELECT monto, concepto FROM gastos WHERE fecha LIKE ?", (f"{fecha_hoy}%",)).fetchall()
    total_v = sum(v['total'] for v in ventas)
    total_g = sum(g['monto'] for g in gastos)
    balance = total_v - total_g
    
    bajo_stock = conn.execute("SELECT nombre, stock FROM productos WHERE stock < 5").fetchall()
    
    nombre_archivo = f"Corte_{fecha_hoy}.csv"
    with open(nombre_archivo, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['CONCEPTO', 'MONTO/CANTIDAD'])
        writer.writerow(['Total Ventas', total_v])
        writer.writerow(['Total Gastos', total_g])
        writer.writerow(['Balance', balance])
        writer.writerow([])
        writer.writerow(['PROVEEDORES PAGADOS'])
        for g in gastos:
            writer.writerow([g['concepto'], g['monto']])
        writer.writerow([])
        writer.writerow(['PRODUCTOS CON POCO STOCK'])
        for p in bajo_stock:
            writer.writerow([p['nombre'], p['stock']])
            
    msg = f"📊 *CORTE DE CAJA: {conf['nombre_negocio']}*\n📅 Fecha: {fecha_hoy}\n" + "━"*20 + "\n"
    msg += f"✅ Ventas: ${total_v:.2f}\n"
    msg += f"💸 Gastos: ${total_g:.2f}\n"
    msg += f"💰 *TOTAL EN CAJA: ${balance:.2f}*\n" + "━"*20 + "\n"
    
    if gastos:
        msg += "\n🚚 *PROVEEDORES:* \n"
        for g in gastos:
            msg += f"• {g['concepto']}: ${g['monto']:.2f}\n"
            
    if bajo_stock:
        msg += "\n⚠️ *STOCK BAJO:* \n"
        for p in bajo_stock:
            msg += f"• {p['nombre']}: {p['stock']}\n"

    tel = conf['telefono_dueno'] if conf['telefono_dueno'] else input("\n📱 Enviar corte a (WhatsApp 10 dígitos): ").strip()
    if tel:
        print(f"📂 Archivo guardado como: {nombre_archivo}")
        webbrowser.open(f"https://api.whatsapp.com/send?phone=52{tel}&text={urllib.parse.quote(msg)}")

# --- MAIN / MENÚS ---
if __name__ == "__main__":
    db_auth = iniciar_db('usuarios_sistema.db')
    iniciar_db_usuarios(db_auth)
    
    while True:
        print("\n" + "="*35 + "\n🔑 INICIO DE SESIÓN\n" + "="*35)
        clave = input("Clave de acceso: ").strip()
        user = db_auth.execute("SELECT * FROM usuarios WHERE clave = ?", (clave,)).fetchone()
        
        if user:
            # VERIFICACIÓN DE SUSPENSIÓN
            if user['estado'] == "Suspendido":
                print("\n🚫 SERVICIO SUSPENDIDO. Contacte al administrador.")
                continue

            db_nombre = f"tienda_{user['creado_por']}.db" if user['rango'] == 'Trabajador' else f"tienda_{user['clave']}.db"
            db = iniciar_db(db_nombre)
            
            while True:
                c = obtener_config(db)
                print(f"\n--- {c['nombre_negocio']} ---")
                if user['rango'] == 'Administrador':
                    print("1. GESTIONAR DUEÑOS (TABLA)\n2. SALIR")
                    op = input("Opción: ")
                    if op == '1': gestionar_usuarios(db_auth, user)
                    elif op == '2': break
                elif user['rango'] == 'Dueño':
                    print("1. REALIZAR VENTA\n2. INVENTARIO (EDITAR/VER)\n3. GESTIONAR MIS TRABAJADORES\n4. PAGAR A PROVEEDOR\n5. CONFIGURAR NEGOCIO (NOMBRE/TEL)\n6. ENVIAR CORTE DE CAJA\n7. SALIR")
                    op = input("Selecciona: ")
                    if op == '1': realizar_venta(db, user)
                    elif op == '2': gestionar_stock(db, user)
                    elif op == '3': gestionar_usuarios(db_auth, user)
                    elif op == '4': pago_proveedor(db)
                    elif op == '5':
                        nn = input(f"Nuevo nombre [{c['nombre_negocio']}]: ")
                        nt = input(f"Nuevo Teléfono Dueño [{c['telefono_dueno']}]: ")
                        if nn: 
                            with db: db.execute("UPDATE configuracion SET nombre_negocio=? WHERE id=1", (nn,))
                        if nt: 
                            with db: db.execute("UPDATE configuracion SET telefono_dueno=? WHERE id=1", (nt,))
                        print("✅ Configuración actualizada.")
                    elif op == '6': enviar_corte_whatsapp(db, c)
                    elif op == '7': break
                elif user['rango'] == 'Trabajador':
                    print("1. REALIZAR VENTA\n2. VER STOCK (SÓLO LECTURA)\n3. PAGAR A PROVEEDOR\n4. SALIR")
                    op = input("Selecciona: ")
                    if op == '1': realizar_venta(db, user)
                    elif op == '2': gestionar_stock(db, user)
                    elif op == '3': pago_proveedor(db)
                    elif op == '4': break
        else: print("❌ Clave incorrecta.")
                    
