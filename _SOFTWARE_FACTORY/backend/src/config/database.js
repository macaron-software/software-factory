const Database = require('better-sqlite3');
const path = require('path');
const bcrypt = require('bcryptjs');
const { v4: uuidv4 } = require('uuid');

const dbPath = path.join(__dirname, '..', 'database.sqlite');
const db = new Database(dbPath);

// Enable foreign keys
db.pragma('foreign_keys = ON');

// Create tables
db.exec(`
  -- Users table
  CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT CHECK(role IN ('patient', 'doctor', 'nurse', 'admin')) NOT NULL,
    firstName TEXT NOT NULL,
    lastName TEXT NOT NULL,
    phone TEXT,
    avatar TEXT,
    createdAt TEXT DEFAULT (datetime('now')),
    updatedAt TEXT DEFAULT (datetime('now'))
  );

  -- Patients table
  CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    userId TEXT UNIQUE NOT NULL,
    dateOfBirth TEXT,
    gender TEXT,
    chronicConditions TEXT DEFAULT '[]',
    emergencyContact TEXT,
    bloodType TEXT,
    assignedDoctorId TEXT,
    createdAt TEXT DEFAULT (datetime('now')),
    updatedAt TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (assignedDoctorId) REFERENCES users(id) ON DELETE SET NULL
  );

  -- Medical Records table
  CREATE TABLE IF NOT EXISTS medical_records (
    id TEXT PRIMARY KEY,
    patientId TEXT NOT NULL,
    doctorId TEXT NOT NULL,
    type TEXT CHECK(type IN ('consultation', 'vital-signs', 'lab-result', 'prescription')) NOT NULL,
    data TEXT DEFAULT '{}',
    notes TEXT,
    createdAt TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (patientId) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctorId) REFERENCES users(id) ON DELETE CASCADE
  );

  -- Appointments table
  CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    patientId TEXT NOT NULL,
    doctorId TEXT NOT NULL,
    scheduledAt TEXT NOT NULL,
    duration INTEGER DEFAULT 30,
    status TEXT CHECK(status IN ('scheduled', 'completed', 'cancelled', 'in-progress')) DEFAULT 'scheduled',
    type TEXT CHECK(type IN ('video', 'in-person', 'phone')) NOT NULL,
    notes TEXT,
    meetingUrl TEXT,
    createdAt TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (patientId) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (doctorId) REFERENCES users(id) ON DELETE CASCADE
  );

  -- Messages table
  CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    senderId TEXT NOT NULL,
    receiverId TEXT NOT NULL,
    content TEXT NOT NULL,
    readAt TEXT,
    createdAt TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (senderId) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (receiverId) REFERENCES users(id) ON DELETE CASCADE
  );

  -- Vital Signs table
  CREATE TABLE IF NOT EXISTS vital_signs (
    id TEXT PRIMARY KEY,
    patientId TEXT NOT NULL,
    type TEXT CHECK(type IN ('blood-pressure', 'heart-rate', 'blood-glucose', 'weight', 'temperature', 'oxygen-saturation')) NOT NULL,
    value TEXT NOT NULL,
    unit TEXT NOT NULL,
    recordedAt TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (patientId) REFERENCES patients(id) ON DELETE CASCADE
  );

  -- Create indexes
  CREATE INDEX IF NOT EXISTS idx_patients_user ON patients(userId);
  CREATE INDEX IF NOT EXISTS idx_patients_doctor ON patients(assignedDoctorId);
  CREATE INDEX IF NOT EXISTS idx_medical_records_patient ON medical_records(patientId);
  CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patientId);
  CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON appointments(doctorId);
  CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(senderId);
  CREATE INDEX IF NOT EXISTS idx_messages_receiver ON messages(receiverId);
  CREATE INDEX IF NOT EXISTS idx_vitals_patient ON vital_signs(patientId);
`);

// Seed data function
function seedDatabase() {
  const existingUsers = db.prepare('SELECT COUNT(*) as count FROM users').get();
  if (existingUsers.count > 0) {
    console.log('Database already seeded');
    return;
  }

  console.log('Seeding database...');

  // Create users
  const hashedPassword = bcrypt.hashSync('password123', 10);
  
  const doctorId = uuidv4();
  const nurseId = uuidv4();
  const patient1Id = uuidv4();
  const patient2Id = uuidv4();

  const insertUser = db.prepare(`
    INSERT INTO users (id, email, password, role, firstName, lastName, phone)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);

  insertUser.run(doctorId, 'dr.durand@chroniccare.com', hashedPassword, 'doctor', 'Jean', 'Durand', '+33 6 12 34 56 78');
  insertUser.run(nurseId, 'infirmiere.martin@chroniccare.com', hashedPassword, 'nurse', 'Marie', 'Martin', '+33 6 23 45 67 89');
  insertUser.run(patient1Id, 'jean.dupont@email.com', hashedPassword, 'patient', 'Jean', 'Dupont', '+33 6 34 56 78 90');
  insertUser.run(patient2Id, 'marce.leroy@email.com', hashedPassword, 'patient', 'Marcel', 'Leroy', '+33 6 45 67 89 01');

  // Create patients
  const insertPatient = db.prepare(`
    INSERT INTO patients (id, userId, dateOfBirth, gender, chronicConditions, emergencyContact, bloodType, assignedDoctorId)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);

  insertPatient.run(patient1Id, patient1Id, '1965-03-15', 'male', '["diabetes", "hypertension"]', '{"name": "Pierre Dupont", "phone": "+33 6 11 22 33 44"}', 'A+', doctorId);
  insertPatient.run(patient2Id, patient2Id, '1958-07-22', 'male', '["heart-failure", "hypertension"]', '{"name": "Annie Leroy", "phone": "+33 6 22 33 44 55"}', 'O-', doctorId);

  // Create appointments
  const insertAppointment = db.prepare(`
    INSERT INTO appointments (id, patientId, doctorId, scheduledAt, duration, status, type, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const nextWeek = new Date();
  nextWeek.setDate(nextWeek.getDate() + 7);

  insertAppointment.run(uuidv4(), patient1Id, doctorId, tomorrow.toISOString(), 30, 'scheduled', 'video', 'Suivi diabète');
  insertAppointment.run(uuidv4(), patient2Id, doctorId, nextWeek.toISOString(), 45, 'scheduled', 'in-person', 'Bilan cardiaque');

  // Create medical records
  const insertRecord = db.prepare(`
    INSERT INTO medical_records (id, patientId, doctorId, type, data, notes, createdAt)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);

  const lastWeek = new Date();
  lastWeek.setDate(lastWeek.getDate() - 7);

  insertRecord.run(uuidv4(), patient1Id, doctorId, 'consultation', '{"chiefComplaint": "Contrôle glycémique", "diagnosis": "Diabète type 2 stable"}', 'HbA1c: 7.2%', lastWeek.toISOString());
  insertRecord.run(uuidv4(), patient2Id, doctorId, 'prescription', '{"medications": [{"name": "Lisinopril", "dosage": "10mg", "frequency": "1x/jour"}]}', 'Renouvellement ordonnance', lastWeek.toISOString());

  // Create vital signs
  const insertVitals = db.prepare(`
    INSERT INTO vital_signs (id, patientId, type, value, unit, recordedAt)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);

  // Patient 1 vitals
  insertVitals.run(uuidv4(), patient1Id, 'blood-pressure', '{"systolic": 135, "diastolic": 85}', 'mmHg', yesterday.toISOString());
  insertVitals.run(uuidv4(), patient1Id, 'blood-glucose', '142', 'mg/dL', today.toISOString());
  insertVitals.run(uuidv4(), patient1Id, 'weight', '78.5', 'kg', yesterday.toISOString());

  // Patient 2 vitals
  insertVitals.run(uuidv4(), patient2Id, 'blood-pressure', '{"systolic": 145, "diastolic": 90}', 'mmHg', yesterday.toISOString());
  insertVitals.run(uuidv4(), patient2Id, 'heart-rate', '72', 'bpm', today.toISOString());
  insertVitals.run(uuidv4(), patient2Id, 'weight', '82.3', 'kg', yesterday.toISOString());

  // Create messages
  const insertMessage = db.prepare(`
    INSERT INTO messages (id, senderId, receiverId, content, readAt)
    VALUES (?, ?, ?, ?, ?)
  `);

  insertMessage.run(uuidv4(), patient1Id, doctorId, 'Bonjour Docteur, j\'ai oublié de prendre ma glycémie ce matin. Est-ce grave?', today.toISOString());
  insertMessage.run(uuidv4(), doctorId, patient1Id, 'Ce n\'est pas grave, faites-le dès que possible. Continuez votre traitement normalement.', null);

  console.log('Database seeded successfully!');
  console.log('Test accounts:');
  console.log('  Doctor: dr.durand@chroniccare.com / password123');
  console.log('  Patient: jean.dupont@email.com / password123');
}

module.exports = { db, seedDatabase };
