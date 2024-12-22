from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import logging
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = os.path.join(app.root_path, 'movies.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Configure file upload
UPLOAD_FOLDER = os.path.join(app.root_path, 'static/uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    logger.info(f"Created uploads directory at {UPLOAD_FOLDER}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    watchlist = db.relationship('Movie', secondary='watchlist', backref=db.backref('watchers', lazy='dynamic'))
    notifications = db.relationship('Notification', backref='user', lazy=True, order_by='desc(Notification.created_at)')

class Watchlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'movie_id', name='unique_user_movie'),)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, default=0)
    movies = db.relationship('Movie', backref='category', lazy=True)

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(200), nullable=False)
    video_url = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    featured = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    release_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    average_rating = db.Column(db.Float, default=0.0)
    ratings_count = db.Column(db.Integer, default=0)
    ratings = db.relationship('Rating', backref='movie', lazy=True)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rating = db.Column(db.Integer, nullable=False)  # 1 to 5 stars
    review = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(200))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('عذراً، هذه الصفحة متاحة فقط للمشرفين.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    categories = Category.query.all()
    movies_by_category = {}
    for category in categories:
        movies = Movie.query.filter_by(category_id=category.id).all()
        if movies:  # فقط إضافة الأقسام التي تحتوي على أفلام
            movies_by_category[category] = movies
    
    return render_template('index.html', 
                         categories=categories,
                         movies_by_category=movies_by_category)

@app.route('/watch/<int:id>')
def watch(id):
    movie = Movie.query.get_or_404(id)
    categories = Category.query.all()  # للقائمة العلوية
    # احضار الأفلام المشابهة من نفس التصنيف
    related_movies = Movie.query.filter(Movie.category_id == movie.category_id, Movie.id != movie.id).limit(10).all()
    return render_template('watch.html', movie=movie, categories=categories, related_movies=related_movies)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('تم تسجيل الدخول بنجاح!', 'success')
            return redirect(url_for('index'))
        
        flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود بالفعل', 'error')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        
        flash('تم إنشاء الحساب بنجاح!', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    movies_count = Movie.query.count()
    categories_count = Category.query.count()
    users_count = User.query.count()
    return render_template('admin/dashboard.html', 
                         movies_count=movies_count,
                         categories_count=categories_count,
                         users_count=users_count)

@app.route('/admin/movies')
@login_required
@admin_required
def admin_movies():
    movies = Movie.query.all()
    return render_template('admin/movies.html', movies=movies)

@app.route('/admin/movies/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_movie():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category_id = request.form.get('category_id')
        video_url = request.form.get('video_url')
        
        # Handle image upload
        if 'image' in request.files:
            image = request.files['image']
            if image.filename != '':
                try:
                    filename = secure_filename(image.filename)
                    image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image_url = url_for('static', filename=f'uploads/{filename}')
                except:
                    flash('حدث خطأ أثناء رفع الصورة. يرجى المحاولة مرة أخرى.', 'error')
                    return redirect(url_for('add_movie'))
            else:
                image_url = request.form.get('image_url')
        else:
            image_url = request.form.get('image_url')
        
        movie = Movie(
            title=title,
            description=description,
            image_url=image_url,
            video_url=video_url,
            category_id=category_id
        )
        db.session.add(movie)
        db.session.commit()
        flash('تمت إضافة الفيلم بنجاح', 'success')
        return redirect(url_for('admin_movies'))
    
    categories = Category.query.all()
    return render_template('admin/add_movie.html', categories=categories)

@app.route('/admin/movies/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_movie(id):
    movie = Movie.query.get_or_404(id)
    if request.method == 'POST':
        movie.title = request.form.get('title')
        movie.description = request.form.get('description')
        movie.category_id = request.form.get('category_id')
        movie.video_url = request.form.get('video_url')
        
        # Handle image upload
        if 'image' in request.files:
            image = request.files['image']
            if image.filename != '':
                try:
                    # Delete old image if it exists in uploads folder
                    if 'uploads/' in movie.image_url:
                        old_image = movie.image_url.split('/')[-1]
                        old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], old_image)
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                    
                    # Save new image
                    filename = secure_filename(image.filename)
                    image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    movie.image_url = url_for('static', filename=f'uploads/{filename}')
                except:
                    flash('حدث خطأ أثناء رفع الصورة. يرجى المحاولة مرة أخرى.', 'error')
                    return redirect(url_for('edit_movie', id=id))
            else:
                movie.image_url = request.form.get('image_url')
        else:
            movie.image_url = request.form.get('image_url')
        
        db.session.commit()
        flash('تم تحديث الفيلم بنجاح', 'success')
        return redirect(url_for('admin_movies'))
    
    categories = Category.query.all()
    return render_template('admin/edit_movie.html', movie=movie, categories=categories)

@app.route('/admin/movies/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_movie(id):
    movie = Movie.query.get_or_404(id)
    db.session.delete(movie)
    db.session.commit()
    flash('تم حذف الفيلم بنجاح', 'success')
    return redirect(url_for('admin_movies'))

@app.route('/admin/categories')
@login_required
@admin_required
def admin_categories():
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/categories/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_category():
    if request.method == 'POST':
        name = request.form.get('name')
        category = Category(name=name)
        db.session.add(category)
        db.session.commit()
        flash('تمت إضافة القسم بنجاح', 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/add_category.html')

@app.route('/admin/categories/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_category(id):
    category = Category.query.get_or_404(id)
    if request.method == 'POST':
        category.name = request.form.get('name')
        db.session.commit()
        flash('تم تحديث القسم بنجاح', 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/edit_category.html', category=category)

@app.route('/admin/categories/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_category(id):
    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    flash('تم حذف القسم بنجاح', 'success')
    return redirect(url_for('admin_categories'))

@app.route('/category/<int:id>')
def category(id):
    category = Category.query.get_or_404(id)
    movies = Movie.query.filter_by(category_id=id).all()
    return render_template('category.html', category=category, movies=movies)

@app.route('/admin/update_order', methods=['POST'])
@login_required
@admin_required
def update_order():
    data = request.get_json()
    item_type = data.get('type')
    items = data.get('items', [])
    
    for index, item_id in enumerate(items):
        if item_type == 'category':
            item = Category.query.get(item_id)
        else:
            item = Movie.query.get(item_id)
        if item:
            item.order = index
    
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/admin/featured')
@login_required
@admin_required
def admin_featured():
    movies = Movie.query.all()
    return render_template('admin/featured.html', movies=movies)

@app.route('/admin/featured/<int:id>', methods=['POST'])
@login_required
@admin_required
def toggle_featured(id):
    movie = Movie.query.get_or_404(id)
    movie.featured = not movie.featured
    db.session.commit()
    return redirect(url_for('admin_featured'))

@app.route('/movie/<int:movie_id>/rate', methods=['POST'])
@login_required
def rate_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    rating_value = int(request.form.get('rating'))
    review_text = request.form.get('review')
    
    if not 1 <= rating_value <= 5:
        return jsonify({'error': 'Invalid rating value'}), 400
    
    # Check if user already rated this movie
    existing_rating = Rating.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
    
    if existing_rating:
        # Update existing rating
        old_rating = existing_rating.rating
        existing_rating.rating = rating_value
        existing_rating.review = review_text
        existing_rating.created_at = datetime.utcnow()
        
        # Update movie's average rating
        movie.average_rating = ((movie.average_rating * movie.ratings_count) - old_rating + rating_value) / movie.ratings_count
    else:
        # Create new rating
        new_rating = Rating(
            rating=rating_value,
            review=review_text,
            user_id=current_user.id,
            movie_id=movie_id
        )
        db.session.add(new_rating)
        movie.ratings_count += 1
        movie.average_rating = ((movie.average_rating * (movie.ratings_count - 1)) + rating_value) / movie.ratings_count
    
    db.session.commit()
    return jsonify({
        'average_rating': round(movie.average_rating, 1),
        'ratings_count': movie.ratings_count
    })

@app.route('/movie/<int:movie_id>/ratings')
def get_movie_ratings(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    ratings = Rating.query.filter_by(movie_id=movie_id).order_by(Rating.created_at.desc()).all()
    ratings_data = []
    
    for rating in ratings:
        user = User.query.get(rating.user_id)
        ratings_data.append({
            'username': user.username,
            'rating': rating.rating,
            'review': rating.review,
            'created_at': rating.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return jsonify(ratings_data)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    # البحث في عنوان الفيلم والوصف
    movies = Movie.query.filter(
        or_(
            Movie.title.ilike(f'%{query}%'),
            Movie.description.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    return jsonify([{
        'id': movie.id,
        'title': movie.title,
        'image_url': movie.image_url,
        'release_date': movie.release_date.strftime('%Y'),
        'category': {'name': movie.category.name}
    } for movie in movies])

@app.route('/watchlist')
@login_required
def user_watchlist():
    watchlist_movies = current_user.watchlist
    categories = Category.query.all()  # للقائمة العلوية
    return render_template('watchlist.html', movies=watchlist_movies, categories=categories)

@app.route('/watchlist/add/<int:movie_id>', methods=['POST'])
@login_required
def add_to_watchlist(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    if movie not in current_user.watchlist:
        watchlist_entry = Watchlist(user_id=current_user.id, movie_id=movie_id)
        db.session.add(watchlist_entry)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'تمت إضافة الفيلم إلى قائمة المشاهدة'})
    return jsonify({'status': 'error', 'message': 'الفيلم موجود بالفعل في قائمة المشاهدة'})

@app.route('/watchlist/remove/<int:movie_id>', methods=['POST'])
@login_required
def remove_from_watchlist(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    if movie in current_user.watchlist:
        Watchlist.query.filter_by(user_id=current_user.id, movie_id=movie_id).delete()
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'تم إزالة الفيلم من قائمة المشاهدة'})
    return jsonify({'status': 'error', 'message': 'الفيلم غير موجود في قائمة المشاهدة'})

@app.route('/watchlist/check/<int:movie_id>')
@login_required
def check_watchlist(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    is_in_watchlist = movie in current_user.watchlist
    return jsonify({'in_watchlist': is_in_watchlist})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/notifications')
@login_required
def user_notifications():
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())\
        .paginate(page=page, per_page=10)
    # Mark all unread notifications as read
    unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).all()
    for notification in unread:
        notification.is_read = True
    db.session.commit()
    return render_template('notifications.html', notifications=notifications, categories=Category.query.all())

@app.route('/notifications/count')
@login_required
def get_notifications_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

def create_notification(user_id, title, message, link=None):
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        link=link
    )
    db.session.add(notification)
    db.session.commit()

if __name__ == '__main__':
    try:
        logger.info("Starting application initialization...")
        
        # Create necessary directories
        if not os.path.exists('static'):
            os.makedirs('static')
            logger.info("Created static directory")
        
        if not os.path.exists('static/uploads'):
            os.makedirs('static/uploads')
            logger.info("Created uploads directory")
        
        with app.app_context():
            logger.info("Creating database tables...")
            db.create_all()
            
            # Create default admin user
            logger.info("Checking for default admin user...")
            if not User.query.filter_by(username='admin').first():
                hashed_password = generate_password_hash('admin')
                admin = User(username='admin', password=hashed_password, is_admin=True)
                db.session.add(admin)
                db.session.commit()
                logger.info("Created default admin user")
            else:
                logger.info("Default admin user already exists")
            
            # Create default category
            logger.info("Checking for default category...")
            if not Category.query.first():
                default_category = Category(name='General Movies')
                db.session.add(default_category)
                db.session.commit()
                logger.info("Created default category")
            else:
                logger.info("Default category already exists")
        
        logger.info("Starting Flask application...")
        print("\n=== Application Information ===")
        print("* Website URL: http://localhost:5000")
        print("* Default username: admin")
        print("* Default password: admin")
        print("============================\n")
        
        app.run(debug=True)
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        print("\n=== Error ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error description: {str(e)}")
        print("\nFull error details:")
        import traceback
        traceback.print_exc()
        print("\nPress Enter to exit...")
        input()
