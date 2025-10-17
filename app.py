import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, func
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

# --- CONFIGURACIONES ---
load_dotenv() # Carga las variables del archivo .env

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "una_clave_secreta_de_respaldo_por_si_falla_dotenv")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- CONFIGURACIÓN DE LOGGING ---
logging.basicConfig(filename='error.log', level=logging.ERROR,
                    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')

db = SQLAlchemy(app)

# --- MODELOS DE LA BASE DE DATOS ---
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    rut = db.Column(db.String(12), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default='Usuario')
    tickets_creados = db.relationship('Ticket', backref='creador', lazy=True, foreign_keys='Ticket.usuario_id')
    tickets_asignados = db.relationship('Ticket', backref='tecnico_asignado', lazy=True, foreign_keys='Ticket.tecnico_id')
    activos_asignados = db.relationship('Activo', backref='asignado_a', lazy=True)
    notificaciones = db.relationship('Notificacion', backref='usuario', lazy=True)
    comentarios = db.relationship('Comentario', backref='autor', lazy=True)

class Categoria(db.Model):
    __tablename__ = 'categorias'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    descripcion = db.Column(db.String(255))
    sla_respuesta = db.Column(db.Integer, nullable=False)
    sla_resolucion = db.Column(db.Integer, nullable=False)

class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    asunto = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(50), nullable=False, default='Abierto')
    prioridad = db.Column(db.String(50), nullable=False, default='Media')
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    fecha_vencimiento_sla = db.Column(db.DateTime, nullable=True)
    fecha_cierre = db.Column(db.DateTime, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=False)
    categoria = db.relationship('Categoria', backref='tickets')
    comentarios = db.relationship('Comentario', backref='ticket', lazy=True, cascade="all, delete-orphan")
    adjuntos = db.relationship('Adjunto', backref='ticket', lazy=True, cascade="all, delete-orphan")

class Activo(db.Model):
    __tablename__ = 'activos'
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(100), nullable=False)
    marca = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    numero_serie = db.Column(db.String(100), unique=True)
    asignado_a_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

class Articulo(db.Model):
    __tablename__ = 'articulos'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    categoria_faq = db.Column(db.String(100), nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

class Notificacion(db.Model):
    __tablename__ = 'notificaciones'
    id = db.Column(db.Integer, primary_key=True)
    mensaje = db.Column(db.String(255), nullable=False)
    leida = db.Column(db.Boolean, default=False, nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=True)

class Comentario(db.Model):
    __tablename__ = 'comentarios'
    id = db.Column(db.Integer, primary_key=True)
    contenido = db.Column(db.Text, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=db.func.current_timestamp())
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)

class Adjunto(db.Model):
    __tablename__ = 'adjuntos'
    id = db.Column(db.Integer, primary_key=True)
    nombre_archivo = db.Column(db.String(255), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)

# --- FUNCIONES Y DECORADORES ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Debes iniciar sesión para ver esta página.', 'warning')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('rol') not in roles:
                flash('No tienes permiso para acceder a esta página.', 'danger')
                return redirect(url_for('tecnico_dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- CONTEXT PROCESSOR ---
@app.context_processor
def inject_global_vars():
    unread_count = 0
    if 'usuario_id' in session and session['rol'] == 'Usuario':
        unread_count = Notificacion.query.filter_by(usuario_id=session['usuario_id'], leida=False).count()
    return dict(unread_notifications=unread_count, now=datetime.utcnow())

# --- LÓGICA DE ASIGNACIÓN AUTOMÁTICA ---
LAST_INDEX_FILE = 'last_technician_index.txt'

def get_next_technician_id():
    tecnicos_n1 = Usuario.query.filter_by(rol='Técnico Nivel 1').order_by(Usuario.id).all()
    if not tecnicos_n1:
        return None
    try:
        with open(LAST_INDEX_FILE, 'r') as f:
            last_index = int(f.read())
    except (FileNotFoundError, ValueError):
        last_index = -1
    next_index = (last_index + 1) % len(tecnicos_n1)
    with open(LAST_INDEX_FILE, 'w') as f:
        f.write(str(next_index))
    return tecnicos_n1[next_index].id

# --- RUTAS PRINCIPALES ---
@app.route("/", methods=["GET", "POST"])
def index():
    if "usuario_id" in session:
        return redirect(url_for("tecnico_dashboard") if session.get("rol") in ["Técnico Nivel 1", "Técnico Nivel 2"] else url_for("usuario_dashboard"))
    if request.method == "POST":
        rut, password = request.form["rut"], request.form["password"]
        usuario_en_db = Usuario.query.filter_by(rut=rut).first()
        if usuario_en_db and check_password_hash(usuario_en_db.password, password):
            session.update({"usuario_id": usuario_en_db.id, "usuario_nombre": usuario_en_db.nombre, "rol": usuario_en_db.rol})
            flash(f"Bienvenido {usuario_en_db.nombre}", "success")
            return redirect(url_for("tecnico_dashboard") if usuario_en_db.rol in ["Técnico Nivel 1", "Técnico Nivel 2"] else url_for("usuario_dashboard"))
        else:
            flash("RUT o contraseña incorrectos", "danger")
    return render_template("index.html")

@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Sesión cerrada correctamente", "info")
    return redirect(url_for("index"))

@app.route('/uploads/<path:filename>')
@login_required
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# --- RUTAS DE USUARIO ---
@app.route("/usuario")
@login_required
@role_required(['Usuario'])
def usuario_dashboard():
    user_id = session.get('usuario_id')
    contadores = {
        'abiertos': Ticket.query.filter(Ticket.usuario_id == user_id, or_(Ticket.estado == 'Abierto', Ticket.estado == 'En Proceso')).count(),
        'cerrados': Ticket.query.filter_by(usuario_id=user_id, estado='Cerrado').count(),
        'total': Ticket.query.filter_by(usuario_id=user_id).count()
    }
    return render_template("usuario/usuario_dashboard.html", contadores=contadores)

@app.route("/usuario/crear", methods=["GET", "POST"])
@login_required
@role_required(['Usuario'])
def usuario_crear_ticket():
    if request.method == "POST":
        categoria_id = request.form.get('categoria_id')
        categoria = Categoria.query.get(categoria_id)
        if not categoria:
            flash("Categoría no válida.", "danger")
            return redirect(url_for('usuario_crear_ticket'))
        fecha_vencimiento = datetime.utcnow() + timedelta(hours=categoria.sla_resolucion)
        tecnico_asignado_id = get_next_technician_id()
        nuevo_ticket = Ticket(
            asunto=request.form.get('asunto'), categoria_id=categoria_id, prioridad=request.form.get('prioridad'),
            descripcion=request.form.get('descripcion'), usuario_id=session.get('usuario_id'), 
            fecha_vencimiento_sla=fecha_vencimiento, tecnico_id=tecnico_asignado_id
        )
        db.session.add(nuevo_ticket)
        file = request.files.get('adjunto')
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            db.session.flush()
            new_filename = f"{nuevo_ticket.id}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
            nuevo_adjunto = Adjunto(nombre_archivo=new_filename, ticket_id=nuevo_ticket.id)
            db.session.add(nuevo_adjunto)
        if tecnico_asignado_id:
            notificacion_tecnico = Notificacion(
                mensaje=f"Se te ha asignado un nuevo ticket: #{nuevo_ticket.id}.",
                usuario_id=tecnico_asignado_id, ticket_id=nuevo_ticket.id)
            db.session.add(notificacion_tecnico)
        db.session.commit()
        flash("Ticket creado y asignado con éxito.", "success")
        return redirect(url_for('usuario_mis_tickets'))
    categorias = Categoria.query.order_by(Categoria.nombre).all()
    return render_template("usuario/usuario_crear_ticket.html", categorias=categorias)

@app.route("/usuario/mis-tickets")
@login_required
@role_required(['Usuario'])
def usuario_mis_tickets():
    user_id = session.get('usuario_id')
    mis_tickets = Ticket.query.filter_by(usuario_id=user_id).order_by(Ticket.fecha_creacion.desc()).all()
    return render_template("usuario/usuario_mis_tickets.html", tickets=mis_tickets)

@app.route("/usuario/notificaciones")
@login_required
@role_required(['Usuario'])
def usuario_notificaciones():
    user_id = session.get('usuario_id')
    notificaciones = Notificacion.query.filter_by(usuario_id=user_id).order_by(Notificacion.fecha_creacion.desc()).all()
    for notif in notificaciones: notif.leida = True
    db.session.commit()
    return render_template("usuario/usuario_notificaciones.html", notificaciones=notificaciones)

@app.route("/usuario/faq")
@login_required
@role_required(['Usuario'])
def usuario_faq():
    query = request.args.get('query', '')
    if query:
        articulos = Articulo.query.filter(or_(Articulo.titulo.ilike(f'%{query}%'), Articulo.contenido.ilike(f'%{query}%'))).all()
    else:
        articulos = Articulo.query.order_by(Articulo.fecha_creacion.desc()).all()
    return render_template("usuario/usuario_faq.html", articulos=articulos, query=query)

# --- RUTAS DE TÉCNICO ---
def es_tecnico(): return session.get("rol") in ["Técnico Nivel 1", "Técnico Nivel 2"]

@app.route("/tecnico")
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def tecnico_dashboard():
    tickets_cerrados = Ticket.query.filter_by(estado='Cerrado').all()
    total_cerrados = len(tickets_cerrados)
    cumplidos = sum(1 for ticket in tickets_cerrados if ticket.fecha_cierre and ticket.fecha_vencimiento_sla and ticket.fecha_cierre <= ticket.fecha_vencimiento_sla)
    sla_percent = round((cumplidos / total_cerrados) * 100) if total_cerrados > 0 else 100
    stats = {'pendientes': Ticket.query.filter_by(estado='Abierto').count(), 'en_proceso': Ticket.query.filter_by(estado='En Proceso').count(), 'cerrados_hoy': total_cerrados, 'sla_cumplido': sla_percent}
    tickets_por_estado = db.session.query(Ticket.estado, func.count(Ticket.id)).group_by(Ticket.estado).all()
    tickets_por_categoria = db.session.query(Categoria.nombre, func.count(Ticket.id)).join(Ticket).group_by(Categoria.nombre).all()
    chart_data = {'estados_labels': [item[0] for item in tickets_por_estado], 'estados_data': [item[1] for item in tickets_por_estado], 'categorias_labels': [item[0] for item in tickets_por_categoria], 'categorias_data': [item[1] for item in tickets_por_categoria]}
    return render_template("tecnico/tecnico_dashboard.html", stats=stats, chart_data=chart_data)

@app.route("/tecnico/todos")
@login_required
@role_required(['Técnico Nivel 2'])
def tecnico_todos_tickets():
    page = request.args.get('page', 1, type=int)
    query = Ticket.query
    filters = {'search': request.args.get('search', ''), 'estado': request.args.get('estado', ''), 'prioridad': request.args.get('prioridad', ''), 'categoria_id': request.args.get('categoria_id', '')}
    if filters['search']: query = query.filter(Ticket.asunto.ilike(f"%{filters['search']}%"))
    if filters['estado']: query = query.filter_by(estado=filters['estado'])
    if filters['prioridad']: query = query.filter_by(prioridad=filters['prioridad'])
    if filters['categoria_id']: query = query.filter_by(categoria_id=filters['categoria_id'])
    pagination = query.order_by(Ticket.fecha_creacion.desc()).paginate(page=page, per_page=10)
    categorias = Categoria.query.order_by(Categoria.nombre).all()
    return render_template("tecnico/tecnico_todos_tickets.html", pagination=pagination, categorias=categorias, filters=filters)

@app.route("/tecnico/mis-asignados")
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def tecnico_mis_asignados():
    page = request.args.get('page', 1, type=int)
    tecnico_id = session.get('usuario_id')
    query = Ticket.query.filter_by(tecnico_id=tecnico_id)
    filters = {'search': request.args.get('search', ''), 'estado': request.args.get('estado', '')}
    if filters['search']: query = query.filter(Ticket.asunto.ilike(f"%{filters['search']}%"))
    if filters['estado']: query = query.filter_by(estado=filters['estado'])
    pagination = query.order_by(Ticket.fecha_creacion.desc()).paginate(page=page, per_page=10)
    return render_template("tecnico/tecnico_ver_tickets.html", pagination=pagination, filters=filters)

@app.route("/tecnico/categorias", methods=["GET", "POST"])
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def tecnico_categorias():
    if request.method == "POST":
        nueva_categoria = Categoria(nombre=request.form['nombre'], descripcion=request.form['descripcion'], sla_respuesta=request.form['sla_respuesta'], sla_resolucion=request.form['sla_resolucion'])
        db.session.add(nueva_categoria); db.session.commit(); flash('Categoría creada con éxito.', 'success')
        return redirect(url_for('tecnico_categorias'))
    categorias = Categoria.query.order_by(Categoria.nombre).all()
    return render_template('tecnico/tecnico_categorias.html', categorias=categorias)

@app.route("/tecnico/categorias/editar", methods=["POST"])
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def editar_categoria():
    categoria = Categoria.query.get_or_404(request.form.get('id_categoria_edit'))
    categoria.nombre, categoria.descripcion, categoria.sla_respuesta, categoria.sla_resolucion = request.form['nombre_edit'], request.form['descripcion_edit'], request.form['sla_respuesta_edit'], request.form['sla_resolucion_edit']
    db.session.commit(); flash('Categoría actualizada con éxito.', 'success')
    return redirect(url_for('tecnico_categorias'))

@app.route("/tecnico/categorias/eliminar", methods=["POST"])
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def eliminar_categoria():
    categoria = Categoria.query.get_or_404(request.form.get('id_categoria_delete'))
    db.session.delete(categoria); db.session.commit(); flash('Categoría eliminada con éxito.', 'danger')
    return redirect(url_for('tecnico_categorias'))

@app.route("/tecnico/inventario", methods=["GET", "POST"])
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def tecnico_inventario():
    if request.method == "POST":
        asignado_id = request.form.get('asignado_a_id')
        nuevo = Activo(tipo=request.form['tipo'], marca=request.form['marca'], modelo=request.form['modelo'], numero_serie=request.form['numero_serie'], asignado_a_id=int(asignado_id) if asignado_id else None)
        db.session.add(nuevo); db.session.commit(); flash('Activo creado con éxito.', 'success')
        return redirect(url_for('tecnico_inventario'))
    page = request.args.get('page', 1, type=int)
    query = Activo.query
    filters = {'search': request.args.get('search', ''), 'asignado_a_id': request.args.get('asignado_a_id', '')}
    if filters['search']: query = query.filter(or_(Activo.tipo.ilike(f"%{filters['search']}%"), Activo.marca.ilike(f"%{filters['search']}%"), Activo.modelo.ilike(f"%{filters['search']}%")))
    if filters['asignado_a_id']: query = query.filter_by(asignado_a_id=filters['asignado_a_id'])
    pagination = query.order_by(Activo.tipo).paginate(page=page, per_page=10)
    usuarios = Usuario.query.order_by(Usuario.nombre).all()
    return render_template("tecnico/tecnico_inventario.html", pagination=pagination, usuarios=usuarios, filters=filters)

@app.route("/tecnico/inventario/editar", methods=["POST"])
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def editar_activo():
    activo = Activo.query.get_or_404(request.form.get('id_activo_edit'))
    asignado_id = request.form.get('asignado_a_id_edit')
    activo.tipo, activo.marca, activo.modelo, activo.numero_serie = request.form['tipo_edit'], request.form['marca_edit'], request.form['modelo_edit'], request.form['numero_serie_edit']
    activo.asignado_a_id = int(asignado_id) if asignado_id else None
    db.session.commit(); flash('Activo actualizado con éxito.', 'success')
    return redirect(url_for('tecnico_inventario'))

@app.route("/tecnico/inventario/eliminar", methods=["POST"])
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def eliminar_activo():
    activo = Activo.query.get_or_404(request.form.get('id_activo_delete'))
    db.session.delete(activo); db.session.commit(); flash('Activo eliminado con éxito.', 'danger')
    return redirect(url_for('tecnico_inventario'))

@app.route("/tecnico/faq/gestion", methods=["GET", "POST"])
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def tecnico_faq_gestion():
    if request.method == "POST":
        nuevo_articulo = Articulo(titulo=request.form['titulo'], contenido=request.form['contenido'], categoria_faq=request.form['categoria_faq'])
        db.session.add(nuevo_articulo); db.session.commit(); flash('Artículo creado con éxito.', 'success')
        return redirect(url_for('tecnico_faq_gestion'))
    articulos = Articulo.query.order_by(Articulo.titulo).all()
    return render_template("tecnico/tecnico_faq_gestion.html", articulos=articulos)

@app.route("/tecnico/faq/editar", methods=["POST"])
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def editar_articulo():
    articulo = Articulo.query.get_or_404(request.form.get('id_articulo_edit'))
    articulo.titulo, articulo.contenido, articulo.categoria_faq = request.form['titulo_edit'], request.form['contenido_edit'], request.form['categoria_faq_edit']
    db.session.commit(); flash('Artículo actualizado con éxito.', 'success')
    return redirect(url_for('tecnico_faq_gestion'))

@app.route("/tecnico/faq/eliminar", methods=["POST"])
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def eliminar_articulo():
    articulo = Articulo.query.get_or_404(request.form.get('id_articulo_delete'))
    db.session.delete(articulo); db.session.commit(); flash('Artículo eliminado con éxito.', 'danger')
    return redirect(url_for('tecnico_faq_gestion'))

# --- RUTAS EXCLUSIVAS TÉCNICO NIVEL 2 ---
@app.route("/tecnico/usuarios", methods=["GET", "POST"])
@login_required
@role_required(['Técnico Nivel 2'])
def tecnico_usuarios():
    if request.method == "POST":
        hashed_password = generate_password_hash(request.form['password'])
        nuevo = Usuario(rut=request.form['rut'], nombre=request.form['nombre'], email=request.form['email'], password=hashed_password, rol=request.form['rol'])
        db.session.add(nuevo); db.session.commit(); flash('Usuario creado con éxito.', 'success')
        return redirect(url_for('tecnico_usuarios'))
    page = request.args.get('page', 1, type=int)
    query = Usuario.query
    filters = {'search': request.args.get('search', ''), 'rol': request.args.get('rol', '')}
    if filters['search']: query = query.filter(or_(Usuario.nombre.ilike(f"%{filters['search']}%"), Usuario.email.ilike(f"%{filters['search']}%")))
    if filters['rol']: query = query.filter_by(rol=filters['rol'])
    pagination = query.order_by(Usuario.nombre).paginate(page=page, per_page=10)
    return render_template("tecnico/tecnico_usuarios.html", pagination=pagination, filters=filters)

@app.route("/tecnico/usuarios/editar", methods=["POST"])
@login_required
@role_required(['Técnico Nivel 2'])
def editar_usuario():
    usuario = Usuario.query.get_or_404(request.form.get('id_usuario_edit'))
    usuario.rut, usuario.nombre, usuario.email, usuario.rol = request.form['rut_edit'], request.form['nombre_edit'], request.form['email_edit'], request.form['rol_edit']
    db.session.commit(); flash('Usuario actualizado con éxito.', 'success')
    return redirect(url_for('tecnico_usuarios'))

@app.route("/tecnico/usuarios/eliminar", methods=["POST"])
@login_required
@role_required(['Técnico Nivel 2'])
def eliminar_usuario():
    usuario_id = int(request.form.get('id_usuario_delete'))
    if usuario_id == session.get('usuario_id'):
        flash('No puedes eliminarte a ti mismo.', 'danger')
        return redirect(url_for('tecnico_usuarios'))
    usuario = Usuario.query.get_or_404(usuario_id)
    db.session.delete(usuario); db.session.commit(); flash('Usuario eliminado con éxito.', 'danger')
    return redirect(url_for('tecnico_usuarios'))

# --- RUTAS COMPARTIDAS ---
@app.route("/ticket/<int:ticket_id>", methods=["GET", "POST"])
@login_required
def ticket_detalle(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if session['rol'] == 'Usuario' and ticket.usuario_id != session['usuario_id']:
        flash("No tienes permiso para ver este ticket.", "danger")
        return redirect(url_for('usuario_mis_tickets'))
    if request.method == 'POST':
        if ticket.estado == 'Cerrado':
            flash("No se pueden añadir comentarios a un ticket cerrado.", "warning")
            return redirect(url_for('ticket_detalle', ticket_id=ticket.id))
        contenido = request.form.get("contenido")
        if contenido:
            comentario = Comentario(contenido=contenido, ticket_id=ticket.id, usuario_id=session.get('usuario_id'))
            db.session.add(comentario)
            autor = Usuario.query.get(session.get('usuario_id'))
            if autor.rol == 'Usuario' and ticket.tecnico_id:
                notificacion = Notificacion(mensaje=f"Hay una nueva respuesta en el ticket #{ticket.id}.", usuario_id=ticket.tecnico_id, ticket_id=ticket.id)
                db.session.add(notificacion)
            elif autor.rol in ["Técnico Nivel 1", "Técnico Nivel 2"]:
                notificacion = Notificacion(mensaje=f"Un técnico ha respondido a tu ticket #{ticket.id}.", usuario_id=ticket.usuario_id, ticket_id=ticket.id)
                db.session.add(notificacion)
            db.session.commit()
        return redirect(url_for('ticket_detalle', ticket_id=ticket.id))
    comentarios = Comentario.query.filter_by(ticket_id=ticket.id).order_by(Comentario.fecha_creacion.asc()).all()
    tecnicos_disponibles = Usuario.query.filter(Usuario.rol.like('Técnico%')).order_by(Usuario.nombre).all()
    return render_template("ticket_detalle.html", ticket=ticket, comentarios=comentarios, tecnicos=tecnicos_disponibles)

@app.route("/ticket/<int:ticket_id>/asignar")
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def asignar_ticket(ticket_id):
    ticket, tecnico = Ticket.query.get_or_404(ticket_id), Usuario.query.get(session.get('usuario_id'))
    ticket.tecnico_id = tecnico.id
    notificacion = Notificacion(mensaje=f"El técnico {tecnico.nombre} ha tomado tu ticket #{ticket.id}.", usuario_id=ticket.usuario_id, ticket_id=ticket.id)
    db.session.add(notificacion); db.session.commit(); flash(f"Te has asignado el ticket #{ticket.id}", "success")
    return redirect(url_for('ticket_detalle', ticket_id=ticket.id))

@app.route("/ticket/<int:ticket_id>/reasignar", methods=["POST"])
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def reasignar_ticket(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    nuevo_tecnico_id = request.form.get('tecnico_id')
    if not nuevo_tecnico_id:
        flash("Debes seleccionar un técnico.", "warning")
        return redirect(url_for('ticket_detalle', ticket_id=ticket.id))
    tecnico_actual_id = ticket.tecnico_id
    ticket.tecnico_id = nuevo_tecnico_id
    nuevo_tecnico = Usuario.query.get(nuevo_tecnico_id)
    notif_nuevo = Notificacion(mensaje=f"Se te ha reasignado el ticket #{ticket.id}.", usuario_id=nuevo_tecnico_id, ticket_id=ticket.id)
    db.session.add(notif_nuevo)
    if tecnico_actual_id and int(tecnico_actual_id) != int(nuevo_tecnico_id):
        notif_anterior = Notificacion(mensaje=f"El ticket #{ticket.id} fue reasignado a {nuevo_tecnico.nombre}.", usuario_id=tecnico_actual_id, ticket_id=ticket.id)
        db.session.add(notif_anterior)
    db.session.commit()
    flash(f"Ticket reasignado a {nuevo_tecnico.nombre} con éxito.", "success")
    return redirect(url_for('ticket_detalle', ticket_id=ticket.id))

@app.route("/ticket/<int:ticket_id>/estado", methods=["POST"])
@login_required
@role_required(['Técnico Nivel 1', 'Técnico Nivel 2'])
def cambiar_estado_ticket(ticket_id):
    ticket, nuevo_estado = Ticket.query.get_or_404(ticket_id), request.form.get('nuevo_estado')
    if ticket.estado != nuevo_estado:
        ticket.estado = nuevo_estado
        if nuevo_estado == 'Cerrado':
            ticket.fecha_cierre = datetime.utcnow()
        else:
            ticket.fecha_cierre = None
        notificacion = Notificacion(mensaje=f"El estado de tu ticket #{ticket.id} ha cambiado a '{nuevo_estado}'.", usuario_id=ticket.usuario_id, ticket_id=ticket.id)
        db.session.add(notificacion)
        db.session.commit()
        flash(f"El estado del ticket ha sido actualizado a '{nuevo_estado}'.", "info")
    return redirect(url_for('ticket_detalle', ticket_id=ticket.id))

if __name__ == "__main__":
    app.run(debug=True)