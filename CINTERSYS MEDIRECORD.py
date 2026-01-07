import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime, timedelta
import sqlite3
import json
import os
import re
import csv
import shutil
import logging
from tkinter import font as tkfont
from PIL import Image, ImageTk

class DatabaseManager:
    def __init__(self, db_name="medirecord.db"):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users Table
            cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL
            )''')
            
            # Hotfix: Check if columns exist (for pre-existing tables)
            cursor.execute("PRAGMA table_info(usuarios)")
            columns = [info[1] for info in cursor.fetchall()]
            
            # Check password
            if 'password' not in columns:
                try:
                    cursor.execute("ALTER TABLE usuarios ADD COLUMN password TEXT NOT NULL DEFAULT 'admin123'")
                    logging.info("Hotfix applied: Added 'password' column to 'usuarios' table.")
                except Exception as e:
                    logging.error(f"Error applying hotfix (password) to usuarios table: {e}")

            # Check username
            if 'username' not in columns:
                try:
                    cursor.execute("ALTER TABLE usuarios ADD COLUMN username TEXT NOT NULL DEFAULT 'admin'")
                    logging.info("Hotfix applied: Added 'username' column to 'usuarios' table.")
                except Exception as e:
                    logging.error(f"Error applying hotfix (username) to usuarios table: {e}")
            
            # Patients Table
            cursor.execute('''CREATE TABLE IF NOT EXISTS pacientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_registro TEXT,
                hora_registro TEXT,
                nombres TEXT,
                apellidos TEXT,
                fecha_nacimiento TEXT,
                edad TEXT,
                sexo TEXT,
                cedula TEXT UNIQUE,
                telefono TEXT,
                direccion TEXT,
                ciudad TEXT,
                pais TEXT,
                estado_civil TEXT,
                instruccion TEXT,
                data_json TEXT -- Stores extra lists like evoluciones, controles, etc.
            )''')

            # Anamnesis Table
            cursor.execute('''CREATE TABLE IF NOT EXISTS anamnesis (
                paciente_id INTEGER PRIMARY KEY,
                tipo_consulta TEXT,
                motivo TEXT,
                enfermedad_actual TEXT,
                ant_familiares TEXT,
                ant_personales TEXT,
                alergias TEXT,
                medicacion TEXT,
                cirugias_previas TEXT,
                hospitalizaciones TEXT,
                dieta TEXT,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
            )''')
            
            # Ginecologico Table
            cursor.execute('''CREATE TABLE IF NOT EXISTS ginecologico (
                paciente_id INTEGER PRIMARY KEY,
                menarquia TEXT,
                ciclos TEXT,
                fum TEXT,
                gestas TEXT,
                partos TEXT,
                abortos TEXT,
                cesareas TEXT,
                FOREIGN KEY (paciente_id) REFERENCES pacientes (id)
            )''')
            
            conn.commit()

            # Hotfix: Check if columns exist in 'pacientes' table
            cursor.execute("PRAGMA table_info(pacientes)")
            columns = [info[1] for info in cursor.fetchall()]
            
            # List of columns to check and their types
            new_cols = {
                'hora_registro': 'TEXT',
                'pais': 'TEXT'
            }
            
            for col_name, col_type in new_cols.items():
                if col_name not in columns:
                    try:
                        cursor.execute(f"ALTER TABLE pacientes ADD COLUMN {col_name} {col_type}")
                        logging.info(f"Hotfix applied: Added '{col_name}' column to 'pacientes' table.")
                    except Exception as e:
                        logging.error(f"Error applying hotfix ({col_name}) to pacientes table: {e}")
            
            conn.commit()


    def add_user(self, username, password):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT OR IGNORE INTO usuarios (username, password) VALUES (?, ?)', (username, password))
                conn.commit()
        except Exception as e:
            logging.error(f"Error adding user: {e}")

    def verify_user(self, username, password):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT password FROM usuarios WHERE username = ?', (username,))
            result = cursor.fetchone()
            if result and result[0] == password:
                return True
            return False

    def upsert_patient(self, p):
        """Insert or Update patient. p is a dictionary matching the app structure."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if exists by CEDULA or ID (if strictly handling updates by ID)
                # Ideally, we depend on ID. But for dict passed, let's see if ID exists and matches DB.
                # Simplify: Upsert by ID if present, else Insert.
                
                # Extract main fields
                main_data = (
                    p.get('fecha', ''), p.get('hora', ''), p.get('nombres', ''), 
                    p.get('apellidos', ''), p.get('fecha_nac', ''), p.get('edad', ''), 
                    p.get('sexo', ''), p.get('cedula', ''), p.get('telefono', ''),
                    p.get('direccion', ''), p.get('ciudad', ''), p.get('pais', ''),
                    p.get('estado_civil', ''), p.get('instruccion', '')
                )
                
                # Extract extra data for JSON
                extras = {k: v for k, v in p.items() if k not in [
                    'id', 'fecha', 'hora', 'nombres', 'apellidos', 'fecha_nac', 'edad', 'sexo',
                    'cedula', 'telefono', 'direccion', 'ciudad', 'pais', 'estado_civil', 
                    'instruccion', 'anamnesis', 'ginecologico'
                ]}
                json_data = json.dumps(extras)
                
                patient_id = p.get('id')
                
                if patient_id:
                     # Update
                    cursor.execute('''UPDATE pacientes SET 
                        fecha_registro=?, hora_registro=?, nombres=?, apellidos=?, 
                        fecha_nacimiento=?, edad=?, sexo=?, cedula=?, telefono=?, 
                        direccion=?, ciudad=?, pais=?, estado_civil=?, instruccion=?, data_json=?
                        WHERE id=?''', main_data + (json_data, patient_id))
                else:
                    # Insert
                    cursor.execute('''INSERT INTO pacientes (
                        fecha_registro, hora_registro, nombres, apellidos, 
                        fecha_nacimiento, edad, sexo, cedula, telefono, 
                        direccion, ciudad, pais, estado_civil, instruccion, data_json)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', main_data + (json_data,))
                    patient_id = cursor.lastrowid
                    p['id'] = patient_id # Update ID in dict

                # Anamnesis
                anam = p.get('anamnesis', {})
                cursor.execute('DELETE FROM anamnesis WHERE paciente_id=?', (patient_id,))
                cursor.execute('''INSERT INTO anamnesis (
                    paciente_id, tipo_consulta, motivo, enfermedad_actual, ant_familiares, 
                    ant_personales, alergias, medicacion, cirugias_previas, hospitalizaciones, dieta)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (
                        patient_id, anam.get('tipo_consulta', ''), anam.get('motivo', ''),
                        anam.get('enfermedad_actual', ''), anam.get('ant_familiares', ''),
                        anam.get('ant_personales', ''), anam.get('alergias', ''),
                        anam.get('medicacion', ''), anam.get('cirugias', ''), # Mapped key
                        anam.get('hospitalizaciones', ''), anam.get('dieta', '')
                    ))

                # Ginecologico
                gine = p.get('ginecologico', {})
                cursor.execute('DELETE FROM ginecologico WHERE paciente_id=?', (patient_id,))
                if gine: # Only insert if data exists
                     cursor.execute('''INSERT INTO ginecologico (
                        paciente_id, menarquia, ciclos, fum, gestas, partos, abortos, cesareas)
                        VALUES (?,?,?,?,?,?,?,?)''', (
                            patient_id, gine.get('menarquia', ''), gine.get('ciclos', ''),
                            gine.get('fum', ''), gine.get('gestas', ''), gine.get('partos', ''),
                            gine.get('abortos', ''), gine.get('cesareas', '')
                        ))
                
                conn.commit()
                return patient_id
        except Exception as e:
            logging.error(f"Error upserting patient: {e}")
            raise e

    def get_all_patients(self):
        patients = []
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Fetch main data
                cursor.execute('SELECT * FROM pacientes')
                rows = cursor.fetchall()
                
                for row in rows:
                    p = {
                        'id': row['id'], 'fecha': row['fecha_registro'], 'hora': row['hora_registro'],
                        'nombres': row['nombres'], 'apellidos': row['apellidos'], 
                        'fecha_nac': row['fecha_nacimiento'], 'edad': row['edad'], 'sexo': row['sexo'],
                        'cedula': row['cedula'], 'telefono': row['telefono'], 
                        'direccion': row['direccion'], 'ciudad': row['ciudad'], 'pais': row['pais'],
                        'estado_civil': row['estado_civil'], 'instruccion': row['instruccion']
                    }
                    
                    # Updates from JSON
                    if row['data_json']:
                        p.update(json.loads(row['data_json']))
                    
                    # Fetch Anamnesis
                    cursor.execute('SELECT * FROM anamnesis WHERE paciente_id=?', (row['id'],))
                    anam_row = cursor.fetchone()
                    if anam_row:
                        p['anamnesis'] = {
                            'tipo_consulta': anam_row['tipo_consulta'], 'motivo': anam_row['motivo'],
                            'enfermedad_actual': anam_row['enfermedad_actual'], 
                            'ant_familiares': anam_row['ant_familiares'],
                            'ant_personales': anam_row['ant_personales'], 'alergias': anam_row['alergias'],
                            'medicacion': anam_row['medicacion'], 'cirugias': anam_row['cirugias_previas'],
                            'hospitalizaciones': anam_row['hospitalizaciones'], 'dieta': anam_row['dieta']
                        }
                    else:
                        p['anamnesis'] = {}

                    # Fetch Ginecologico
                    cursor.execute('SELECT * FROM ginecologico WHERE paciente_id=?', (row['id'],))
                    gine_row = cursor.fetchone()
                    if gine_row:
                        p['ginecologico'] = {
                            'menarquia': gine_row['menarquia'], 'ciclos': gine_row['ciclos'],
                            'fum': gine_row['fum'], 'gestas': gine_row['gestas'],
                            'partos': gine_row['partos'], 'abortos': gine_row['abortos'],
                            'cesareas': gine_row['cesareas']
                        }
                    
                    patients.append(p)
        except Exception as e:
            logging.error(f"Error fetching patients: {e}")
        return patients
            
    def migrate_from_json(self):
        """Migrate legacy JSON files to SQLite"""
        # Migrate Users
        if os.path.exists("usuarios.json"):
            try:
                with open("usuarios.json", "r") as f:
                    users = json.load(f)
                    for u, p in users.items():
                        self.add_user(u, p)
                logging.info("Users migrated from JSON.")
            except Exception as e:
                logging.error(f"Error migrating users: {e}")

        # Migrate Patients
        if os.path.exists("pacientes.json"):
            # Check if DB is empty
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM pacientes")
                if cursor.fetchone()[0] == 0:
                    try:
                        with open("pacientes.json", "r", encoding='utf-8') as f:
                            patients = json.load(f)
                            for p in patients:
                                # Ensure minimal fields or dict structure for compatibility
                                if 'anamnesis' not in p: p['anamnesis'] = {}
                                self.upsert_patient(p)
                        logging.info(f"Migrated {len(patients)} patients from JSON.")
                        # Rename backup
                        shutil.move("pacientes.json", "pacientes.json.bak")
                    except Exception as e:
                         logging.error(f"Error migrating patients: {e}")
                         
        # Ensure at least one user exists (Default Admin)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM usuarios")
            if cursor.fetchone()[0] == 0:
                self.add_user("admin", "admin123")
                logging.info("Default admin user created.")

class SistemaRegistroPacientes:
    def __init__(self, root):
        self.root = root
        self.root.title("CINTERSYS MEDIRECORD")
        
        # Configurar icono
        try:
            if os.path.exists("favicon.ico"):
                self.root.iconbitmap("favicon.ico")
            elif os.path.exists("logo.jpg"):
                img = Image.open("logo.jpg")
                photo = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, photo)
                self.root._icon = photo # Mantener referencia
        except Exception as e:
            logging.error(f"Error al cargar el icono: {e}")

        self.root.geometry("1100x650")
        self.root.state('zoomed') # Maximizar ventana
        
        # Configurar logging
        self.setup_logging()
        
        # Inicializar base de datos
        self.db = DatabaseManager()
        self.db.migrate_from_json()
        
        # Configurar estilo
        self.setup_styles()
        
        # Cargar datos CIE-10
        self.configurar_datos_cie10()
        
        # Configurar atajos de teclado
        self.configurar_atajos()
        
        # Variables globales
        self.pacientes = []
        self.current_user = "admin"  # Usuario por defecto
        
        # Inicializar lista de pacientes
        self.cargar_datos()
        
        # Configurar autoguardado
        self.setup_autoguardado()
        
        # Listas de exámenes predefinidos
        self.examenes_lab_comunes = [
            "Hemograma completo",
            "Glicemia en ayunas",
            "Perfil lipídico (Colesterol total, HDL, LDL, Triglicéridos)",
            "Urianálisis completo",
            "Creatinina sérica",
            "Urea",
            "Ácido úrico",
            "Perfil hepático (TGO, TGP, Bilirrubina, Fosfatasa alcalina)",
            "TSH (Hormona estimulante de tiroides)",
            "TP y TTP (Tiempo de protrombina y tromboplastina)",
            "Electrolitos séricos (Na, K, Cl)",
            "Proteína C reactiva (PCR)",
            "VSG (Velocidad de sedimentación globular)",
            "Hemoglobina glicosilada (HbA1c)",
            "Coprológico",
            "Parasitológico seriado",
            "Grupo sanguíneo y factor Rh",
            "Prueba de embarazo en sangre",
            "PSA (Antígeno prostático específico)",
            "Cultivo y antibiograma (según muestra)"
        ]
        
        self.examenes_imagenologia = [
            "Radiografía de tórax",
            "Radiografía abdominal",
            "Radiografía de columna",
            "Radiografía de extremidades",
            "Ecografía abdominal",
            "Ecografía pélvica",
            "Ecografía de tiroides",
            "Ecografía de partes blandas",
            "Tomografía axial computarizada (TAC)",
            "Resonancia magnética",
            "Mamografía bilateral",
            "Densitometría ósea",
            "Ultrasonido doppler vascular",
            "Eco cardiograma",
            "Endoscopia digestiva alta",
            "Colonoscopia",
            "Arteriografía",
            "Urografía excretora",
            "Gammagrafía ósea",
            "PET Scan"
        ]
        
        # Listas dinámicas para tratamientos
        self.cirugias_comunes = [
            "Circuncisión", "Colecistectomía laparoscópica", "Exéresis de tumor superficial",
            "Frenilectomía sublingual", "Herniorrafia/hernioplastia inguinal", "Hidrocelectomía",
            "Ligadura tubárica laparoscópica", "Orquidopexia", "Orquiectomía",
            "Varicocelectomía", "Vasectomía", "Otras"
        ]
        
        self.grupos_farmacologicos = [
            "Analgesicos",
            "Antiinflamatorios (AINEs)",
            "Antibióticos",
            "Antipiréticos",
            "Antihistamínicos",
            "Antiácidos/Protectores Gástricos",
            "Antidiabéticos",
            "Antihipertensivos",
            "Cardiovasculares",
            "Dermatológicos",
            "Vitaminas y Suplementos",
            "Otros"
        ]
        
        # Variables para datos del paciente
        self.setup_variables()
        
        # Crear interfaz con pestañas
        self.crear_interfaz_con_pestanas()
        
        # Verificar próximas consultas
        self.verificar_proximas_consultas()
        
        # Crear menú
        self.crear_menu()
        
        logging.info("Sistema de registro de pacientes iniciado correctamente")
    
    def setup_logging(self):
        """Configura el sistema de logging"""
        logging.basicConfig(
            filename='sistema_pacientes.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.info("=" * 50)
        logging.info("Iniciando sistema de registro de pacientes")
    
    def setup_styles(self):
        """Configura estilos para la interfaz"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configurar colores modernos (Pizarra + Azul Indigo + Esmeralda)
        self.color_principal = "#1e293b" # Slate 800
        self.color_secundario = "#3b82f6" # Blue 500
        self.color_fondo = "#f8fafc"      # Slate 50
        self.color_blanco = "#ffffff"
        self.color_boton = "#10b981"      # Emerald 500
        self.color_texto = "#334155"      # Slate 700
        self.color_acento = "#6366f1"    # Indigo 500
        
        # Colores para pestañas (Modernizados)
        self.colores_pestanas = {
            'Info': '#3b82f6',         # Azul
            'Anamnesis': '#ec4899',    # Rosa
            'Signos': '#ef4444',       # Rojo
            'Fisico': '#f59e0b',       # Ambar
            'Examenes': '#8b5cf6',     # Violeta
            'Diagnostico': '#06b6d4',  # Cian
            'Tratamiento': '#f97316',  # Naranja
            'Control': '#10b981',      # Esmeralda
            'Lista': '#64748b',        # Pizarra
            'Estadisticas': '#6366f1'  # Indigo
        }
        
        self.root.configure(bg=self.color_fondo)
        
        # Configurar estilos de widgets
        style.configure("TNotebook", background=self.color_fondo, borderwidth=0)
        style.configure("TNotebook.Tab", padding=[15, 8], font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", 
                  background=[("selected", self.color_blanco)],
                  foreground=[("selected", self.color_principal)])

        style.configure("Treeview", 
                        background=self.color_blanco,
                        foreground=self.color_texto,
                        rowheight=35,
                        fieldbackground=self.color_blanco,
                        font=("Segoe UI", 10))
        style.configure("Treeview.Heading", 
                        background=self.color_fondo,
                        foreground=self.color_principal,
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#dbeafe")]) # Soft blue highlight

        # Estilo para botones primarios
        style.configure("Action.TButton", 
                        font=("Segoe UI", 10, "bold"),
                        background=self.color_acento,
                        foreground="white",
                        padding=10)
    
    def configurar_atajos(self):
        """Configura atajos de teclado"""
        self.root.bind('<Control-s>', lambda e: self.guardar_registro())
        self.root.bind('<Control-l>', lambda e: self.limpiar_formulario_completo())
        self.root.bind('<Control-e>', lambda e: self.exportar_json())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        self.root.bind('<Control-f>', lambda e: self.focus_busqueda())
        self.root.bind('<F1>', lambda e: self.mostrar_ayuda())
        self.root.bind('<F5>', lambda e: self.actualizar_lista_pacientes())
        self.root.bind('<Delete>', lambda e: self.eliminar_registro())
    
    def focus_busqueda(self):
        """Coloca el foco en el campo de búsqueda"""
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Frame):
                for child in widget.winfo_children():
                    if isinstance(child, tk.Frame):
                        for entry in child.winfo_children():
                            if isinstance(entry, tk.Entry) and hasattr(entry, 'busqueda_field'):
                                entry.focus_set()
                                return
    
    def setup_autoguardado(self):
        """Configura autoguardado periódico"""
        self.root.after(300000, self.autoguardar)  # 300000 ms = 5 minutos
    
    def autoguardar(self):
        """Guarda automáticamente los datos"""
        try:
            if self.pacientes:
                self.guardar_datos()
                logging.info("Autoguardado realizado exitosamente")
            # Reprogramar el siguiente autoguardado
            self.root.after(300000, self.autoguardar)
        except Exception as e:
            logging.error(f"Error en autoguardado: {str(e)}")
    
    def crear_backup(self):
        """Crea un backup de los datos"""
        try:
            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"backup_pacientes_{fecha}.json"
            
            if os.path.exists("pacientes.json"):
                shutil.copy2("pacientes.json", backup_file)
                logging.info(f"Backup creado: {backup_file}")
                return backup_file
            return None
        except Exception as e:
            logging.error(f"Error al crear backup: {str(e)}")
            return None
    
    def configurar_datos_cie10(self):
        """Configura la lista de diagnósticos CIE-10 más comunes"""
        self.cie10_data = [
            "A09 - DIARREA Y GASTROENTERITIS DE PRESUNTO ORIGEN INFECCIOSO",
            "J00 - RINOFARINGITIS AGUDA [RESFRIADO COMUN]",
            "J01 - SINUSITIS AGUDA",
            "J02 - FARINGITIS AGUDA",
            "J03 - AMIGDALITIS AGUDA",
            "J06 - INFECCIONES AGUDAS DE LAS VIAS RESPIRATORIAS SUPERIORES",
            "J18 - NEUMONIA, ORGANISMO NO ESPECIFICADO",
            "J20 - BRONQUITIS AGUDA",
            "J45 - ASMA",
            "I10 - HIPERTENSION ESENCIAL (PRIMARIA)",
            "E11 - DIABETES MELLITUS NO INSULINODEPENDIENTE",
            "E10 - DIABETES MELLITUS INSULINODEPENDIENTE",
            "E78 - TRASTORNOS DEL METABOLISMO DE LAS LIPOPROTEINAS",
            "E66 - OBESIDAD",
            "N39 - OTROS TRASTORNOS DEL SISTEMA URINARIO (INFECCION URINARIA)",
            "K29 - GASTRITIS Y DUODENITIS",
            "K21 - ENFERMEDAD DEL REFLUJO GASTROESOFAGICO",
            "K30 - DISPEPSIA",
            "K58 - SINDROME DEL COLON IRRITABLE",
            "K59 - OTROS TRASTORNOS FUNCIONALES DEL INTESTINO (ESTREÑIMIENTO)",
            "M54 - DORSALGIA (DOLOR DE ESPALDA)",
            "M25 - OTROS TRASTORNOS ARTICULARES",
            "M17 - GONARTROSIS [ARTROSIS DE LA RODILLA]",
            "M79 - OTROS TRASTORNOS DE LOS TEJIDOS BLANDOS",
            "G44 - OTROS SINDROMES DE CEFALEA",
            "G43 - MIGRAÑA",
            "H10 - CONJUNTIVITIS",
            "H66 - OTITIS MEDIA SUPURATIVA Y LA NO ESPECIFICADA",
            "L03 - CELULITIS",
            "L20 - DERMATITIS ATOPICA",
            "L30 - OTRAS DERMATITIS",
            "L50 - URTICARIA",
            "B35 - DERMATOFITOSIS (MICOSIS)",
            "S01 - HERIDA DE LA CABEZA",
            "S61 - HERIDA DE LA MUÑECA Y DE LA MANO",
            "T14 - TRAUMATISMO DE REGION DEL CUERPO NO ESPECIFICADA",
            "R05 - TOS",
            "R07 - DOLOR DE GARGANTA Y EN EL PECHO",
            "R10 - DOLOR ABDOMINAL Y PELVICO",
            "R50 - FIEBRE DE ORIGEN DESCONOCIDO",
            "R51 - CEFALEA",
            "R55 - SINCOPE Y COLAPSO",
            "Z00 - EXAMEN GENERAL E INVESTIGACION DE PERSONAS SIN QUEJAS",
            "Z76 - PERSONAS EN CONTACTO CON LOS SERVICIOS DE SALUD",
            # Quirúrgicos comunes y otros
            "K35 - APENDICITIS AGUDA",
            "K80 - COLELITIASIS",
            "K81 - COLECISTITIS",
            "K40 - HERNIA INGUINAL",
            "K42 - HERNIA UMBILICAL",
            "K43 - HERNIA VENTRAL",
            "N40 - HIPERPLASIA DE LA PROSTATA",
            "N20 - CALCULO DEL RIÑON Y DEL URETER",
            "D25 - LEIOMIOMA DEL UTERO",
            "N80 - ENDOMETRIOSIS",
            "N83 - TRASTORNOS NO INFLAMATORIOS DEL OVARIO",
            "O80 - PARTO UNICO ESPONTANEO",
            "O82 - PARTO UNICO POR CESAREA",
            "S82 - FRACTURA DE LA PIERNA, INCLUSIVE EL TOBILLO",
            "S52 - FRACTURA DEL ANTEBRAZO",
            "S42 - FRACTURA DEL HOMBRO Y DEL BRAZO",
            "S22 - FRACTURA DE LA COSTILLA, EL ESTERNON Y COLUMNA TORACICA",
            "I84 - HEMORROIDES",
            "L72 - QUISTE FOLICULAR DE LA PIEL Y D. TEJIDO SUBCUTANEO",
            "L02 - ABSCESO CUTANEO, FURUNCULO Y CARBUNCO",
            "K60 - FISURA Y FISTULA DE LAS REGIONES ANAL Y RECTAL",
            "N43 - HIDROCELE Y ESPERMATOCELE",
            "N47 - PREPUCIO REDUNDANTE, FIMOSIS Y PARAFIMOSIS",
            "D17 - LIPOMA",
            "M20 - DEFORMIDADES ADQUIRIDAS DE LOS DEDOS DE LA MANO Y DEL PIE",
            "M67 - OTROS TRASTORNOS DE LA SINOVIA Y DEL TENDON",
            "I83 - VENAS VARICOSAS DE LAS EXTREMIDADES INFERIORES",
            "H25 - CATARATA SENIL",
            "H00 - ORZUELO Y CALACIO",
            "T20 - QUEMADURA Y CORROSION DE LA CABEZA Y EL CUELLO",
            "T21 - QUEMADURA Y CORROSION DEL TRONCO",
            "T22 - QUEMADURA Y CORROSION DEL HOMBRO Y MIEMBRO SUPERIOR",
            "J34 - OTROS TRASTORNOS DE LA NARIZ Y DE LOS SENOS PARANASALES",
            "J35 - ENFERMEDADES CRONICAS DE LAS AMIGDALAS Y ADENOIDES",
            "N60 - DISPLASIA MAMARIA BENIGNA",
            "N63 - MASA NO ESPECIFICADA EN LA MAMA",
            "C50 - TUMOR MALIGNO DE LA MAMA",
            "C53 - TUMOR MALIGNO DEL CUELLO DEL UTERO",
            "C61 - TUMOR MALIGNO DE LA PROSTATA",
            "C18 - TUMOR MALIGNO DEL COLON",
            "C16 - TUMOR MALIGNO DEL ESTOMAGO",
            "B20 - ENFERMEDAD POR VIH",
            "A15 - TUBERCULOSIS RESPIRATORIA",
            "A90 - FIEBRE DEL DENGUE [DENGUE CLASICO]",
            "B50 - PALUDISMO POR PLASMODIUM FALCIPARUM",
            "A00 - COLERA",
            "A01 - FIEBRES TIFOIDEA Y PARATIFOIDEA",
            "B01 - VARICELA",
            "B02 - HERPES ZOSTER",
            "B00 - INFECCIONES POR EL VIRUS DEL HERPES [HERPES SIMPLE]",
            "B26 - PAROTIDITIS INFECCIOSA",
            "J10 - INFLUENZA DEBIDA A VIRUS DE LA INFLUENZA IDENTIFICADO",
            "U07 - USO DE EMERGENCIA DE U07 (COVID-19)",
            "I20 - ANGINA DE PECHO",
            "I21 - INFARTO AGUDO DEL MIOCARDIO",
            "I50 - INSUFICIENCIA CARDIACA",
            "I64 - ACCIDENTE VASCULAR ENCEFALICO AGUDO",
            "F32 - EPISODIO DEPRESIVO",
            "F41 - OTROS TRASTORNOS DE ANSIEDAD"
        ]
        self.cie10_data.sort()

    def setup_variables(self):
        """Configura las variables para almacenar datos"""
        # Información básica
        self.id_var = tk.StringVar(value=str(len(self.pacientes) + 1)) # Usado como Historia Clínica
        self.fecha_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        self.hora_var = tk.StringVar(value=datetime.now().strftime("%H:%M"))
        self.nombres_var = tk.StringVar()
        self.apellidos_var = tk.StringVar()
        self.fecha_nac_var = tk.StringVar()
        self.edad_var = tk.StringVar()
        self.sexo_var = tk.StringVar(value="Masculino")
        self.cedula_var = tk.StringVar()
        self.telefono_var = tk.StringVar()
        self.direccion_var = tk.StringVar()
        self.ciudad_var = tk.StringVar()
        self.pais_var = tk.StringVar(value="ECUADOR") # Nuevo campo País
        self.pais_var = tk.StringVar(value="ECUADOR") # Nuevo campo País
        self.instruccion_var = tk.StringVar(value="Ninguno")
        self.estado_civil_var = tk.StringVar(value="Soltero")
        
        # Anamnesis
        self.consulta_tipo_var = tk.StringVar(value="Clínica")
        self.dieta_var = tk.StringVar(value="General")
        self.motivo_corto_var = tk.StringVar()
        self.antecedentes_familiares_var = tk.StringVar()
        # Los textos largos (enfermedad actual, etc) se manejarán con Text widgets
        
        # Signos vitales
        self.presion_sistolica_var = tk.StringVar() # Separado
        self.presion_diastolica_var = tk.StringVar() # Separado
        self.presion_clasificacion_var = tk.StringVar() # Nuevo: Clasificación HTA
        self.frecuencia_var = tk.StringVar()
        self.temperatura_var = tk.StringVar()
        self.respiratoria_var = tk.StringVar()
        self.saturacion_var = tk.StringVar()
        self.peso_var = tk.StringVar()
        self.talla_var = tk.StringVar()
        self.imc_var = tk.StringVar()
        self.imc_clasificacion_var = tk.StringVar(value="")
        
        # Examen Físico (Desglosado)
        self.fisico_apariencia_var = tk.StringVar()
        self.fisico_piel_var = tk.StringVar()
        self.fisico_cabeza_var = tk.StringVar()
        self.fisico_cuello_var = tk.StringVar()
        self.fisico_torax_var = tk.StringVar()
        self.fisico_abdomen_var = tk.StringVar()
        self.fisico_extremidades_var = tk.StringVar()
        self.fisico_genital_var = tk.StringVar()
        self.fisico_anoperineal_var = tk.StringVar()
        self.fisico_otros_var = tk.StringVar()
        
        # Exámenes
        self.lista_lab_var = tk.StringVar()
        self.lista_img_var = tk.StringVar()
        
        # Búsqueda
        self.busqueda_var = tk.StringVar()
        self.tipo_busqueda_var = tk.StringVar(value="nombre")
        
        # Tratamiento (Nuevo)
        self.tratamiento_tipo_var = tk.StringVar() # Farmacológico / Terapéutico
        self.cie10_seleccion_var = tk.StringVar()
        
        # Planificación
        self.prox_consulta_var = tk.StringVar()
        
        # Variables para control del paciente
        self.control_resultados_var = tk.StringVar()
        self.control_resultados_var = tk.StringVar()
        self.control_evolucion_var = tk.StringVar()
        self.control_tratamiento_var = tk.StringVar()
        self.control_nuevos_examenes_var = tk.StringVar()
        
        # Ginecológicos (Variables de control)
        self.ginecologicos_menarquia_var = tk.StringVar()
        self.ginecologicos_ciclos_var = tk.StringVar()
        self.ginecologicos_fum_var = tk.StringVar() # Fecha Ultima Menstruacion
        self.ginecologicos_gestas_var = tk.StringVar()
        self.ginecologicos_partos_var = tk.StringVar()
        self.ginecologicos_abortos_var = tk.StringVar()
        self.ginecologicos_cesareas_var = tk.StringVar()
        self.control_tratamiento_var = tk.StringVar()
        self.control_nuevos_examenes_var = tk.StringVar()
        self.control_seleccionado_index = None # Índice del control seleccionado
        
        # Variables para estadísticas
        self.estadisticas_mes_var = tk.StringVar()
        self.estadisticas_total_var = tk.StringVar()
    
    def validar_fecha(self, fecha_str):
        """Valida el formato de fecha DD/MM/AAAA"""
        try:
            datetime.strptime(fecha_str, "%d/%m/%Y")
            return True
        except ValueError:
            return False
    
    def validar_hora(self, hora_str):
        """Valida el formato de hora HH:MM"""
        try:
            datetime.strptime(hora_str, "%H:%M")
            return True
        except ValueError:
            return False
    
    def validar_cedula(self, cedula):
        """Valida que la cédula tenga 10 dígitos"""
        return cedula.isdigit() and len(cedula) == 10
    
    def validar_telefono(self, telefono):
        """Valida que el teléfono tenga 10 dígitos"""
        return telefono.isdigit() and len(telefono) == 10

    def validar_enteros_limitado(self, new_val, limit):
        """Valida que la entrada sean solo números y no exceda el límite de caracteres"""
        # Permitir vacío (para borrar)
        if new_val == "":
            return True
        # Solo dígitos
        if not new_val.isdigit():
            return False
        # Límite de longitud
        try:
            return len(new_val) <= int(limit)
        except:
            return False

    def validar_decimales_limitado(self, new_val, limit_int, limit_dec):
        """Valida formato decimal (enteros.decimales) con límites"""
        if new_val == "":
            return True
        
        # Permitir solo números y un punto
        if not new_val.replace(".", "").isdigit():
             # Verificar si es solo un punto (permite escribir .5)
             if new_val == "." and int(limit_int) > 0: 
                 return True # Dejar pasar, aunque lógica estricta podría requerir 0.
             return False
        
        # Verificar cantidad de puntos
        if new_val.count(".") > 1:
            return False
            
        parts = new_val.split(".")
        
        # Validar parte entera
        if len(parts[0]) > int(limit_int):
            return False
            
        # Validar parte decimal (si existe)
        if len(parts) > 1:
            if len(parts[1]) > int(limit_dec):
                return False
                
        return True
    
    def calcular_edad(self, fecha_nacimiento):
        """Calcula la edad a partir de la fecha de nacimiento"""
        try:
            if not self.validar_fecha(fecha_nacimiento):
                return ""
            
            # Formato esperado: DD/MM/AAAA
            dia, mes, anio = map(int, fecha_nacimiento.split('/'))
            fecha_nac = datetime(anio, mes, dia)
            hoy = datetime.now()
            
            # Calcular edad
            edad = hoy.year - fecha_nac.year
            
            # Ajustar si aún no ha cumplido años este año
            if (hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day):
                edad -= 1
                
            return str(edad)
        except Exception as e:
            logging.error(f"Error al calcular edad: {str(e)}")
            return ""
    
    def calcular_imc(self, peso, talla):
        """Calcula el IMC a partir de peso y talla"""
        try:
            if not peso or not talla:
                return ""
                
            peso_float = float(peso)
            talla_float = float(talla) / 100  # Convertir cm a metros
            
            if peso_float <= 0 or talla_float <= 0:
                return ""
                
            imc = peso_float / (talla_float ** 2)
            return f"{imc:.2f}"
        except Exception as e:
            logging.error(f"Error al calcular IMC: {str(e)}")
            return ""
    
    def crear_interfaz_con_pestanas(self):
        """Crea la interfaz gráfica principal con pestañas"""
        # Frame principal
        main_frame = tk.Frame(self.root, bg=self.color_fondo)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        

        
        
        # 1. Barra de búsqueda (Arriba)
        self.crear_barra_busqueda(main_frame)
        
        # 2. Botones de acción (Abajo)
        # Los llamo antes que el notebook para asegurar que no los tape
        self.crear_botones_accion(main_frame)
        
        # 3. Notebook (Centro - Expandible)
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Crear pestañas en el orden nuevo usando tk.Frame para control total del fondo
        self.pestana_info = tk.Frame(self.notebook, bg=self.color_fondo)
        self.pestana_anamnesis = tk.Frame(self.notebook, bg=self.color_fondo)
        self.pestana_signos = tk.Frame(self.notebook, bg=self.color_fondo)
        self.pestana_fisico = tk.Frame(self.notebook, bg=self.color_fondo)
        self.pestana_examenes = tk.Frame(self.notebook, bg=self.color_fondo)
        self.pestana_diagnostico = tk.Frame(self.notebook, bg=self.color_fondo)
        self.pestana_tratamiento = tk.Frame(self.notebook, bg=self.color_fondo)
        self.pestana_control = tk.Frame(self.notebook, bg=self.color_fondo)
        self.pestana_lista_pacientes = tk.Frame(self.notebook, bg=self.color_fondo)
        self.pestana_estadisticas = tk.Frame(self.notebook, bg=self.color_fondo)
        
        # Crear imágenes para las pestañas (cuadrados de color)
        self.imagenes_pestanas = {}
        for key, color in self.colores_pestanas.items():
            img = tk.PhotoImage(width=15, height=15)
            img.put(color, to=(0, 0, 15, 15))
            self.imagenes_pestanas[key] = img

        self.notebook.add(self.pestana_info, text=" DATOS GENERALES", image=self.imagenes_pestanas['Info'], compound=tk.LEFT)
        self.notebook.add(self.pestana_anamnesis, text=" ANAMNESIS", image=self.imagenes_pestanas['Anamnesis'], compound=tk.LEFT)
        self.notebook.add(self.pestana_signos, text=" SIGNOS VITALES", image=self.imagenes_pestanas['Signos'], compound=tk.LEFT)
        self.notebook.add(self.pestana_fisico, text=" EXAMEN FISICO", image=self.imagenes_pestanas['Fisico'], compound=tk.LEFT)
        self.notebook.add(self.pestana_examenes, text=" LABORATORIO", image=self.imagenes_pestanas['Examenes'], compound=tk.LEFT)
        self.notebook.add(self.pestana_diagnostico, text=" DIAGNOSTICO", image=self.imagenes_pestanas['Diagnostico'], compound=tk.LEFT)
        self.notebook.add(self.pestana_tratamiento, text=" TRATAMIENTO", image=self.imagenes_pestanas['Tratamiento'], compound=tk.LEFT)
        # self.notebook.add(self.pestana_planificacion, text=" CITAS", image=self.imagenes_pestanas['Planificacion'], compound=tk.LEFT) # Removed
        self.notebook.add(self.pestana_control, text=" CONTROL Y CITAS", image=self.imagenes_pestanas['Control'], compound=tk.LEFT)
        self.notebook.add(self.pestana_lista_pacientes, text=" REGISTRO", image=self.imagenes_pestanas['Lista'], compound=tk.LEFT)
        self.notebook.add(self.pestana_estadisticas, text=" ESTADISTICA", image=self.imagenes_pestanas['Estadisticas'], compound=tk.LEFT)
        
        # Configurar cada pestaña
        self.configurar_pestana_info()
        self.configurar_pestana_anamnesis()
        self.configurar_pestana_signos()
        self.configurar_pestana_fisico_v2() # V2
        self.configurar_pestana_examenes()
        self.configurar_pestana_diagnostico_v2() # V2
        self.configurar_pestana_tratamiento() # NUEVA
        # self.configurar_pestana_planificacion() # Removed
        self.configurar_pestana_control()
        self.configurar_pestana_estadisticas()
        
        
        # Lista de pacientes registrados
        self.crear_lista_pacientes(self.pestana_lista_pacientes)
    
    def crear_barra_busqueda(self, parent):
        """Crea la barra de búsqueda de pacientes con aspecto moderno"""
        search_frame = tk.Frame(parent, bg="white", highlightthickness=1, highlightbackground="#e2e8f0")
        search_frame.pack(fill=tk.X, ipady=5)
        
        inner_frame = tk.Frame(search_frame, bg="white")
        inner_frame.pack(padx=20, pady=10, fill=tk.X)
        
        tk.Label(inner_frame, text="Búsqueda de Paciente:", 
                 font=("Segoe UI", 10, "bold"), fg=self.color_principal, bg="white").pack(side=tk.LEFT, padx=(0, 15))
        
        # Opciones de búsqueda con RadioButtons estilizados
        tipo_frame = tk.Frame(inner_frame, bg="white")
        tipo_frame.pack(side=tk.LEFT)
        
        for text, val in [("Nombre", "nombre"), ("ID", "id"), ("Cédula", "cedula")]:
            tk.Radiobutton(tipo_frame, text=text, variable=self.tipo_busqueda_var, 
                          value=val, bg="white", font=("Segoe UI", 9),
                          activebackground="white").pack(side=tk.LEFT, padx=5)
        
        # Campo de búsqueda
        self.busqueda_var.trace("w", self.buscar_paciente)
        self.entry_busqueda = tk.Entry(inner_frame, textvariable=self.busqueda_var, 
                                      font=("Segoe UI", 11), bg="#f8fafc", width=35,
                                      bd=1, relief="solid")
        self.entry_busqueda.pack(side=tk.LEFT, padx=15, ipady=5)
        self.entry_busqueda.busqueda_field = True
        
        # Botones
        tk.Button(inner_frame, text="Limpiar Filtros", command=self.limpiar_busqueda,
                  bg="#94a3b8", fg="white", font=("Segoe UI", 9, "bold"), 
                  relief="flat", cursor="hand2", padx=15).pack(side=tk.LEFT, padx=5)
        
        tk.Button(inner_frame, text="Actualizar Datos", command=self.actualizar_lista_pacientes,
                  bg=self.color_secundario, fg="white", font=("Segoe UI", 9, "bold"), 
                  relief="flat", cursor="hand2", padx=15).pack(side=tk.LEFT, padx=5)
        
        # Info Usuario
        user_info = tk.Frame(inner_frame, bg="white")
        user_info.pack(side=tk.RIGHT)
        tk.Label(user_info, text=f"👤 {self.current_user}", 
                 font=("Segoe UI", 9, "bold"), fg=self.color_acento, bg="white").pack()
    
    def configurar_pestana_info(self):
        """Configura la pestaña de información del paciente"""
        # Frame con scrollbar
        canvas_info = tk.Canvas(self.pestana_info, bg=self.color_fondo, highlightthickness=0)
        scrollbar_info = ttk.Scrollbar(self.pestana_info, orient=tk.VERTICAL, command=canvas_info.yview)
        frame_info_scroll = tk.Frame(canvas_info, bg=self.color_fondo)
        
        frame_info_scroll.bind(
            "<Configure>",
            lambda e: canvas_info.configure(scrollregion=canvas_info.bbox("all"))
        )
        
        window_id = canvas_info.create_window((0, 0), window=frame_info_scroll, anchor="nw")
        canvas_info.bind("<Configure>", lambda e: canvas_info.itemconfig(window_id, width=e.width))
        canvas_info.configure(yscrollcommand=scrollbar_info.set)
        
        canvas_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_info.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido de la pestaña (Modernizado con estilo pero manteniendo compatibilidad de layout)
        frame_contenido = tk.LabelFrame(frame_info_scroll, 
                                      text=" DATOS PERSONALES DEL PACIENTE ",
                                      font=("Segoe UI", 11, "bold"),
                                      fg=self.color_principal,
                                      bg="white",
                                      padx=20, pady=20,
                                      relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_contenido.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Helper para etiquetas modernas
        def style_label(parent, text):
            return tk.Label(parent, text=text, bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b")
        
        # Helper para entradas modernas
        def style_entry(parent, var, width, state='normal', bg="#f8fafc"):
            return tk.Entry(parent, textvariable=var, width=width, font=("Segoe UI", 10), 
                           bd=1, relief="solid", bg=bg, state=state)
        
        # Fila 0: Fecha, Hora y ID
        tk.Label(frame_contenido, text="Fecha de Consulta:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=0, column=0, sticky="w", padx=5, pady=8)
        entry_fecha = tk.Entry(frame_contenido, textvariable=self.fecha_var, width=12, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        entry_fecha.grid(row=0, column=1, padx=5, pady=8, ipady=3)
        # Binding para formato de fecha
        entry_fecha.bind('<KeyRelease>', self.formatear_fecha_evento)
        
        tk.Label(frame_contenido, text="Hora:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=0, column=2, sticky="w", padx=20, pady=8)
        entry_hora = tk.Entry(frame_contenido, textvariable=self.hora_var, width=8, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        entry_hora.grid(row=0, column=3, padx=5, pady=8, ipady=3)
        
        tk.Label(frame_contenido, text="ID Paciente:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=0, column=4, sticky="w", padx=20, pady=8)
        entry_id = tk.Entry(frame_contenido, textvariable=self.id_var, width=10, state='readonly', font=("Segoe UI", 10), bd=1, relief="solid", bg="#f1f5f9")
        entry_id.grid(row=0, column=5, padx=5, pady=8, ipady=3)
        
        # Fila 1: Nombres y Apellidos
        tk.Label(frame_contenido, text="Nombres (*):", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=1, column=0, sticky="w", padx=5, pady=8)
        entry_nombres = tk.Entry(frame_contenido, textvariable=self.nombres_var, width=30, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        entry_nombres.grid(row=1, column=1, columnspan=2, padx=5, pady=8, sticky="ew", ipady=3)
        
        tk.Label(frame_contenido, text="Apellidos (*):", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=1, column=3, sticky="w", padx=5, pady=8)
        entry_apellidos = tk.Entry(frame_contenido, textvariable=self.apellidos_var, width=30, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        entry_apellidos.grid(row=1, column=4, columnspan=2, padx=5, pady=8, sticky="ew", ipady=3)
        
        # Fila 2: Fecha Nac, Edad, Cedula
        tk.Label(frame_contenido, text="Fecha Nac:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=2, column=0, sticky="w", padx=5, pady=8)
        
        frame_nac = tk.Frame(frame_contenido, bg="white")
        frame_nac.grid(row=2, column=1, columnspan=2, sticky="w")
        
        # Trace solo para cálculo de edad (ya no para formato)
        self.fecha_nac_var.trace("w", self.calcular_edad_auto)
        
        entry_fecha_nac = tk.Entry(frame_nac, textvariable=self.fecha_nac_var, width=12, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        entry_fecha_nac.bind('<KeyRelease>', self.formatear_fecha_evento)
        entry_fecha_nac.pack(side=tk.LEFT, padx=(5,0), ipady=3)
        tk.Label(frame_nac, text="(DD/MM/AAAA)", bg="white", font=("Segoe UI", 8), fg="#94a3b8").pack(side=tk.LEFT, padx=2)
        
        tk.Label(frame_contenido, text="Edad:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=2, column=3, sticky="w", padx=5, pady=8)
        frame_edad = tk.Frame(frame_contenido, bg="white")
        frame_edad.grid(row=2, column=4, columnspan=2, sticky="w")
        entry_edad = tk.Entry(frame_edad, textvariable=self.edad_var, width=5, state='readonly', font=("Segoe UI", 10), bd=1, relief="solid", bg="#f1f5f9")
        entry_edad.pack(side=tk.LEFT, padx=(5,0), ipady=3)
        tk.Label(frame_edad, text="años", bg="white", font=("Segoe UI", 9), fg="#64748b").pack(side=tk.LEFT, padx=2)
        
        vcmd = (self.root.register(self.validar_solo_numeros), '%P')

        # Fila 3: Cedula y Telefono
        tk.Label(frame_contenido, text="Cédula:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=3, column=0, sticky="w", padx=5, pady=8)
        entry_cedula = tk.Entry(frame_contenido, textvariable=self.cedula_var, width=15, 
                                font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc",
                                validate='key', validatecommand=vcmd)
        entry_cedula.grid(row=3, column=1, columnspan=2, padx=5, pady=8, sticky="w", ipady=3)
        
        tk.Label(frame_contenido, text="Teléfono:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=3, column=3, sticky="w", padx=5, pady=8)
        entry_telefono = tk.Entry(frame_contenido, textvariable=self.telefono_var, width=15,
                                  font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc",
                                  validate='key', validatecommand=vcmd)
        entry_telefono.grid(row=3, column=4, columnspan=2, padx=5, pady=8, sticky="w", ipady=3)
        
        # Fila 4: Sexo y Ciudad
        tk.Label(frame_contenido, text="Sexo:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=4, column=0, sticky="w", padx=5, pady=8)
        sexo_frame = tk.Frame(frame_contenido, bg="white")
        sexo_frame.grid(row=4, column=1, columnspan=2, padx=5, pady=8, sticky="w")
        tk.Radiobutton(sexo_frame, text="M", variable=self.sexo_var, 
                       value="Masculino", bg="white", font=("Segoe UI", 10), activebackground="white").pack(side=tk.LEFT)
        tk.Radiobutton(sexo_frame, text="F", variable=self.sexo_var, 
                       value="Femenino", bg="white", font=("Segoe UI", 10), activebackground="white").pack(side=tk.LEFT, padx=5)
        
        tk.Label(frame_contenido, text="Ciudad:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=4, column=3, sticky="w", padx=5, pady=8)
        entry_ciudad = tk.Entry(frame_contenido, textvariable=self.ciudad_var, width=25, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        entry_ciudad.grid(row=4, column=4, columnspan=2, padx=5, pady=8, sticky="ew", ipady=3)
        
        # Fila 5: Dirección y País
        tk.Label(frame_contenido, text="Dirección:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=5, column=0, sticky="w", padx=5, pady=8)
        entry_direccion = tk.Entry(frame_contenido, textvariable=self.direccion_var, width=35, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        entry_direccion.grid(row=5, column=1, columnspan=2, padx=5, pady=8, sticky="ew", ipady=3)
        
        tk.Label(frame_contenido, text="País:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=5, column=3, sticky="w", padx=5, pady=8)
        entry_pais = tk.Entry(frame_contenido, textvariable=self.pais_var, width=20, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        entry_pais.grid(row=5, column=4, columnspan=2, padx=5, pady=8, sticky="ew", ipady=3)
        
        # Fila 6: Estado Civil
        tk.Label(frame_contenido, text="Estado Civil:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=6, column=0, sticky="w", padx=5, pady=8)
        frame_civil = tk.Frame(frame_contenido, bg="white")
        frame_civil.grid(row=6, column=1, columnspan=5, padx=5, pady=8, sticky="w")
        
        opciones_civil = ["Soltero", "Casado", "Divorciado", "Viudo", "Unión Libre"]
        for op in opciones_civil:
            tk.Radiobutton(frame_civil, text=op, variable=self.estado_civil_var, 
                           value=op, bg="white", font=("Segoe UI", 9), activebackground="white").pack(side=tk.LEFT, padx=2)
                           
        # Fila 7: Nivel de Instrucción
        tk.Label(frame_contenido, text="Instrucción:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=7, column=0, sticky="w", padx=5, pady=8)
        frame_instruccion = tk.Frame(frame_contenido, bg="white")
        frame_instruccion.grid(row=7, column=1, columnspan=5, padx=5, pady=8, sticky="w")
        
        opciones_inst = ["Ninguno", "Primaria", "Secundaria", "Superior"]
        for op in opciones_inst:
            tk.Radiobutton(frame_instruccion, text=op, variable=self.instruccion_var, 
                           value=op, bg="white", font=("Segoe UI", 9), activebackground="white").pack(side=tk.LEFT, padx=5)
        
        # Configurar expansión de filas y columnas
        for i in range(8):
            frame_contenido.grid_rowconfigure(i, weight=0)
        
        for i in range(6):
            frame_contenido.grid_columnconfigure(i, weight=1)
    
    def configurar_pestana_anamnesis(self):
        """Configura la pestaña de Anamnesis"""
        # Frame con scrollbar
        canvas_anamnesis = tk.Canvas(self.pestana_anamnesis, bg=self.color_fondo, highlightthickness=0)
        scrollbar_anamnesis = ttk.Scrollbar(self.pestana_anamnesis, orient=tk.VERTICAL, command=canvas_anamnesis.yview)
        frame_anamnesis_scroll = tk.Frame(canvas_anamnesis, bg=self.color_fondo)
        
        frame_anamnesis_scroll.bind(
            "<Configure>",
            lambda e: canvas_anamnesis.configure(scrollregion=canvas_anamnesis.bbox("all"))
        )
        
        window_id = canvas_anamnesis.create_window((0, 0), window=frame_anamnesis_scroll, anchor="nw")
        canvas_anamnesis.bind("<Configure>", lambda e: canvas_anamnesis.itemconfig(window_id, width=e.width))
        canvas_anamnesis.bind("<Configure>", lambda e: canvas_anamnesis.itemconfig(window_id, width=e.width))
        canvas_anamnesis.configure(yscrollcommand=scrollbar_anamnesis.set)
        
        canvas_anamnesis.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_anamnesis.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido de la pestaña (Modernizado con estilo de tarjeta blanca)
        frame_contenido = tk.LabelFrame(frame_anamnesis_scroll, 
                                      text=" HISTORIA CLÍNICA Y ANAMNESIS ",
                                      font=("Segoe UI", 11, "bold"),
                                      fg=self.color_principal,
                                      bg="white",
                                      padx=20, pady=20,
                                      relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_contenido.pack(expand=True, fill="both", padx=20, pady=20)
        
        # 1. Tipo de consulta
        tk.Label(frame_contenido, text="Tipo de Consulta:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        frame_tipo = tk.Frame(frame_contenido, bg="white")
        frame_tipo.grid(row=0, column=1, columnspan=3, sticky="w", padx=5, pady=5)
        
        tk.Radiobutton(frame_tipo, text="Clínica", variable=self.consulta_tipo_var, 
                       value="Clínica", bg="white", font=("Segoe UI", 10), activebackground="white").pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(frame_tipo, text="Quirúrgica", variable=self.consulta_tipo_var, 
                       value="Quirúrgica", bg="white", font=("Segoe UI", 10), activebackground="white").pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(frame_tipo, text="Otra Especialidad", variable=self.consulta_tipo_var, 
                       value="Otra", bg="white", font=("Segoe UI", 10), activebackground="white").pack(side=tk.LEFT, padx=10)
                       
        # 2. Motivo de Consulta (Texto corto)
        tk.Label(frame_contenido, text="Motivo Consulta:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=1, column=0, sticky="nw", padx=5, pady=5)
        self.entry_motivo_anamnesis = tk.Entry(frame_contenido, textvariable=self.motivo_corto_var, width=80, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.entry_motivo_anamnesis.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5, pady=5, ipady=3)
        
        # 3. Enfermedad Actual (Texto Largo)
        tk.Label(frame_contenido, text="Enfermedad Actual:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=2, column=0, sticky="nw", padx=5, pady=5)
        self.texto_enfermedad_actual = tk.Text(frame_contenido, height=3, width=80, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_enfermedad_actual.grid(row=2, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        
        # 4. Antecedentes (Grid de textos más pequeños)
        tk.Label(frame_contenido, text="Ant. Familiares:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=3, column=0, sticky="nw", padx=5, pady=5)
        self.entry_ant_familiares = tk.Entry(frame_contenido, textvariable=self.antecedentes_familiares_var, width=80, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.entry_ant_familiares.grid(row=3, column=1, columnspan=3, sticky="ew", padx=5, pady=5, ipady=3)
        
        tk.Label(frame_contenido, text="Ant. Personales:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=4, column=0, sticky="nw", padx=5, pady=5)
        self.texto_ant_personales = tk.Text(frame_contenido, height=2, width=80, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_ant_personales.grid(row=4, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        
        # Alergias / Medicación
        tk.Label(frame_contenido, text="Alergias:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=5, column=0, sticky="nw", padx=5, pady=5)
        self.texto_alergias = tk.Text(frame_contenido, height=1, width=80, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_alergias.grid(row=5, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

        tk.Label(frame_contenido, text="Medicación actual:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=6, column=0, sticky="nw", padx=5, pady=5)
        self.texto_medicacion = tk.Text(frame_contenido, height=1, width=80, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_medicacion.grid(row=6, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

        # Cirugías / Hospitalizaciones
        tk.Label(frame_contenido, text="Cirugías Realizadas:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=7, column=0, sticky="nw", padx=5, pady=5)
        self.texto_cirugias_previas = tk.Text(frame_contenido, height=2, width=80, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_cirugias_previas.grid(row=7, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        
        tk.Label(frame_contenido, text="Hospitalizaciones:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=8, column=0, sticky="nw", padx=5, pady=5)
        self.texto_hospitalizaciones = tk.Text(frame_contenido, height=2, width=80, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_hospitalizaciones.grid(row=8, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        
        # Tipo de Dieta
        tk.Label(frame_contenido, text="Tipo de Dieta:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=9, column=0, sticky="nw", padx=5, pady=5)
        
        frame_dieta = tk.Frame(frame_contenido, bg="white")
        frame_dieta.grid(row=9, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
        
        opciones_dieta = ["General", "Blanda", "Hiposódica", "Hipoglucida", "Líquida", "Otra"]
        for opcion in opciones_dieta:
            tk.Radiobutton(frame_dieta, text=opcion, variable=self.dieta_var, 
                           value=opcion, bg="white", font=("Segoe UI", 9), activebackground="white").pack(side=tk.LEFT, padx=5)
        
        # Datos Ginecológicos (Frame condicional)
        self.frame_ginecologico = tk.LabelFrame(frame_contenido, text=" DATOS GINECOLÓGICOS ", 
                                              font=("Segoe UI", 10, "bold"), fg="#ec4899", bg="white", 
                                              padx=15, pady=15, relief="flat", highlightthickness=1, highlightbackground="#fce7f3")
        self.frame_ginecologico.grid(row=10, column=0, columnspan=4, sticky="ew", padx=5, pady=10)
        
        # Menarquia, Ciclos, FUM
        tk.Label(self.frame_ginecologico, text="Menarquia:", bg="white", font=("Segoe UI", 9), fg="#64748b").grid(row=0, column=0, sticky="w", padx=5)
        tk.Entry(self.frame_ginecologico, textvariable=self.ginecologicos_menarquia_var, width=10, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc").grid(row=0, column=1, padx=5, ipady=2)
        
        tk.Label(self.frame_ginecologico, text="Ciclos:", bg="white", font=("Segoe UI", 9), fg="#64748b").grid(row=0, column=2, sticky="w", padx=5)
        tk.Entry(self.frame_ginecologico, textvariable=self.ginecologicos_ciclos_var, width=10, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc").grid(row=0, column=3, padx=5, ipady=2)
        
        tk.Label(self.frame_ginecologico, text="FUM:", bg="white", font=("Segoe UI", 9), fg="#64748b").grid(row=0, column=4, sticky="w", padx=5)
        tk.Entry(self.frame_ginecologico, textvariable=self.ginecologicos_fum_var, width=12, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc").grid(row=0, column=5, padx=5, ipady=2)

        # Gestas, Partos, Abortos, Cesareas
        tk.Label(self.frame_ginecologico, text="G:", bg="white", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        tk.Entry(self.frame_ginecologico, textvariable=self.ginecologicos_gestas_var, width=5, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc").grid(row=1, column=1, padx=5, ipady=2)
        
        tk.Label(self.frame_ginecologico, text="P:", bg="white", font=("Segoe UI", 9, "bold")).grid(row=1, column=2, sticky="w", padx=5)
        tk.Entry(self.frame_ginecologico, textvariable=self.ginecologicos_partos_var, width=5, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc").grid(row=1, column=3, padx=5, ipady=2)
        
        tk.Label(self.frame_ginecologico, text="A:", bg="white", font=("Segoe UI", 9, "bold")).grid(row=1, column=4, sticky="w", padx=5)
        tk.Entry(self.frame_ginecologico, textvariable=self.ginecologicos_abortos_var, width=5, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc").grid(row=1, column=5, padx=5, ipady=2)
        
        tk.Label(self.frame_ginecologico, text="C:", bg="white", font=("Segoe UI", 9, "bold")).grid(row=1, column=6, sticky="w", padx=5)
        tk.Entry(self.frame_ginecologico, textvariable=self.ginecologicos_cesareas_var, width=5, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc").grid(row=1, column=7, padx=5, ipady=2)
        
        # Trace sexo to show/hide ginecologico
        self.sexo_var.trace("w", self.toggle_ginecologico)
        self.toggle_ginecologico()

        # Botón limpiar anamnesis
        btn_limpiar = tk.Button(frame_contenido, text="Limpiar Anamnesis",
                               command=self.limpiar_anamnesis,
                               bg="#94a3b8", fg="white", font=("Segoe UI", 9, "bold"),
                               relief="flat", cursor="hand2", padx=20, pady=8)
        btn_limpiar.grid(row=11, column=0, columnspan=4, pady=20)
        
        # Configurar expansión
        frame_contenido.grid_columnconfigure(1, weight=1)

    def toggle_ginecologico(self, *args):
        """Muestra u oculta campos ginecológicos según el sexo"""
        try:
            if self.sexo_var.get() == "Femenino":
                self.frame_ginecologico.grid()
            else:
                self.frame_ginecologico.grid_remove()
        except:
            pass

    def limpiar_anamnesis(self):
        """Limpia los campos de anamnesis"""
        self.consulta_tipo_var.set("Clínica")
        self.motivo_corto_var.set("")
        self.texto_enfermedad_actual.delete("1.0", tk.END)
        self.antecedentes_familiares_var.set("")
        self.texto_ant_personales.delete("1.0", tk.END)
        self.texto_alergias.delete("1.0", tk.END)
        self.texto_medicacion.delete("1.0", tk.END)
        self.texto_cirugias_previas.delete("1.0", tk.END)
        self.texto_hospitalizaciones.delete("1.0", tk.END)
        self.dieta_var.set("General")
        
        self.ginecologicos_menarquia_var.set("")
        self.ginecologicos_ciclos_var.set("")
        self.ginecologicos_fum_var.set("")
        self.ginecologicos_gestas_var.set("")
        self.ginecologicos_partos_var.set("")
        self.ginecologicos_abortos_var.set("")
        self.ginecologicos_cesareas_var.set("")

    def configurar_pestana_signos(self):
        """Configura la pestaña de signos vitales"""
        # Frame con scrollbar
        canvas_signos = tk.Canvas(self.pestana_signos, bg=self.color_fondo, highlightthickness=0)
        scrollbar_signos = ttk.Scrollbar(self.pestana_signos, orient=tk.VERTICAL, command=canvas_signos.yview)
        frame_signos_scroll = tk.Frame(canvas_signos, bg=self.color_fondo)
        
        frame_signos_scroll.bind(
            "<Configure>",
            lambda e: canvas_signos.configure(scrollregion=canvas_signos.bbox("all"))
        )
        
        window_id = canvas_signos.create_window((0, 0), window=frame_signos_scroll, anchor="nw")
        canvas_signos.bind("<Configure>", lambda e: canvas_signos.itemconfig(window_id, width=e.width))
        canvas_signos.configure(yscrollcommand=scrollbar_signos.set)
        
        canvas_signos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_signos.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido de la pestaña (Modernizado con estilo de tarjeta blanca)
        frame_contenido = tk.LabelFrame(frame_signos_scroll, 
                                      text=" SIGNOS VITALES Y ANTROPOMETRÍA ",
                                      font=("Segoe UI", 11, "bold"),
                                      fg=self.color_principal,
                                      bg="white",
                                      padx=20, pady=20,
                                      relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_contenido.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Presión Arterial Especial (Sistólica / Diastólica)
        tk.Label(frame_contenido, text="Presión Arterial (mmHg):", bg="white", 
                font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        
        frame_pa = tk.Frame(frame_contenido, bg="white")
        frame_pa.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        
        tk.Entry(frame_pa, textvariable=self.presion_sistolica_var, width=5, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc").pack(side=tk.LEFT, ipady=3)
        tk.Label(frame_pa, text="/", bg="white", font=("Segoe UI", 12, "bold"), fg="#64748b").pack(side=tk.LEFT, padx=5)
        tk.Entry(frame_pa, textvariable=self.presion_diastolica_var, width=5, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc").pack(side=tk.LEFT, ipady=3)
        
        # Trigger para clasificación de HTA
        self.presion_sistolica_var.trace("w", self.calcular_hta)
        self.presion_diastolica_var.trace("w", self.calcular_hta)

        # Otros signos
        signos = [
            ("Frecuencia Cardiaca (lpm):", "frecuencia_var", 15),
            ("Temperatura (°C):", "temperatura_var", 15),
            ("Frecuencia Respiratoria (rpm):", "respiratoria_var", 15),
            ("Saturación de O2 (%):", "saturacion_var", 15),
            ("Peso (kg):", "peso_var", 15),
            ("Talla (cm):", "talla_var", 15),
            ("IMC:", "imc_var", 15)
        ]
        
        for i, (texto, var_name, ancho) in enumerate(signos, 1): # Empezar index en 1 porque 0 es PA
            row = (i+1) // 2
            col = ((i+1) % 2) * 3
            
            # Ajuste manual para que quede ordenado
            if i == 1: row, col = 0, 3
            elif i == 2: row, col = 1, 0
            elif i == 3: row, col = 1, 3
            elif i == 4: row, col = 2, 0
            elif i == 5: row, col = 2, 3
            elif i == 6: row, col = 3, 0
            elif i == 7: row, col = 3, 3

            tk.Label(frame_contenido, text=texto, bg="white", 
                    font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=row, column=col, sticky="w", padx=10, pady=10)
            
            var = getattr(self, var_name)
            
            if var_name == "imc_var":
                entry = tk.Entry(frame_contenido, textvariable=var, width=ancho, state='readonly', font=("Segoe UI", 10), bd=1, relief="solid", bg="#f1f5f9")
            else:
                entry = tk.Entry(frame_contenido, textvariable=var, width=ancho, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
                
                # Validaciones (mantengo lógica original)
                if var_name in ["frecuencia_var", "talla_var"]:
                     vcmd = (self.root.register(self.validar_enteros_limitado), '%P', '3')
                     entry.config(validate="key", validatecommand=vcmd)
                elif var_name in ["saturacion_var", "respiratoria_var"]:
                     vcmd = (self.root.register(self.validar_enteros_limitado), '%P', '2')
                     entry.config(validate="key", validatecommand=vcmd)
                elif var_name in ["temperatura_var", "peso_var"]:
                     vcmd = (self.root.register(self.validar_decimales_limitado), '%P', '3', '1')
                     entry.config(validate="key", validatecommand=vcmd)

            entry.grid(row=row, column=col+1, padx=5, pady=10, ipady=3)
            
            if var_name in ["peso_var", "talla_var"]:
                var.trace("w", self.calcular_imc_auto)
        
        # Clasificaciones (HTA e IMC)
        info_frame = tk.Frame(frame_contenido, bg="#f8fafc", padx=15, pady=15, highlightthickness=1, highlightbackground="#e2e8f0")
        info_frame.grid(row=4, column=0, columnspan=6, pady=20, sticky="ew")

        tk.Label(info_frame, text="Clasificación HTA:", bg="#f8fafc", font=("Segoe UI", 10, "bold"), fg="#475569").grid(row=0, column=0, sticky="w")
        tk.Label(info_frame, textvariable=self.presion_clasificacion_var, bg="#f8fafc", font=("Segoe UI", 10, "bold"), fg="#ef4444").grid(row=0, column=1, sticky="w", padx=10)

        tk.Label(info_frame, text="Clasificación IMC:", bg="#f8fafc", font=("Segoe UI", 10, "bold"), fg="#475569").grid(row=1, column=0, sticky="w", pady=(10,0))
        tk.Label(info_frame, textvariable=self.imc_clasificacion_var, bg="#f8fafc", font=("Segoe UI", 10, "bold"), fg="#3b82f6").grid(row=1, column=1, sticky="w", padx=10, pady=(10,0))
        
        # Botón para calcular IMC manualmente
        btn_calcular_imc = tk.Button(frame_contenido, text="Actualizar Cálculos",
                                    command=self.calcular_imc_manual,
                                    bg=self.color_secundario, fg="white",
                                    font=("Segoe UI", 9, "bold"),
                                    relief="flat", cursor="hand2", padx=20, pady=8)
        btn_calcular_imc.grid(row=5, column=0, columnspan=2, pady=10, sticky="w")
        
        # Configurar expansión de columnas
        for i in range(6):
            frame_contenido.grid_columnconfigure(i, weight=1)
    
    def configurar_pestana_examenes(self):
        """Configura la pestaña de exámenes solicitados"""
        # Frame con scrollbar
        canvas_examenes = tk.Canvas(self.pestana_examenes, bg=self.color_fondo, highlightthickness=0)
        scrollbar_examenes = ttk.Scrollbar(self.pestana_examenes, orient=tk.VERTICAL, command=canvas_examenes.yview)
        frame_examenes_scroll = tk.Frame(canvas_examenes, bg=self.color_fondo)
        
        frame_examenes_scroll.bind(
            "<Configure>",
            lambda e: canvas_examenes.configure(scrollregion=canvas_examenes.bbox("all"))
        )
        
        window_id = canvas_examenes.create_window((0, 0), window=frame_examenes_scroll, anchor="nw")
        canvas_examenes.bind("<Configure>", lambda e: canvas_examenes.itemconfig(window_id, width=e.width))
        canvas_examenes.configure(yscrollcommand=scrollbar_examenes.set)
        
        canvas_examenes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_examenes.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido de la pestaña (Modernizado con estilo de tarjeta blanca)
        frame_contenido = tk.LabelFrame(frame_examenes_scroll, 
                                      text=" EXÁMENES SOLICITADOS (LABORATORIO/IMAGEN) ",
                                      font=("Segoe UI", 11, "bold"),
                                      fg=self.color_principal,
                                      bg="white",
                                      padx=20, pady=20,
                                      relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_contenido.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Frame para organizar en tres columnas
        frame_columnas = tk.Frame(frame_contenido, bg="white")
        frame_columnas.pack(fill=tk.BOTH, expand=True)
        
        # Columna izquierda: Exámenes de laboratorio
        frame_lab = tk.LabelFrame(frame_columnas, 
                                 text=" EXÁMENES DE LABORATORIO ",
                                 font=("Segoe UI", 10, "bold"),
                                 fg=self.color_principal,
                                 bg="white",
                                 padx=10, pady=10,
                                 relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_lab.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Lista desplegable para exámenes de laboratorio
        self.combo_lab = ttk.Combobox(frame_lab, textvariable=self.lista_lab_var, 
                                     values=self.examenes_lab_comunes,
                                     state="readonly", font=("Segoe UI", 10))
        self.combo_lab.pack(fill=tk.X, pady=(0, 10))
        self.combo_lab.bind("<<ComboboxSelected>>", self.agregar_examen_lab)
        
        # Botón para agregar examen manualmente
        frame_btn_lab = tk.Frame(frame_lab, bg="white")
        frame_btn_lab.pack(fill=tk.X, pady=(0, 10))
        
        btn_agregar_lab = tk.Button(frame_btn_lab, text="Agregar Examen",
                                   command=self.agregar_examen_lab_manual,
                                   bg=self.color_secundario, fg="white", font=("Segoe UI", 9, "bold"),
                                   relief="flat", cursor="hand2", padx=10, pady=5)
        btn_agregar_lab.pack(side=tk.LEFT)
        
        # Área de texto para exámenes de laboratorio seleccionados
        self.texto_examenes_lab = tk.Text(frame_lab, height=15, width=35, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_examenes_lab.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Botón para limpiar exámenes de laboratorio
        btn_limpiar_lab = tk.Button(frame_lab, text="Limpiar Laboratorio",
                                   command=lambda: self.texto_examenes_lab.delete("1.0", tk.END),
                                   bg="#94a3b8", fg="white", font=("Segoe UI", 9, "bold"),
                                   relief="flat", cursor="hand2", padx=15, pady=8)
        btn_limpiar_lab.pack()
        
        # Columna central: Exámenes de imagenología
        frame_img = tk.LabelFrame(frame_columnas, 
                                 text=" EXÁMENES DE IMAGENOLOGÍA ",
                                 font=("Segoe UI", 10, "bold"),
                                 fg=self.color_principal,
                                 bg="white",
                                 padx=10, pady=10,
                                 relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_img.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Lista desplegable para exámenes de imagenología
        self.combo_img = ttk.Combobox(frame_img, textvariable=self.lista_img_var, 
                                     values=self.examenes_imagenologia,
                                     state="readonly", font=("Segoe UI", 10))
        self.combo_img.pack(fill=tk.X, pady=(0, 10))
        self.combo_img.bind("<<ComboboxSelected>>", self.agregar_examen_img)
        
        # Botón para agregar examen manualmente
        frame_btn_img = tk.Frame(frame_img, bg="white")
        frame_btn_img.pack(fill=tk.X, pady=(0, 10))
        
        btn_agregar_img = tk.Button(frame_btn_img, text="Agregar Examen",
                                   command=self.agregar_examen_img_manual,
                                   bg=self.color_secundario, fg="white", font=("Segoe UI", 9, "bold"),
                                   relief="flat", cursor="hand2", padx=10, pady=5)
        btn_agregar_img.pack(side=tk.LEFT)
        
        # Área de texto para exámenes de imagenología seleccionados
        self.texto_examenes_img = tk.Text(frame_img, height=15, width=35, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_examenes_img.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Botón para limpiar exámenes de imagenología
        btn_limpiar_img = tk.Button(frame_img, text="Limpiar Imagenología",
                                   command=lambda: self.texto_examenes_img.delete("1.0", tk.END),
                                   bg="#94a3b8", fg="white", font=("Segoe UI", 9, "bold"),
                                   relief="flat", cursor="hand2", padx=15, pady=8)
        btn_limpiar_img.pack()
        
        # Columna derecha: Otros exámenes
        frame_otros = tk.LabelFrame(frame_columnas, 
                                   text=" OTROS EXÁMENES ",
                                   font=("Segoe UI", 10, "bold"),
                                   fg=self.color_principal,
                                   bg="white",
                                   padx=10, pady=10,
                                   relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_otros.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Exámenes predefinidos para "otros"
        examenes_otros = [
            "Electrocardiograma (ECG)",
            "Espirometría",
            "Electroencefalograma (EEG)",
            "Prueba de esfuerzo",
            "Holter de 24 horas",
            "Monitorización ambulatoria de presión arterial (MAPA)"
        ]
        
        self.combo_otros = ttk.Combobox(frame_otros, 
                                       values=examenes_otros,
                                       state="readonly", font=("Segoe UI", 10))
        self.combo_otros.pack(fill=tk.X, pady=(0, 10))
        self.combo_otros.bind("<<ComboboxSelected>>", self.agregar_examen_otros)
        
        # Botón para agregar examen manualmente
        frame_btn_otros = tk.Frame(frame_otros, bg="white")
        frame_btn_otros.pack(fill=tk.X, pady=(0, 10))
        
        btn_agregar_otros = tk.Button(frame_btn_otros, text="Agregar Examen",
                                     command=self.agregar_examen_otros_manual,
                                     bg=self.color_secundario, fg="white", font=("Segoe UI", 9, "bold"),
                                     relief="flat", cursor="hand2", padx=10, pady=5)
        btn_agregar_otros.pack(side=tk.LEFT)
        
        # Área de texto para otros exámenes seleccionados
        self.texto_examenes_otros = tk.Text(frame_otros, height=15, width=35, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_examenes_otros.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Botón para limpiar otros exámenes
        btn_limpiar_otros = tk.Button(frame_otros, text="Limpiar Otros",
                                     command=lambda: self.texto_examenes_otros.delete("1.0", tk.END),
                                     bg="#94a3b8", fg="white", font=("Segoe UI", 9, "bold"),
                                     relief="flat", cursor="hand2", padx=15, pady=8)
        btn_limpiar_otros.pack()
    
    def agregar_examen_otros(self, event=None):
        """Agrega un examen de otros seleccionado al área de texto"""
        examen = self.combo_otros.get()
        if examen:
            contenido_actual = self.texto_examenes_otros.get("1.0", tk.END).strip()
            if contenido_actual:
                nuevo_contenido = contenido_actual + "\n• " + examen
            else:
                nuevo_contenido = "• " + examen
            
            self.texto_examenes_otros.delete("1.0", tk.END)
            self.texto_examenes_otros.insert("1.0", nuevo_contenido)
            self.combo_otros.set("")
    
    def agregar_examen_otros_manual(self):
        """Permite agregar un examen de otros manualmente"""
        try:
            examen = simpledialog.askstring("Agregar Examen", "Ingrese el examen:")
            if examen:
                contenido_actual = self.texto_examenes_otros.get("1.0", tk.END).strip()
                if contenido_actual:
                    nuevo_contenido = contenido_actual + "\n• " + examen
                else:
                    nuevo_contenido = "• " + examen
                
                self.texto_examenes_otros.delete("1.0", tk.END)
                self.texto_examenes_otros.insert("1.0", nuevo_contenido)
        except Exception as e:
            logging.error(f"Error al agregar examen otros manual: {str(e)}")
    
    def configurar_pestana_fisico(self):
        """Configura la pestaña de examen físico"""
        # Frame con scrollbar
        canvas_fisico = tk.Canvas(self.pestana_fisico, bg=self.color_fondo, highlightthickness=0)
        scrollbar_fisico = ttk.Scrollbar(self.pestana_fisico, orient=tk.VERTICAL, command=canvas_fisico.yview)
        frame_fisico_scroll = tk.Frame(canvas_fisico, bg=self.color_fondo)
        
        frame_fisico_scroll.bind(
            "<Configure>",
            lambda e: canvas_fisico.configure(scrollregion=canvas_fisico.bbox("all"))
        )
        
        canvas_fisico.create_window((0, 0), window=frame_fisico_scroll, anchor="nw")
        canvas_fisico.configure(yscrollcommand=scrollbar_fisico.set)
        
        canvas_fisico.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_fisico.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido de la pestaña (Modernizado con estilo de tarjeta blanca)
        frame_contenido = tk.LabelFrame(frame_fisico_scroll, 
                                      text=" HALLAZGOS AL EXAMEN FÍSICO ",
                                      font=("Segoe UI", 11, "bold"),
                                      fg=self.color_principal,
                                      bg="white",
                                      padx=20, pady=20,
                                      relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_contenido.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Instrucciones
        instrucciones = tk.Label(frame_contenido, 
                                text="Documente los hallazgos en cada sistema. Deje en blanco si es normal/no evaluado.",
                                bg="white", font=("Segoe UI", 9, "italic"), fg="#64748b")
        instrucciones.grid(row=0, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 15))
        
        # Campos del examen físico en 2 columnas
        campos_fisicos = [
            ("Apariencia General:", "fisico_apariencia_var"),
            ("Piel y Faneras:", "fisico_piel_var"),
            ("Cabeza (Ojos/ORL):", "fisico_cabeza_var"),
            ("Cuello:", "fisico_cuello_var"),
            ("Tórax (Cardiopulmonar):", "fisico_torax_var"),
            ("Abdomen:", "fisico_abdomen_var"),
            ("Extremidades:", "fisico_extremidades_var"),
            ("Genital:", "fisico_genital_var"),
            ("Anoperineal:", "fisico_anoperineal_var"),
            ("Neurológico/Otros:", "fisico_otros_var")
        ]
        
        for i, (label_text, var_name) in enumerate(campos_fisicos):
            row = (i // 2) + 1
            col = (i % 2) * 2 # 0 or 2 (para dejar espacio para entry)
            
            # Label
            tk.Label(frame_contenido, text=label_text, 
                    bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=row, column=col, sticky="nw", padx=5, pady=5)
            
            # Entry/Text
            # Usaremos Text pequeño en lugar de Entry para permitir multilineas breves
            # Pero necesitamos bindear la variable. Como Text no tiene textvariable, usaremos eventos o Entry largo.
            # Para simplificar persistencia con las variables StringVar existentes, usaremos Entry.
            # Si se requiere más texto, el usuario usará "Otros" o escribirá seguido.
            
            # O mejor, usamos Text y hacemos un binding manual a la variable al guardar?
            # NO, el metodo guardar usa .get() de la VARIABLE.
            # Si uso Text, la variable no se actualiza sola.
            # Por simplicidad y robustez: Usaremos Entry grandes.
            
            entry = tk.Entry(frame_contenido, textvariable=getattr(self, var_name), width=45, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
            entry.grid(row=row, column=col+1, sticky="w", padx=5, pady=5, ipady=3)
            
        # Botón para limpiar examen físico
        btn_limpiar = tk.Button(frame_contenido, text="Limpiar Todo",
                               command=self.limpiar_fisico,
                               bg="#95a5a6", fg="white",
                               padx=15, pady=5)
        btn_limpiar.grid(row=8, column=0, columnspan=4, pady=20)
        
        # Configurar columnas
        frame_contenido.grid_columnconfigure(1, weight=1)
        frame_contenido.grid_columnconfigure(3, weight=1)
    
    def configurar_pestana_diagnostico(self):
        """Configura la pestaña de diagnóstico y tratamiento"""
        # Frame con scrollbar
        canvas_diag = tk.Canvas(self.pestana_diagnostico, bg=self.color_fondo, highlightthickness=0)
        scrollbar_diag = ttk.Scrollbar(self.pestana_diagnostico, orient=tk.VERTICAL, command=canvas_diag.yview)
        frame_diag_scroll = tk.Frame(canvas_diag, bg=self.color_fondo)
        
        frame_diag_scroll.bind(
            "<Configure>",
            lambda e: canvas_diag.configure(scrollregion=canvas_diag.bbox("all"))
        )
        
        canvas_diag.create_window((0, 0), window=frame_diag_scroll, anchor="nw")
        canvas_diag.configure(yscrollcommand=scrollbar_diag.set)
        
        canvas_diag.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_diag.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido de la pestaña (Modernizado con estilo de tarjeta blanca)
        frame_contenido = tk.LabelFrame(frame_diag_scroll, 
                                      text=" DIAGNÓSTICO Y TRATAMIENTO ",
                                      font=("Segoe UI", 11, "bold"),
                                      fg=self.color_principal,
                                      bg="white",
                                      padx=20, pady=20,
                                      relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_contenido.pack(expand=True, fill="both", padx=20, pady=20)
        
        # --- CIE-10 Selector ---
        tk.Label(frame_contenido, text="Seleccionar CIE-10 (Comunes):", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=0, column=0, sticky="w", padx=5, pady=(5,0))
        
        self.combo_cie10 = ttk.Combobox(frame_contenido, textvariable=self.cie10_seleccion_var,
                                       values=self.cie10_data, width=50)
        self.combo_cie10.grid(row=1, column=0, sticky="w", padx=5, pady=(0, 10))
        self.combo_cie10.bind("<<ComboboxSelected>>", self.agregar_diagnostico_cie10)

        # Diagnóstico Texto
        tk.Label(frame_contenido, text="Diagnóstico Detallado:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=2, column=0, sticky="nw", padx=5, pady=5)
        
        self.texto_diagnostico = tk.Text(frame_contenido, height=10, width=60, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_diagnostico.grid(row=3, column=0, padx=5, pady=5)
        
        # Scrollbar para diagnóstico
        scrollbar_diag_texto = tk.Scrollbar(frame_contenido, command=self.texto_diagnostico.yview)
        scrollbar_diag_texto.grid(row=3, column=1, sticky="ns")
        self.texto_diagnostico.config(yscrollcommand=scrollbar_diag_texto.set)
        
        # Tratamiento
        tk.Label(frame_contenido, text="Tratamiento:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=0, column=2, sticky="nw", padx=20, pady=5)
        
        self.texto_tratamiento = tk.Text(frame_contenido, height=14, width=60, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_tratamiento.grid(row=1, column=2, rowspan=3, padx=5, pady=5, sticky="n")
        
        # Scrollbar para tratamiento
        scrollbar_trat_texto = tk.Scrollbar(frame_contenido, command=self.texto_tratamiento.yview)
        scrollbar_trat_texto.grid(row=1, column=3, rowspan=3, sticky="ns")
        self.texto_tratamiento.config(yscrollcommand=scrollbar_trat_texto.set)
        
        # Botón para limpiar
        btn_limpiar_diag = tk.Button(frame_contenido, text="Limpiar Todo",
                                    command=self.limpiar_diagnostico_tratamiento,
                                    bg="#95a5a6", fg="white",
                                    font=("Arial", 10),
                                    padx=15, pady=5)
        btn_limpiar_diag.grid(row=4, column=0, columnspan=4, pady=10)
        
        # Configurar expansión
        frame_contenido.grid_columnconfigure(2, weight=1)
        frame_contenido.grid_rowconfigure(3, weight=1)

    def agregar_diagnostico_cie10(self, event=None):
        """Agrega el diagnóstico seleccionado al texto"""
        diag = self.cie10_seleccion_var.get()
        if diag:
            texto_actual = self.texto_diagnostico.get("1.0", tk.END).strip()
            if texto_actual:
                nuevo_texto = texto_actual + "\n" + diag
            else:
                nuevo_texto = diag
            
            self.texto_diagnostico.delete("1.0", tk.END)
            self.texto_diagnostico.insert("1.0", nuevo_texto)
            # Limpiar selección para permitir seleccionar otro
            # self.cie10_seleccion_var.set("") # Opcional, mejor dejarlo visible
    
            # self.cie10_seleccion_var.set("") # Opcional, mejor dejarlo visible
            
    def limpiar_diagnostico_tratamiento(self):
        """Limpia los campos de diagnóstico y tratamiento"""
        self.texto_diagnostico.delete("1.0", tk.END)
        self.texto_tratamiento.delete("1.0", tk.END)
        self.cie10_seleccion_var.set("") # Limpiar selección de combo
        
    def limpiar_fisico(self):
        """Limpia los campos del examen físico"""
        vars_fisico = [
            "fisico_apariencia_var", "fisico_piel_var", "fisico_cabeza_var",
            "fisico_cuello_var", "fisico_torax_var", "fisico_abdomen_var",
            "fisico_extremidades_var", "fisico_genital_var", "fisico_anoperineal_var",
            "fisico_otros_var"
        ]
        for var_name in vars_fisico:
            if hasattr(self, var_name):
                getattr(self, var_name).set("")

    def configurar_pestana_tratamiento(self):
        """Configura la pestaña de tratamiento (Nueva)"""
        canvas = tk.Canvas(self.pestana_tratamiento, bg=self.color_fondo, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.pestana_tratamiento, orient=tk.VERTICAL, command=canvas.yview)
        frame_scroll = tk.Frame(canvas, bg=self.color_fondo)
        
        frame_scroll.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=frame_scroll, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido (Modernizado con estilo de tarjeta blanca)
        frame_contenido = tk.LabelFrame(frame_scroll, 
                                      text=" INDICACIONES Y TRATAMIENTO FARMACOLÓGICO ",
                                      font=("Segoe UI", 11, "bold"),
                                      fg=self.color_principal,
                                      bg="white",
                                      padx=20, pady=20,
                                      relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_contenido.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Tipo de Tratamiento / Uso Terapéutico
        tk.Label(frame_contenido, text="Por Actividad Farmacológica / Uso Terapéutico:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        usos_terapeuticos = [
            "Analgésicos / Antiinflamatorios",
            "Antibióticos / Antimicrobianos",
            "Antihipertensivos",
            "Antidiabéticos",
            "Antihistamínicos",
            "Broncodilatadores",
            "Corticosteroides",
            "Diuréticos",
            "Gastrointestinales (Antiácidos/Protectores)",
            "Hipolipemiantes",
            "Psicofármacos",
            "Vitaminas y Suplementos",
            "Otros"
        ]
        
        combo_tratamiento = ttk.Combobox(frame_contenido, textvariable=self.tratamiento_tipo_var, 
                                        values=usos_terapeuticos, state="readonly", width=40, font=("Segoe UI", 10))
        combo_tratamiento.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        def agregar_tipo_tratamiento(event=None):
            tipo = self.tratamiento_tipo_var.get()
            if tipo:
                texto_actual = self.texto_tratamiento_pestana.get("1.0", tk.END).strip()
                nuevo_texto = f"\n--- {tipo.upper()} ---\n"
                if texto_actual:
                    self.texto_tratamiento_pestana.insert(tk.END, nuevo_texto)
                else:
                    self.texto_tratamiento_pestana.insert("1.0", nuevo_texto.strip() + "\n")
        
        combo_tratamiento.bind("<<ComboboxSelected>>", agregar_tipo_tratamiento)
        
        # Área de texto Tratamiento
        tk.Label(frame_contenido, text="Prescripción y Detalles del Tratamiento:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=1, column=0, columnspan=2, sticky="nw", padx=5, pady=(10,5))
        
        self.texto_tratamiento_pestana = tk.Text(frame_contenido, height=15, width=80, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_tratamiento_pestana.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        
        scrollbar_txt = tk.Scrollbar(frame_contenido, command=self.texto_tratamiento_pestana.yview)
        scrollbar_txt.grid(row=2, column=2, sticky="ns")
        self.texto_tratamiento_pestana.config(yscrollcommand=scrollbar_txt.set)
        
        # Botón limpiar
        btn_limpiar = tk.Button(frame_contenido, text="Limpiar Tratamiento",
                               command=lambda: self.texto_tratamiento_pestana.delete("1.0", tk.END),
                               bg="#95a5a6", fg="white", padx=15, pady=5)
        btn_limpiar.grid(row=3, column=0, columnspan=3, pady=10)
        
        frame_contenido.grid_columnconfigure(0, weight=1)
        frame_contenido.grid_rowconfigure(2, weight=1)
    
    # La pestaña de Planificación (Citas) se ha fusionado con la pestaña de Control.
    # El método configurar_pestana_planificacion ha sido eliminado.
    
    def configurar_pestana_control(self):
        """Configura la pestaña de control del paciente"""
        # Dividir en dos paneles: Lista (izq) y Detalles (der)
        paned_window = tk.PanedWindow(self.pestana_control, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- Panel Izquierdo: Lista de Controles ---
        frame_lista = tk.Frame(paned_window, bg="white", padx=10, pady=10)
        paned_window.add(frame_lista, width=280)
        
        tk.Label(frame_lista, text="HISTORIAL DE CONTROLES", bg="white", font=("Segoe UI", 10, "bold"), fg=self.color_principal).pack(fill=tk.X, pady=(0, 10))
        
        # Treeview para controles
        columnas_control = ("Fecha", "Hora")
        self.tree_controles = ttk.Treeview(frame_lista, columns=columnas_control, show="headings", height=15)
        
        self.tree_controles.heading("Fecha", text="Fecha")
        self.tree_controles.column("Fecha", width=80)
        self.tree_controles.heading("Hora", text="Hora")
        self.tree_controles.column("Hora", width=60)
        
        scrollbar_controles = ttk.Scrollbar(frame_lista, orient=tk.VERTICAL, command=self.tree_controles.yview)
        self.tree_controles.configure(yscrollcommand=scrollbar_controles.set)
        
        self.tree_controles.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_controles.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree_controles.bind("<<TreeviewSelect>>", self.seleccionar_control)
        
        # --- Panel Derecho: Detalles del Control ---
        # Frame con scrollbar para el formulario
        frame_detalle_container = tk.Frame(paned_window, bg=self.color_fondo)
        paned_window.add(frame_detalle_container)
        
        canvas_control = tk.Canvas(frame_detalle_container, bg=self.color_fondo, highlightthickness=0)
        scrollbar_control = ttk.Scrollbar(frame_detalle_container, orient=tk.VERTICAL, command=canvas_control.yview)
        frame_control_scroll = tk.Frame(canvas_control, bg=self.color_fondo)
        
        frame_control_scroll.bind(
            "<Configure>",
            lambda e: canvas_control.configure(scrollregion=canvas_control.bbox("all"))
        )
        
        window_id = canvas_control.create_window((0, 0), window=frame_control_scroll, anchor="nw")
        canvas_control.bind("<Configure>", lambda e: canvas_control.itemconfig(window_id, width=e.width))
        canvas_control.configure(yscrollcommand=scrollbar_control.set)
        
        canvas_control.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_control.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido del formulario (Modernizado con estilo de tarjeta blanca)
        frame_contenido = tk.LabelFrame(frame_control_scroll, 
                                      text=" DETALLES DEL CONTROL SELECCIONADO ",
                                      font=("Segoe UI", 11, "bold"),
                                      fg=self.color_principal,
                                      bg="white",
                                      padx=20, pady=20,
                                      relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_contenido.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Info fecha control seleccionado
        self.lbl_fecha_control_actual = tk.Label(frame_contenido, text="NUEVO CONTROL", 
                                                font=("Segoe UI", 10, "bold"), fg=self.color_secundario, bg="white")
        self.lbl_fecha_control_actual.grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 15))
        
        # --- Fila 1: Resultados y Evolución ---
        tk.Label(frame_contenido, text="Resultados de Exámenes:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=2, column=0, sticky="nw", padx=5, pady=5)
        
        self.texto_resultados = tk.Text(frame_contenido, height=6, width=40, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_resultados.grid(row=3, column=0, padx=5, pady=5, sticky="nsew")
        
        tk.Label(frame_contenido, text="Evolución del Paciente:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=2, column=1, sticky="nw", padx=5, pady=5)
        
        self.texto_evolucion = tk.Text(frame_contenido, height=6, width=40, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_evolucion.grid(row=3, column=1, padx=5, pady=5, sticky="nsew")
        
        # --- Fila 2: Tratamiento y Nuevos Exámenes ---
        tk.Label(frame_contenido, text="Tratamiento Adicional:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=4, column=0, sticky="nw", padx=5, pady=5)
        
        self.texto_tratamiento_adicional = tk.Text(frame_contenido, height=6, width=40, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_tratamiento_adicional.grid(row=5, column=0, padx=5, pady=5, sticky="nsew")
        
        tk.Label(frame_contenido, text="Nuevos Exámenes Solicitados:", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=4, column=1, sticky="nw", padx=5, pady=5)
        
        self.texto_nuevos_examenes = tk.Text(frame_contenido, height=6, width=40, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        self.texto_nuevos_examenes.grid(row=5, column=1, padx=5, pady=5, sticky="nsew")
        
        # --- Planificación Futura / Citas (Merge) ---
        frame_plan = tk.LabelFrame(frame_contenido, text=" PLANIFICACIÓN FUTURA / CITAS ", 
                                font=("Segoe UI", 10, "bold"), fg=self.color_principal, bg="white", 
                                padx=15, pady=15, relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_plan.grid(row=0, column=0, sticky="nsew", padx=5, pady=10)
        
        # Botones (Movido a Row 5, Columna 1)
        frame_botones = tk.Frame(frame_contenido, bg="white")
        frame_botones.grid(row=0, column=1, sticky="nsew", padx=5, pady=10)
        
        # Fila 0: Próxima Consulta
        tk.Label(frame_plan, text="Próxima Consulta:", bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=0, column=0, sticky="w")
        
        entry_prox = tk.Entry(frame_plan, textvariable=self.prox_consulta_var, width=12, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
        entry_prox.grid(row=0, column=1, sticky="w", padx=5, ipady=3)
        
        tk.Label(frame_plan, text="(DD/MM/AAAA)", bg="white", font=("Segoe UI", 8), fg="#94a3b8").grid(row=0, column=2, sticky="w")
        
        # Botones dias
        frame_dias = tk.Frame(frame_plan, bg="white")
        frame_dias.grid(row=0, column=3, sticky="w", padx=10)
        
        for dias in [3, 5, 7, 15, 30, 60]:
             tk.Button(frame_dias, text=f"+{dias}d", command=lambda d=dias: self.calcular_fecha_futura(d), 
                       bg=self.color_secundario, fg="white", font=("Segoe UI", 8, "bold"), 
                       relief="flat", cursor="hand2", padx=8, pady=2).pack(side=tk.LEFT, padx=1)


        
        # Expansion frame plan
        frame_plan.grid_columnconfigure(3, weight=1)


        
        btn_nuevo_control = tk.Button(frame_botones, text="Nuevo Control",
                                       command=self.nuevo_control,
                                       bg=self.color_secundario, fg="white",
                                       font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2", padx=15, pady=8)
        btn_nuevo_control.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        btn_guardar_control = tk.Button(frame_botones, text="Guardar Control",
                                       command=self.guardar_control,
                                       bg=self.color_principal, fg="white",
                                       font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2", padx=15, pady=8)
        btn_guardar_control.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        btn_eliminar_control = tk.Button(frame_botones, text="Eliminar Control",
                                       command=self.eliminar_control,
                                       bg="#ef4444", fg="white",
                                       font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2", padx=15, pady=8)
        btn_eliminar_control.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Configurar expansión
        frame_contenido.grid_columnconfigure(0, weight=1)
        frame_contenido.grid_columnconfigure(1, weight=1)
        frame_contenido.grid_rowconfigure(3, weight=1)
        frame_contenido.grid_rowconfigure(5, weight=1)
    
    def configurar_pestana_estadisticas(self):
        """Configura la pestaña de estadísticas"""
        # Frame con scrollbar
        canvas_estadisticas = tk.Canvas(self.pestana_estadisticas, bg=self.color_fondo, highlightthickness=0)
        scrollbar_estadisticas = ttk.Scrollbar(self.pestana_estadisticas, orient=tk.VERTICAL, command=canvas_estadisticas.yview)
        frame_estadisticas_scroll = tk.Frame(canvas_estadisticas, bg=self.color_fondo)
        
        frame_estadisticas_scroll.bind(
            "<Configure>",
            lambda e: canvas_estadisticas.configure(scrollregion=canvas_estadisticas.bbox("all"))
        )
        
        canvas_estadisticas.create_window((0, 0), window=frame_estadisticas_scroll, anchor="nw")
        canvas_estadisticas.configure(yscrollcommand=scrollbar_estadisticas.set)
        
        canvas_estadisticas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_estadisticas.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido de la pestaña (Modernizado con estilo de tarjeta blanca)
        frame_contenido = tk.LabelFrame(frame_estadisticas_scroll, 
                                      text=" ESTADÍSTICAS MENSUALES ",
                                      font=("Segoe UI", 11, "bold"),
                                      fg=self.color_principal,
                                      bg="white",
                                      padx=20, pady=20,
                                      relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_contenido.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Frame para estadísticas
        frame_stats = tk.Frame(frame_contenido, bg="white")
        frame_stats.pack(fill=tk.BOTH, expand=True)
        
        # Título
        tk.Label(frame_stats, text="RESUMEN MENSUAL DE CONSULTAS", 
                font=("Segoe UI", 14, "bold"), fg=self.color_principal, bg="white").pack(pady=(0, 20))
        
        # Selección de mes
        frame_mes = tk.Frame(frame_stats, bg="white")
        frame_mes.pack(pady=(0, 20))
        
        tk.Label(frame_mes, text="Seleccionar Mes:", 
                font=("Segoe UI", 10, "bold"), fg="#64748b", bg="white").pack(side=tk.LEFT, padx=(0, 10))
        
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        
        self.mes_seleccionado = tk.StringVar(value=meses[datetime.now().month - 1])
        combo_mes = ttk.Combobox(frame_mes, textvariable=self.mes_seleccionado, 
                                values=meses, state="readonly", width=15)
        combo_mes.pack(side=tk.LEFT, padx=(0, 20))
        
        tk.Label(frame_mes, text="Año:", 
                font=("Segoe UI", 10, "bold"), fg="#64748b", bg="white").pack(side=tk.LEFT, padx=(0, 10))
        
        año_actual = datetime.now().year
        años = [str(año) for año in range(año_actual - 5, año_actual + 1)]
        self.año_seleccionado = tk.StringVar(value=str(año_actual))
        combo_año = ttk.Combobox(frame_mes, textvariable=self.año_seleccionado, 
                                values=años, state="readonly", width=10)
        combo_año.pack(side=tk.LEFT)
        
        # Botón para generar estadísticas
        btn_generar = tk.Button(frame_mes, text="Generar Estadísticas",
                               command=self.generar_estadisticas_mensuales,
                               bg=self.color_secundario, fg="white", font=("Segoe UI", 9, "bold"),
                               relief="flat", cursor="hand2", padx=20, pady=8)
        btn_generar.pack(side=tk.LEFT, padx=(20, 0))
        
        # Área de texto para estadísticas
        self.texto_estadisticas = tk.Text(frame_stats, height=20, width=80, 
                                         font=("Courier", 10), wrap=tk.WORD)
        self.texto_estadisticas.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Botón para exportar
        btn_exportar_stats = tk.Button(frame_stats, text="Exportar Estadísticas a TXT",
                                      command=self.exportar_estadisticas,
                                      bg=self.color_principal, fg="white", font=("Segoe UI", 9, "bold"),
                                      relief="flat", cursor="hand2", padx=25, pady=10)
        btn_exportar_stats.pack()
        
        # Generar estadísticas del mes actual por defecto
        self.generar_estadisticas_mensuales()
    
    def generar_estadisticas_mensuales(self):
        """Genera estadísticas mensuales"""
        try:
            mes_nombre = self.mes_seleccionado.get()
            año = int(self.año_seleccionado.get())
            
            # Convertir nombre del mes a número
            meses_dict = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, 
                         "Mayo": 5, "Junio": 6, "Julio": 7, "Agosto": 8,
                         "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}
            mes_num = meses_dict[mes_nombre]
            
            # Filtrar pacientes del mes seleccionado
            pacientes_mes = []
            for paciente in self.pacientes:
                try:
                    fecha_str = paciente.get('fecha', '')
                    if fecha_str:
                        fecha = datetime.strptime(fecha_str, "%d/%m/%Y")
                        if fecha.month == mes_num and fecha.year == año:
                            pacientes_mes.append(paciente)
                except:
                    continue
            
            # Calcular estadísticas
            total = len(pacientes_mes)
            
            if total == 0:
                estadisticas = f"""
                ESTADÍSTICAS MENSUALES - {mes_nombre.upper()} {año}
                {'=' * 50}
                
                No hay pacientes registrados para este período.
                """
            else:
                # Estadísticas por sexo
                masculinos = sum(1 for p in pacientes_mes if p.get('sexo', '').lower() == 'masculino')
                femeninos = sum(1 for p in pacientes_mes if p.get('sexo', '').lower() == 'femenino')
                
                # Estadísticas por edad
                edades = []
                for p in pacientes_mes:
                    try:
                        edad = int(p.get('edad', 0))
                        if edad > 0:
                            edades.append(edad)
                    except:
                        pass
                
                edad_promedio = sum(edades) / len(edades) if edades else 0
                edad_min = min(edades) if edades else 0
                edad_max = max(edades) if edades else 0
                
                # Diagnósticos más comunes
                diagnosticos = {}
                for p in pacientes_mes:
                    diag = p.get('diagnostico', '').strip()
                    if diag:
                        if diag in diagnosticos:
                            diagnosticos[diag] += 1
                        else:
                            diagnosticos[diag] = 1
                
                # Top 5 diagnósticos
                top_diagnosticos = sorted(diagnosticos.items(), key=lambda x: x[1], reverse=True)[:5]
                
                estadisticas = f"""
                ESTADÍSTICAS MENSUALES - {mes_nombre.upper()} {año}
                {'=' * 50}
                
                TOTAL DE PACIENTES ATENDIDOS: {total}
                
                DISTRIBUCIÓN POR SEXO:
                • Masculinos: {masculinos} ({masculinos/total*100:.1f}%)
                • Femeninos: {femeninos} ({femeninos/total*100:.1f}%)
                
                ESTADÍSTICAS DE EDAD:
                • Edad promedio: {edad_promedio:.1f} años
                • Edad mínima: {edad_min} años
                • Edad máxima: {edad_max} años
                
                DIAGNÓSTICOS MÁS COMUNES:
                """
                
                for i, (diag, cantidad) in enumerate(top_diagnosticos, 1):
                    porcentaje = (cantidad / total) * 100
                    estadisticas += f"{i}. {diag[:50]}...: {cantidad} ({porcentaje:.1f}%)\n"
                
                if not top_diagnosticos:
                    estadisticas += "No hay diagnósticos registrados.\n"
                
                estadisticas += f"""
                {'=' * 50}
                Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}
                """
            
            # Mostrar en el área de texto
            self.texto_estadisticas.delete("1.0", tk.END)
            self.texto_estadisticas.insert("1.0", estadisticas)
            
        except Exception as e:
            logging.error(f"Error al generar estadísticas mensuales: {str(e)}")
            self.texto_estadisticas.delete("1.0", tk.END)
            self.texto_estadisticas.insert("1.0", f"Error al generar estadísticas: {str(e)}")
    
    def exportar_estadisticas(self):
        """Exporta las estadísticas a un archivo TXT"""
        try:
            contenido = self.texto_estadisticas.get("1.0", tk.END).strip()
            if not contenido:
                messagebox.showwarning("Sin contenido", "No hay estadísticas para exportar.")
                return
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"estadisticas_{self.mes_seleccionado.get()}_{self.año_seleccionado.get()}.txt"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(contenido)
                
                messagebox.showinfo("Exportación Exitosa", 
                                   f"Estadísticas exportadas a:\n{filename}")
                logging.info(f"Estadísticas exportadas a TXT: {filename}")
                
        except Exception as e:
            messagebox.showerror("Error de Exportación", 
                                f"No se pudo exportar las estadísticas: {str(e)}")
            logging.error(f"Error al exportar estadísticas: {str(e)}")
    
    def crear_menu(self):
        """Crea el menú principal"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menú Archivo
        menu_archivo = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=menu_archivo)
        menu_archivo.add_command(label="Nuevo Registro", command=self.limpiar_formulario_completo, accelerator="Ctrl+L")
        menu_archivo.add_command(label="Guardar", command=self.guardar_registro, accelerator="Ctrl+S")
        menu_archivo.add_separator()
        menu_archivo.add_command(label="Exportar a JSON", command=self.exportar_json, accelerator="Ctrl+E")
        menu_archivo.add_command(label="Exportar a CSV", command=self.exportar_csv)
        menu_archivo.add_command(label="Crear Backup", command=self.mostrar_backup_dialog)
        menu_archivo.add_separator()
        menu_archivo.add_command(label="Salir", command=self.root.quit, accelerator="Ctrl+Q")
        
        # Menú Edición
        menu_edicion = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edición", menu=menu_edicion)
        menu_edicion.add_command(label="Copiar", command=self.copiar_seleccionado)
        menu_edicion.add_separator()
        menu_edicion.add_command(label="Buscar", command=self.focus_busqueda, accelerator="Ctrl+F")
        
        # Menú Herramientas
        menu_herramientas = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Herramientas", menu=menu_herramientas)
        menu_herramientas.add_command(label="Verificar Próximas Consultas", command=self.verificar_proximas_consultas)
        menu_herramientas.add_command(label="Imprimir Registro", command=self.imprimir_registro)
        
        # Menú Ayuda
        menu_ayuda = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=menu_ayuda)
        menu_ayuda.add_command(label="Manual de Usuario", command=self.mostrar_ayuda, accelerator="F1")
        menu_ayuda.add_command(label="Acerca de", command=self.mostrar_acerca_de)
    
    def crear_botones_accion(self, parent):
        """Crea los botones de acción con estilo moderno al fondo"""
        frame_botones = tk.Frame(parent, bg=self.color_fondo)
        frame_botones.pack(side=tk.BOTTOM, fill=tk.X, pady=(20, 0))
        
        # Botones principales (Derecha)
        frame_derecha = tk.Frame(frame_botones, bg=self.color_fondo)
        frame_derecha.pack(side=tk.RIGHT)
        
        # Uso mis colores de token
        btn_config = {
            "font": ("Segoe UI", 10, "bold"),
            "relief": "flat",
            "cursor": "hand2",
            "padx": 20, "pady": 8,
            "fg": "white"
        }
        
        tk.Button(frame_derecha, text="Guardar Registro", command=self.guardar_registro,
                  bg=self.color_boton, **btn_config).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(frame_derecha, text="Actualizar", command=self.actualizar_registro,
                  bg=self.color_secundario, **btn_config).pack(side=tk.RIGHT, padx=5)
                  
        tk.Button(frame_derecha, text="Nuevo / Limpiar", command=self.limpiar_formulario_completo,
                  bg="#94a3b8", **btn_config).pack(side=tk.RIGHT, padx=5)
        
        # Botones de gestión (Izquierda)
        frame_izquierda = tk.Frame(frame_botones, bg=self.color_fondo)
        frame_izquierda.pack(side=tk.LEFT)
        
        tk.Button(frame_izquierda, text="Eliminar Paciente", command=self.eliminar_registro,
                  bg="#ef4444", **btn_config).pack(side=tk.LEFT, padx=5)

        tk.Button(frame_izquierda, text="Exportar JSON", command=self.exportar_json,
                  bg=self.color_acento, **btn_config).pack(side=tk.LEFT, padx=5)
    
    def crear_lista_pacientes(self, parent):
        """Crea la lista de pacientes registrados con estilo moderno"""
        frame_lista = tk.Frame(parent, bg="white")
        frame_lista.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Etiqueta de encabezado
        tk.Label(frame_lista, text="Pacientes Registrados en el Sistema", 
                 font=("Segoe UI", 12, "bold"), fg=self.color_principal, bg="white").pack(anchor="w", pady=(0, 15))
        
        # Treeview para mostrar pacientes
        columnas = ("ID", "Fecha", "Cédula", "Nombre", "Edad", "Sexo", "Motivo")
        self.tree = ttk.Treeview(frame_lista, columns=columnas, show="headings", style="Treeview")
        
        # Configurar columnas
        anchos = [50, 90, 100, 250, 60, 80, 200]
        for col, ancho in zip(columnas, anchos):
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width=ancho, anchor="center")
        
        self.tree.column("Nombre", anchor="w")
        self.tree.column("Motivo", anchor="w")
        
        # Scrollbar moderno
        scrollbar = ttk.Scrollbar(frame_lista, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configurar evento de selección
        self.tree.bind("<<TreeviewSelect>>", self.cargar_paciente_seleccionado)
        
        # Cargar pacientes existentes
        self.actualizar_lista_pacientes()
    
    def calcular_edad_auto(self, *args):
        """Calcula la edad automáticamente cuando cambia la fecha de nacimiento"""
        fecha_nac = self.fecha_nac_var.get()
        if fecha_nac and len(fecha_nac) == 10:  # DD/MM/AAAA
            edad = self.calcular_edad(fecha_nac)
            self.edad_var.set(edad)
    
    def calcular_imc_auto(self, *args):
        """Calcula el IMC automáticamente cuando cambian peso o talla"""
        peso = self.peso_var.get()
        talla = self.talla_var.get()
        
        if peso and talla:
            imc = self.calcular_imc(peso, talla)
            if imc:
                self.imc_var.set(imc)
                self.clasificar_imc(float(imc))
    
    def calcular_imc_manual(self):
        """Calcula el IMC manualmente"""
        peso = self.peso_var.get()
        talla = self.talla_var.get()
        
        if not peso or not talla:
            messagebox.showwarning("Datos incompletos", "Ingrese peso y talla para calcular el IMC.")
            return
        
        imc = self.calcular_imc(peso, talla)
        if imc:
            self.imc_var.set(imc)
            self.clasificar_imc(float(imc))
    
    def calcular_hta(self, *args):
        """Calcula y clasifica la hipertensión arterial"""
        try:
            sis = self.presion_sistolica_var.get()
            dia = self.presion_diastolica_var.get()
            
            if not sis or not dia:
                self.presion_clasificacion_var.set("")
                return
                
            sis = int(sis)
            dia = int(dia)
            
            # Clasificación JNC 7 / AHA
            if sis < 120 and dia < 80:
                clasificacion = "Normal"
            elif 120 <= sis <= 129 and dia < 80:
                clasificacion = "Elevada"
            elif 130 <= sis <= 139 or 80 <= dia <= 89:
                clasificacion = "Hipertensión Nivel 1"
            elif sis >= 140 or dia >= 90:
                clasificacion = "Hipertensión Nivel 2"
            elif sis > 180 or dia > 120:
                clasificacion = "CRISIS HIPERTENSIVA"
            else:
                clasificacion = "Indeterminado"
                
            self.presion_clasificacion_var.set(clasificacion)
        except:
            self.presion_clasificacion_var.set("")
    
    def clasificar_imc(self, imc):
        """Clasifica el IMC según valores estándar"""
        try:
            if imc < 18.5:
                clasificacion = "Bajo peso"
                color = "#3498db"
            elif imc < 25:
                clasificacion = "Peso normal"
                color = "#2ecc71"
            elif imc < 30:
                clasificacion = "Sobrepeso"
                color = "#f39c12"
            elif imc < 35:
                clasificacion = "Obesidad grado I"
                color = "#e67e22"
            elif imc < 40:
                clasificacion = "Obesidad grado II"
                color = "#d35400"
            else:
                clasificacion = "Obesidad grado III (mórbida)"
                color = "#c0392b"
            
            self.imc_clasificacion_var.set(f"{clasificacion}")
        except:
            self.imc_clasificacion_var.set("")
    
    def agregar_examen_lab(self, event=None):
        """Agrega un examen de laboratorio seleccionado al área de texto"""
        examen = self.lista_lab_var.get()
        if examen:
            contenido_actual = self.texto_examenes_lab.get("1.0", tk.END).strip()
            if contenido_actual:
                nuevo_contenido = contenido_actual + "\n• " + examen
            else:
                nuevo_contenido = "• " + examen
            
            self.texto_examenes_lab.delete("1.0", tk.END)
            self.texto_examenes_lab.insert("1.0", nuevo_contenido)
            self.lista_lab_var.set("")
    
    def agregar_examen_lab_manual(self):
        """Permite agregar un examen de laboratorio manualmente"""
        try:
            examen = simpledialog.askstring("Agregar Examen", "Ingrese el examen de laboratorio:")
            if examen:
                contenido_actual = self.texto_examenes_lab.get("1.0", tk.END).strip()
                if contenido_actual:
                    nuevo_contenido = contenido_actual + "\n• " + examen
                else:
                    nuevo_contenido = "• " + examen
                
                self.texto_examenes_lab.delete("1.0", tk.END)
                self.texto_examenes_lab.insert("1.0", nuevo_contenido)
        except Exception as e:
            logging.error(f"Error al agregar examen lab manual: {str(e)}")
    
    def agregar_examen_img(self, event=None):
        """Agrega un examen de imagenología seleccionado al área de texto"""
        examen = self.lista_img_var.get()
        if examen:
            contenido_actual = self.texto_examenes_img.get("1.0", tk.END).strip()
            if contenido_actual:
                nuevo_contenido = contenido_actual + "\n• " + examen
            else:
                nuevo_contenido = "• " + examen
            
            self.texto_examenes_img.delete("1.0", tk.END)
            self.texto_examenes_img.insert("1.0", nuevo_contenido)
            self.lista_img_var.set("")
    
    def agregar_examen_img_manual(self):
        """Permite agregar un examen de imagenología manualmente"""
        try:
            examen = simpledialog.askstring("Agregar Examen", "Ingrese el examen de imagenología:")
            if examen:
                contenido_actual = self.texto_examenes_img.get("1.0", tk.END).strip()
                if contenido_actual:
                    nuevo_contenido = contenido_actual + "\n• " + examen
                else:
                    nuevo_contenido = "• " + examen
                
                self.texto_examenes_img.delete("1.0", tk.END)
                self.texto_examenes_img.insert("1.0", nuevo_contenido)
        except Exception as e:
            logging.error(f"Error al agregar examen img manual: {str(e)}")
    
    def buscar_paciente(self, *args):
        """Busca pacientes según el criterio seleccionado"""
        if not hasattr(self, 'tree'):
            return

        # Cambiar automáticamente a la pestaña de lista para ver resultados
        if hasattr(self, 'notebook') and hasattr(self, 'pestana_lista_pacientes'):
            self.notebook.select(self.pestana_lista_pacientes)

        busqueda = self.busqueda_var.get().lower()
        tipo = self.tipo_busqueda_var.get()
        
        if not busqueda:
            self.actualizar_lista_pacientes()
            return
        
        # Filtrar pacientes
        pacientes_filtrados = []
        
        for paciente in self.pacientes:
            if tipo == "nombre":
                nombre_completo = f"{paciente['nombres']} {paciente['apellidos']}".lower()
                if busqueda in nombre_completo:
                    pacientes_filtrados.append(paciente)
            elif tipo == "id":
                if busqueda == str(paciente["id"]):
                    pacientes_filtrados.append(paciente)
            elif tipo == "cedula":
                cedula = paciente.get("cedula", "").lower()
                if busqueda in cedula:
                    pacientes_filtrados.append(paciente)
        
        # Actualizar treeview con resultados filtrados
        self.actualizar_lista_pacientes_filtrados(pacientes_filtrados)
    
    def actualizar_lista_pacientes_filtrados(self, pacientes_filtrados):
        """Actualiza la lista con pacientes filtrados"""
        if not hasattr(self, 'tree'):
            return

        # Limpiar lista actual
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Agregar pacientes filtrados
        for paciente in pacientes_filtrados:
            self.tree.insert("", tk.END, values=(
                paciente["id"],
                paciente["fecha"],
                paciente.get("cedula", ""),
                f"{paciente['nombres']} {paciente['apellidos']}",
                paciente["edad"],
                paciente.get("sexo", ""),
                paciente.get("motivo", "")[:30] + "..." if len(paciente.get("motivo", "")) > 30 else paciente.get("motivo", "")
            ))
    
    def actualizar_lista_pacientes(self):
        """Actualiza la lista de pacientes en el Treeview"""
        if not hasattr(self, 'tree'):
            return
            
        # Limpiar lista actual
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Agregar pacientes
        for paciente in self.pacientes:
            self.tree.insert("", tk.END, values=(
                paciente["id"],
                paciente["fecha"],
                paciente.get("cedula", ""),
                f"{paciente['nombres']} {paciente['apellidos']}",
                paciente["edad"],
                paciente.get("sexo", ""),
                paciente.get("motivo", "")[:30] + "..." if len(paciente.get("motivo", "")) > 30 else paciente.get("motivo", "")
            ))
    
    def limpiar_busqueda(self):
        """Limpia la búsqueda y muestra todos los pacientes"""
        self.busqueda_var.set("")
        self.actualizar_lista_pacientes()
    
    def calcular_fecha_futura(self, dias):
        """Calcula una fecha futura basada en los días proporcionados"""
        try:
            hoy = datetime.now()
            fecha_futura = hoy + timedelta(days=dias)
            self.prox_consulta_var.set(fecha_futura.strftime("%d/%m/%Y"))
        except Exception as e:
            logging.error(f"Error al calcular fecha futura: {str(e)}")
            
    def calcular_fecha_30dias(self):
        """Deprecated: Use calcular_fecha_futura(30)"""
        self.calcular_fecha_futura(30)
    
    def calcular_fecha_60dias(self):
        """Deprecated: Use calcular_fecha_futura(60)"""
        self.calcular_fecha_futura(60)

    def agregar_cirugia_planificada(self, event=None):
        """Agrega la cirugía seleccionada al campo de texto"""
        cirugia = self.combo_cirugias.get()
        if not cirugia:
            return
            
        texto_actual = self.texto_cirugia.get("1.0", tk.END).strip()
        
        prefijo = "Cirugía Programada: "
        nuevo_texto = ""
        
        if cirugia == "Otras":
             # Solo agregar el prefijo si no existe, para que usuario escriba
             nuevo_item = f"{prefijo}"
        else:
             nuevo_item = f"{prefijo}{cirugia}"
        
        if texto_actual:
            self.texto_cirugia.insert(tk.END, f"\n{nuevo_item}")
        else:
            self.texto_cirugia.insert("1.0", f"{nuevo_item}")
            
        # Si es "Otras", poner foco al final
        if cirugia == "Otras":
            self.texto_cirugia.focus_set()
            self.texto_cirugia.see(tk.END)
    
    def limpiar_diagnostico_tratamiento(self):
        """Limpia las áreas de diagnóstico y tratamiento"""
        self.texto_diagnostico.delete("1.0", tk.END)
        self.texto_tratamiento.delete("1.0", tk.END)
    
    def limpiar_planificacion(self):
        """Limpia las áreas de planificación"""
        self.prox_consulta_var.set("")
        self.texto_cirugia.delete("1.0", tk.END)
    
    def limpiar_control(self):
        """Limpia las áreas de control del paciente"""
        self.texto_resultados.delete("1.0", tk.END)
        self.texto_evolucion.delete("1.0", tk.END)
        self.texto_tratamiento_adicional.delete("1.0", tk.END)
        self.texto_nuevos_examenes.delete("1.0", tk.END)
        # Limpiar treeview y selección
        for item in self.tree_controles.get_children():
            self.tree_controles.delete(item)
        self.control_seleccionado_index = None
        self.lbl_fecha_control_actual.config(text="Nuevo Control")
    
    def nuevo_control(self):
        """Prepara el formulario para un nuevo control"""
        self.control_seleccionado_index = None
        self.tree_controles.selection_remove(self.tree_controles.selection())
        self.limpiar_campos_control()
        self.lbl_fecha_control_actual.config(text="Nuevo Control (Mode Création)")
    
    def limpiar_campos_control(self):
        """Limpia solo los campos del formulario de control"""
        self.texto_resultados.delete("1.0", tk.END)
        self.texto_evolucion.delete("1.0", tk.END)
        self.texto_tratamiento_adicional.delete("1.0", tk.END)
        self.texto_nuevos_examenes.delete("1.0", tk.END)

    def seleccionar_control(self, event):
        """Carga los datos del control seleccionado en el formulario"""
        seleccion = self.tree_controles.selection()
        if not seleccion:
            return
        
        # Obtener índice del control
        item_id = seleccion[0]
        index = int(self.tree_controles.index(item_id))
        self.control_seleccionado_index = index
        
        # Obtener paciente actual
        paciente_seleccionado = self.tree.selection()
        if not paciente_seleccionado:
            return
            
        paciente_id = int(self.tree.item(paciente_seleccionado[0])['values'][0])
        paciente = next((p for p in self.pacientes if p["id"] == paciente_id), None)
        
        if paciente and 'controles' in paciente and index < len(paciente['controles']):
            control = paciente['controles'][index]
            
            # Cargar datos en campos
            self.limpiar_campos_control()
            self.texto_resultados.insert("1.0", control.get('resultados', ''))
            self.texto_evolucion.insert("1.0", control.get('evolucion', ''))
            self.texto_tratamiento_adicional.insert("1.0", control.get('tratamiento_adicional', ''))
            self.texto_nuevos_examenes.insert("1.0", control.get('nuevos_examenes', ''))
            
            # Actualizar etiqueta
            fecha = control.get('fecha_control', 'N/A')
            self.lbl_fecha_control_actual.config(text=f"Control del: {fecha}")

    def actualizar_lista_controles(self, paciente):
        """Actualiza la lista de controles en el Treeview"""
        # Limpiar lista actual
        for item in self.tree_controles.get_children():
            self.tree_controles.delete(item)
            
        # Verificar si hay controles (lista o dict legado)
        controles = paciente.get('controles', [])
        
        # Migración al vuelo si existe 'control' antiguo y no 'controles'
        if not controles and 'control' in paciente and paciente['control']:
            # Convertir dict único a lista
            control_antiguo = paciente['control']
            if any(control_antiguo.values()): # Si tiene algo de contenido
                if 'fecha_control' not in control_antiguo:
                    control_antiguo['fecha_control'] = datetime.now().strftime("%d/%m/%Y %H:%M")
                controles = [control_antiguo]
                paciente['controles'] = controles
                # Opcional: eliminar 'control' antiguo, o dejarlo por seguridad hasta guardar
        
        # Llenar Treeview
        for i, control in enumerate(controles):
            fecha_hora = control.get('fecha_control', 'N/A')
            parts = fecha_hora.split(' ')
            fecha = parts[0]
            hora = parts[1] if len(parts) > 1 else ""
            self.tree_controles.insert("", tk.END, values=(fecha, hora))

    def guardar_control(self):
        """Guarda la información de control del paciente (Nuevo o Edición)"""
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Sin selección", "Seleccione un paciente para guardar el control.")
            return
        
        # Obtener ID del paciente seleccionado
        item = self.tree.item(seleccion[0])
        paciente_id = int(item['values'][0])
        
        # Buscar paciente por ID
        paciente = next((p for p in self.pacientes if p["id"] == paciente_id), None)
        
        if not paciente:
            messagebox.showerror("Error", "No se encontró el paciente seleccionado.")
            return
        
        # Preparar datos del control
        datos_control = {
            'resultados': self.texto_resultados.get("1.0", tk.END).strip(),
            'evolucion': self.texto_evolucion.get("1.0", tk.END).strip(),
            'tratamiento_adicional': self.texto_tratamiento_adicional.get("1.0", tk.END).strip(),
            'nuevos_examenes': self.texto_nuevos_examenes.get("1.0", tk.END).strip(),
            'fecha_control': datetime.now().strftime("%d/%m/%Y %H:%M")
        }

        # Inicializar lista de controles si no existe
        if 'controles' not in paciente:
            paciente['controles'] = []

        if self.control_seleccionado_index is not None:
            # ACTUALIZAR existente
            # Mantener la fecha original si se edita, o actualizarla? 
            # Generalmente se mantiene la fecha de creación del control,
            # pero aquí actualizaremos el contenido. 
            # Si se desea mantener la fecha original:
            original_fecha = paciente['controles'][self.control_seleccionado_index].get('fecha_control')
            if original_fecha:
                datos_control['fecha_control'] = original_fecha
            
            paciente['controles'][self.control_seleccionado_index] = datos_control
            accion = "actualizado"
        else:
            # CREAR nuevo
            paciente['controles'].append(datos_control)
            accion = "agregado"
        
        # Guardar en archivo
        self.guardar_datos()
        
        # Actualizar lista visual
        self.actualizar_lista_controles(paciente)
        
        # Si fue nuevo, limpiar para otro
        if self.control_seleccionado_index is None:
             self.nuevo_control()
             
        messagebox.showinfo("Control Guardado", f"Control {accion} exitosamente.")
        logging.info(f"Control {accion} para paciente ID: {paciente_id}")

    def eliminar_control(self):
        """Elimina el control seleccionado"""
        if self.control_seleccionado_index is None:
            messagebox.showwarning("Sin selección", "Seleccione un control de la lista para eliminar.")
            return
            
        if not messagebox.askyesno("Confirmar", "¿Está seguro de eliminar este registro de control?"):
            return

        seleccion = self.tree.selection()
        if not seleccion:
            return
        
        paciente_id = int(self.tree.item(seleccion[0])['values'][0])
        paciente = next((p for p in self.pacientes if p["id"] == paciente_id), None)
        
        if paciente and 'controles' in paciente:
            paciente['controles'].pop(self.control_seleccionado_index)
            self.guardar_datos()
            self.actualizar_lista_controles(paciente)
            self.nuevo_control()
            messagebox.showinfo("Eliminado", "Control eliminado exitosamente.")
    
    def limpiar_formulario_completo(self):
        """Limpia todos los campos del formulario en todas las pestañas"""
        # Confirmar limpieza
        if not messagebox.askyesno("Confirmar limpieza", "¿Está seguro de limpiar todos los datos del formulario?"):
            return
        
        # Establecer fecha y hora actual
        self.fecha_var.set(datetime.now().strftime("%d/%m/%Y"))
        self.hora_var.set(datetime.now().strftime("%H:%M"))
        
        # Actualizar ID
        self.id_var.set(str(len(self.pacientes) + 1))
        
        # Limpiar campos de texto básicos
        self.nombres_var.set("")
        self.apellidos_var.set("")
        self.fecha_nac_var.set("")
        self.edad_var.set("")
        self.cedula_var.set("")
        self.telefono_var.set("")
        self.sexo_var.set("Masculino")
        self.direccion_var.set("")
        self.ciudad_var.set("")
        self.instruccion_var.set("Ninguno")
        self.estado_civil_var.set("Soltero")
        
        # Limpiar motivo de consulta (área de texto)
        # self.texto_motivo.delete("1.0", tk.END) # Ya no existe
        
        # Limpiar anamnesis
        self.limpiar_anamnesis()
        
        # Limpiar signos vitales
        self.presion_sistolica_var.set("")
        self.presion_diastolica_var.set("")
        self.presion_clasificacion_var.set("")
        self.frecuencia_var.set("")
        self.temperatura_var.set("")
        self.respiratoria_var.set("")
        self.saturacion_var.set("")
        self.peso_var.set("")
        self.talla_var.set("")
        self.imc_var.set("")
        self.imc_clasificacion_var.set("")
        
        # Limpiar áreas de texto de exámenes
        self.texto_examenes_lab.delete("1.0", tk.END)
        self.texto_examenes_img.delete("1.0", tk.END)
        if hasattr(self, 'texto_examenes_otros'):
            self.texto_examenes_otros.delete("1.0", tk.END)
        
        # Limpiar examen físico (Variables)
        self.limpiar_fisico()
        
        # Limpiar diagnóstico y tratamiento
        self.texto_diagnostico.delete("1.0", tk.END)
        if hasattr(self, 'texto_tratamiento_pestana'):
             self.texto_tratamiento_pestana.delete("1.0", tk.END)
        
        self.tratamiento_tipo_var.set("")
        
        # Limpiar planificación
        self.prox_consulta_var.set("")
        self.texto_cirugia.delete("1.0", tk.END)
        
        # Limpiar control
        self.limpiar_control()
        
        # Restablecer comboboxes
        self.lista_lab_var.set("")
        self.lista_img_var.set("")
        if hasattr(self, 'combo_otros'):
            self.combo_otros.set("")
    
    def guardar_registro(self):
        """Guarda el registro del paciente con validaciones mejoradas"""
        # Validar campos obligatorios
        if not self.nombres_var.get() or not self.apellidos_var.get():
            messagebox.showwarning("Campos incompletos", 
                                 "Debe ingresar al menos el nombre y apellido del paciente.")
            return
        
        # Validar fecha de nacimiento
        if not self.fecha_nac_var.get():
            messagebox.showwarning("Fecha de nacimiento", 
                                 "Debe ingresar la fecha de nacimiento del paciente.")
            return
        
        if not self.validar_fecha(self.fecha_nac_var.get()):
            messagebox.showerror("Fecha inválida", 
                               "La fecha de nacimiento no tiene el formato correcto (DD/MM/AAAA).")
            return
        
        # Validar fecha de consulta
        if not self.validar_fecha(self.fecha_var.get()):
            messagebox.showerror("Fecha inválida", 
                               "La fecha de consulta no tiene el formato correcto (DD/MM/AAAA).")
            return
        
        # Validar hora
        if self.hora_var.get() and not self.validar_hora(self.hora_var.get()):
            messagebox.showerror("Hora inválida", 
                               "La hora no tiene el formato correcto (HH:MM).")
            return
        
        # Validar cédula (si se ingresó)
        if self.cedula_var.get() and not self.validar_cedula(self.cedula_var.get()):
            messagebox.showerror("Cédula inválida", 
                               "La cédula debe tener exactamente 10 dígitos.")
            return
        
        # Validar teléfono (si se ingresó)
        if self.telefono_var.get() and not self.validar_telefono(self.telefono_var.get()):
            messagebox.showerror("Teléfono inválido", 
                               "El teléfono debe tener exactamente 10 dígitos.")
            return
        
        # Calcular edad si no está calculada
        if not self.edad_var.get():
            self.calcular_edad_auto()
        
        # Crear diccionario con los datos
        paciente = {
            "id": len(self.pacientes) + 1,
            "fecha": self.fecha_var.get(),
            "hora": self.hora_var.get(),
            "nombres": self.nombres_var.get(),
            "apellidos": self.apellidos_var.get(),
            "fecha_nacimiento": self.fecha_nac_var.get(),
            "edad": self.edad_var.get(),
            "sexo": self.sexo_var.get(),
            "cedula": self.cedula_var.get(),
            "telefono": self.telefono_var.get(),
            "direccion": self.direccion_var.get(),
            "ciudad": self.ciudad_var.get(),
            "pais": self.pais_var.get(),
            "estado_civil": self.estado_civil_var.get(),
            "instruccion": self.instruccion_var.get(),
            "motivo": self.entry_motivo_anamnesis.get(), # Guardar también en root para compatibilidad o referencia rápida
            "anamnesis": {
                "tipo_consulta": self.consulta_tipo_var.get(),
                "motivo": self.entry_motivo_anamnesis.get(),
                "enfermedad_actual": self.texto_enfermedad_actual.get("1.0", tk.END).strip(),
                "ant_familiares": self.antecedentes_familiares_var.get(),
                "ant_personales": self.texto_ant_personales.get("1.0", tk.END).strip(),
                "alergias": self.texto_alergias.get("1.0", tk.END).strip(),
                "medicacion": self.texto_medicacion.get("1.0", tk.END).strip(),
                "cirugias_previas": self.texto_cirugias_previas.get("1.0", tk.END).strip(),
                "hospitalizaciones": self.texto_hospitalizaciones.get("1.0", tk.END).strip(),
                "dieta": self.dieta_var.get(),
                "ginecologico": {
                    "menarquia": self.ginecologicos_menarquia_var.get(),
                    "ciclos": self.ginecologicos_ciclos_var.get(),
                    "fum": self.ginecologicos_fum_var.get(),
                    "gestas": self.ginecologicos_gestas_var.get(),
                    "partos": self.ginecologicos_partos_var.get(),
                    "abortos": self.ginecologicos_abortos_var.get(),
                    "cesareas": self.ginecologicos_cesareas_var.get()
                }
            },
            "signos_vitales": {
                "presion": f"{self.presion_sistolica_var.get()}/{self.presion_diastolica_var.get()}",
                "sistolica": self.presion_sistolica_var.get(),
                "diastolica": self.presion_diastolica_var.get(),
                "clasificacion_hta": self.presion_clasificacion_var.get(),
                "frecuencia": self.frecuencia_var.get(),
                "temperatura": self.temperatura_var.get(),
                "respiratoria": self.respiratoria_var.get(),
                "saturacion": self.saturacion_var.get(),
                "peso": self.peso_var.get(),
                "talla": self.talla_var.get(),
                "imc": self.imc_var.get(),
                "clasificacion_imc": self.imc_clasificacion_var.get()
            },
            "examenes_lab": self.texto_examenes_lab.get("1.0", tk.END).strip(),
            "examenes_img": self.texto_examenes_img.get("1.0", tk.END).strip(),
            "examenes_otros": self.texto_examenes_otros.get("1.0", tk.END).strip() if hasattr(self, 'texto_examenes_otros') else "",
            
            # Examen físico detallado
            "examen_fisico_detalle": {
                "apariencia": self.fisico_apariencia_var.get(),
                "piel": self.fisico_piel_var.get(),
                "cabeza": self.fisico_cabeza_var.get(),
                "cuello": self.fisico_cuello_var.get(),
                "torax": self.fisico_torax_var.get(),
                "abdomen": self.fisico_abdomen_var.get(),
                "extremidades": self.fisico_extremidades_var.get(),
                "genital": self.fisico_genital_var.get(),
                "anoperineal": self.fisico_anoperineal_var.get(),
                "otros": self.fisico_otros_var.get()
            },
            # Solo guardamos el texto antiguo concatenado por compatibilidad o reporte
            "examen_fisico": "Detalle en ficha fisica", 
            
            "diagnostico": self.texto_diagnostico.get("1.0", tk.END).strip(),
            "tratamiento": self.texto_tratamiento_pestana.get("1.0", tk.END).strip() if hasattr(self, 'texto_tratamiento_pestana') else "",
            "proxima_consulta": self.prox_consulta_var.get(),
            "cirugia": ""
        }
        
        # Guardar en base de datos
        try:
            patient_id = self.db.upsert_patient(paciente)
            paciente['id'] = patient_id # Actualizar ID generado
            
            # Actualizar lista en memoria
            idx_existente = -1
            for i, p in enumerate(self.pacientes):
                if p.get('cedula') == paciente['cedula']: # Simplificación, idealmente usar ID
                    idx_existente = i
                    break
            
            if idx_existente >= 0:
                self.pacientes[idx_existente] = paciente
            else:
                self.pacientes.append(paciente)
            
            # Actualizar lista visual
            self.actualizar_lista_pacientes()
            
            # Actualizar ID para el siguiente (aprox)
            self.id_var.set(str(len(self.pacientes) + 1))
            
            # Registrar en log
            logging.info(f"Paciente guardado en BD: {paciente['nombres']} {paciente['apellidos']} (ID: {paciente['id']})")
            
            # Sincronizar con respaldo JSON
            self.guardar_datos()
            
            # Mostrar mensaje de confirmación
            messagebox.showinfo("Registro guardado", 
                               f"Paciente {paciente['nombres']} {paciente['apellidos']} registrado exitosamente.\nID asignado: {paciente['id']}")
            
            # Limpiar formulario después de guardar
            self.limpiar_formulario_completo()
            
        except Exception as e:
            logging.error(f"Error al guardar registro en BD: {e}")
            messagebox.showerror("Error", f"No se pudo guardar el registro: {e}")

    def formatear_fecha_evento(self, event):
        """Formatea la fecha al soltar una tecla (evita problemas de cursor)"""
        # Si se presiona BackSpace o Delete, no formatear para permitir borrar
        if event.keysym in ('BackSpace', 'Delete'):
            return

        entry = event.widget
        text = entry.get()
        
        # Eliminar cualquier caracter que no sea dígito
        clean_text = ''.join(filter(str.isdigit, text))
        
        formatted = ""
        if len(clean_text) > 0:
            formatted += clean_text[:2]
        if len(clean_text) > 2:
            formatted += "/" + clean_text[2:4]
        if len(clean_text) > 4:
            formatted += "/" + clean_text[4:8]
            
        # Solo actualizar si el formato es diferente
        if text != formatted:
            # Guardar posición del cursor (aunque al escribir al final, suele ir al final)
            insert_pos = len(formatted)
            
            entry.delete(0, tk.END)
            entry.insert(0, formatted)
            entry.icursor(insert_pos)

    def validar_solo_numeros(self, P):
        """Valida que solo se ingresen números y máximo 10 dígitos"""
        if P == "": return True
        return P.isdigit() and len(P) <= 10


    
    def cargar_paciente_seleccionado(self, event):
        """Carga los datos del paciente seleccionado en el formulario"""
        seleccion = self.tree.selection()
        if not seleccion:
            return
        
        # Obtener ID del paciente seleccionado
        item = self.tree.item(seleccion[0])
        paciente_id = int(item['values'][0])
        
        # Buscar paciente por ID
        paciente = None
        for p in self.pacientes:
            if p["id"] == paciente_id:
                paciente = p
                break
        
        if not paciente:
            return
        
        # Llenar campos del formulario
        self.id_var.set(str(paciente.get("id", "")))
        self.fecha_var.set(paciente.get("fecha", ""))
        self.hora_var.set(paciente.get("hora", ""))
        self.nombres_var.set(paciente.get("nombres", ""))
        self.apellidos_var.set(paciente.get("apellidos", ""))
        self.fecha_nac_var.set(paciente.get("fecha_nacimiento", ""))
        self.edad_var.set(paciente.get("edad", ""))
        self.sexo_var.set(paciente.get("sexo", "Masculino"))
        self.cedula_var.set(paciente.get("cedula", ""))
        self.telefono_var.set(paciente.get("telefono", ""))
        self.direccion_var.set(paciente.get("direccion", ""))
        self.ciudad_var.set(paciente.get("ciudad", ""))
        self.pais_var.set(paciente.get("pais", "ECUADOR"))
        
        self.pais_var.set(paciente.get("pais", "ECUADOR"))
        self.estado_civil_var.set(paciente.get("estado_civil", "Soltero"))
        self.instruccion_var.set(paciente.get("instruccion", "Ninguno"))
        
        # Anamnesis
        self.limpiar_anamnesis() # Limpiar primero
        anamnesis = paciente.get("anamnesis", {})
        
        # Migración legado: Si existe 'motivo' en root pero no en anamnesis, usarlo
        motivo_legado = paciente.get("motivo", "")
        motivo_nuevo = anamnesis.get("motivo", "")
        
        if not motivo_nuevo and motivo_legado:
            self.motivo_corto_var.set(motivo_legado)
        else:
            self.motivo_corto_var.set(motivo_nuevo)
            
        self.consulta_tipo_var.set(anamnesis.get("tipo_consulta", "Clínica"))
        self.texto_enfermedad_actual.insert("1.0", anamnesis.get("enfermedad_actual", ""))
        self.antecedentes_familiares_var.set(anamnesis.get("ant_familiares", ""))
        self.texto_ant_personales.insert("1.0", anamnesis.get("ant_personales", ""))
        self.texto_alergias.insert("1.0", anamnesis.get("alergias", ""))
        self.texto_medicacion.insert("1.0", anamnesis.get("medicacion", ""))
        self.texto_cirugias_previas.insert("1.0", anamnesis.get("cirugias_previas", ""))
        self.texto_hospitalizaciones.insert("1.0", anamnesis.get("hospitalizaciones", ""))
        self.dieta_var.set(anamnesis.get("dieta", "General"))
        
        ginecologico = anamnesis.get("ginecologico", {})
        self.ginecologicos_menarquia_var.set(ginecologico.get("menarquia", ""))
        self.ginecologicos_ciclos_var.set(ginecologico.get("ciclos", ""))
        self.ginecologicos_fum_var.set(ginecologico.get("fum", ""))
        self.ginecologicos_gestas_var.set(ginecologico.get("gestas", ""))
        self.ginecologicos_partos_var.set(ginecologico.get("partos", ""))
        self.ginecologicos_abortos_var.set(ginecologico.get("abortos", ""))
        self.ginecologicos_cesareas_var.set(ginecologico.get("cesareas", ""))
        
        self.toggle_ginecologico() # Actualizar visibilidad

        # Signos vitales
        signos = paciente.get("signos_vitales", {})
        self.presion_sistolica_var.set(signos.get("sistolica", ""))
        self.presion_diastolica_var.set(signos.get("diastolica", ""))
        self.presion_clasificacion_var.set(signos.get("clasificacion_hta", ""))
        self.frecuencia_var.set(signos.get("frecuencia", ""))
        self.temperatura_var.set(signos.get("temperatura", ""))
        self.respiratoria_var.set(signos.get("respiratoria", ""))
        self.saturacion_var.set(signos.get("saturacion", ""))
        self.peso_var.set(signos.get("peso", ""))
        self.talla_var.set(signos.get("talla", ""))
        self.imc_var.set(signos.get("imc", ""))
        self.imc_clasificacion_var.set(signos.get("clasificacion_imc", ""))
        
        # Textos largos
        self.texto_examenes_lab.delete("1.0", tk.END)
        self.texto_examenes_lab.insert("1.0", paciente.get("examenes_lab", ""))
        
        self.texto_examenes_img.delete("1.0", tk.END)
        self.texto_examenes_img.insert("1.0", paciente.get("examenes_img", ""))
        
        if hasattr(self, 'texto_examenes_otros'):
            self.texto_examenes_otros.delete("1.0", tk.END)
            self.texto_examenes_otros.insert("1.0", paciente.get("examenes_otros", ""))
        
        # Examen Físico (Cargar detalle)
        self.limpiar_fisico()
        detalle_fisico = paciente.get("examen_fisico_detalle", {})
        if detalle_fisico:
            self.fisico_apariencia_var.set(detalle_fisico.get("apariencia", ""))
            self.fisico_piel_var.set(detalle_fisico.get("piel", ""))
            self.fisico_cabeza_var.set(detalle_fisico.get("cabeza", ""))
            self.fisico_cuello_var.set(detalle_fisico.get("cuello", ""))
            self.fisico_torax_var.set(detalle_fisico.get("torax", ""))
            self.fisico_abdomen_var.set(detalle_fisico.get("abdomen", ""))
            self.fisico_extremidades_var.set(detalle_fisico.get("extremidades", ""))
            self.fisico_genital_var.set(detalle_fisico.get("genital", ""))
            self.fisico_anoperineal_var.set(detalle_fisico.get("anoperineal", ""))
            self.fisico_otros_var.set(detalle_fisico.get("otros", ""))
        
        self.texto_diagnostico.delete("1.0", tk.END)
        self.texto_diagnostico.insert("1.0", paciente.get("diagnostico", ""))
        
        if hasattr(self, 'texto_tratamiento_pestana'):
            self.texto_tratamiento_pestana.delete("1.0", tk.END)
            self.texto_tratamiento_pestana.insert("1.0", paciente.get("tratamiento", ""))
        
        self.prox_consulta_var.set(paciente.get("proxima_consulta", ""))
        

        
        # Cargar lista de controles
        self.actualizar_lista_controles(paciente)
        self.nuevo_control() # Resetear formulario de control a estado "Nuevo"
    
    def actualizar_registro(self):
        """Actualiza el registro del paciente seleccionado"""
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Sin selección", "Seleccione un paciente para actualizar.")
            return
        
        # Obtener ID del paciente seleccionado
        item = self.tree.item(seleccion[0])
        paciente_id = int(item['values'][0])
        
        # Buscar paciente por ID
        paciente_index = -1
        for i, p in enumerate(self.pacientes):
            if p["id"] == paciente_id:
                paciente_index = i
                break
        
        if paciente_index == -1:
            messagebox.showerror("Error", "No se encontró el paciente seleccionado.")
            return
        
        # Validar campos obligatorios
        if not self.nombres_var.get() or not self.apellidos_var.get():
            messagebox.showwarning("Campos incompletos", "Debe ingresar al menos el nombre y apellido del paciente.")
            return
        
        # Actualizar datos del paciente
        self.pacientes[paciente_index] = {
            "id": paciente_id,
            "fecha": self.fecha_var.get(),
            "hora": self.hora_var.get(),
            "nombres": self.nombres_var.get(),
            "apellidos": self.apellidos_var.get(),
            "fecha_nacimiento": self.fecha_nac_var.get(),
            "edad": self.edad_var.get(),
            "sexo": self.sexo_var.get(),
            "cedula": self.cedula_var.get(),
            "telefono": self.telefono_var.get(),
            "direccion": self.direccion_var.get(),
            "ciudad": self.ciudad_var.get(),
            "pais": self.pais_var.get(),
            "estado_civil": self.estado_civil_var.get(),
            "instruccion": self.instruccion_var.get(),
            "motivo": self.entry_motivo_anamnesis.get(), # Guardar también en root para compatibilidad
            "anamnesis": {
                "tipo_consulta": self.consulta_tipo_var.get(),
                "motivo": self.entry_motivo_anamnesis.get(),
                "enfermedad_actual": self.texto_enfermedad_actual.get("1.0", tk.END).strip(),
                "ant_familiares": self.antecedentes_familiares_var.get(),
                "ant_personales": self.texto_ant_personales.get("1.0", tk.END).strip(),
                "alergias": self.texto_alergias.get("1.0", tk.END).strip(),
                "medicacion": self.texto_medicacion.get("1.0", tk.END).strip(),
                "cirugias_previas": self.texto_cirugias_previas.get("1.0", tk.END).strip(),
                "hospitalizaciones": self.texto_hospitalizaciones.get("1.0", tk.END).strip(),
                "dieta": self.dieta_var.get(),
                "ginecologico": {
                    "menarquia": self.ginecologicos_menarquia_var.get(),
                    "ciclos": self.ginecologicos_ciclos_var.get(),
                    "fum": self.ginecologicos_fum_var.get(),
                    "gestas": self.ginecologicos_gestas_var.get(),
                    "partos": self.ginecologicos_partos_var.get(),
                    "abortos": self.ginecologicos_abortos_var.get(),
                    "cesareas": self.ginecologicos_cesareas_var.get()
                }
            },
            "signos_vitales": {
                "presion": f"{self.presion_sistolica_var.get()}/{self.presion_diastolica_var.get()}",
                "sistolica": self.presion_sistolica_var.get(),
                "diastolica": self.presion_diastolica_var.get(),
                "clasificacion_hta": self.presion_clasificacion_var.get(),
                "frecuencia": self.frecuencia_var.get(),
                "temperatura": self.temperatura_var.get(),
                "respiratoria": self.respiratoria_var.get(),
                "saturacion": self.saturacion_var.get(),
                "peso": self.peso_var.get(),
                "talla": self.talla_var.get(),
                "imc": self.imc_var.get(),
                "clasificacion_imc": self.imc_clasificacion_var.get()
            },
            "examenes_lab": self.texto_examenes_lab.get("1.0", tk.END).strip(),
            "examenes_img": self.texto_examenes_img.get("1.0", tk.END).strip(),
            "examenes_otros": self.texto_examenes_otros.get("1.0", tk.END).strip() if hasattr(self, 'texto_examenes_otros') else "",
            
            # Examen físico detallado
            "examen_fisico_detalle": {
                "apariencia": self.fisico_apariencia_var.get(),
                "piel": self.fisico_piel_var.get(),
                "cabeza": self.fisico_cabeza_var.get(),
                "cuello": self.fisico_cuello_var.get(),
                "torax": self.fisico_torax_var.get(),
                "abdomen": self.fisico_abdomen_var.get(),
                "extremidades": self.fisico_extremidades_var.get(),
                "genital": self.fisico_genital_var.get(),
                "anoperineal": self.fisico_anoperineal_var.get(),
                "otros": self.fisico_otros_var.get()
            },
            "examen_fisico": "Detalle en ficha fisica",
            
            "diagnostico": self.texto_diagnostico.get("1.0", tk.END).strip(),
            "tratamiento": self.texto_tratamiento_pestana.get("1.0", tk.END).strip() if hasattr(self, 'texto_tratamiento_pestana') else "",
            "proxima_consulta": self.prox_consulta_var.get(),
            "cirugia": "",
            "control": self.pacientes[paciente_index].get('control', {}), # Mantener legacy por si acaso
            "controles": self.pacientes[paciente_index].get('controles', []) # Mantener nueva lista
        }
        
        # Guardar en archivo
        self.guardar_datos()
        
        # Actualizar lista
        self.actualizar_lista_pacientes()
        
        # Mostrar mensaje de confirmación
        messagebox.showinfo("Registro actualizado", 
                           f"Paciente {self.nombres_var.get()} {self.apellidos_var.get()} actualizado exitosamente.")
    
    def eliminar_registro(self):
        """Elimina el registro seleccionado"""
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Sin selección", "Seleccione un paciente para eliminar.")
            return
        
        # Confirmar eliminación
        if not messagebox.askyesno("Confirmar eliminación", "¿Está seguro de eliminar este registro?"):
            return
        
        # Obtener ID del paciente seleccionado
        item = self.tree.item(seleccion[0])
        paciente_id = int(item['values'][0])
        
        # Buscar y eliminar paciente
        paciente_eliminado = None
        for i, paciente in enumerate(self.pacientes):
            if paciente["id"] == paciente_id:
                paciente_eliminado = self.pacientes.pop(i)
                break
        
        if paciente_eliminado:
            # Reasignar IDs
            for i, paciente in enumerate(self.pacientes):
                paciente["id"] = i + 1
            
            # Guardar cambios
            self.guardar_datos()
            
            # Actualizar lista
            self.actualizar_lista_pacientes()
            
            # Actualizar ID en formulario
            self.id_var.set(str(len(self.pacientes) + 1))
            
            # Limpiar formulario
            self.limpiar_formulario_completo()
            
            messagebox.showinfo("Registro eliminado", 
                               f"Paciente {paciente_eliminado['nombres']} {paciente_eliminado['apellidos']} eliminado.")
            logging.info(f"Paciente eliminado: {paciente_eliminado['nombres']} {paciente_eliminado['apellidos']} (ID: {paciente_id})")
    
    def exportar_csv(self):
        """Exporta los datos a CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile="pacientes_exportados.csv"
            )
            
            if filename:
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    # Encabezados
                    writer.writerow(['ID', 'Fecha', 'Hora', 'Cédula', 'Nombres', 'Apellidos', 
                                   'Fecha Nacimiento', 'Edad', 'Sexo', 'Teléfono', 'Dirección', 
                                   'Ciudad', 'Motivo Consulta', 'Diagnóstico Principal'])
                    
                    # Datos
                    for paciente in self.pacientes:
                        writer.writerow([
                            paciente['id'],
                            paciente['fecha'],
                            paciente.get('hora', ''),
                            paciente.get('cedula', ''),
                            paciente['nombres'],
                            paciente['apellidos'],
                            paciente.get('fecha_nacimiento', ''),
                            paciente['edad'],
                            paciente['sexo'],
                            paciente.get('telefono', ''),
                            paciente.get('direccion', ''),
                            paciente.get('ciudad', ''),
                            paciente.get('motivo', '')[:100],
                            paciente.get('diagnostico', '')[:200]
                        ])
                
                messagebox.showinfo("Exportación Exitosa", 
                                   f"Datos exportados a:\n{filename}")
                logging.info(f"Datos exportados a CSV: {filename}")
                
        except Exception as e:
            messagebox.showerror("Error de Exportación", 
                                f"No se pudo exportar los datos: {str(e)}")
            logging.error(f"Error al exportar CSV: {str(e)}")
    
    def exportar_json(self):
        """Exporta todos los datos a un archivo JSON con interfaz de diálogo"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile="pacientes_exportados.json"
            )
            
            if filename:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(self.pacientes, f, ensure_ascii=False, indent=2)
                
                messagebox.showinfo("Exportación exitosa", 
                                   f"Todos los pacientes han sido exportados a:\n{filename}")
                logging.info(f"Datos exportados a JSON: {filename}")
                
        except Exception as e:
            messagebox.showerror("Error de exportación", 
                               f"No se pudo exportar los datos: {str(e)}")
            logging.error(f"Error al exportar JSON: {str(e)}")
    
    def mostrar_backup_dialog(self):
        """Muestra diálogo para crear backup"""
        if messagebox.askyesno("Crear Backup", "¿Desea crear un backup de los datos actuales?"):
            backup_file = self.crear_backup()
            if backup_file:
                messagebox.showinfo("Backup Creado", 
                                   f"Backup creado exitosamente:\n{backup_file}")
                logging.info(f"Usuario creó backup: {backup_file}")
            else:
                messagebox.showerror("Error", "No se pudo crear el backup")
    
    def verificar_proximas_consultas(self):
        """Verifica consultas próximas y muestra notificaciones"""
        try:
            hoy = datetime.now()
            consultas_proximas = []
            
            for paciente in self.pacientes:
                prox = paciente.get('proxima_consulta', '')
                if prox and self.validar_fecha(prox):
                    fecha_consulta = datetime.strptime(prox, "%d/%m/%Y")
                    dias_faltantes = (fecha_consulta - hoy).days
                    
                    if 0 <= dias_faltantes <= 7:  # Consultas en los próximos 7 días
                        consultas_proximas.append({
                            'paciente': f"{paciente['nombres']} {paciente['apellidos']}",
                            'fecha': prox,
                            'dias': dias_faltantes,
                            'motivo': paciente.get('motivo', '')[:50]
                        })
            
            if consultas_proximas:
                self.mostrar_recordatorio(consultas_proximas)
                return len(consultas_proximas)
            
            return 0
            
        except Exception as e:
            logging.error(f"Error al verificar próximas consultas: {str(e)}")
            return 0
    
    def mostrar_recordatorio(self, consultas):
        """Muestra recordatorio de consultas próximas"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Recordatorio - Próximas Consultas")
        ventana.geometry("600x400")
        ventana.configure(bg=self.color_fondo)
        
        # Frame principal
        frame = tk.Frame(ventana, bg=self.color_fondo, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        tk.Label(frame, text="⚠️ CONSULTAS PRÓXIMAS ⚠️", 
                font=("Arial", 16, "bold"), bg=self.color_fondo,
                fg="#e74c3c").pack(pady=(0, 20))
        
        # Frame para lista
        frame_lista = tk.Frame(frame, bg=self.color_fondo)
        frame_lista.pack(fill=tk.BOTH, expand=True)
        
        # Encabezados
        encabezados = ["Paciente", "Fecha Consulta", "Días", "Motivo"]
        for i, encabezado in enumerate(encabezados):
            tk.Label(frame_lista, text=encabezado, font=("Arial", 10, "bold"),
                    bg=self.color_principal, fg="white", padx=10, pady=5).grid(
                    row=0, column=i, sticky="ew", padx=1, pady=1)
        
        # Datos
        for i, consulta in enumerate(consultas, 1):
            # Determinar color según días faltantes
            if consulta['dias'] <= 1:
                bg_color = "#ffcccc"
            elif consulta['dias'] <= 3:
                bg_color = "#ffebcc"
            else:
                bg_color = "#e8f4f8"
            
            tk.Label(frame_lista, text=consulta['paciente'], 
                    bg=bg_color, padx=10, pady=5).grid(
                    row=i, column=0, sticky="ew", padx=1, pady=1)
            tk.Label(frame_lista, text=consulta['fecha'], 
                    bg=bg_color, padx=10, pady=5).grid(
                    row=i, column=1, sticky="ew", padx=1, pady=1)
            tk.Label(frame_lista, text=str(consulta['dias']), 
                    bg=bg_color, padx=10, pady=5).grid(
                    row=i, column=2, sticky="ew", padx=1, pady=1)
            tk.Label(frame_lista, text=consulta['motivo'], 
                    bg=bg_color, padx=10, pady=5).grid(
                    row=i, column=3, sticky="ew", padx=1, pady=1)
        
        # Configurar pesos de columnas
        for i in range(4):
            frame_lista.grid_columnconfigure(i, weight=1)
        
        # Botones
        frame_botones = tk.Frame(frame, bg=self.color_fondo)
        frame_botones.pack(pady=20)
        
        btn_cerrar = tk.Button(frame_botones, text="Cerrar", 
                              command=ventana.destroy,
                              bg=self.color_secundario, fg="white",
                              padx=20, pady=5)
        btn_cerrar.pack()
    
    def imprimir_registro(self):
        """Prepara registro para impresión/visualización"""
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning("Sin selección", "Seleccione un paciente para imprimir.")
            return
        
        # Obtener datos del paciente seleccionado
        item = self.tree.item(seleccion[0])
        paciente_id = int(item['values'][0])
        
        # Buscar paciente
        paciente = None
        for p in self.pacientes:
            if p["id"] == paciente_id:
                paciente = p
                break
        
        if not paciente:
            return
        
        # Crear contenido para impresión
        contenido = self.generar_contenido_impresion(paciente)
        
        # Mostrar en ventana
        self.mostrar_ventana_impresion(contenido, paciente)
    
    def generar_contenido_impresion(self, paciente):
        """Genera contenido formateado para impresión"""
        try:
            contenido = f"""
{'='*60}
            REGISTRO MÉDICO - CONSULTA EXTERNA
{'='*60}

DATOS DEL PACIENTE:
{'='*60}
ID: {paciente['id']}
Fecha: {paciente['fecha']} | Hora: {paciente.get('hora', 'N/A')}
Cédula: {paciente.get('cedula', 'N/A')}
Nombre: {paciente['nombres']} {paciente['apellidos']}
Fecha Nacimiento: {paciente.get('fecha_nacimiento', 'N/A')} | Edad: {paciente['edad']} años
Sexo: {paciente.get('sexo', 'N/A')} | Teléfono: {paciente.get('telefono', 'N/A')}
Dirección: {paciente.get('direccion', 'N/A')}
Ciudad: {paciente.get('ciudad', 'N/A')}
Motivo de Consulta: {paciente.get('motivo', 'N/A')}

SIGNOS VITALES:
{'='*60}
Presión Arterial: {paciente.get('signos_vitales', {}).get('presion', 'N/A')} mmHg
Frecuencia Cardíaca: {paciente.get('signos_vitales', {}).get('frecuencia', 'N/A')} lpm
Temperatura: {paciente.get('signos_vitales', {}).get('temperatura', 'N/A')} °C
Frecuencia Respiratoria: {paciente.get('signos_vitales', {}).get('respiratoria', 'N/A')} rpm
Saturación O2: {paciente.get('signos_vitales', {}).get('saturacion', 'N/A')} %
Peso: {paciente.get('signos_vitales', {}).get('peso', 'N/A')} kg
Talla: {paciente.get('signos_vitales', {}).get('talla', 'N/A')} cm
IMC: {paciente.get('signos_vitales', {}).get('imc', 'N/A')} ({paciente.get('signos_vitales', {}).get('clasificacion_imc', 'N/A')})

EXAMEN FÍSICO:
{'='*60}
{paciente.get('examen_fisico', 'N/A')}

DIAGNÓSTICO:
{'='*60}
{paciente.get('diagnostico', 'N/A')}

TRATAMIENTO:
{'='*60}
{paciente.get('tratamiento', 'N/A')}

EXÁMENES SOLICITADOS:
{'='*60}
Laboratorio:
{paciente.get('examenes_lab', 'N/A')}

Imagenología:
{paciente.get('examenes_img', 'N/A')}

Otros:
{paciente.get('examenes_otros', 'N/A')}

PLANIFICACIÓN:
{'='*60}
Próxima Consulta: {paciente.get('proxima_consulta', 'N/A')}

{paciente.get('cirugia', 'N/A')}

CONTROL DEL PACIENTE:
{'='*60}
Resultados: {paciente.get('control', {}).get('resultados', 'N/A')}
Evolución: {paciente.get('control', {}).get('evolucion', 'N/A')}
Tratamiento Adicional: {paciente.get('control', {}).get('tratamiento_adicional', 'N/A')}
Nuevos Exámenes: {paciente.get('control', {}).get('nuevos_examenes', 'N/A')}

{'='*60}
            FIN DEL REGISTRO
{'='*60}
Fecha de impresión: {datetime.now().strftime('%d/%m/%Y %H:%M')}
"""
            return contenido
        except Exception as e:
            logging.error(f"Error al generar contenido impresión: {str(e)}")
            return f"Error al generar contenido: {str(e)}"
    
    def mostrar_ventana_impresion(self, contenido, paciente):
        """Muestra ventana con contenido para impresión"""
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Impresión - {paciente['nombres']} {paciente['apellidos']}")
        ventana.geometry("700x600")
        
        # Frame principal
        frame = tk.Frame(ventana)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Área de texto
        texto = tk.Text(frame, wrap=tk.WORD, font=("Courier", 10))
        texto.pack(fill=tk.BOTH, expand=True)
        
        # Insertar contenido
        texto.insert("1.0", contenido)
        texto.config(state=tk.DISABLED)
        
        # Scrollbar
        scrollbar = tk.Scrollbar(frame, command=texto.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        texto.config(yscrollcommand=scrollbar.set)
        
        # Botones
        frame_botones = tk.Frame(ventana)
        frame_botones.pack(pady=10)
        
        btn_imprimir = tk.Button(frame_botones, text="Guardar como TXT",
                                command=lambda: self.guardar_como_txt(contenido, paciente),
                                bg=self.color_boton, fg="white",
                                padx=15, pady=5)
        btn_imprimir.pack(side=tk.LEFT, padx=5)
        
        btn_cerrar = tk.Button(frame_botones, text="Cerrar",
                              command=ventana.destroy,
                              bg="#95a5a6", fg="white",
                              padx=15, pady=5)
        btn_cerrar.pack(side=tk.LEFT, padx=5)
    
    def guardar_como_txt(self, contenido, paciente):
        """Guarda el contenido como archivo TXT"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"registro_{paciente['id']}_{paciente['apellidos']}.txt"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(contenido)
                
                messagebox.showinfo("Guardado", f"Archivo guardado:\n{filename}")
                logging.info(f"Registro guardado como TXT: {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {str(e)}")
            logging.error(f"Error al guardar TXT: {str(e)}")
    
    def mostrar_ayuda(self):
        """Muestra ventana de ayuda"""
        ayuda_texto = """
MANUAL RÁPIDO DEL SISTEMA
=========================

FUNCIONALIDADES PRINCIPALES:
1. REGISTRO DE PACIENTES:
   • Complete todas las pestañas con la información del paciente
   • Use Ctrl+S para guardar rápidamente
   • Los campos con (*) son obligatorios

2. NUEVOS CAMPOS:
   • Cédula: 10 dígitos (opcional)
   • Teléfono: 10 dígitos (opcional)
   • Motivo de consulta: Área de texto ampliada

3. SIGNOS VITALES MEJORADOS:
   • Peso y temperatura aceptan decimales
   • Clasificación automática del IMC

4. EXÁMENES ADICIONALES:
   • Nueva sección para "Otros Exámenes"
   • Incluye Electrocardiograma, Espirometría, etc.

5. FICHA DE CONTROL:
   • Nueva pestaña para seguimiento del paciente
   • Resultados de exámenes
   • Evolución del paciente
   • Tratamiento adicional
   • Nuevos exámenes solicitados

6. ESTADÍSTICAS MENSUALES:
   • Resumen mensual de consultas
   • Número de pacientes atendidos
   • Distribución por sexo y edad
   • Diagnósticos más comunes

ATAJOS DE TECLADO:
• Ctrl+S: Guardar registro
• Ctrl+L: Limpiar formulario
• Ctrl+F: Buscar paciente
• Ctrl+E: Exportar a JSON
• Ctrl+Q: Salir del sistema
• F1: Mostrar esta ayuda
• F5: Actualizar lista de pacientes
• Delete: Eliminar registro seleccionado

CONSEJOS:
• Realice backups regularmente desde el menú Archivo
• Use la pestaña de Control para seguimiento de pacientes
• Genere estadísticas mensuales para análisis
• Exporte datos periódicamente para respaldo
"""
        
        ventana = tk.Toplevel(self.root)
        ventana.title("Ayuda del Sistema")
        ventana.geometry("600x500")
        
        frame = tk.Frame(ventana, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        texto = tk.Text(frame, wrap=tk.WORD, font=("Arial", 10))
        texto.pack(fill=tk.BOTH, expand=True)
        
        texto.insert("1.0", ayuda_texto)
        texto.config(state=tk.DISABLED)
        
        btn_cerrar = tk.Button(frame, text="Cerrar",
                              command=ventana.destroy,
                              bg=self.color_secundario, fg="white",
                              padx=20, pady=5)
        btn_cerrar.pack(pady=10)
    
    def mostrar_acerca_de(self):
        """Muestra información acerca del sistema"""
        acerca_de = """
SISTEMA DE REGISTRO DE PACIENTES
=================================

Versión: 2.1 (Mejoras Completas)
Desarrollado para: Consulta Externa
Fecha: 2024

MEJORAS IMPLEMENTADAS:
• Campos de cédula y teléfono (10 dígitos)
• Área de texto ampliada para motivo de consulta
• Signos vitales con decimales para peso y temperatura
• Clasificación automática del IMC
• Nueva sección para "Otros Exámenes" (incluye ECG)
• Examen físico sin texto preestablecido
• Diagnóstico y tratamiento sin texto preestablecido
• Planificación de cirugía sin texto preestablecido
• Nueva ficha de control del paciente
• Estadísticas mensuales completas

TECNOLOGÍAS UTILIZADAS:
• Python 3.x
• Tkinter para interfaz gráfica
• JSON para almacenamiento
• Logging para seguimiento

FUNCIONALIDADES CLAVE:
• Registro completo de pacientes
• Búsqueda por cédula, nombre o ID
• Exportación a JSON y CSV
• Sistema de backups automático
• Recordatorio de consultas próximas
• Estadísticas y reportes mensuales

LICENCIA:
Software de uso libre para instituciones de salud
"""
        
        ventana = tk.Toplevel(self.root)
        ventana.title("Acerca del Sistema")
        ventana.geometry("500x450")
        
        frame = tk.Frame(ventana, padx=20, pady=20, bg=self.color_fondo)
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame, text="Acerca del Sistema", 
                font=("Arial", 16, "bold"), bg=self.color_fondo).pack(pady=(0, 20))
        
        texto = tk.Text(frame, wrap=tk.WORD, font=("Arial", 10), 
                       height=15, width=50, bg="#f8f9fa")
        texto.pack(fill=tk.BOTH, expand=True)
        
        texto.insert("1.0", acerca_de)
        texto.config(state=tk.DISABLED)
        
        btn_cerrar = tk.Button(frame, text="Cerrar",
                              command=ventana.destroy,
                              bg=self.color_secundario, fg="white",
                              padx=20, pady=5)
        btn_cerrar.pack(pady=10)
    
    def copiar_seleccionado(self):
        """Copia el paciente seleccionado al portapapeles"""
        seleccion = self.tree.selection()
        if seleccion:
            item = self.tree.item(seleccion[0])
            paciente_id = int(item['values'][0])
            
            for paciente in self.pacientes:
                if paciente["id"] == paciente_id:
                    # Formatear datos para copiar
                    datos = f"Paciente: {paciente['nombres']} {paciente['apellidos']}\n"
                    datos += f"ID: {paciente['id']} | Cédula: {paciente.get('cedula', 'N/A')}\n"
                    datos += f"Fecha: {paciente['fecha']}\n"
                    datos += f"Diagnóstico: {paciente.get('diagnostico', '')[:100]}"
                    
                    self.root.clipboard_clear()
                    self.root.clipboard_append(datos)
                    messagebox.showinfo("Copiado", "Datos del paciente copiados al portapapeles.")
                    break
    
    def guardar_datos(self):
        """Guarda los datos en un archivo JSON con manejo de errores"""
        try:
            # Crear backup antes de guardar
            backup_file = self.crear_backup()
            
            with open("pacientes.json", "w", encoding="utf-8") as f:
                json.dump(self.pacientes, f, ensure_ascii=False, indent=2)
            
            logging.info(f"Datos guardados exitosamente. Backup: {backup_file}")
        except Exception as e:
            logging.error(f"Error al guardar datos: {e}")
            messagebox.showerror("Error de guardado", 
                               f"No se pudieron guardar los datos: {str(e)}")
    
    def cargar_datos(self):
        """Carga los datos desde la base de datos SQL"""
        try:
            self.pacientes = self.db.get_all_patients()
            logging.info(f"Datos cargados exitosamente de la BD. {len(self.pacientes)} pacientes encontrados.")
        except Exception as e:
            logging.error(f"Error al cargar datos de BD: {e}")
            messagebox.showerror("Error de carga", 
                               f"No se pudieron cargar los datos: {str(e)}")
            self.pacientes = []
    def configurar_pestana_fisico_v2(self):
        """Configura la pestaña de examen físico (Versión 2 Desglosada)"""
        # Frame con scrollbar
        canvas_fisico = tk.Canvas(self.pestana_fisico, bg=self.color_fondo, highlightthickness=0)
        scrollbar_fisico = ttk.Scrollbar(self.pestana_fisico, orient=tk.VERTICAL, command=canvas_fisico.yview)
        frame_fisico_scroll = tk.Frame(canvas_fisico, bg=self.color_fondo)
        
        frame_fisico_scroll.bind(
            "<Configure>",
            lambda e: canvas_fisico.configure(scrollregion=canvas_fisico.bbox("all"))
        )
        
        window_id = canvas_fisico.create_window((0, 0), window=frame_fisico_scroll, anchor="nw")
        canvas_fisico.bind("<Configure>", lambda e: canvas_fisico.itemconfig(window_id, width=e.width))
        canvas_fisico.configure(yscrollcommand=scrollbar_fisico.set)
        
        canvas_fisico.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_fisico.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido de la pestaña (Modernizado con estilo de tarjeta blanca)
        frame_contenido = tk.LabelFrame(frame_fisico_scroll, 
                                      text=" EXAMEN FÍSICO REGIONAL ",
                                      font=("Segoe UI", 11, "bold"),
                                      fg=self.color_principal,
                                      bg="white",
                                      padx=20, pady=20,
                                      relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_contenido.pack(expand=True, fill="both", padx=20, pady=20)
        
        campos_fisicos = [
            ("Apariencia General", "fisico_apariencia_var"),
            ("Piel y Tegumentos", "fisico_piel_var"),
            ("Cabeza", "fisico_cabeza_var"),
            ("Cuello", "fisico_cuello_var"),
            ("Tórax (Corazón/Pulmones)", "fisico_torax_var"),
            ("Abdomen", "fisico_abdomen_var"),
            ("Extremidades", "fisico_extremidades_var"),
            ("Región Inguino Genital", "fisico_genital_var"),
            ("Región Anoperineal", "fisico_anoperineal_var"),
            ("Otros", "fisico_otros_var")
        ]
        
        for i, (label, var_name) in enumerate(campos_fisicos):
            # Calculate row and column indices for 2-column layout
            # Even index: Left column (0, 1)
            # Odd index: Right column (2, 3)
            row = i // 2
            col_label = 0 if i % 2 == 0 else 2
            col_text = 1 if i % 2 == 0 else 3
            
            tk.Label(frame_contenido, text=f"{label}:", bg="white", 
                    font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=row, column=col_label, sticky="nw", padx=5, pady=5)
            
            # Reduced width to 40 (approx half of 80)
            text_widget = tk.Text(frame_contenido, height=4, width=40, font=("Segoe UI", 10), bd=1, relief="solid", bg="#f8fafc")
            text_widget.grid(row=row, column=col_text, padx=5, pady=5, sticky="nsew")
            
            # Bind retrieval from var
            current_val = getattr(self, var_name).get()
            text_widget.insert("1.0", current_val)
            
            # Bind update to var
            def update_var(event, v=getattr(self, var_name), t=text_widget):
                v.set(t.get("1.0", "end-1c"))
                
            text_widget.bind("<KeyRelease>", update_var)
            
            # Configure row weight for vertical expansion
            # Only need to configure once per row (when handling even items)
            if i % 2 == 0:
                frame_contenido.grid_rowconfigure(row, weight=1)
                
        # Botón para limpiar examen físico
        final_row = (len(campos_fisicos) + 1) // 2
        btn_limpiar = tk.Button(frame_contenido, text="Limpiar Examen Físico",
                                command=self.limpiar_fisico,
                                bg="#94a3b8", fg="white", font=("Segoe UI", 9, "bold"),
                                relief="flat", cursor="hand2", padx=20, pady=8)
        btn_limpiar.grid(row=final_row, column=0, columnspan=4, pady=20)
        
        # Configure columns for equal weight
        frame_contenido.grid_columnconfigure(1, weight=1)
        frame_contenido.grid_columnconfigure(3, weight=1)
            


    def limpiar_fisico(self):
        """Limpia los campos del examen físico"""
        vars_fisico = [
            "fisico_apariencia_var", "fisico_piel_var", "fisico_cabeza_var",
            "fisico_cuello_var", "fisico_torax_var", "fisico_abdomen_var",
            "fisico_extremidades_var", "fisico_genital_var", "fisico_anoperineal_var",
            "fisico_otros_var"
        ]
        for var_name in vars_fisico:
            getattr(self, var_name).set("")

    def configurar_pestana_diagnostico_v2(self):
        """Configura la pestaña de diagnóstico (Versión 2 Solo Diagnóstico)"""
        # Frame con scrollbar
        canvas_diag = tk.Canvas(self.pestana_diagnostico, bg=self.color_fondo, highlightthickness=0)
        scrollbar_diag = ttk.Scrollbar(self.pestana_diagnostico, orient=tk.VERTICAL, command=canvas_diag.yview)
        frame_diag_scroll = tk.Frame(canvas_diag, bg=self.color_fondo)
        
        frame_diag_scroll.bind(
            "<Configure>",
            lambda e: canvas_diag.configure(scrollregion=canvas_diag.bbox("all"))
        )
        
        window_id = canvas_diag.create_window((0, 0), window=frame_diag_scroll, anchor="nw")
        canvas_diag.bind("<Configure>", lambda e: canvas_diag.itemconfig(window_id, width=e.width))
        canvas_diag.configure(yscrollcommand=scrollbar_diag.set)
        
        canvas_diag.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_diag.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido de la pestaña (Modernizado con estilo de tarjeta blanca)
        frame_contenido = tk.LabelFrame(frame_diag_scroll, 
                                      text=" DIAGNÓSTICO (CIE-10) ",
                                      font=("Segoe UI", 11, "bold"),
                                      fg=self.color_principal,
                                      bg="white",
                                      padx=20, pady=20,
                                      relief="flat", highlightthickness=1, highlightbackground="#e2e8f0")
        frame_contenido.pack(expand=True, fill="both", padx=20, pady=20)
        
        # CIE-10 Selector
        tk.Label(frame_contenido, text="Seleccionar CIE-10 (Comunes):", 
                bg="white", font=("Segoe UI", 10, "bold"), fg="#64748b").grid(row=0, column=0, sticky="w", padx=5, pady=5)
                
        self.cie10_var = tk.StringVar()
        combo_cie10 = ttk.Combobox(frame_contenido, textvariable=self.cie10_var, 
                                  values=self.cie10_data, state="normal", width=80)
        combo_cie10.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        def agregar_cie10(event=None):
            cie = self.cie10_var.get()
            if cie:
                texto_actual = self.texto_diagnostico.get("1.0", tk.END).strip()
                nuevo_texto = f"• {cie}"
                if texto_actual:
                    self.texto_diagnostico.insert(tk.END, "\n" + nuevo_texto)
                else:
                    self.texto_diagnostico.insert("1.0", nuevo_texto)
                self.cie10_var.set("") # Limpiar selección
        
        def filtrar_cie10(event):
            valor = self.cie10_var.get().upper()
            if valor == "":
                combo_cie10["values"] = self.cie10_data
            else:
                filtrados = [x for x in self.cie10_data if valor in x.upper()]
                combo_cie10["values"] = filtrados
            combo_cie10.event_generate('<Down>')

        combo_cie10.bind("<KeyRelease>", filtrar_cie10)
        combo_cie10.bind("<<ComboboxSelected>>", agregar_cie10)
        
        # Diagnóstico Texto
        tk.Label(frame_contenido, text="Diagnóstico Detallado:", 
                bg=self.color_fondo, font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="nw", padx=5, pady=10)
        
        self.texto_diagnostico = tk.Text(frame_contenido, height=15, width=80, font=("Arial", 10))
        self.texto_diagnostico.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        
        # Scrollbar para diagnóstico
        scrollbar_diag_texto = tk.Scrollbar(frame_contenido, command=self.texto_diagnostico.yview)
        scrollbar_diag_texto.grid(row=2, column=2, sticky="ns")
        self.texto_diagnostico.config(yscrollcommand=scrollbar_diag_texto.set)
        
        # Botón para limpiar
        btn_limpiar_diag = tk.Button(frame_contenido, text="Limpiar Diagnóstico",
                                    command=lambda: self.texto_diagnostico.delete("1.0", tk.END),
                                    bg="#95a5a6", fg="white",
                                    font=("Arial", 10),
                                    padx=15, pady=5)
        btn_limpiar_diag.grid(row=3, column=0, columnspan=3, pady=10)
        
        # Configurar expansión
        frame_contenido.grid_columnconfigure(1, weight=1)
        frame_contenido.grid_rowconfigure(2, weight=1)

    def configurar_pestana_tratamiento(self):
        """Configura la pestaña de tratamiento detallado"""
        # Frame con scrollbar
        canvas_trat = tk.Canvas(self.pestana_tratamiento, bg=self.color_fondo, highlightthickness=0)
        scrollbar_trat = ttk.Scrollbar(self.pestana_tratamiento, orient=tk.VERTICAL, command=canvas_trat.yview)
        frame_trat_scroll = tk.Frame(canvas_trat, bg=self.color_fondo)
        
        frame_trat_scroll.bind(
            "<Configure>",
            lambda e: canvas_trat.configure(scrollregion=canvas_trat.bbox("all"))
        )
        
        window_id = canvas_trat.create_window((0, 0), window=frame_trat_scroll, anchor="nw")
        canvas_trat.bind("<Configure>", lambda e: canvas_trat.itemconfig(window_id, width=e.width))
        canvas_trat.configure(yscrollcommand=scrollbar_trat.set)
        
        canvas_trat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_trat.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Contenido
        frame_contenido = tk.LabelFrame(frame_trat_scroll, 
                                      text="Tratamiento e Indicaciones",
                                      font=("Arial", 12, "bold"),
                                      bg=self.color_fondo,
                                      padx=15, pady=15)
        frame_contenido.pack(expand=True, padx=10, pady=10)
        
        # Tipo Tratamiento
        tk.Label(frame_contenido, text="Tipo de Tratamiento:", 
                bg=self.color_fondo, font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        combo_tipo = ttk.Combobox(frame_contenido, textvariable=self.tratamiento_tipo_var, 
                                 values=["Farmacológico", "Terapéutico", "Quirúrgico", "Mixto"],
                                 state="readonly", width=30)
        combo_tipo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        combo_tipo.bind("<<ComboboxSelected>>", self.actualizar_opciones_tratamiento)
        
        # Frame Dinámico para opciones secundarias
        self.frame_opciones_tratamiento = tk.Frame(frame_contenido, bg=self.color_fondo)
        self.frame_opciones_tratamiento.grid(row=0, column=2, padx=10, pady=5, sticky="w")
        
        # Texto Detalle
        tk.Label(frame_contenido, text="Detalle del Tratamiento / Receta:", 
                bg=self.color_fondo, font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="nw", padx=5, pady=10)
        
        self.texto_tratamiento_pestana = tk.Text(frame_contenido, height=15, width=80, font=("Arial", 10))
        self.texto_tratamiento_pestana.grid(row=2, column=0, columnspan=3, padx=5, pady=5)
        
        # Scroll
        scrollbar_text = tk.Scrollbar(frame_contenido, command=self.texto_tratamiento_pestana.yview)
        scrollbar_text.grid(row=2, column=3, sticky="ns")
        self.texto_tratamiento_pestana.config(yscrollcommand=scrollbar_text.set)

    def actualizar_opciones_tratamiento(self, event=None):
        """Actualiza las opciones dinámicas según el tipo de tratamiento"""
        # Limpiar frame dinámico
        for widget in self.frame_opciones_tratamiento.winfo_children():
            widget.destroy()
            
        tipo = self.tratamiento_tipo_var.get()
        
        if tipo == "Farmacológico":
            tk.Label(self.frame_opciones_tratamiento, text="Grupo:", bg=self.color_fondo).pack(side=tk.LEFT, padx=2)
            combo = ttk.Combobox(self.frame_opciones_tratamiento, values=self.grupos_farmacologicos, 
                                state="readonly", width=25)
            combo.pack(side=tk.LEFT, padx=2)
            
            def agregar_grupo(event):
                val = combo.get()
                if val:
                    self.texto_tratamiento_pestana.insert(tk.END, f"• Grupo: {val}\n  - ")
                    
            combo.bind("<<ComboboxSelected>>", agregar_grupo)
            
        elif tipo == "Quirúrgico":
            tk.Label(self.frame_opciones_tratamiento, text="Cirugía:", bg=self.color_fondo).pack(side=tk.LEFT, padx=2)
            combo = ttk.Combobox(self.frame_opciones_tratamiento, values=self.cirugias_comunes, 
                                state="readonly", width=30)
            combo.pack(side=tk.LEFT, padx=2)
            
            def agregar_cirugia(event):
                val = combo.get()
                if val:
                    self.texto_tratamiento_pestana.insert(tk.END, f"• Procedimiento: {val}\n")
                    
            combo.bind("<<ComboboxSelected>>", agregar_cirugia)
        
        # Boton limpiar
        btn_limpiar = tk.Button(frame_contenido, text="Limpiar Tratamiento",
                               command=lambda: self.texto_tratamiento_pestana.delete("1.0", tk.END),
                               bg="#95a5a6", fg="white", font=("Arial", 10), padx=10)
        btn_limpiar.grid(row=3, column=0, columnspan=3, pady=10)
        
        frame_contenido.grid_columnconfigure(1, weight=1)
        frame_contenido.grid_rowconfigure(2, weight=1)

class LoginWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CINTERSYS MEDIRECORD")
        
        # Configurar icono
        try:
            if os.path.exists("favicon.ico"):
                self.root.iconbitmap("favicon.ico")
            elif os.path.exists("logo.jpg"):
                img = Image.open("logo.jpg")
                photo = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, photo)
                self.root._icon = photo # Mantener referencia
        except Exception as e:
            logging.error(f"Error al cargar el icono: {e}")

        # Configuración de ventana
        self.root.geometry("450x600")
        self.root.resizable(False, False)
        self.root.configure(bg="#f8fafc") # Slate 50
        
        # Inicializar Base de Datos
        self.db = DatabaseManager()
        self.db.migrate_from_json()
        
        self.usuario_logueado = None
        
        # Estilo principal (reutilizando tokens si se puede, pero para login usaremos específicos)
        # para que se vea premium
        
        # Contenedor centrado (Efecto Tarjeta)
        card = tk.Frame(self.root, bg="white", highlightthickness=1, highlightbackground="#e2e8f0")
        card.place(relx=0.5, rely=0.5, anchor="center", width=380, height=520)
        
        # Contenido de la tarjeta
        content = tk.Frame(card, bg="white")
        content.pack(expand=True, fill='both', padx=40, pady=20)
        
        # Logo
        try:
            logo_path = "logo.jpg" if os.path.exists("logo.jpg") else "logo.png"
            if os.path.exists(logo_path):
                pil_image = Image.open(logo_path)
                pil_image.thumbnail((200, 120))
                logo_img = ImageTk.PhotoImage(pil_image)
                logo_label = tk.Label(content, image=logo_img, bg="white")
                logo_label.image = logo_img 
                logo_label.pack(pady=(0, 20))
            else:
                tk.Label(content, text="CINTERSYS", font=("Arial", 24, "bold"), fg="#6366f1", bg="white").pack(pady=(0, 20))
        except Exception as e:
            logging.error(f"Error loading logo in login: {e}")
        
        tk.Label(content, text="Bienvenido", 
                font=("Segoe UI", 22, "bold"), fg="#1e293b", bg="white").pack(pady=(0, 5))
        
        tk.Label(content, text="Inicie sesión para continuar", 
                font=("Segoe UI", 10), fg="#64748b", bg="white").pack(pady=(0, 20))
        
        # Campos de entrada
        field_font = ("Segoe UI", 10)
        
        # Usuario
        tk.Label(content, text="Usuario", font=("Segoe UI", 9, "bold"), 
                fg="#475569", bg="white").pack(fill='x', pady=(0, 5))
        self.user_var = tk.StringVar()
        entry_user = tk.Entry(content, textvariable=self.user_var, font=field_font,
                             bd=1, relief="solid", bg="#f8fafc", highlightthickness=0)
        entry_user.pack(fill='x', pady=(0, 15), ipady=8)
        
        # Contraseña
        tk.Label(content, text="Contraseña", font=("Segoe UI", 9, "bold"), 
                fg="#475569", bg="white").pack(fill='x', pady=(0, 5))
        self.pass_var = tk.StringVar()
        entry_pass = tk.Entry(content, textvariable=self.pass_var, show="*", font=field_font,
                             bd=1, relief="solid", bg="#f8fafc", highlightthickness=0)
        entry_pass.pack(fill='x', pady=(0, 20), ipady=8)
        
        # Botón Ingresar (Estilo Moderno)
        btn_login = tk.Button(content, text="Iniciar Sesión", command=self.login, 
                              bg="#6366f1", fg="white", font=("Segoe UI", 11, "bold"), 
                              relief="flat", cursor="hand2", pady=12, activebackground="#4f46e5", activeforeground="white")
        btn_login.pack(fill='x', pady=5)
                 
        # Footer
        footer = tk.Frame(content, bg="white")
        footer.pack(fill='x', side=tk.BOTTOM)
        
        tk.Button(footer, text="Registrar Usuario", command=self.registrar,
                 bg="white", fg="#6366f1", font=("Segoe UI", 9, "bold"), 
                 bd=0, cursor="hand2").pack(side=tk.LEFT)
        
        tk.Button(footer, text="Salir", command=self.root.destroy,
                 bg="white", fg="#ef4444", font=("Segoe UI", 9, "bold"), 
                 bd=0, cursor="hand2").pack(side=tk.RIGHT)
        
        self.center_window()
        
    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
    def login(self):
        user = self.user_var.get()
        password = self.pass_var.get()
        
        if self.db.verify_user(user, password):
            self.usuario_logueado = user
            self.root.destroy()
        else:
            # Fallback for first run if DB is empty and no json, but migrate handles it.
            # verify_user handles check.
            messagebox.showerror("Error", "Usuario o contraseña incorrectos")
            
    def registrar(self):
        user = self.user_var.get()
        password = self.pass_var.get()
        
        if not user or not password:
            messagebox.showwarning("Atención", "Ingrese usuario y contraseña para registrar")
            return
            
        # Intentar agregar, si falla es porque existe (username UNIQUE)
        # Verify existence first? verify_user checks pass...
        # Let's clean up: add_user handles uniqueness internally (INSERT OR IGNORE) 
        # but we want to tell user if it failed.
        # Check manually if user exists is harder without specific method exposed.
        # But verify_user needs pass.
        # We can implement user_exists in db manager or just try to verify ANY password.
        # For simplicity, let's trust add_user or update DBManager.
        
        # Let's verify existence by "verify_user" logic? No.
        # I'll rely on add_user silently ignoring if exists, but I want to show error.
        
        try:
             # Check if we can fetch
             with self.db.get_connection() as conn:
                 cursor = conn.cursor()
                 cursor.execute("SELECT 1 FROM usuarios WHERE username=?", (user,))
                 if cursor.fetchone():
                     messagebox.showerror("Error", "El usuario ya existe")
                     return
             
             self.db.add_user(user, password)
             messagebox.showinfo("Éxito", "Usuario registrado correctamente")
             
        except Exception as e:
             messagebox.showerror("Error", f"No se pudo registrar: {e}")



def main():
    """Función principal"""
    # 1. Login
    login_app = LoginWindow()
    login_app.root.mainloop()
    
    # Si el login fue exitoso (usuario_logueado no es None)
    # Si el login fue exitoso (usuario_logueado no es None)
    if login_app.usuario_logueado:
        try:
            root = tk.Tk()
            app = SistemaRegistroPacientes(root)
            
            # Configurar para cerrar correctamente
            def on_closing():
                if messagebox.askokcancel("Salir", "¿Está seguro de salir del sistema?"):
                    logging.info("Sistema cerrado por el usuario")
                    root.destroy()
            
            root.protocol("WM_DELETE_WINDOW", on_closing)
            root.mainloop()
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            logging.error(f"Error fatal al iniciar aplicación principal: {error_msg}")
            # Si root existe, usarlo messagebox, sino crear uno temporal
            try:
                messagebox.showerror("Error Fatal", f"Error al iniciar el sistema:\n{e}\n\nVer log para detalles.")
            except:
                pass
            print(error_msg)

if __name__ == "__main__":
    main()