# seed.py

from app import app, db, Usuario, Categoria, Ticket, Activo, get_next_technician_id
from faker import Faker
from werkzeug.security import generate_password_hash
import random
from datetime import datetime, timedelta
from itertools import cycle

# --- CONFIGURACIÓN DE CANTIDADES ---
NUM_USUARIOS = 25
NUM_TECNICOS_N1 = 4
NUM_TECNICOS_N2 = 2
NUM_TICKETS = 40
NUM_ACTIVOS = 60

# Inicializa Faker con localización de Chile para nombres latinos
fake = Faker('es_CL')

# --- FUNCIÓN GENERADORA DE RUT VÁLIDO (Módulo 11) ---
def generar_rut():
    """Genera un RUT chileno válido con formato XX.XXX.XXX-Y"""
    numero = random.randint(10_000_000, 25_000_000)
    
    # Algoritmo de cálculo de dígito verificador
    reversed_digits = map(int, reversed(str(numero)))
    factors = cycle(range(2, 8))
    s = sum(d * f for d, f in zip(reversed_digits, factors))
    mod = (-s) % 11
    
    if mod == 10:
        dv = 'K'
    elif mod == 11: # Esto matemáticamente en este algoritmo suele ser 0, ajustamos caso borde
        dv = '0'
    else:
        dv = str(mod)
    
    # Formateo con puntos
    rut_str = f"{numero:,}".replace(",", ".")
    return f"{rut_str}-{dv}"

def generar_email(nombre):
    """Genera un email corporativo basado en el nombre"""
    # Normalizar: quitar tildes, espacios, etc.
    clean_name = nombre.lower().replace(' ', '.').replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u').replace('ñ','n')
    return f"{clean_name}@ticketera.cl"

def run_seed():
    """Borra la BD y la llena con datos coherentes y realistas."""
    with app.app_context():
        print("🔄 Reiniciando base de datos...")
        db.drop_all()
        db.create_all()

        # --- 1. CATEGORÍAS ---
        print("📂 Creando categorías de soporte...")
        cat_hw = Categoria(nombre='Hardware', descripcion='Fallas físicas en equipos, periféricos o componentes.', sla_respuesta=4, sla_resolucion=24)
        cat_sw = Categoria(nombre='Software', descripcion='Instalación, licencias, errores de S.O. y Office.', sla_respuesta=2, sla_resolucion=12)
        cat_red = Categoria(nombre='Redes y Conectividad', descripcion='Problemas de Wifi, VPN, acceso a internet.', sla_respuesta=1, sla_resolucion=4)
        cat_acc = Categoria(nombre='Accesos y Cuentas', descripcion='Reseteo de claves, creación de usuarios, permisos.', sla_respuesta=2, sla_resolucion=8)
        
        db.session.add_all([cat_hw, cat_sw, cat_red, cat_acc])
        db.session.commit()
        categorias = [cat_hw, cat_sw, cat_red, cat_acc]

        # --- 2. USUARIOS ---
        print(f"👥 Creando {NUM_USUARIOS} usuarios finales...")
        usuarios_db = []
        password_comun = generate_password_hash('1234') # Pre-calculamos para rapidez

        for _ in range(NUM_USUARIOS):
            nombre = fake.name()
            user = Usuario(
                nombre=nombre,
                email=generar_email(nombre),
                rut=generar_rut(),
                password=password_comun,
                rol='Usuario'
            )
            usuarios_db.append(user)
        
        db.session.add_all(usuarios_db)
        db.session.commit() # Commit intermedio para tener IDs

        # --- 3. TÉCNICOS ---
        print(f"🔧 Creando equipo técnico...")
        
        # Técnicos Nivel 1
        for _ in range(NUM_TECNICOS_N1):
            nombre = fake.name()
            tec1 = Usuario(
                nombre=nombre,
                email=f"soporte.{nombre.split()[0].lower()}@ticketera.cl", # ej: soporte.juan@...
                rut=generar_rut(),
                password=password_comun,
                rol='Técnico Nivel 1'
            )
            db.session.add(tec1)

        # Técnico Nivel 2 (Admin Genérico)
        tec2 = Usuario(
            nombre="Jefe de Soporte",
            email="jefe.soporte@ticketera.cl",
            rut=generar_rut(),
            password=password_comun,
            rol='Técnico Nivel 2'
        )
        db.session.add(tec2)

        # --- 4. TU USUARIO SOLICITADO ---
        print("🔑 Creando tu usuario Administrador (RUT: 12.345.678-9)...")
        mi_admin = Usuario(
            nombre='Administrador Principal',
            email='admin@ticketera.cl',
            rut='12.345.678-9',
            password=password_comun, # Clave: 1234
            rol='Técnico Nivel 2'
        )
        db.session.add(mi_admin)
        
        db.session.commit()
        
        # Obtenemos lista completa para asignaciones
        todos_usuarios = Usuario.query.filter_by(rol='Usuario').all()
        todos_tecnicos = Usuario.query.filter(Usuario.rol.like('Técnico%')).all()

        # --- 5. INVENTARIO REALISTA ---
        print(f"💻 Generando {NUM_ACTIVOS} activos de inventario...")
        
        modelos_pc = [
            ('Notebook', 'Dell', 'Latitude 5420'),
            ('Notebook', 'Lenovo', 'ThinkPad T14 Gen 2'),
            ('Notebook', 'HP', 'EliteBook 840 G8'),
            ('Notebook', 'Apple', 'MacBook Air M1'),
            ('All-in-One', 'HP', 'ProOne 400'),
        ]
        
        modelos_otros = [
            ('Monitor', 'Samsung', '24" IPS Borderless'),
            ('Monitor', 'Dell', 'P2419H Professional'),
            ('Impresora', 'Kyocera', 'Ecosys M2040dn'),
            ('Proyector', 'Epson', 'PowerLite X41'),
            ('Periférico', 'Logitech', 'Kit Teclado/Mouse MK270'),
        ]

        for _ in range(NUM_ACTIVOS):
            # 70% PCs, 30% Otros
            if random.random() > 0.3:
                tipo, marca, modelo = random.choice(modelos_pc)
            else:
                tipo, marca, modelo = random.choice(modelos_otros)

            activo = Activo(
                tipo=tipo,
                marca=marca,
                modelo=modelo,
                numero_serie=fake.bothify(text='??####-??##').upper(), # Genera algo como A1234-XY99
                asignado_a_id=random.choice(todos_usuarios).id if random.random() > 0.2 else None # 80% asignados
            )
            db.session.add(activo)

        # --- 6. TICKETS COHERENTES ---
        print(f"🎫 Generando {NUM_TICKETS} tickets con historial...")
        
        problemas_hw = [
            ("El monitor parpadea intermitentemente", "Desde ayer la pantalla se pone negra por segundos."),
            ("Teclado no responde algunas teclas", "La barra espaciadora y el Enter están pegados."),
            ("Notebook se calienta mucho", "El ventilador suena muy fuerte y el equipo está lento."),
            ("Mouse dejó de funcionar", "Probé cambiarle las pilas pero sigue sin prender.")
        ]
        problemas_sw = [
            ("No puedo abrir Outlook", "Me sale un error de conexión con el servidor Exchange."),
            ("Necesito instalar Adobe Acrobat", "Requiere clave de administrador para instalar."),
            ("Excel se cierra solo", "Al abrir archivos pesados el programa crashea."),
            ("Error al generar PDF", "La impresora virtual no aparece en la lista.")
        ]
        problemas_red = [
            ("Sin acceso a internet", "Aparece el triángulo amarillo en la conexión Wifi."),
            ("No puedo conectarme a la VPN", "Error de credenciales al intentar trabajar remoto."),
            ("Lentitud en la red", "Las páginas tardan mucho en cargar hoy.")
        ]
        problemas_acc = [
            ("Olvide mi contraseña", "Necesito restablecer mi clave de dominio."),
            ("No tengo acceso a la carpeta compartida", "Dice acceso denegado en la unidad Z:."),
            ("Crear correo para nuevo ingreso", "Entra un practicante el lunes, necesito su cuenta.")
        ]

        for _ in range(NUM_TICKETS):
            # Elegir categoría y un problema acorde
            cat = random.choice(categorias)
            if cat.nombre == 'Hardware': asunto, desc = random.choice(problemas_hw)
            elif cat.nombre == 'Software': asunto, desc = random.choice(problemas_sw)
            elif cat.nombre == 'Redes y Conectividad': asunto, desc = random.choice(problemas_red)
            else: asunto, desc = random.choice(problemas_acc)

            # Fecha aleatoria en los últimos 30 días
            fecha_creacion = datetime.utcnow() - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            
            # Estado y lógica
            estado = random.choice(['Abierto', 'En Proceso', 'Cerrado'])
            prioridad = random.choice(['Baja', 'Media', 'Alta', 'Crítica'])
            
            # Si es Crítica, a veces la fecha de SLA ya pasó (para probar alertas)
            if prioridad == 'Crítica' and random.random() > 0.5:
                vencimiento = fecha_creacion + timedelta(hours=1) # SLA corto que ya venció
            else:
                vencimiento = fecha_creacion + timedelta(hours=cat.sla_resolucion)

            ticket = Ticket(
                asunto=asunto,
                descripcion=desc,
                estado=estado,
                prioridad=prioridad,
                fecha_creacion=fecha_creacion,
                fecha_vencimiento_sla=vencimiento,
                usuario_id=random.choice(todos_usuarios).id,
                categoria_id=cat.id,
                tecnico_id=get_next_technician_id() # Asignación Round Robin
            )

            # Si está cerrado, poner fecha de cierre
            if estado == 'Cerrado':
                ticket.fecha_cierre = fecha_creacion + timedelta(hours=random.randint(1, 48))

            db.session.add(ticket)

        db.session.commit()
        print("\n✅ ¡Base de datos poblada con éxito!")
        print("------------------------------------------------")
        print(f"🔹 Usuarios creados: {NUM_USUARIOS}")
        print(f"🔹 Activos creados: {NUM_ACTIVOS}")
        print(f"🔹 Tickets creados: {NUM_TICKETS}")
        print(f"🔹 Admin disponible: 12.345.678-9  /  1234")
        print("------------------------------------------------")

if __name__ == '__main__':
    run_seed()