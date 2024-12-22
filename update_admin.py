from app import app, db, User
from werkzeug.security import generate_password_hash

def update_admin():
    with app.app_context():
        # Update admin user permissions
        user = User.query.filter_by(username='admin').first()
        if user:
            user.is_admin = True
            db.session.commit()
            print('Updated admin user permissions')
        else:
            # Create admin user if not exists
            admin = User(
                username='admin',
                password=generate_password_hash('admin'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print('Created admin user')

if __name__ == '__main__':
    update_admin()
