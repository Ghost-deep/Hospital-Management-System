# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from mysql.connector import Error
from db_config import db_config # Import config from db_config.py

app = Flask(__name__)
app.secret_key = 'your_very_secret_key' # Change this for production!

# --- Database Connection ---
def get_db_connection():
    """Establishes a connection to the database."""
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        # In a real app, you might want to handle this more gracefully
        # For now, return None or raise the exception
        return None

# --- Helper Function ---
def fetch_query(query, params=None):
    """Executes a SELECT query and returns all results."""
    conn = get_db_connection()
    if conn is None:
        return [] # Return empty list if connection failed
    cursor = conn.cursor(dictionary=True) # Get results as dictionaries
    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        return results
    except Error as e:
        print(f"Error executing query: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def execute_query(query, params=None):
    """Executes an INSERT, UPDATE, or DELETE query."""
    conn = get_db_connection()
    if conn is None:
        return False # Indicate failure
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        conn.commit() # Commit the transaction
        return True # Indicate success
    except Error as e:
        print(f"Error executing query: {e}")
        conn.rollback() # Rollback on error
        return False # Indicate failure
    finally:
        cursor.close()
        conn.close()

# --- Routes ---

# Home Page
@app.route('/')
def index():
    return render_template('index.html')

# --- Patient Routes ---
@app.route('/patients')
def list_patients():
    patients = fetch_query("SELECT PatientID, FirstName, LastName, DateOfBirth, Gender FROM Patients ORDER BY LastName, FirstName")
    return render_template('patients.html', patients=patients)

@app.route('/patients/add', methods=['GET', 'POST'])
def add_patient():
    if request.method == 'POST':
        # Get data from form
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        dob = request.form['dob']
        gender = request.form['gender']
        contact = request.form['contact']
        address = request.form['address']

        # Basic Validation (add more as needed)
        if not first_name or not last_name or not dob:
            flash('First Name, Last Name, and Date of Birth are required.', 'error')
            return render_template('add_patient.html') # Re-render form

        sql = """
            INSERT INTO Patients (FirstName, LastName, DateOfBirth, Gender, ContactNumber, Address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (first_name, last_name, dob, gender, contact, address)

        if execute_query(sql, params):
            flash('Patient added successfully!', 'success')
            return redirect(url_for('list_patients'))
        else:
            flash('Error adding patient.', 'error')
            # Optionally log the detailed error here
            return render_template('add_patient.html') # Re-render form on error

    # If GET request, just show the form
    return render_template('add_patient.html')

@app.route('/patients/<int:patient_id>')
def view_patient(patient_id):
    patient = fetch_query("SELECT * FROM Patients WHERE PatientID = %s", (patient_id,))
    if not patient:
        flash('Patient not found.', 'error')
        return redirect(url_for('list_patients'))

    # Fetch related data
    medical_history = fetch_query("SELECT * FROM MedicalHistory WHERE PatientID = %s ORDER BY DiagnosisDate DESC", (patient_id,))
    # Join TreatmentPlans with Doctors to get doctor's name
    treatment_plans = fetch_query("""
        SELECT tp.*, d.FirstName AS DoctorFirstName, d.LastName AS DoctorLastName
        FROM TreatmentPlans tp
        LEFT JOIN Doctors d ON tp.DoctorID = d.DoctorID
        WHERE tp.PatientID = %s ORDER BY TreatmentDate DESC
    """, (patient_id,))
    medical_records = fetch_query("SELECT * FROM MedicalRecords WHERE PatientID = %s ORDER BY RecordDate DESC", (patient_id,))
    billing = fetch_query("SELECT * FROM Billing WHERE PatientID = %s ORDER BY BillDate DESC", (patient_id,))
    doctors = fetch_query("SELECT DoctorID, FirstName, LastName FROM Doctors ORDER BY LastName, FirstName") # For Add Treatment Form


    return render_template('view_patient.html',
                           patient=patient[0],
                           medical_history=medical_history,
                           treatment_plans=treatment_plans,
                           medical_records=medical_records,
                           billing=billing,
                           doctors=doctors) # Pass doctors for the form

# --- Doctor Routes ---
@app.route('/doctors')
def list_doctors():
    doctors = fetch_query("SELECT DoctorID, FirstName, LastName, Specialization, ContactNumber FROM Doctors ORDER BY LastName, FirstName")
    return render_template('doctors.html', doctors=doctors)

@app.route('/doctors/add', methods=['GET', 'POST'])
def add_doctor():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        specialization = request.form['specialization']
        contact = request.form['contact']
        email = request.form['email']
        address = request.form['address']

        if not first_name or not last_name or not specialization:
            flash('First Name, Last Name, and Specialization are required.', 'error')
            return render_template('add_doctor.html')

        sql = """
            INSERT INTO Doctors (FirstName, LastName, Specialization, ContactNumber, Email, Address)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (first_name, last_name, specialization, contact, email, address)

        if execute_query(sql, params):
            flash('Doctor added successfully!', 'success')
            return redirect(url_for('list_doctors'))
        else:
            flash('Error adding doctor.', 'error')
            return render_template('add_doctor.html')

    return render_template('add_doctor.html')

@app.route('/doctors/<int:doctor_id>')
def view_doctor(doctor_id):
    """Displays details for a specific doctor."""
    # Fetch the doctor's main details
    doctor_details = fetch_query("SELECT * FROM Doctors WHERE DoctorID = %s", (doctor_id,))

    if not doctor_details:
        flash('Doctor not found.', 'error')
        return redirect(url_for('list_doctors'))

    # Fetch treatments provided by this doctor (joining with Patients for names)
    treatments_provided = fetch_query("""
        SELECT
            tp.TreatmentID,
            tp.TreatmentDate,
            tp.Diagnosis,
            tp.FollowUpDate,
            p.PatientID,
            p.FirstName AS PatientFirstName,
            p.LastName AS PatientLastName
        FROM TreatmentPlans tp
        JOIN Patients p ON tp.PatientID = p.PatientID
        WHERE tp.DoctorID = %s
        ORDER BY tp.TreatmentDate DESC
    """, (doctor_id,))

    return render_template(
        'view_doctor.html',
        doctor=doctor_details[0],
        treatments=treatments_provided
    )


# --- Routes to Add Related Patient Data (Example: Add Medical History) ---
@app.route('/patients/<int:patient_id>/history/add', methods=['POST'])
def add_medical_history(patient_id):
    # Check if patient exists (optional but good practice)
    patient = fetch_query("SELECT PatientID FROM Patients WHERE PatientID = %s", (patient_id,))
    if not patient:
        flash('Patient not found.', 'error')
        return redirect(url_for('list_patients'))

    # Get data from form (assuming form fields named 'diagnosis_date', 'diagnosis_details')
    diag_date = request.form.get('diagnosis_date')
    diag_details = request.form.get('diagnosis_details')

    if not diag_date or not diag_details:
        flash('Diagnosis Date and Details are required for Medical History.', 'error')
    else:
        sql = "INSERT INTO MedicalHistory (PatientID, DiagnosisDate, DiagnosisDetails) VALUES (%s, %s, %s)"
        params = (patient_id, diag_date, diag_details)
        if execute_query(sql, params):
            flash('Medical History added successfully.', 'success')
        else:
            flash('Error adding medical history.', 'error')

    # Redirect back to the patient detail page
    return redirect(url_for('view_patient', patient_id=patient_id))


# --- Route to Add Treatment Plan ---
@app.route('/patients/<int:patient_id>/treatment/add', methods=['POST'])
def add_treatment_plan(patient_id):
    # Check if patient exists
    patient = fetch_query("SELECT PatientID FROM Patients WHERE PatientID = %s", (patient_id,))
    if not patient:
        flash('Patient not found.', 'error')
        return redirect(url_for('list_patients'))

    # Get data from form
    doctor_id = request.form.get('doctor_id')
    treatment_date = request.form.get('treatment_date')
    diagnosis = request.form.get('diagnosis')
    treatment_details = request.form.get('treatment_details')
    follow_up_date = request.form.get('follow_up_date') # Can be NULL/empty

    if not doctor_id or not treatment_date or not diagnosis or not treatment_details:
        flash('Doctor, Treatment Date, Diagnosis, and Treatment Details are required.', 'error')
    else:
         # Handle potentially empty follow-up date
        follow_up_date_param = follow_up_date if follow_up_date else None

        sql = """
            INSERT INTO TreatmentPlans (PatientID, DoctorID, TreatmentDate, Diagnosis, TreatmentDetails, FollowUpDate)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (patient_id, doctor_id, treatment_date, diagnosis, treatment_details, follow_up_date_param)

        if execute_query(sql, params):
            flash('Treatment Plan added successfully.', 'success')
        else:
            flash('Error adding treatment plan.', 'error')

    return redirect(url_for('view_patient', patient_id=patient_id))

# --- Add Routes for Medical Records and Billing similarly ---
# (Left as an exercise - follow the pattern for Medical History/Treatment Plan)
@app.route('/patients/<int:patient_id>/record/add', methods=['POST'])
def add_medical_record(patient_id):
    # Check patient exists...
    record_type = request.form.get('record_type')
    record_date = request.form.get('record_date')
    description = request.form.get('description')

    if not record_type or not record_date or not description:
        flash('Record Type, Date, and Description are required.', 'error')
    else:
        sql = "INSERT INTO MedicalRecords (PatientID, RecordType, RecordDate, Description) VALUES (%s, %s, %s, %s)"
        params = (patient_id, record_type, record_date, description)
        if execute_query(sql, params):
            flash('Medical Record added.', 'success')
        else:
            flash('Error adding medical record.', 'error')

    return redirect(url_for('view_patient', patient_id=patient_id))


@app.route('/patients/<int:patient_id>/billing/add', methods=['POST'])
def add_billing(patient_id):
    # Check patient exists...
    bill_amount = request.form.get('bill_amount')
    bill_date = request.form.get('bill_date')

    if not bill_amount or not bill_date:
        flash('Bill Amount and Date are required.', 'error')
    else:
        try:
            # Attempt to convert amount to decimal for validation
            amount_decimal = float(bill_amount)
            sql = "INSERT INTO Billing (PatientID, BillAmount, BillDate) VALUES (%s, %s, %s)"
            params = (patient_id, amount_decimal, bill_date)
            if execute_query(sql, params):
                flash('Billing record added.', 'success')
            else:
                flash('Error adding billing record.', 'error')
        except ValueError:
            flash('Invalid Bill Amount.', 'error')

    return redirect(url_for('view_patient', patient_id=patient_id))


# --- Run the App ---
if __name__ == '__main__':
    app.run(debug=True) # debug=True for development, remove for production