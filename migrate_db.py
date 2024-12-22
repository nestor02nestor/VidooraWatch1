from app import db, app
from sqlalchemy import text

def migrate_database():
    with app.app_context():
        # Add new columns to Movie table if they don't exist
        with db.engine.connect() as conn:
            # Check if average_rating column exists
            result = conn.execute(text("PRAGMA table_info(movie)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'average_rating' not in columns:
                conn.execute(text("ALTER TABLE movie ADD COLUMN average_rating FLOAT DEFAULT 0.0"))
            
            if 'ratings_count' not in columns:
                conn.execute(text("ALTER TABLE movie ADD COLUMN ratings_count INTEGER DEFAULT 0"))
            
            # Create Rating table if it doesn't exist
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS rating (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rating INTEGER NOT NULL,
                    review TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER NOT NULL,
                    movie_id INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES user (id),
                    FOREIGN KEY (movie_id) REFERENCES movie (id)
                )
            """))
            
            # Create Watchlist table if it doesn't exist
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    movie_id INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user (id),
                    FOREIGN KEY (movie_id) REFERENCES movie (id),
                    UNIQUE(user_id, movie_id)
                )
            """))
            
            # إنشاء جدول الإشعارات
            conn.execute(text('''
            CREATE TABLE IF NOT EXISTS notification (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title VARCHAR(100) NOT NULL,
                message TEXT NOT NULL,
                link VARCHAR(200),
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user (id)
            )
            '''))
            
            # إضافة عمود is_admin إلى جدول user إذا لم يكن موجوداً
            try:
                conn.execute(text('''ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0'''))
                conn.commit()
                print("تم إضافة عمود is_admin بنجاح")
            except Exception as e:
                if 'duplicate column name' not in str(e):
                    print(f"خطأ في إضافة عمود is_admin: {e}")
            
            # تحديث المستخدم admin ليكون مسؤولاً
            conn.execute(text('''UPDATE user SET is_admin = 1 WHERE username = 'admin' '''))
            conn.commit()
            print("تم تحديث صلاحيات المستخدم admin")
            
            conn.commit()

if __name__ == '__main__':
    migrate_database()
    print("Database migration completed successfully!")
