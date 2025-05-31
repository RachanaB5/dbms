from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort, send_file
from extensions import db, login_manager
from models import User, Product, Review, Order, OrderItem, Payment, Cart as CartModel, PaymentDetails
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import secrets
import atexit
from sqlalchemy import create_engine
from decimal import Decimal
import imghdr
import requests
from werkzeug.utils import secure_filename
from urllib.parse import urlparse
import io

app = Flask(__name__)

# Security configurations
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:Rachana%4005@localhost/EcommerceDB'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 3600,
    'pool_timeout': 30,
    'pool_size': 10
}
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# File upload configurations
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Create directory for review images if it doesn't exist
REVIEW_IMAGES_FOLDER = os.path.join(app.root_path, 'static', 'review_images')
if not os.path.exists(REVIEW_IMAGES_FOLDER):
    os.makedirs(REVIEW_IMAGES_FOLDER)

# Setup logging
log_dir = 'logs'
try:
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, mode=0o755)
    
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'ecommerce.log'),
        maxBytes=10240,
        backupCount=10,
        delay=False,
        encoding='utf-8',
        mode='a'  # Append mode with default permissions
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)

    # Configure app logger directly - removing queue to avoid file locking issues
    app.logger.setLevel(logging.INFO)
    for handler in app.logger.handlers[:]:  # Remove any existing handlers
        app.logger.removeHandler(handler)
    app.logger.addHandler(file_handler)
    app.logger.info('Ecommerce startup')

except PermissionError as e:
    print(f"Permission error setting up logs: {e}")
    print("Try running: chmod 755 logs/")
    # Fallback to console logging
    import sys
    file_handler = logging.StreamHandler(sys.stdout)

# Clean up function
@atexit.register
def cleanup():
    file_handler.close()

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'show_login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.session_protection = 'strong'

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    app.logger.error(f'Server Error: {error}')
    return render_template('errors/500.html'), 500

# Request handlers
@app.before_request
def before_request():
    if not session.get('cart'):
        session['cart'] = {}
    session.permanent = True
    
    # Log requests for monitoring
    if not request.path.startswith('/static'):
        app.logger.info(f'Request: {request.method} {request.path} from {request.remote_addr}')

@app.after_request
def after_request(response):
    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

def init_db():
    with app.app_context():
        try:
            # First disable foreign key checks
            from sqlalchemy import text
            db.session.execute(text('SET FOREIGN_KEY_CHECKS=0'))
            
            # Drop all tables
            db.session.execute(text('DROP TABLE IF EXISTS userauthlogs'))
            db.session.execute(text('DROP TABLE IF EXISTS cart'))
            db.session.execute(text('DROP TABLE IF EXISTS reviews'))
            db.session.execute(text('DROP TABLE IF EXISTS payments'))
            db.session.execute(text('DROP TABLE IF EXISTS order_items'))
            db.session.execute(text('DROP TABLE IF EXISTS orders'))
            db.session.execute(text('DROP TABLE IF EXISTS products'))
            db.session.execute(text('DROP TABLE IF EXISTS users'))
            
            # Re-enable foreign key checks
            db.session.execute(text('SET FOREIGN_KEY_CHECKS=1'))
            db.session.commit()
            
            # Create all tables
            db.create_all()
            app.logger.info("Database tables created successfully")
            
            # Create admin users
            admin1 = User(
                username='Rachana',
                email='rachana@gmail.com',
                phone='',
                password_hash=generate_password_hash('12345678'),
                is_admin=True
            )
            
            admin2 = User(
                username='Priyanshu',
                email='priyanshu@gmail.com',
                phone='',
                password_hash=generate_password_hash('98765432'),
                is_admin=True
            )
            
            # Add both admins
            db.session.add(admin1)
            db.session.add(admin2)
            db.session.commit()
            app.logger.info("Both admin users created successfully!")

            # Initialize sample data only if products table is empty
            if Product.query.count() == 0:
                # Add sample products
                sample_products = [
                    {
                        'name': 'Laptop',
                        'description': 'Power through work and play with this sleek, high-performance laptop. Featuring a blazing-fast processor, vibrant HD display, and ample RAM, it effortlessly handles demanding tasks like video editing, complex spreadsheets, and immersive gaming. Enjoy all-day battery life, a comfortable backlit keyboard, and a lightweight design perfect for commuting. With lightning-fast Wi-Fi, multiple USB ports (including USB-C), and a crystal-clear webcam, it\'s your ultimate hub for productivity, creativity, and seamless video calls. Whether you\'re a student, professional, or creative, this laptop delivers reliable power and stunning visuals in a portable package. Experience speed, clarity, and versatility – upgrade your digital life today.',
                        'price': 59999,
                        'category': 'Electronics',
                        'image': 'laptop.jpg',
                        'discount': 10,
                        'stock_quantity': 15
                    },
                    {
                        'name': 'Smart Watch',
                        'description': 'Stay connected, motivated, and healthy effortlessly with this feature-packed smartwatch. Track your heart rate, sleep patterns, SpO2, and countless workouts with incredible accuracy. Receive call, text, and app notifications directly on your wrist, so you never miss a beat. Customize your style with interchangeable bands and watch faces. Enjoy contactless payments, music control, and built-in GPS for runs without your phone. Monitor stress levels, breathe mindfully, and set hydration reminders. With a bright, always-on display and multi-day battery life, it\'s your perfect 24/7 health companion and digital assistant. Elevate your fitness journey and streamline your day, right from your wrist.',
                        'price': 2999,
                        'category': 'Electronics',
                        'image': 'smart-watch.jpg',
                        'discount': 5,
                        'stock_quantity': 30
                    },
                    {
                        'name': 'Tablet',
                        'description': 'Experience stunning entertainment and productivity on a brilliant, high-resolution tablet display. Stream movies, read eBooks, browse the web, or sketch your ideas with incredible clarity and vibrant colors. Powered by a responsive processor and ample storage, it runs apps and games smoothly. The long-lasting battery ensures hours of use, while the slim, lightweight design makes it easy to carry anywhere. Perfect for video calls with its front-facing camera, note-taking with a compatible stylus, or keeping kids entertained on the go.',
                        'price': 39999,
                        'category': 'Electronics',
                        'image': 'tablet.jpg',
                        'discount': 15,
                        'stock_quantity': 20
                    },
                    {
                        'name': 'Gaming Console',
                        'description': 'Dive into next-generation gaming with this powerful console. Experience breathtakingly realistic graphics, incredibly fast load times thanks to the cutting-edge SSD, and immersive 3D audio that puts you in the heart of the action. Enjoy exclusive blockbuster titles and beloved classics. The innovative controller offers haptic feedback and adaptive triggers for unprecedented realism. Stream 4K movies and shows seamlessly, connect with friends online, and enjoy backward compatibility with previous generations. Whether you are a competitive player or a story-driven adventurer, this console delivers unparalleled performance, speed, and a vast world of entertainment right in your living room. Get ready to play without limits.',
                        'price': 79999,
                        'category': 'Gadgets',
                        'image': 'gaming-console.jpg',
                        'discount': 0,
                        'stock_quantity': 10
                    },
                    {
                        'name': 'Wireless Mouse',
                        'description': 'Unleash productivity and comfort with this ergonomic wireless mouse. Designed to fit naturally in your hand, it reduces strain during long work or gaming sessions. Enjoy precise, lag-free tracking on almost any surface with its advanced optical sensor. Connect effortlessly via Bluetooth or included USB receiver for reliable performance. Features programmable buttons for custom shortcuts, smooth scrolling, and long battery life measured in months. The sleek, portable design slips easily into your bag. Free yourself from cords and experience responsive, comfortable control that enhances your workflow and gaming precision. Upgrade your desktop experience today.',
                        'price': 1999,
                        'category': 'Gadgets',
                        'image': 'mouse.jpg',
                        'discount': 0,
                        'stock_quantity': 50
                    },
                    {
                        'name': 'Smart Phone',
                        'description': 'Capture life in stunning detail and stay effortlessly connected with this advanced smartphone. Boasting a professional-grade multi-lens camera system with AI enhancements, take breathtaking photos and videos day or night. The vibrant, edge-to-edge display offers an immersive viewing experience for streaming and gaming. Powered by a flagship processor, it handles multitasking and demanding apps with ease. Enjoy all-day battery life with super-fast charging, enhanced security features, and the latest operating system. With 5G connectivity, crystal-clear audio, and a sleek, durable design, this phone is your powerful pocket-sized companion for work, creativity, and entertainment.',
                        'price': 49999,
                        'category': 'Electronics',
                        'image': 'smart-phone.jpg',
                        'discount': 8,
                        'stock_quantity': 25
                    },
                    {
                        'name': 'Headphones',
                        'description': 'Immerse yourself in pure sound with these premium headphones. Experience crystal-clear audio, deep bass, and balanced mids thanks to high-fidelity drivers and advanced noise cancellation that silences the world around you. Enjoy seamless wireless freedom with Bluetooth 5.0 or use the included audio cable. The plush, over-ear cushions and adjustable headband provide exceptional comfort for hours of listening. Take calls with the integrated microphone and manage music effortlessly with intuitive touch controls. With impressive battery life and a stylish, foldable design for portability, these headphones deliver an unparalleled auditory escape for music lovers, travelers, and professionals alike.',
                        'price': 2999,
                        'category': 'Electronics',
                        'image': 'headphones.jpg',
                        'discount': 12,
                        'stock_quantity': 40
                    },
                    {
                        'name': 'Keyboard',
                        'description': 'Type with speed, comfort, and satisfying precision using this high-performance keyboard. Featuring responsive mechanical switches (choose your preferred type: clicky, tactile, or linear) for accurate keystrokes and a tactile feel loved by gamers and typists. The durable construction ensures longevity, while the ergonomic design promotes comfortable typing posture. Customize your experience with RGB backlighting, programmable macro keys, and dedicated media controls. Connect wirelessly via Bluetooth or use the USB-C cable for a lag-free connection. Built for productivity and gaming dominance, this keyboard offers reliability, customization, and a superior typing experience.',
                        'price': 3499,
                        'category': 'Electronics',
                        'image': 'keyboard.jpg',
                        'discount': 0,
                        'stock_quantity': 35
                    },
                    {
                        'name': 'Home Decor Set',
                        'description': ' Transform your space instantly with this beautifully curated home decor set. Designed to complement each other perfectly, the collection includes coordinating cushions, a luxurious throw blanket, elegant candles, and sophisticated decorative trays or vases. Crafted from high-quality materials like soft velvet, natural ceramics, and brushed metals, each piece adds texture, warmth, and a touch of modern elegance. Effortlessly elevate your living room, bedroom, or entryway with this cohesive look. Create a welcoming, stylish, and harmonious atmosphere without the hassle of matching individual items. Refresh your home aesthetic with this effortlessly chic set.',
                        'price': 2499,
                        'category': 'Home',
                        'image': 'home.jpg',
                        'discount': 20,
                        'stock_quantity': 18
                    },
                    {
                        'name': 'Beauty Kit',
                        'description': 'Discover your signature look with this all-inclusive beauty kit, perfect for beginners and enthusiasts. Packed with high-quality, blendable essentials: a versatile eyeshadow palette with matte and shimmer finishes, creamy lip colors, long-lasting mascara, buildable foundation/concealer, and essential brushes. Achieve natural daytime glam or dramatic evening looks with ease. The curated selection features universally flattering shades and nourishing formulas that feel comfortable on the skin. Housed in a chic, travel-friendly case, it is your complete makeup solution for home or on-the-go. Simplify your routine and unleash your creativity with this must-have kit.',
                        'price': 1599,
                        'category': 'Beauty',
                        'image': 'beauty.jpg',
                        'discount': 10,
                        'stock_quantity': 22
                    },
                    {
                        'name': 'Fashion Handbag',
                        'description': 'Make a statement with this exquisite fashion handbag, the epitome of style and practicality. Crafted from premium leather or durable vegan materials, it features a sophisticated silhouette and luxe hardware. The spacious main compartment, secure zip closure, and well-organized interior pockets keep your essentials neatly stowed. Adjustable straps offer versatile carrying options – crossbody, shoulder, or handheld. Perfect for daily commutes, office days, or weekend adventures, this bag seamlessly blends timeless elegance with modern functionality. Elevate any outfit with this essential accessory that promises durability, organization, and undeniable chic.',
                        'price': 2199.00,  
                        'category': 'Fashion', 
                        'image': 'fashion.jpg',  
                        'discount': 5,
                        'stock_quantity': 28
                    },
                    {
                        'name': 'Book: Learn Python',
                        'description': 'Master the worlds most popular programming language with this comprehensive and beginner-friendly Python guide. Start from absolute basics and progress to building real-world applications. Clear explanations, practical examples, and hands-on exercises demystify core concepts like variables, loops, functions, data structures, and object-oriented programming. Learn to work with files, handle errors, and utilize essential libraries. Written by experienced instructors, this book focuses on practical application, making coding engaging and accessible. Perfect for aspiring developers, data analysts, or anyone seeking valuable tech skills. Unlock your coding potential and open doors to exciting career opportunities – start your Python journey today!',
                        'price': 499,
                        'category': 'Books',
                        'image': 'book.jpg',
                        'discount': 0,
                        'stock_quantity': 60
                    },
                    {
                        'name': 'Decorative Wall Mirror',
                        'description': 'Add a striking focal point to any room with this stunning decorative wall clock. More than just a timepiece, it is a work of art featuring a unique design, premium materials (like metal, wood, or acrylic), and sophisticated finishes. The large, easy-to-read face ensures functionality, while the eye-catching style – be it minimalist, industrial, vintage, or modern – makes a bold design statement. Perfect for living rooms, kitchens, offices, or entryways. Reliable quartz movement guarantees accurate timekeeping. Elevate your home decor and keep track of time in style with this conversation-starting clock.',
                        'price': 3499,
                        'category': 'Home',
                        'image': 'wall-mirror.jpg',
                        'discount': 15,
                        'stock_quantity': 25
                    },
                    {
                        'name': 'Artificial Plants Set',
                        'description': ' Enjoy the beauty of nature without the upkeep! This lifelike artificial plants set brings vibrant greenery and a touch of tranquility to any space. Crafted from high-quality silk or plastic, each plant features realistic textures, colors, and details. The set includes a variety of stylish pots or planters, ready to display. Perfect for adding life to dim corners, shelves, desks, or bathrooms where real plants struggle. Allergy-friendly and permanently pristine, they require no watering, sunlight, or maintenance. Instantly refresh your home or office décor with effortless, year-round botanical charm.',
                        'price': 1499,
                        'category': 'Home',
                        'image': 'plants.jpg',
                        'discount': 10,
                        'stock_quantity': 30
                    },
                    {
                        'name': 'Designer Heels',
                        'description': ' Step out in show-stopping confidence with these exquisite designer-inspired heels. Crafted with meticulous attention to detail, they feature premium materials like supple leather or luxurious satin, elegant silhouettes (stiletto, block heel, or kitten), and sophisticated embellishments. The carefully engineered arch and cushioned insole provide surprising comfort for extended wear. A secure closure (ankle strap, pump) ensures stability. Whether for a glamorous event, a special date, or adding polish to office attire, these heels deliver unparalleled style, quality, and a touch of luxury that elevates any ensemble.',
                        'price': 3999,
                        'category': 'Fashion',
                        'image': 'heels.jpg',
                        'discount': 15,
                        'stock_quantity': 40
                    },
                    {
                        'name': 'Fashion Jewelry Set',
                        'description': 'Complete your look with instant glamour using this elegant fashion jewelry set. The coordinated collection features pieces like a delicate necklace, matching earrings, and a chic bracelet or ring, all designed with a cohesive aesthetic – perhaps minimalist, bohemian, geometric, or classic pearls. Crafted from high-quality plated metals and featuring lustrous faux stones or pearls, it offers sophisticated shine without the luxury price tag. Hypoallergenic materials ensure comfortable wear. Perfect for accessorizing everyday outfits or adding polish to evening wear. Effortlessly elevate your style with this versatile and beautifully presented set.',
                        'price': 1999,
                        'category': 'Fashion',
                        'image': 'jewelry.jpg',
                        'discount': 10,
                        'stock_quantity': 45
                    },
                    {
                        'name': 'Premium Makeup Set',
                        'description': 'Achieve flawless makeup application every time with this premium illuminated vanity mirror. Featuring bright, natural daylight-simulating LED lights with adjustable brightness levels, it reveals true colors and every detail for perfect blending. The large magnification side (typically 5x, 7x, or 10x) allows for precise work like brows and liner, while the standard side provides an overall view. A stable, weighted base or sleek tabletop design ensures it stays put. Some models offer touch controls, dimmable settings, or Bluetooth speakers. Essential for skincare routines and professional-looking makeup results, day or night.',
                        'price': 2999,
                        'category': 'Beauty',
                        'image': 'makeup.jpg',
                        'discount': 12,
                        'stock_quantity': 35
                    },
                    {
                        'name': 'Skincare Collection',
                        'description': ' Nourish your skin and reveal a radiant complexion with this luxurious, results-driven skincare collection. Formulated with potent, high-quality ingredients like hyaluronic acid, vitamins (C, E), peptides, and natural extracts, this multi-step regimen addresses hydration, brightness, fine lines, and overall skin health. The curated set typically includes a gentle cleanser, potent serum, rich moisturizer, and targeted treatment (eye cream/mask). Dermatologist-tested and suitable for your skin type (specify if known: sensitive, dry, combination, aging), it delivers visible improvements in texture, tone, and glow. Elevate your self-care ritual with this transformative collection.',
                        'price': 3499,
                        'category': 'Beauty',
                        'image': 'skincare.jpg',
                        'discount': 8,
                        'stock_quantity': 30
                    },
                    {
                        'name': 'Mystery Novel',
                        'description': 'Get lost in a gripping page-turner with this suspenseful mystery novel. A complex crime shatters the peace in [Setting - e.g., a sleepy village, a bustling city], leaving seasoned detective [Detective Name/Type] or an unlikely amateur sleuth racing against time. Clues are hidden in plain sight, suspects abound, each with motives and secrets, and unexpected twists will keep you guessing until the final, shocking reveal. Masterfully plotted with rich atmosphere and compelling characters, this novel delivers the perfect blend of intellectual puzzle and heart-pounding suspense. Escape into a world of intrigue and test your detective skills.',
                        'price': 599,
                        'category': 'Books',
                        'image': 'novel.jpg',
                        'discount': 5,
                        'stock_quantity': 80
                    },
                    {
                        'name': 'Fashion Magazine',
                        'description': 'Stay ahead of the curve with the latest issue of this iconic fashion magazine! Immerse yourself in stunning editorial spreads showcasing the seasons hottest trends, must-have pieces, and inspiring style directions. Get expert advice from top stylists, discover emerging designers, and read insightful interviews with fashion icons. Beyond clothing, explore beauty innovations, fragrance reviews, culture features, and lifestyle inspiration. Packed with aspirational photography and authoritative reporting, it is your essential guide to navigating the ever-evolving world of style. Fuel your fashion passion and find endless inspiration within its glossy pages.',
                        'price': 299,
                        'category': 'Books',
                        'image': 'magazine.jpg',
                        'discount': 0,
                        'stock_quantity': 100
                    },
                    {
                        'name': 'Smart Speaker',
                        'description': ' Fill your home with rich sound and effortless convenience using this powerful smart speaker. Stream music, podcasts, and audiobooks from your favorite services with crystal-clear audio and impressive bass. Control it all with just your voice via the built-in intelligent assistant (e.g., Alexa, Google Assistant, Siri) – play songs, set timers, check the weather, control smart home devices, get news updates, and more. Make hands-free calls, create multi-room audio systems, and enjoy its sleek, compact design. Your voice-activated hub for entertainment, information, and smart home control.',
                        'price': 4999,
                        'category': 'Gadgets',
                        'image': 'speaker.jpg',
                        'discount': 15,
                        'stock_quantity': 50
                    }
                ]
                
                for prod in sample_products:
                    p = Product(**prod)
                    db.session.add(p)
                db.session.commit()
                app.logger.info("Sample products added successfully")
                
        except Exception as e:
            app.logger.error(f"Database initialization error: {e}")
            db.session.rollback()
            raise

@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    logging.info(f"user_loader loaded user with id: {user_id}, found: {user is not None}")
    return user

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.')
            return redirect(url_for('show_login'))
        return f(*args, **kwargs)
    return decorated_function

# User registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            # Validation
            if not all([name, email, password, confirm_password]):
                flash('All fields except phone are required', 'error')
                return render_template('register.html')

            # Check if user already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already registered', 'error')
                return render_template('register.html')

            # Create new user
            new_user = User(
                username=name,
                email=email,
                password_hash=generate_password_hash(password),
                phone=phone if phone else None
            )

            # Save to database
            db.session.add(new_user)
            db.session.commit()

            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('show_login'))

        except Exception as e:
            db.session.rollback()
            print(f"Registration error: {e}")
            flash('Registration failed. Please try again.', 'error')
            return render_template('register.html')

    return render_template('register.html')

# User login route
@app.route('/login', methods=['POST'])
def login():
    print('Login route called')
    data = request.form
    print('Form data:', data)
    email = data.get('email')
    password = data.get('password')
    print('Email:', email)
    user = User.query.filter_by(email=email).first()
    print('User found:', user)
    if user:
        print('User password hash:', user.password_hash)
    if user and check_password_hash(user.password_hash, password):
        print('Password check passed')
        login_user(user)
        flash('Login Successful')
        if user.is_admin:
            return redirect(url_for('admin'))
        return redirect(url_for('products'))  # Changed from index to products
    else:
        print('Invalid email or password')
        flash('Invalid email or password.')
        return redirect(url_for('show_login'))

# User logout route
@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('index'))

# Home page route
@app.route('/')
def index():
    featured_products = Product.query\
        .filter(Product.discount > 0)\
        .filter(Product.stock_quantity > 0)\
        .order_by(Product.discount.desc())\
        .limit(4)\
        .all()
    return render_template('index.html', featured_products=featured_products)

def prepare_product_list(products):
    product_list = []
    for product in products:
        reviews = product.reviews
        review_count = len(reviews)
        avg_rating = int(round(sum([r.rating for r in reviews]) / review_count)) if review_count else 0
        product_list.append({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': product.price,
            'category': product.category,
            'image': product.image,
            'discount': product.discount,
            'stock_quantity': product.stock_quantity,
            'reviews': review_count,
            'rating': avg_rating
        })
    return product_list

# Products listing route
@app.route('/products')
def products():
    try:
        # Direct SQL query to verify table and data
        from sqlalchemy import text
        with db.engine.connect() as conn:
            # Check if table exists
            result = conn.execute(text("""
                SELECT TABLE_NAME 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = 'EcommerceDB' 
                AND TABLE_NAME = 'products'
            """))
            if not result.fetchone():
                app.logger.error("Products table does not exist!")
                init_db()  # Create tables and add sample data
            
            # Verify table structure
            result = conn.execute(text("DESCRIBE products"))
            columns = [row[0] for row in result]
            app.logger.info(f"Table columns: {columns}")
            
            # Check for data
            result = conn.execute(text("SELECT * FROM products LIMIT 1"))
            row = result.fetchone()
            app.logger.info(f"Sample product row: {row}")
            
            if not row:
                app.logger.info("No products found, adding sample data...")
                init_db()

        # Now try to fetch products again
        products = Product.query.all()
        if not products:
            flash("No products available. Adding sample products...")
            init_db()
            products = Product.query.all()
        
        product_list = []
        for p in products:
            product_dict = {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'price': float(p.price),
                'category': p.category,
                'image': p.image,  # Use the new method
                'discount': float(p.discount or 0),
                'stock_quantity': p.stock_quantity,
                'rating': 0,
                'reviews': 0
            }
            product_list.append(product_dict)

        return render_template('products.html', 
                            products=product_list,
                            debug=app.debug)
                            
    except Exception as e:
        app.logger.error(f"Error in products route: {str(e)}")
        return render_template('products.html', 
                            products=[],
                            error=str(e),
                            debug=app.debug)

# Category products route
@app.route('/category/<category_name>')
def category_products(category_name):
    try:
        products = Product.query.filter(Product.category == category_name).all()
        product_list = []
        for p in products:
            price = float(p.price)
            discount = float(p.discount or 0)
            discounted_price = float(price * (1 - discount/100))
            
            product_dict = {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'price': price,
                'category': p.category,
                'image': p.image,
                'discount': discount,
                'discounted_price': discounted_price,
                'stock_quantity': p.stock_quantity,
                'rating': 0,
                'reviews': 0
            }
            product_list.append(product_dict)
        
        return render_template('products.html',
                            products=product_list,
                            category=category_name,
                            category_title=category_name.replace('_', ' ').title())
    except Exception as e:
        app.logger.error(f"Error in category products: {str(e)}")
        return render_template('products.html', 
                            products=[],
                            error=str(e))

# Product detail route

# Product detail route
@app.route('/product/1')
@app.route('/product/2')
@app.route('/product/3')
@app.route('/product/4')
@app.route('/product/7')
@app.route('/product/8')
@app.route('/product/9')
@app.route('/product/10')
def product_detail_shortcut():
    product_id = int(request.path.split('/')[-1])
    return product_detail(product_id)

@app.route('/product/<int:product_id>', methods=['GET'])
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    reviews = Review.query.filter_by(product_id=product_id).order_by(Review.created_at.desc()).all()
    
    # Calculate average rating
    total_rating = sum(review.rating for review in reviews)
    avg_rating = round(total_rating / len(reviews)) if reviews else 0
    
    # Calculate prices
    price = float(product.price)
    discount = float(product.discount or 0)
    discounted_price = price * (1 - discount/100)
    
    # Get review information with user data from join
    review_list = []
    for r in reviews:
        user = User.query.get(r.user_id)
        review_list.append({
            'username': user.username if user else 'Anonymous',
            'created_at': r.created_at,
            'rating': r.rating,
            'review_text': r.review_text,
            'helpful_count': r.helpful_count or 0,
            'id': r.id,
            'review_image': r.review_image if hasattr(r, 'review_image') else None
        })
    
    return render_template('product_detail.html', 
                         product=product,
                         price=price,
                         discounted_price=discounted_price,
                         reviews=review_list, 
                         avg_rating=avg_rating,
                         now=datetime.utcnow,
                         timedelta=timedelta)

# Add review route
@app.route('/add_review/<int:product_id>', methods=['POST'])
@login_required
def add_review(product_id):
    try:
        # Get form data
        rating = int(request.form.get('rating', 0))
        review_text = request.form.get('review_text', '').strip()
        
        # Create new review
        new_review = Review(
            user_id=current_user.id,
            product_id=product_id,
            rating=rating,
            review_text=review_text,
            created_at=datetime.utcnow()
        )

        # Handle image upload
        if 'review_image' in request.files:
            image_file = request.files['review_image']
            if image_file and allowed_file(image_file.filename):
                # Read image data
                image_data = image_file.read()
                new_review.review_image = image_data
                new_review.image_mimetype = image_file.content_type

        db.session.add(new_review)
        db.session.commit()
        flash('Review added successfully!')
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error adding review: {str(e)}")
        flash('Error adding review. Please try again.')
    
    return redirect(url_for('product_detail', product_id=product_id))

# Review image serving route
@app.route('/review_image/<int:review_id>')
def serve_review_image(review_id):
    try:
        review = Review.query.get_or_404(review_id)
        if not review.review_image:
            abort(404)
        
        return send_file(
            io.BytesIO(review.review_image),
            mimetype=review.image_mimetype or 'image/jpeg',
            as_attachment=False
        )
    except Exception as e:
        app.logger.error(f"Error serving review image: {str(e)}")
        abort(404)

# Add to cart route
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    try:
        product = Product.query.get_or_404(product_id)
        quantity = int(request.form.get('quantity', 1))
        if quantity <= 0:
            return jsonify({'error': 'Invalid quantity'}), 400
        if quantity > product.stock_quantity:
            return jsonify({'error': f'Sorry, only {product.stock_quantity} items available'}), 400
        # Check if item already in cart
        cart_item = CartModel.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        if cart_item:
            new_quantity = cart_item.quantity + quantity
            if new_quantity > product.stock_quantity:
                return jsonify({'error': f'Sorry, cannot add {quantity} more items. Only {product.stock_quantity - cart_item.quantity} available'}), 400
            cart_item.quantity = new_quantity
        else:
            cart_item = CartModel(user_id=current_user.id, product_id=product_id, quantity=quantity)
            db.session.add(cart_item)
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': f'Added {quantity} {product.name} to cart'})
        flash(f'Added {quantity} {product.name} to cart')
        return redirect(url_for('products'))
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error adding to cart: {str(e)}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Failed to add item to cart'}), 500
        flash('Failed to add item to cart')
        return redirect(url_for('products'))

# Cart page route
@app.route('/cart', methods=['GET'])
@login_required
def cart():
    try:
        cart_items = CartModel.query.filter_by(user_id=current_user.id).all()
        items = []
        total = 0
        
        for cart_item in cart_items:
            product = Product.query.get(cart_item.product_id)
            if product:
                # Calculate price with discount
                unit_price = float(product.price)
                if product.discount:
                    unit_price = unit_price * (1 - float(product.discount)/100)
                
                subtotal = unit_price * cart_item.quantity
                total += subtotal
                
                # Generate image URL based on product data
                if product.image_data:
                    image_url = url_for('serve_image', product_id=product.id)
                else:
                    image_url = url_for('static', filename=f'images/{product.image}') if product.image else None
                
                items.append({
                    'product': product,
                    'quantity': cart_item.quantity,
                    'unit_price': unit_price,
                    'subtotal': subtotal,
                    'image_url': image_url
                })
        
        return render_template('cart.html', 
                            items=items, 
                            total=total,
                            cart_count=len(items))
                            
    except Exception as e:
        app.logger.error(f"Cart error: {str(e)}")
        flash('Error loading cart. Please try again.')
        return redirect(url_for('products'))

# Update cart route
@app.route('/update_cart/<int:product_id>', methods=['POST'])
@login_required
def update_cart(product_id):
    try:
        action = request.form.get('action')
        cart_item = CartModel.query.filter_by(user_id=current_user.id, product_id=product_id).first()
        product = Product.query.get_or_404(product_id)
        if not cart_item:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Item not in cart'}), 400
            flash('Item not in cart')
            return redirect(url_for('cart'))
        if action == 'remove':
            db.session.delete(cart_item)
        elif action == 'decrease':
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
            else:
                db.session.delete(cart_item)
        elif action == 'increase':
            if cart_item.quantity < product.stock_quantity:
                cart_item.quantity += 1
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True})
        return redirect(url_for('cart'))
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating cart: {str(e)}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'Failed to update cart'}), 500
        flash('Failed to update cart')
        return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    try:
        cart_items = CartModel.query.filter_by(user_id=current_user.id).all()
        if not cart_items:
            flash('Your cart is empty')
            return redirect(url_for('cart'))

        # Calculate total and prepare items list
        items = []
        total = Decimal('0.0')
        
        for cart_item in cart_items:
            product = Product.query.get(cart_item.product_id)
            if not product or product.stock_quantity < cart_item.quantity:
                flash(f'Sorry, {product.name if product else "an item"} is out of stock')
                return redirect(url_for('cart'))
            
            price = product.get_discounted_price()
            subtotal = price * Decimal(str(cart_item.quantity))
            total += subtotal
            
            items.append({
                'product': product,
                'quantity': cart_item.quantity,
                'subtotal': float(subtotal),
                'unit_price': float(price)
            })

        if request.method == 'POST':
            try:
                # Create new order
                order = Order(
                    user_id=current_user.id,
                    shipping_address=request.form.get('address'),
                    shipping_city=request.form.get('city'),
                    shipping_state=request.form.get('state'),
                    shipping_zip=request.form.get('zip'),
                    status='pending'
                )
                db.session.add(order)
                db.session.flush()

                # Add order items
                for cart_item in cart_items:
                    product = Product.query.get(cart_item.product_id)
                    order_item = OrderItem(
                        order_id=order.id,
                        product_id=cart_item.product_id,
                        quantity=cart_item.quantity,
                        price_at_time=float(product.price),
                        discount_at_time=product.discount
                    )
                    db.session.add(order_item)
                    # Update stock
                    if not product.update_stock(cart_item.quantity):
                        db.session.rollback()
                        flash(f'Sorry, {product.name} is out of stock')
                        return redirect(url_for('cart'))

                # Create payment record with card details
                payment_method = request.form.get('payment_method', 'card')
                payment = Payment(
                    order_id=order.id,
                    amount=float(total),
                    payment_status='pending',
                    payment_method=payment_method
                )

                # Add card details if payment method is card
                if payment_method == 'card':
                    card_number = request.form.get('card_number')
                    payment.set_card_number(card_number)
                    payment.card_expiry = request.form.get('card_expiry')
                    payment.card_holder = current_user.username

                db.session.add(payment)
                db.session.flush()

                # Clear cart
                for item in cart_items:
                    db.session.delete(item)

                db.session.commit()
                flash('Order placed successfully!')
                return redirect(url_for('order_confirmation', order_id=order.id))

            except Exception as e:
                db.session.rollback()
                app.logger.error(f'Checkout error: {str(e)}')
                flash('An error occurred while processing your order')
                return redirect(url_for('cart'))

        # GET request - show checkout page
        return render_template('checkout.html', items=items, total=float(total))

    except Exception as e:
        app.logger.error(f'Checkout error: {str(e)}')
        flash('An error occurred while processing your checkout')
        return redirect(url_for('cart'))

@app.route('/order_confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    # Update order and payment status
    order.status = 'completed'
    if order.payment:
        order.payment.payment_status = 'completed'
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating order status: {str(e)}')
    
    # Calculate total amount
    total_amount = 0
    for item in order.items:
        item_price = item.price_at_time
        item_discount = item.discount_at_time or 0
        discounted_price = item_price * (1 - item_discount/100)
        item_total = discounted_price * item.quantity
        total_amount += item_total
    
    return render_template('order_confirmation.html', order=order, total_amount=total_amount)

# Show login page (for non-modal fallback)
@app.route('/login')
def show_login():
    return render_template('login.html')

# Show register page (for non-modal fallback)
@app.route('/register')
def show_register():
    return render_template('register.html')

# Search route
@app.route('/search')
def search():
    try:
        query = request.args.get('q', '').strip()
        if not query:
            flash('Please enter a search term.')
            return redirect(url_for('products'))
        
        products = Product.query.filter(Product.name.ilike(f'%{query}%')).all()
        product_list = [] 
        
        for p in products:
            # Convert Decimal to float for calculations
            price = float(p.price)
            discount = float(p.discount or 0)
            discounted_price = price * (1 - discount/100)
            
            product_dict = {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'price': price,
                'category': p.category,
                'image': p.image,
                'discount': discount,
                'discounted_price': discounted_price,
                'stock_quantity': p.stock_quantity,
                'rating': 0,
                'reviews': 0
            }
            product_list.append(product_dict)
            
        return render_template('products.html', 
                            products=product_list,
                            search_query=query)
                            
    except Exception as e:
        app.logger.error(f"Search error: {str(e)}")
        flash('Search failed. Please try again.')
        return redirect(url_for('products'))

# Admin page route
@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)
    return render_template('admin/dashboard.html')

# Admin add product route
def validate_image_url(url):
    """Validate if URL points to an image"""
    try:
        import requests
        from urllib.parse import urlparse

        # Check if URL is valid
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False

        # Check if URL points to an image
        response = requests.head(url)
        content_type = response.headers.get('content-type', '')
        return content_type.startswith('image/')
    except:
        return False

@app.route('/admin/add', methods=['POST'])
@admin_required
def admin_add_product():
    try:
        # Get form data
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        category = request.form.get('category')
        stock_quantity = int(request.form.get('stock_quantity'))
        discount = int(request.form.get('discount', 0))
        
        # Validate required fields
        if not all([name, description, price, category, stock_quantity]):
            flash('All fields are required', 'error')
            return redirect(url_for('admin_products'))

        # Handle image upload
        if 'image' not in request.files:
            flash('No image file uploaded', 'error')
            return redirect(url_for('admin_products'))
            
        image_file = request.files['image']
        if image_file and allowed_file(image_file.filename):
            # Read image data
            image_data = image_file.read()
            image_mimetype = image_file.content_type
            filename = secure_filename(image_file.filename)
            
            # Create new product
            new_product = Product(
                name=name,
                description=description,
                price=price,
                category=category,
                stock_quantity=stock_quantity,
                discount=discount,
                image=filename,  # Store filename
                image_data=image_data,
                image_mimetype=image_mimetype
            )
            
            db.session.add(new_product)
            db.session.commit()
            
            flash('Product added successfully!', 'success')
            return redirect(url_for('admin_products'))
        
        flash('Invalid image file', 'error')
        return redirect(url_for('admin_products'))
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error adding product: {str(e)}")
        flash(f'Error adding product: {str(e)}', 'error')
        return redirect(url_for('admin_products'))

# Admin delete product route
@app.route('/admin/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully!')
    return redirect(url_for('admin'))

# Admin edit product route
@app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    try:
        product = Product.query.get_or_404(product_id)
        
        if request.method == 'POST':
            # Validate form data
            name = request.form.get('name')
            description = request.form.get('description')
            price = request.form.get('price')
            category = request.form.get('category')
            image = request.form.get('image')
            stock_quantity = request.form.get('stock_quantity')
            discount = request.form.get('discount', 0)

            if not all([name, description, price, category, image, stock_quantity]):
                flash('All fields are required', 'error')
                return render_template('admin/edit_product.html', product=product)

            try:
                # Validate numeric fields
                price = float(price)
                stock_quantity = int(stock_quantity)
                discount = int(discount)

                if price < 0 or stock_quantity < 0 or not (0 <= discount <= 100):
                    raise ValueError("Invalid numeric values")

            except ValueError as e:
                flash('Invalid numeric values provided', 'error')
                return render_template('admin/edit_product.html', product=product)

            # Validate image URL if changed
            if image != product.image and not validate_image_url(image):
                flash('Invalid image URL provided', 'error')
                return render_template('admin/edit_product.html', product=product)

            try:
                # Update product attributes
                product.name = name
                product.description = description
                product.price = price
                product.category = category
                product.image = image
                product.stock_quantity = stock_quantity
                product.discount = discount

                # Save changes to database
                db.session.commit()
                
                # Log the successful update
                app.logger.info(f"Product {product_id} updated successfully by admin {current_user.id}")
                
                flash('Product updated successfully!', 'success')
                return redirect(url_for('admin_products'))

            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Database error updating product {product_id}: {str(e)}")
                flash('Error saving changes to database', 'error')
                return render_template('admin/edit_product.html', product=product)

        return render_template('admin/edit_product.html', product=product)

    except Exception as e:
        app.logger.error(f"Error in edit product route: {str(e)}")
        flash('An error occurred', 'error')
        return redirect(url_for('admin_products'))

# Dashboard route
@app.route('/dashboard')
def dashboard():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    # Get all products
    all_products = Product.query.all()
    
    # Get featured products (showing all products)
    featured_products = Product.query.all()
    
    # Categorize products
    electronics = [p for p in all_products if p.category == 'Electronics']
    gadgets = [p for p in all_products if p.category == 'Gadgets']
    
    # Get user's orders if authenticated
    orders = []
    if current_user.is_authenticated:
        orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.id.desc()).all()
    
    return render_template('dashboard.html', 
                         featured_products=featured_products,
                         electronics=electronics,
                         gadgets=gadgets,
                         orders=orders)

# Add sample products route
@app.route('/add_sample_products')
def add_sample_products():
    sample_products = [
        {
            'name': 'Laptop',
            'description': 'High performance laptop for work and play.',
            'price': 59999,
            'category': 'Electronics',
            'image': 'laptop.jpg',
            'discount': 10,
            'stock_quantity': 15
        },
        {
            'name': 'Smart Watch',
            'description': 'Track your fitness and notifications on the go.',
            'price': 2999,
            'category': 'Electronics',
            'image': 'smart-watch.jpg',
            'discount': 5,
            'stock_quantity': 30
        },
        {
            'name': 'Tablet',
            'description': 'Portable tablet for entertainment and productivity.',
            'price': 39999,
            'category': 'Electronics',
            'image': 'tablet.jpg',
            'discount': 15,
            'stock_quantity': 20
        },
        {
            'name': 'Gaming Console',
            'description': 'Next-gen gaming console for immersive experiences.',
            'price': 79999,
            'category': 'Gadgets',
            'image': 'gaming-console.jpg',
            'discount': 0,
            'stock_quantity': 10
        },
        {
            'name': 'Wireless Mouse',
            'description': 'Ergonomic wireless mouse for smooth navigation.',
            'price': 1999,
            'category': 'Gadgets',
            'image': 'mouse.jpg',
            'discount': 0,
            'stock_quantity': 50
        },
        {
            'name': 'Smart Phone',
            'description': 'Latest smartphone with advanced features.',
            'price': 49999,
            'category': 'Electronics',
            'image': 'smart-phone.jpg',
            'discount': 8,
            'stock_quantity': 25
        },
        {
            'name': 'Headphones',
            'description': 'Noise-cancelling headphones for music lovers.',
            'price': 2999,
            'category': 'Electronics',
            'image': 'headphones.jpg',
            'discount': 12,
            'stock_quantity': 40
        },
        {
            'name': 'Keyboard',
            'description': 'Mechanical keyboard for fast and accurate typing.',
            'price': 3499,
            'category': 'Electronics',
            'image': 'keyboard.jpg',
            'discount': 0,
            'stock_quantity': 35
        },
        {
            'name': 'Home Decor Set',
            'description': 'Beautiful decor set to enhance your living space.',
            'price': 2499,
            'category': 'Home & Kitchen',
            'image': 'home.jpg',
            'discount': 20,
            'stock_quantity': 18
        },
        {
            'name': 'Beauty Kit',
            'description': 'Complete beauty kit for your daily routine.',
            'price': 1599.00,
            'category': 'Beauty',
            'image': 'beauty.jpg',
            'discount': 10,
            'stock_quantity': 22
        },
        {
            'name': 'Fashion Handbag',
            'description': 'Trendy handbag to complement your style.',
            'price': 2199.00,  # Added missing price
            'category': 'Fashion',  # Added missing category
            'image': 'fashion.jpg',  # Added missing image
            'discount': 5,
            'stock_quantity': 28
        },
        {
            'name': 'Book: Learn Python',
            'description': 'Comprehensive guide to learning Python programming.',
            'price': 499.00,
            'category': 'Books',
            'image': 'book.jpg',
            'discount': 0,
            'stock_quantity': 60
        },
        {
            'name': 'Designer Heels',
            'description': 'Elegant designer heels for special occasions.',
            'price': 3999,
            'category': 'Fashion',
            'image': 'heels.jpg',
            'discount': 15,
            'stock_quantity': 40
        },
        {
            'name': 'Fashion Jewelry Set',
            'description': 'Designer necklace and earrings set.',
            'price': 1999,
            'category': 'Fashion',
            'image': 'jewelry.jpg',
            'discount': 10,
            'stock_quantity': 45
        },
        {
            'name': 'Premium Makeup Set',
            'description': 'Professional makeup kit with brushes.',
            'price': 2999,
            'category': 'Beauty',
            'image': 'makeup.jpg',
            'discount': 12,
            'stock_quantity': 35
        },
        {
            'name': 'Skincare Collection',
            'description': 'Luxury skincare products for daily routine.',
            'price': 3499,
            'category': 'Beauty',
            'image': 'skincare.jpg',
            'discount': 8,
            'stock_quantity': 30
        },
        {
            'name': 'Mystery Novel',
            'description': 'Bestselling mystery thriller book.',
            'price': 599,
            'category': 'Books',
            'image': 'novel.jpg',
            'discount': 5,
            'stock_quantity': 80
        },
        {
            'name': 'Fashion Magazine',
            'description': 'Latest trends and style magazine.',
            'price': 299,
            'category': 'Books',
            'image': 'magazine.jpg',
            'discount': 0,
            'stock_quantity': 100
        },
        {
            'name': 'Smart Speaker',
            'description': 'Wireless smart speaker with voice control.',
            'price': 4999,
            'category': 'Gadgets',
            'image': 'speaker.jpg',
            'discount': 15,
            'stock_quantity': 50
        }
        
    ]
    for prod in sample_products:
        if not Product.query.filter_by(name=prod['name']).first():
            p = Product(**prod)
            db.session.add(p)
    db.session.commit()
    return 'Sample products added!'

@app.route('/reset_products')
def reset_products():
    try:
        # Delete all products
        Product.query.delete()
        db.session.commit()
        
        # Sample products data
        sample_products = [
            {
                'name': 'Laptop',
                'description': 'High-performance laptop for work and play.',
                'price': 74899.00,
                'category': 'Electronics',
                'image': 'laptop.jpg',
                'discount': 10,
                'stock_quantity': 50
            },
            {
                'name': 'Smartphone',
                'description': 'Latest model smartphone with advanced features.',
                'price': 24999.00,
                'category': 'Electronics',
                'image': 'smart-phone.jpg',
                'discount': 8,
                'stock_quantity': 100
            },
            {
                'name': 'Headphones',
                'description': 'Noise-canceling headphones for music lovers.',
                'price': 2999.00,
                'category': 'Electronics',
                'image': 'headphones.jpg',
                'discount': 12,
                'stock_quantity': 75
            },
            {
                'name': 'Smartwatch',
                'description': 'Waterproof smartwatch with fitness tracking.',
                'price': 2499.00,
                'category': 'Electronics',
                'image': 'smart-watch.jpg',
                'discount': 5,
                'stock_quantity': 60
            },
            {
                'name': 'Tablet',
                'description': 'Lightweight tablet for entertainment and productivity.',
                'price': 39999.00,
                'category': 'Electronics',
                'image': 'tablet.jpg',
                'discount': 15,
                'stock_quantity': 80
            },
            {
                'name': 'Gaming Console',
                'description': 'Next-gen gaming console for immersive experiences.',
                'price': 79999.00,
                'category': 'Gadgets',
                'image': 'gaming-console.jpg',
                'discount': 0,
                'stock_quantity': 40
            },
            {
                'name': 'Wireless Mouse',
                'description': 'Ergonomic wireless mouse for smooth navigation.',
                'price': 1999.00,
                'category': 'Gadgets',
                'image': 'mouse.jpg',
                'discount': 0,
                'stock_quantity': 150
            },
            {
                'name': 'Home Decor Set',
                'description': 'Beautiful decor set to enhance your living space.',
                'price': 122499.00,
                'category': 'Home & Kitchen',
                'image': 'home.jpg',
                'discount': 20,
                'stock_quantity': 18
            },
            {
                'name': 'Beauty Kit',
                'description': 'Complete beauty kit for your daily routine.',
                'price': 1599.00,
                'category': 'Beauty',
                'image': 'beauty.jpg',
                'discount': 10,
                'stock_quantity': 22
            },
            {
                'name': 'Fashion Handbag',
                'description': 'Trendy handbag to complement your style.',
                'price': 2199.00,
                'category': 'Fashion',
                'image': 'fashion.jpg',
                'discount': 5,
                'stock_quantity': 28
            },
            {
                'name': 'Book: Learn Python',
                'description': 'Comprehensive guide to learning Python programming.',
                'price': 499.00,
                'category': 'Books',
                'image': 'book.jpg',
                'discount': 0,
                'stock_quantity': 60
            },
            {
                'name': 'Keyboard',
                'description': 'Mechanical keyboard for fast and accurate typing.',
                'price': 3499.00,
                'category': 'Electronics',
                'image': 'keyboard.jpg',
                'discount': 0,
                'stock_quantity': 35
            }
        ]
        
        # Add all products
        for prod_data in sample_products:
            product = Product(**prod_data)
            db.session.add(product)
        
        db.session.commit()
        flash('Products reset successfully!')
        return redirect(url_for('products'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting products: {str(e)}')
        return redirect(url_for('products'))

@app.route('/debug/products')
def debug_products():
    try:
        products = Product.query.all()
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'price': p.price,
            'category': p.category,
            'image': p.image,
            'discount': p.discount,
            'stock_quantity': p.stock_quantity
        } for p in products])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Helper functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def test_db_connection():
    try:
        with app.app_context():
            db.engine.connect()
            app.logger.info("Database connection successful")
    except Exception as e:
        app.logger.error(f"Database connection failed: {str(e)}")
        raise

def init_database():
    try:
        # Create database if it doesn't exist
        engine = create_engine('mysql://root:Rachana@05@localhost')
        with engine.connect() as conn:
            conn.execute("CREATE DATABASE IF NOT EXISTS EcommerceDB")
            conn.execute("USE EcommerceDB")
            
            # Reset MySQL root password
            conn.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY 'Rachana@05'")
            conn.execute("GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost'")
            conn.execute("FLUSH PRIVILEGES")
        
        with app.app_context():
            db.create_all()
            app.logger.info("Database initialized successfully")
            
    except Exception as e:
        app.logger.error(f"Database initialization error: {e}")
        raise

with app.app_context():
    init_db()

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    product_count = Product.query.count()
    order_count = Order.query.count()
    user_count = User.query.count()
    return render_template('admin/dashboard.html',
                         product_count=product_count,
                         order_count=order_count,
                         user_count=user_count)

@app.route('/admin/products')
@login_required
@admin_required
def admin_products():
    products = Product.query.all()
    return render_template('admin/products.html', products=products)

@app.route('/admin/orders')
@login_required
@admin_required
def admin_orders():
    orders = Order.query.options(db.joinedload(Order.user)).order_by(Order.created_at.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/<int:user_id>/orders')
@admin_required
def admin_user_orders(user_id):
    user = User.query.get_or_404(user_id)
    orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()
    return render_template('admin/user.html', user=user, orders=orders)

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        try:
            user.username = request.form.get('username')
            user.email = request.form.get('email')
            user.phone = request.form.get('phone')
            db.session.commit()
            flash('User updated successfully')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'error')
            return render_template('admin/edit_user.html', user=user)
    return render_template('admin/edit_user.html', user=user)

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        
        # Don't allow deleting self
        if current_user.id == user_id:
            return jsonify({'success': False, 'error': 'Cannot delete yourself'}), 400
            
        # Don't allow deleting other admins
        if user.is_admin:
            return jsonify({'success': False, 'error': 'Cannot delete admin users'}), 400
            
        # Delete user's data
        # First delete payments
        orders = Order.query.filter_by(user_id=user_id).all()
        for order in orders:
            # Delete associated payments first
            Payment.query.filter_by(order_id=order.id).delete()
            # Delete order items
            OrderItem.query.filter_by(order_id=order.id).delete()
        # Now delete orders
        Order.query.filter_by(user_id=user_id).delete()
        # Delete other user data
        Review.query.filter_by(user_id=user_id).delete()
        CartModel.query.filter_by(user_id=user_id).delete()
        
        # Delete user
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting user: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/orders/<int:order_id>/status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    try:
        order = Order.query.get_or_404(order_id)
        data = request.get_json()
        order.status = data['status']
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/orders/<int:order_id>/details')
@admin_required
def order_details(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('admin/order_details.html', order=order)

@app.route('/product/image/<int:product_id>')
def serve_image(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.image_data:
        return app.send_static_file('images/default.jpg')
    return send_file(
        io.BytesIO(product.image_data),
        mimetype=product.image_mimetype
    )

@app.route('/my-orders')
@login_required
def user_orders():
    try:
        # Get all orders for the current user, ordered by date
        orders = Order.query\
            .filter_by(user_id=current_user.id)\
            .order_by(Order.created_at.desc())\
            .all()
            
        return render_template('user_orders.html', orders=orders)
    except Exception as e:
        app.logger.error(f"Error fetching user orders: {str(e)}")
        flash('Error loading orders. Please try again.')
        return redirect(url_for('dashboard'))

# Cancel order route
@app.route('/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    try:
        order = Order.query.get_or_404(order_id)
        
        # Check if the order belongs to the current user
        if order.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Only allow cancellation of orders that are not delivered or already cancelled
        if order.status in ['delivered', 'cancelled']:
            return jsonify({'success': False, 'error': 'Cannot cancel this order'}), 400
            
        # Update order status to cancelled
        order.status = 'cancelled'
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
