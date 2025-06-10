from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models.user_model import User
from db import get_connection
import pandas as pd
import io
from datetime import datetime

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

@app.route('/admin/add_worker', methods=['GET', 'POST'])
@login_required
def add_worker():
    if current_user.role != 'admin':
        flash("Access denied.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        login = request.form.get('login')
        password = request.form.get('password')

        if not all([login, password]):
            flash("Please fill in all fields.")
            return redirect(url_for('add_worker'))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE login = %s", (login,))
        if cursor.fetchone():
            flash("This login already exists. Please choose another.")
            conn.close()
            return redirect(url_for('add_worker'))

        cursor.execute("SELECT MAX(id) AS max_id FROM users")
        max_id_row = cursor.fetchone()
        next_id = (max_id_row['max_id'] or 0) + 1

        cursor.execute("""
            INSERT INTO users (id, login, password, role)
            VALUES (%s, %s, %s, 'livreur')
        """, (next_id, login, password))

        conn.commit()
        conn.close()

        flash("Delivery worker added successfully!")
        return redirect(url_for('admin_dashboard'))

    return render_template('add_worker.html')

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
        SELECT c.id, c.nom, c.prenom, c.adresse, c.latitude, c.longitude, c.telephone, u.login AS delivery_person_name
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
            'latitude': row['latitude'],
            'longitude': row['longitude'],
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
               c.latitude, c.longitude, c.telephone AS phone, u.login AS delivery_person_name
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
        'latitude': 'Latitude',
        'longitude': 'Longitude',
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
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        phone = request.form.get('phone')
        delivery_person_id = request.form.get('delivery_person_id')

        if not all([last_name, first_name, address, phone]):
            flash("Please fill in all required fields.")
            return redirect(url_for('modify_customer', client_id=client_id))

        cursor.execute("""
            UPDATE clients
            SET nom = %s, prenom = %s, adresse = %s, latitude = %s, longitude = %s, telephone = %s, livreur_id = %s
            WHERE id = %s
        """, (last_name, first_name, address, latitude, longitude, phone, delivery_person_id, client_id))

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
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        phone = request.form.get('phone')
        delivery_person_id = request.form.get('delivery_person_id')

        if not all([last_name, first_name, address, phone]):
            flash("Please fill in all required fields.")
            return redirect(url_for('add_customer'))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO clients (nom, prenom, adresse, latitude, longitude, telephone, livreur_id) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (last_name, first_name, address, latitude, longitude, phone, delivery_person_id))

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
    
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nom, prenom, adresse, telephone
        FROM clients
        WHERE livreur_id = %s
    """, (current_user.id,))
    clients = cursor.fetchall()

    cursor.execute("""
        SELECT o.id, o.date_commande, o.produit, c.nom, c.prenom
        FROM orders o
        JOIN clients c ON o.client_id = c.id
        WHERE c.livreur_id = %s
        ORDER BY o.date_commande DESC
    """, (current_user.id,))
    orders = cursor.fetchall()

    conn.close()

    return render_template('livreur_dashboard.html', clients=clients, orders=orders)
@app.route('/livreur/add_client', methods=['GET', 'POST'])
@login_required
def add_client():
    if current_user.role != 'livreur':
        flash("Access denied.")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        nom = request.form.get('nom')
        prenom = request.form.get('prenom')
        adresse = request.form.get('adresse')
        telephone = request.form.get('telephone')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        if not all([nom, prenom, adresse, telephone]):
            flash("Please fill in all required fields.")
            return redirect(url_for('add_client'))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO clients (nom, prenom, adresse, telephone, latitude, longitude, livreur_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (nom, prenom, adresse, telephone, latitude, longitude, current_user.id))

        conn.commit()
        conn.close()

        flash("Client added successfully!")
        return redirect(url_for('livreur_dashboard'))

    return render_template('add_client.html')
@app.route('/livreur/add_order', methods=['GET', 'POST'])
@login_required
def add_order():
    if current_user.role != 'livreur':
        flash("Access denied.")
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor()
    # Get clients for the livreur to choose when creating order
    cursor.execute("SELECT id, nom, prenom FROM clients WHERE livreur_id = %s", (current_user.id,))
    clients = cursor.fetchall()

    if request.method == 'POST':
        produit = request.form.get('produit')
        client_id = request.form.get('client_id')

        if not produit or not client_id:
            flash("Please fill in all required fields.")
            return redirect(url_for('add_order'))

        # Validate client_id belongs to current livreur
        cursor.execute("SELECT id FROM clients WHERE id = %s AND livreur_id = %s", (client_id, current_user.id))
        if cursor.fetchone() is None:
            flash("Invalid client selected.")
            conn.close()
            return redirect(url_for('add_order'))

        cursor.execute("""
            INSERT INTO orders (produit, client_id)
            VALUES (%s, %s)
        """, (produit, client_id))

        conn.commit()
        conn.close()

        flash("Order added successfully!")
        return redirect(url_for('livreur_dashboard'))

    conn.close()
    return render_template('add_order.html', clients=clients)


if __name__ == "__main__":
    app.run(debug=True)
