from app import app, db, User
from sqlalchemy import text

def migrate():
    with app.app_context():
        # Add is_admin column
        try:
            db.session.execute(text('ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0'))
            db.session.commit()
            print("Added is_admin column")
        except Exception as e:
            print(f"Error adding column: {e}")
            db.session.rollback()
        
        # Update admin user
        try:
            db.session.execute(text("UPDATE user SET is_admin = 1 WHERE username = 'admin'"))
            db.session.commit()
            print("Updated admin privileges")
        except Exception as e:
            print(f"Error updating admin: {e}")
            db.session.rollback()

if __name__ == '__main__':
    migrate()
