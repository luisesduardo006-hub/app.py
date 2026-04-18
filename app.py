from flask import Flask, render_template_string, request
import sqlite3

app = Flask(__name__)

# Configuración de la Base de Datos
def init_db():
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS productos 
                      (id INTEGER PRIMARY KEY, nombre TEXT, precio REAL)''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM productos")
    lista = cursor.fetchall()
    conn.close()
    
    html = """
    <h1>🛒 Mi Punto de Venta Pro</h1>
    <form action="/agregar" method="post">
        <input type="text" name="nombre" placeholder="Producto" required>
        <input type="number" name="precio" placeholder="Precio" required>
        <button type="submit">Agregar</button>
    </form>
    <hr>
    <ul>
        {% for p in lista %}
            <li>{{ p[1] }} - ${{ p[2] }}</li>
        {% endfor %}
    </ul>
    """
    return render_template_string(html, lista=lista)

@app.route('/agregar', methods=['POST'])
def agregar():
    nombre = request.form['nombre']
    precio = request.form['precio']
    conn = sqlite3.connect('ventas.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO productos (nombre, precio) VALUES (?, ?)", (nombre, precio))
    conn.commit()
    conn.close()
    return '<script>window.location="/";</script>'

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=8080)
  
