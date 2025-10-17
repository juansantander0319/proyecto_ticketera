# seed.py

from app import app, db, Usuario, Categoria, Ticket, Activo, get_next_technician_id
from faker import Faker
from werkzeug.security import generate_password_hash
import random
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
NUM_USUARIOS = 30
NUM_TECNICOS_N1 = 5
NUM_TECNICOS_N2 = 2
NUM_TICKETS = 50
NUM_ACTIVOS = 40

# Inicializa Faker para generar datos en español
fake = Faker('es_ES')

def run_seed():
    """Borra la BD y la llena con datos de prueba."""
    with app.app_context():
        print("Borrando la base de datos...")
        db.drop_all()
        db.create_all()

        print("Creando categorías...")
        cat1 = Categoria(nombre='Hardware', descripcion='Problemas con equipos físicos', sla_respuesta=2, sla_resolucion=8)
        cat2 = Categoria(nombre='Software', descripcion='Errores o instalación de programas', sla_respuesta=4, sla_resolucion=24)
        cat3 = Categoria(nombre='Redes', descripcion='Conectividad y acceso a internet', sla_respuesta=1, sla_resolucion=4)
        db.session.add_all([cat1, cat2, cat3])
        db.session.commit()
        todas_las_categorias = [cat1, cat2, cat3]
        
        print(f"Creando {NUM_USUARIOS} usuarios de prueba...")
        usuarios_creados = []
        for _ in range(NUM_USUARIOS):
            user = Usuario(
                nombre=fake.name(),
                email=fake.unique.email(),
                rut=f"{random.randint(10, 25)}.{fake.numerify('###.###')}-{fake.random_digit_or_empty()}",
                password=generate_password_hash('1234'),
                rol='Usuario'
            )
            usuarios_creados.append(user)
        db.session.add_all(usuarios_creados)

        print(f"Creando {NUM_TECNICOS_N1} técnicos de Nivel 1...")
        for _ in range(NUM_TECNICOS_N1):
            tec1 = Usuario(
                nombre=fake.name(),
                email=fake.unique.email(),
                rut=f"{random.randint(10, 15)}.{fake.numerify('###.###')}-{fake.random_digit_or_empty()}",
                password=generate_password_hash('tecnico123'),
                rol='Técnico Nivel 1'
            )
            db.session.add(tec1)

        print(f"Creando {NUM_TECNICOS_N2} técnicos de Nivel 2...")
        for _ in range(NUM_TECNICOS_N2):
            tec2 = Usuario(
                nombre=fake.name(),
                email=fake.unique.email(),
                rut=f"{random.randint(8, 9)}.{fake.numerify('###.###')}-{fake.random_digit_or_empty()}",
                password=generate_password_hash('admin123'),
                rol='Técnico Nivel 2'
            )
            db.session.add(tec2)

        # Guardamos todos los usuarios para obtener sus IDs
        db.session.commit()
        todos_los_usuarios_db = Usuario.query.all()

        print(f"Creando {NUM_ACTIVOS} activos de inventario...")
        tipos_activo = ['Laptop', 'Monitor', 'Teclado', 'Mouse', 'Impresora', 'Docking Station']
        marcas = ['Dell', 'HP', 'Lenovo', 'Apple', 'Logitech', 'Samsung']
        for _ in range(NUM_ACTIVOS):
            activo = Activo(
                tipo=random.choice(tipos_activo),
                marca=random.choice(marcas),
                modelo=fake.word().capitalize() + " " + str(random.randint(100, 999)),
                numero_serie=fake.ean(length=13),
                # 70% de probabilidad de que un activo esté asignado
                asignado_a_id=random.choice(todos_los_usuarios_db).id if random.random() > 0.3 else None
            )
            db.session.add(activo)

        print(f"Creando {NUM_TICKETS} tickets de prueba...")
        for _ in range(NUM_TICKETS):
            categoria_seleccionada = random.choice(todas_las_categorias)
            fecha_creacion = fake.date_time_this_year()
            vencimiento = fecha_creacion + timedelta(hours=categoria_seleccionada.sla_resolucion)
            
            ticket = Ticket(
                asunto=fake.sentence(nb_words=random.randint(4, 7)),
                descripcion=fake.paragraph(nb_sentences=3),
                estado=random.choice(['Abierto', 'En Proceso', 'Cerrado']),
                prioridad=random.choice(['Baja', 'Media', 'Alta', 'Crítica']),
                fecha_creacion=fecha_creacion,
                fecha_vencimiento_sla=vencimiento,
                usuario_id=random.choice(usuarios_creados).id,
                categoria_id=categoria_seleccionada.id,
                tecnico_id=get_next_technician_id() # Usamos la lógica round-robin!
            )
            # Si el ticket se crea como "Cerrado", le ponemos una fecha de cierre
            if ticket.estado == 'Cerrado':
                ticket.fecha_cierre = fecha_creacion + timedelta(hours=random.randint(1, categoria_seleccionada.sla_resolucion - 1))
            db.session.add(ticket)

        db.session.commit()
        print("\n¡Base de datos poblada con éxito! ✅")

if __name__ == '__main__':
    run_seed()