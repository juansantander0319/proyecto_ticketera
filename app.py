from flask import Flask, render_template

app = Flask(__name__)

# =========================
# RUTAS PARA USUARIO
# =========================
@app.route("/usuario")
def usuario_dashboard():
    return render_template("usuario/usuario_dashboard.html")

@app.route("/usuario/crear-ticket")
def usuario_crear_ticket():
    return render_template("usuario/usuario_crear_ticket.html")

@app.route("/usuario/mis-tickets")
def usuario_mis_tickets():
    return render_template("usuario/usuario_mis_tickets.html")

@app.route("/usuario/notificaciones")
def usuario_notificaciones():
    return render_template("usuario/usuario_notificaciones.html")

@app.route("/usuario/faq")
def usuario_faq():
    return render_template("usuario/usuario_faq.html")


# =========================
# RUTAS PARA TÉCNICO
# =========================
@app.route("/tecnico")
def tecnico_dashboard():
    return render_template("tecnico/tecnico_dashboard.html")

@app.route("/tecnico/ver-tickets")
def tecnico_ver_tickets():
    return render_template("tecnico/tecnico_ver_tickets.html")

@app.route("/tecnico/calendario")
def tecnico_calendario():
    return render_template("tecnico/tecnico_calendario.html")

@app.route("/tecnico/usuarios")
def tecnico_usuarios():
    return render_template("tecnico/tecnico_usuarios.html")

@app.route("/tecnico/categorias")
def tecnico_categorias():
    return render_template("tecnico/tecnico_categorias.html")

@app.route("/tecnico/reportes")
def tecnico_reportes():
    return render_template("tecnico/tecnico_reportes.html")

@app.route("/tecnico/inventario")
def tecnico_inventario():
    return render_template("tecnico/tecnico_inventario.html")


# =========================
# RUTA DE INICIO GENERAL
# =========================
@app.route("/")
def home():
    return render_template("index.html")  # Página de bienvenida o login

if __name__ == "__main__":
    app.run(debug=True)
