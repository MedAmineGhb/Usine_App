from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models.user_model import User
from db import get_connection
import pandas as pd
import io

app = Flask(__name__)
app.secret_key = '123123123123'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return User(user['id'], user['login'], user['password'], user['role'])
    return None

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_form = request.form['username']
        password_form = request.form['password']
        role_form = request.form['role']

        user = User.get_by_username_and_role(login_form, role_form)
        if user and user.check_password(password_form):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'livreur':
                return redirect(url_for('livreur_dashboard'))
            else:
                flash('Incorrect role')
        else:
            flash('Invalid credentials or incorrect role.')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM clients")
    total_clients = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'livreur'")
    total_delivery_persons = cursor.fetchone()['total']

    cursor.execute("""
        SELECT c.id, c.nom, c.prenom, c.adresse, c.telephone, u.login AS delivery_person_name
        FROM clients c
        LEFT JOIN users u ON c.livreur_id = u.id
    """)
    rows = cursor.fetchall()

    clients = []
    for row in rows:
        clients.append({
            'id': row['id'],
            'last_name': row['nom'],
            'first_name': row['prenom'],
            'address': row['adresse'],
            'phone': row['telephone'],
            'delivery_person_name': row['delivery_person_name'] if row['delivery_person_name'] else 'Unassigned'
        })

    conn.close()

    return render_template("admin_dashboard.html",
                           clients=clients,
                           total_clients=total_clients,
                           total_delivery_persons=total_delivery_persons)

@app.route('/export_clients')
@login_required
def export_clients():
    if current_user.role != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.nom AS last_name, c.prenom AS first_name, c.adresse AS address,
               c.telephone AS phone, u.login AS delivery_person_name
        FROM clients c
        LEFT JOIN users u ON c.livreur_id = u.id
    """)
    rows = cursor.fetchall()
    conn.close()

    
    df = pd.DataFrame(rows)
    df.rename(columns={
        'last_name': 'Last Name',
        'first_name': 'First Name',
        'address': 'Address',
        'phone': 'Phone',
        'delivery_person_name': 'Assigned Delivery Person'
    }, inplace=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Clients')
    output.seek(0)

    return send_file(output,
                     download_name="clients.xlsx",
                     as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/admin/modify_customer/<int:client_id>', methods=['GET', 'POST'])
@login_required
def modify_customer(client_id):
    if current_user.role != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        last_name = request.form.get('last_name')
        first_name = request.form.get('first_name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        delivery_person_id = request.form.get('delivery_person_id')

        if not all([last_name, first_name, address, phone]):
            flash("Please fill in all required fields.")
            return redirect(url_for('modify_customer', client_id=client_id))

        cursor.execute("""
            UPDATE clients
            SET nom = %s, prenom = %s, adresse = %s, telephone = %s, livreur_id = %s
            WHERE id = %s
        """, (last_name, first_name, address, phone, delivery_person_id, client_id))

        conn.commit()
        conn.close()

        flash("Client updated successfully!")
        return redirect(url_for('admin_dashboard'))

    cursor.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
    client = cursor.fetchone()

    cursor.execute("SELECT id, login FROM users WHERE role = 'livreur'")
    delivery_persons = cursor.fetchall()

    conn.close()

    if not client:
        flash("Client not found.")
        return redirect(url_for('admin_dashboard'))

    return render_template('modify_customer.html', client=client, delivery_persons=delivery_persons)


@app.route('/admin/delete_customer/<int:client_id>', methods=['POST'])
@login_required
def delete_customer(client_id):
    if current_user.role != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM clients WHERE id = %s", (client_id,))
    conn.commit()
    conn.close()

    flash("Client deleted successfully!")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/add_customer', methods=['GET', 'POST'])
@login_required
def add_customer():
    if current_user.role != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        last_name = request.form.get('last_name')
        first_name = request.form.get('first_name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        delivery_person_id = request.form.get('delivery_person_id')

        if not all([last_name, first_name, address, phone]):
            flash("Please fill in all required fields.")
            return redirect(url_for('add_customer'))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO clients (nom, prenom, adresse, telephone, livreur_id) 
            VALUES (%s, %s, %s, %s, %s)
        """, (last_name, first_name, address, phone, delivery_person_id))

        conn.commit()
        conn.close()

        flash("Customer added successfully!")
        return redirect(url_for('admin_dashboard'))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, login FROM users WHERE role = 'livreur'")
    delivery_persons = cursor.fetchall()
    conn.close()

    return render_template('add_customer.html', delivery_persons=delivery_persons)




@app.route('/livreur/dashboard')
@login_required
def livreur_dashboard():
    if current_user.role != 'livreur':
        flash("Access denied.")
        return redirect(url_for('login'))
    return "Delivery person dashboard"

if __name__ == '__main__':
    app.run(debug=True)
