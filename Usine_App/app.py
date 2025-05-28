from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models.user_model import User
from db import get_connection

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
                flash('Rôle utilisateur non reconnu.')
        else:
            flash('Identifiants invalides ou rôle incorrect.')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash("Accès refusé.")
        return redirect(url_for('login'))
    return "Tableau de bord Admin"

@app.route('/livreur/dashboard')
@login_required
def livreur_dashboard():
    if current_user.role != 'livreur':
        flash("Accès refusé.")
        return redirect(url_for('login'))
    return "Tableau de bord Livreur"

if __name__ == '__main__':
    app.run(debug=True)
