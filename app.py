from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from dotenv import load_dotenv
load_dotenv(override=True)
from extensions import db, login_manager
from models import User, Product, Review, Order, OrderItem, Payment, Cart as CartModel, Wishlist, Address, Category, Coupon, ProductImage
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from mail_helper import MailHelper
import os
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import secrets
import atexit

app = Flask(__name__)

# Security configurations
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
db_uri = os.environ.get('SQLALCHEMY_DATABASE_URI', 'mysql+mysqlconnector://root:Rachana%4005@127.0.0.1:3306/EcommerceDB')
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

engine_options = {
    'pool_recycle': 280,
    'pool_timeout': 20,
}
if '127.0.0.1' in db_uri or 'localhost' in db_uri:
    engine_options['connect_args'] = {
        'auth_plugin': 'mysql_native_password'
    }
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Setup logging
if not os.path.exists('logs'):
    os.mkdir('logs')

# Configure file handler with Windows-friendly settings
file_handler = RotatingFileHandler(
    'logs/ecommerce.log',
    maxBytes=10240,
    backupCount=10,
    delay=False,  # Create file immediately
    encoding='utf-8'  # Explicit encoding for Windows
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
            db.session.execute(text('DROP TABLE IF EXISTS wishlist'))
            db.session.execute(text('DROP TABLE IF EXISTS addresses'))
            db.session.execute(text('DROP TABLE IF EXISTS categories'))
            db.session.execute(text('DROP TABLE IF EXISTS coupons'))
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
            
            # Create admin user if it doesn't exist
            admin = User.query.filter_by(email='admin@example.com').first()
            if not admin:
                admin = User(
                    username='Admin',
                    email='admin@example.com',
                    password_hash=generate_password_hash('admin123'),
                    _is_admin=True,
                    phone=''
                )
                db.session.add(admin)
                db.session.commit()
                app.logger.info("Admin user created successfully")

            # Seed categories
            if Category.query.count() == 0:
                categories = [
                    Category(name='Electronics', description='Gadgets, devices, and accessories'),
                    Category(name='Gadgets', description='Useful tools and novelties'),
                    Category(name='Home & Kitchen', description='Decorations and cooking utilities'),
                    Category(name='Beauty', description='Skincare and cosmetics'),
                    Category(name='Fashion', description='Trendy garments and bags'),
                    Category(name='Books', description='Educational and leisure reading')
                ]
                for cat in categories:
                    db.session.add(cat)
                db.session.commit()
                app.logger.info("Categories seeded successfully")

            # Seed coupons
            if Coupon.query.count() == 0:
                coupons = [
                    Coupon(code='SAVE10', discount_percent=10, active=True),
                    Coupon(code='WELCOME20', discount_percent=20, active=True),
                    Coupon(code='MEGA30', discount_percent=30, active=True)
                ]
                for c in coupons:
                    db.session.add(c)
                db.session.commit()
                app.logger.info("Coupons seeded successfully")


            # Initialize sample data only if products table is empty
            if Product.query.count() == 0:
                # Create standard mock users for reviews if they do not exist
                users_to_seed = [
                    {'username': 'Rohan Sharma', 'email': 'rohan@example.com', 'pwd': 'password123'},
                    {'username': 'Deepika Roy', 'email': 'deepika@example.com', 'pwd': 'password123'},
                    {'username': 'Amit Verma', 'email': 'amit@example.com', 'pwd': 'password123'}
                ]
                seeded_users = {}
                for u in users_to_seed:
                    user_obj = User.query.filter_by(email=u['email']).first()
                    if not user_obj:
                        user_obj = User(
                            username=u['username'],
                            email=u['email'],
                            password_hash=generate_password_hash(u['pwd']),
                            _is_admin=False,
                            phone='1234567890'
                        )
                        db.session.add(user_obj)
                        db.session.commit()
                    seeded_users[u['username']] = user_obj.id

                # Add sample products
                sample_products = [
                    {
                        'name': 'Laptop',
                        'brand': 'ApexTech',
                        'description': 'High performance laptop for work and play. Features an incredible display, robust battery, and clean thermal design.',
                        'price': 59999,
                        'category': 'Electronics',
                        'image': 'laptop.jpg',
                        'discount': 10,
                        'stock_quantity': 15,
                        'specifications': '{"Processor": "Intel Core i7 12th Gen", "RAM": "16GB LPDDR5", "Storage": "512GB NVMe SSD", "Display": "15.6 inch FHD IPS", "OS": "Windows 11"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?q=80&w=600',
                            'https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?q=80&w=600',
                            'https://images.unsplash.com/photo-1603302576837-37561b2e2302?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Rohan Sharma', 'rating': 5, 'title': 'Absolute Powerhouse!', 'text': 'This laptop exceeded all my expectations. The processor handles programming and virtual machines effortlessly.', 'verified': True},
                            {'username': 'Deepika Roy', 'rating': 4, 'title': 'Stunning Screen', 'text': 'The display is absolutely sharp and color accurate. Heat management is decent but runs a bit warm under loads.', 'verified': True},
                            {'username': 'Amit Verma', 'rating': 3, 'title': 'Good but pricey', 'text': 'Hardware is solid, but the built-in speakers are quite average for this price tier.', 'verified': False}
                        ]
                    },
                    {
                        'name': 'Smart Watch',
                        'brand': 'FitPulse',
                        'description': 'Track your fitness and notifications on the go with this sleek smartwatch featuring a brilliant AMOLED display and long battery life.',
                        'price': 2999,
                        'category': 'Electronics',
                        'image': 'smart-watch.jpg',
                        'discount': 5,
                        'stock_quantity': 30,
                        'specifications': '{"Display": "1.43 inch AMOLED", "Battery Life": "Up to 10 Days", "Sensors": "Heart Rate, SpO2, Sleep Tracker, GPS", "Waterproof": "IP68 / 5 ATM"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?q=80&w=600',
                            'https://images.unsplash.com/photo-1434494878577-86c23bcb06b9?q=80&w=600',
                            'https://images.unsplash.com/photo-1517502884422-41eaaced0168?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Rohan Sharma', 'rating': 5, 'title': 'Best fitness companion', 'text': 'Extremely accurate step tracker and excellent sleep logging details. Battery easily lasts 9 days.', 'verified': True},
                            {'username': 'Deepika Roy', 'rating': 4, 'title': 'Sleek design', 'text': 'Looks very premium and elegant on the wrist. Wish there were more custom watch faces available.', 'verified': True}
                        ]
                    },
                    {
                        'name': 'Tablet',
                        'brand': 'SlatePro',
                        'description': 'Portable tablet for entertainment and productivity. Outstanding screen clarity and compatible with advanced digitizer pens.',
                        'price': 39999,
                        'category': 'Electronics',
                        'image': 'tablet.jpg',
                        'discount': 15,
                        'stock_quantity': 20,
                        'specifications': '{"Display": "11-inch Liquid Retina", "Processor": "Octa-core A14 Bionic", "Storage": "128GB", "Cameras": "12MP Rear / 7MP Front"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?q=80&w=600',
                            'https://images.unsplash.com/photo-1589739900243-4b52cd9b104e?q=80&w=600',
                            'https://images.unsplash.com/photo-1561154464-82e9adf32764?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Amit Verma', 'rating': 5, 'title': 'Great for artists', 'text': 'Incredible pressure sensitivity and zero pen lag. The display colors are remarkably deep and accurate.', 'verified': True},
                            {'username': 'Rohan Sharma', 'rating': 4, 'title': 'Perfect media player', 'text': 'Netflix and YouTube look beautiful on this. Speakers are loud and punchy, excellent for movies.', 'verified': True}
                        ]
                    },
                    {
                        'name': 'Gaming Console',
                        'brand': 'PlaySphere',
                        'description': 'Next-gen gaming console for immersive 4K experiences. High framerates, ray tracing technology, and lightning-fast load times.',
                        'price': 79999,
                        'category': 'Gadgets',
                        'image': 'gaming-console.jpg',
                        'discount': 0,
                        'stock_quantity': 10,
                        'specifications': '{"Resolution": "True 4K UHD", "Storage": "1TB Custom SSD", "Frame Rate": "Up to 120 FPS", "GPU": "Custom AMD RDNA 2"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1606144042614-b2417e99c4e3?q=80&w=600',
                            'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=600',
                            'https://images.unsplash.com/photo-1592840496694-26d035b52b48?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Rohan Sharma', 'rating': 5, 'title': 'Pure Next-Gen Joy', 'text': 'Games load in less than 3 seconds. The ray tracing effects make current titles look stunning.', 'verified': True},
                            {'username': 'Amit Verma', 'rating': 4, 'title': 'Exceptional console', 'text': 'Quiet operation even under heavy gaming. Controller haptic feedback is revolutionary.', 'verified': True}
                        ]
                    },
                    {
                        'name': 'Wireless Mouse',
                        'brand': 'ErgoClick',
                        'description': 'Ergonomic wireless mouse for smooth navigation and long-lasting productivity. Designed to fit the contour of your hand perfectly.',
                        'price': 1999,
                        'category': 'Gadgets',
                        'image': 'mouse.jpg',
                        'discount': 0,
                        'stock_quantity': 50,
                        'specifications': '{"DPI": "Adjustable up to 4000", "Battery": "Up to 24 Months", "Buttons": "6 Customizable", "Weight": "95g"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7?q=80&w=600',
                            'https://images.unsplash.com/photo-1625842268584-8f3296236761?q=80&w=600',
                            'https://images.unsplash.com/photo-1625842268023-8ab51a83685e?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Deepika Roy', 'rating': 5, 'title': 'Incredibly comfortable', 'text': 'No more wrist pain after long workdays. The dynamic scrolls and click dampeners feel very premium.', 'verified': True}
                        ]
                    },
                    {
                        'name': 'Smart Phone',
                        'brand': 'NovaPhone',
                        'description': 'Latest premium smartphone with high-end cameras, 120Hz display, and powerful processor for clean multi-tasking.',
                        'price': 49999,
                        'category': 'Electronics',
                        'image': 'smart-phone.jpg',
                        'discount': 8,
                        'stock_quantity': 25,
                        'specifications': '{"Processor": "Snapdragon 8 Gen 1", "RAM": "8GB", "Storage": "256GB", "Display": "6.7 inch AMOLED 120Hz"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?q=80&w=600',
                            'https://images.unsplash.com/photo-1598327105666-5b89351aff97?q=80&w=600',
                            'https://images.unsplash.com/photo-1565849906660-f8c67c8a2801?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Rohan Sharma', 'rating': 5, 'title': 'Flagship killer!', 'text': 'Camera quality in low light is mind-blowing. Charging from 0% to 100% in 35 minutes is super handy.', 'verified': True},
                            {'username': 'Amit Verma', 'rating': 4, 'title': 'Great value', 'text': 'Sleek and extremely responsive interface. The back glass has a very clean matte finish.', 'verified': True}
                        ]
                    },
                    {
                        'name': 'Headphones',
                        'brand': 'AuraSound',
                        'description': 'Noise-cancelling wireless headphones with dynamic bass and comfort earcups. Experience high-fidelity audio.',
                        'price': 2999,
                        'category': 'Electronics',
                        'image': 'headphones.jpg',
                        'discount': 12,
                        'stock_quantity': 40,
                        'specifications': '{"ANC": "Active Noise Cancellation", "Battery": "Up to 40 Hours", "Driver": "40mm Dynamic", "Bluetooth": "v5.2"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?q=80&w=600',
                            'https://images.unsplash.com/photo-1484704849700-f032a568e944?q=80&w=600',
                            'https://images.unsplash.com/photo-1546435770-a3e426bf472b?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Deepika Roy', 'rating': 5, 'title': 'Silent bliss', 'text': 'The active noise cancellation blocks office chatter completely. Sound profile is rich and warm.', 'verified': True},
                            {'username': 'Rohan Sharma', 'rating': 3, 'title': 'Average mic quality', 'text': 'Music sounds incredible, but the microphone on calls is slightly muffled in noisy settings.', 'verified': True}
                        ]
                    },
                    {
                        'name': 'Keyboard',
                        'brand': 'KeyTac',
                        'description': 'Premium mechanical keyboard with customizable RGB backlighting and tactile switches for responsive typing.',
                        'price': 3499,
                        'category': 'Electronics',
                        'image': 'keyboard.jpg',
                        'discount': 0,
                        'stock_quantity': 35,
                        'specifications': '{"Switches": "Mechanical Brown", "Layout": "Tenkeyless 80%", "Backlight": "RGB Customizable", "Keycaps": "Double-shot PBT"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1587829741301-dc798b83add3?q=80&w=600',
                            'https://images.unsplash.com/photo-1618384887929-16ec33fab9ef?q=80&w=600',
                            'https://images.unsplash.com/photo-1595225476474-87563907a212?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Amit Verma', 'rating': 5, 'title': 'Super tactile typing', 'text': 'The brown switches have the perfect tactile bump without being overly loud. Extremely sturdy frame.', 'verified': True}
                        ]
                    },
                    {
                        'name': 'Home Decor Set',
                        'brand': 'VibeHome',
                        'description': 'Minimalist boho home decorations. Includes unique ceramic vases, oak wood frames, and a calming scented candle.',
                        'price': 2499,
                        'category': 'Home & Kitchen',
                        'image': 'home.jpg',
                        'discount': 20,
                        'stock_quantity': 18,
                        'specifications': '{"Material": "Ceramic & Oak wood", "Included": "3 Vases, 2 Wall Frames, 1 Candle", "Style": "Modern Bohemian"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?q=80&w=600',
                            'https://images.unsplash.com/photo-1615876234886-fd9a39fda97f?q=80&w=600',
                            'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Deepika Roy', 'rating': 5, 'title': 'So beautiful!', 'text': 'Totally transformed my living room layout. The vases look extremely high quality and elegant.', 'verified': True}
                        ]
                    },
                    {
                        'name': 'Beauty Kit',
                        'brand': 'GlowAura',
                        'description': 'Hydrating and brightening organic skincare bundle containing active cleanser, Vitamin C serum, and nourishing night cream.',
                        'price': 1599,
                        'category': 'Beauty',
                        'image': 'beauty.jpg',
                        'discount': 10,
                        'stock_quantity': 22,
                        'specifications': '{"Skin Type": "All Skins", "Ingredients": "Hyaluronic Acid, Vitamin C", "Organic": "100% Vegan & Cruelty-free"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1608248597481-496100c80836?q=80&w=600',
                            'https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?q=80&w=600',
                            'https://images.unsplash.com/photo-1601049541289-9b1b7bbbfe19?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Deepika Roy', 'rating': 5, 'title': 'Glowing results', 'text': 'My skin feels incredibly hydrated and soft in the mornings. The serum is light and absorbs fast.', 'verified': True}
                        ]
                    },
                    {
                        'name': 'Fashion Handbag',
                        'brand': 'ModaLux',
                        'description': 'Premium tan vegan leather handbag with sturdy dynamic straps and multi-compartment spacing layout.',
                        'price': 2199,
                        'category': 'Fashion',
                        'image': 'fashion.jpg',
                        'discount': 5,
                        'stock_quantity': 28,
                        'specifications': '{"Material": "Premium Vegan Leather", "Dimensions": "30x20x12 cm", "Compartments": "2 Main + 3 Zip pockets"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1584917865442-de89df76afd3?q=80&w=600',
                            'https://images.unsplash.com/photo-1590874103328-eac38a683ce7?q=80&w=600',
                            'https://images.unsplash.com/photo-1566150905458-1bf1fc15a7a0?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Deepika Roy', 'rating': 4, 'title': 'Very chic', 'text': 'Perfect size for carrying my tablet and planner. The stitching is clean and color is exactly as pictured.', 'verified': True}
                        ]
                    },
                    {
                        'name': 'Book: Learn Python',
                        'brand': 'O\'Publish',
                        'description': 'Comprehensive modern guide to programming and algorithm implementations using Python. Full of clean mock exercises.',
                        'price': 499,
                        'category': 'Books',
                        'image': 'book.jpg',
                        'discount': 0,
                        'stock_quantity': 60,
                        'specifications': '{"Author": "Dr. Sarah Jenkins", "Format": "Paperback", "Pages": "450 Pages", "Edition": "4th Revised"}',
                        'gallery': [
                            'https://images.unsplash.com/photo-1515879218367-8466d910aaa4?q=80&w=600',
                            'https://images.unsplash.com/photo-1532012197267-da84d127e765?q=80&w=600',
                            'https://images.unsplash.com/photo-1506880018603-83d5b814b5a6?q=80&w=600'
                        ],
                        'reviews': [
                            {'username': 'Rohan Sharma', 'rating': 5, 'title': 'Best beginner resource', 'text': 'Dr. Jenkins explains complex programming ideas with beautiful simplicity. Exercises are super practical.', 'verified': True},
                            {'username': 'Amit Verma', 'rating': 4, 'title': 'Great textbook', 'text': 'Extremely thorough. The chapter on object-oriented programming is the best I have ever read.', 'verified': True}
                        ]
                    }
                ]

                for prod_data in sample_products:
                    # Find category id
                    cat = Category.query.filter_by(name=prod_data['category']).first()
                    cat_id = cat.id if cat else None
                    
                    p = Product(
                        name=prod_data['name'],
                        brand=prod_data['brand'],
                        description=prod_data['description'],
                        price=prod_data['price'],
                        category=prod_data['category'],
                        category_id=cat_id,
                        image=prod_data['image'],
                        discount=prod_data['discount'],
                        stock_quantity=prod_data['stock_quantity'],
                        specifications=prod_data['specifications']
                    )
                    db.session.add(p)
                    db.session.flush() # Flush to get product ID for gallery and reviews

                    # Add gallery images
                    for img_url in prod_data['gallery']:
                        img_rec = ProductImage(product_id=p.id, image_url=img_url)
                        db.session.add(img_rec)

                    # Add reviews
                    for rev_data in prod_data['reviews']:
                        u_id = seeded_users.get(rev_data['username'])
                        if u_id:
                            r = Review(
                                user_id=u_id,
                                product_id=p.id,
                                rating=rev_data['rating'],
                                title=rev_data['title'],
                                review_text=rev_data['text'],
                                verified_purchase=rev_data['verified'],
                                created_at=datetime.utcnow() - timedelta(days=secrets.randbelow(30) + 1)
                            )
                            db.session.add(r)

                db.session.commit()
                app.logger.info("Sample products, galleries, and verified reviews added successfully")
                
        except Exception as e:
            app.logger.error(f"Database initialization error: {e}")
            db.session.rollback()
            raise

def init_database():
    try:
        with app.app_context():
            # Test connection before creating tables
            from sqlalchemy import text
            engine = db.engine
            connection = engine.connect()
            connection.execute(text('SELECT 1'))
            connection.close()
            
            # Create tables
            db.create_all()
            app.logger.info("Database tables created successfully")
            
            # Initialize admin user
            if not User.query.filter_by(email='admin@example.com').first():
                admin = User(
                    username='admin',
                    email='admin@example.com',
                    password_hash=generate_password_hash('admin123'),
                    _is_admin=True
                )
                db.session.add(admin)
                db.session.commit()
                app.logger.info("Admin user created")
            return True
            
    except Exception as e:
        app.logger.error(f"Database initialization error: {str(e)}")
        return False

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
@app.route('/register', methods=['POST'])
def register():
    app.logger.info('Register route called')
    data = request.form
    app.logger.debug(f'Form data: {data}')
    
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    confirm_password = data.get('confirm_password')

    # Validate required fields
    if not all([name, email, password, confirm_password]):
        app.logger.warning('Missing required fields')
        flash('Please fill out all required fields.')
        return redirect(url_for('show_register'))

    if password != confirm_password:
        app.logger.warning('Passwords do not match')
        flash('Passwords do not match.')
        return redirect(url_for('show_register'))

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        app.logger.warning(f'Email already registered: {email}')
        flash('Email already registered.')
        return redirect(url_for('show_register'))

    try:
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=name,  # Changed from 'name'
            email=email,
            phone=phone,
            password_hash=hashed_password,
            _is_admin=False
        )
        db.session.add(new_user)
        db.session.commit()
        app.logger.info(f'User registered successfully: {email}')
        
        # Trigger welcome email system
        MailHelper.send_welcome_email(new_user.email, new_user.username)
        
        flash('Registration successful. Please log in.')
        return redirect(url_for('show_login'))
        
    except Exception as e:
        app.logger.error(f'Registration error: {e}')
        db.session.rollback()
        flash('An error occurred during registration. Please try again.')
        return redirect(url_for('show_register'))

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
        flash('Login successful.')
        MailHelper.send_login_notification_email(user.email, user.username)
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
    return products

# Products listing route
@app.route('/products')
def products():
    products = Product.query.all()
    product_list = prepare_product_list(products)
    return render_template('products.html', products=product_list)

# Category products route
@app.route('/category/<category_name>')
def category_products(category_name):
    products = Product.query.filter(Product.category == category_name).all()
    product_list = prepare_product_list(products)
    return render_template('products.html', products=product_list, category=category_name)

# Product detail route
@app.route('/product/<int:product_id>', methods=['GET'])
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    reviews = Review.query.filter_by(product_id=product_id).order_by(Review.created_at.desc()).all()
    avg_rating = round(sum([r.rating for r in reviews]) / len(reviews), 1) if reviews else 0
    
    # Prepare review data for template
    review_list = []
    for r in reviews:
        review_list.append({
            'username': r.username,
            'created_at': r.created_at,
            'rating': r.rating,
            'title': r.title or ('Verified Purchase' if r.verified_purchase else 'Customer Review'),
            'review_text': r.review_text,
            'verified_purchase': r.verified_purchase or False,
            'helpful_count': r.helpful_count or 0
        })
    
    # Related products: in the same category, excluding current product
    related = Product.query.filter(Product.category == product.category, Product.id != product.id).limit(4).all()
    
    # Decode specifications
    import json
    try:
        specs_dict = json.loads(product.specifications) if product.specifications else {}
    except Exception:
        specs_dict = {}
        
    return render_template(
        'product_detail.html',
        product=product,
        reviews=review_list,
        avg_rating=avg_rating,
        related_products=related,
        specs=specs_dict,
        now=datetime.utcnow,
        timedelta=timedelta
    )

# Add review route
@app.route('/add_review/<int:product_id>', methods=['POST'])
@login_required
def add_review(product_id):
    rating = int(request.form.get('rating'))
    review_text = request.form.get('review_text')
    title = request.form.get('title', '')
    
    # Check if this user has any completed/confirmed order containing this product
    from models import Order, OrderItem
    verified = db.session.query(OrderItem).join(Order).filter(
        Order.user_id == current_user.id,
        OrderItem.product_id == product_id,
        Order.status.in_(['confirmed', 'delivered', 'shipped'])
    ).first() is not None
    
    new_review = Review(
        user_id=current_user.id,
        product_id=product_id,
        rating=rating,
        title=title or ('Verified Purchase' if verified else 'Review'),
        review_text=review_text,
        verified_purchase=verified,
        created_at=datetime.utcnow()
    )
    db.session.add(new_review)
    db.session.commit()
    flash('Review added successfully!')
    return redirect(url_for('product_detail', product_id=product_id))


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
    app.logger.info(f"/cart accessed by user_id={getattr(current_user, 'id', None)}, is_authenticated={getattr(current_user, 'is_authenticated', None)}")
    try:
        cart_items = CartModel.query.filter_by(user_id=current_user.id).all()
        app.logger.info(f"Cart items found for user {current_user.id}: {cart_items}")
        items = []
        total = 0
        for cart_item in cart_items:
            product = Product.query.get(cart_item.product_id)
            if product:
                price = product.price
                if hasattr(product, 'discount') and product.discount:
                    price = price * (1 - product.discount/100)
                subtotal = price * cart_item.quantity
                total += subtotal
                items.append({
                    'product': product,
                    'quantity': cart_item.quantity,
                    'subtotal': subtotal,
                    'unit_price': price
                })
        app.logger.info(f"Items to render: {items}")
        return render_template('cart.html', items=items, total=total)
    except Exception as e:
        app.logger.error(f"Error in /cart route: {str(e)}")
        return render_template('errors/500.html'), 500

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

# Checkout route
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    # Fetch cart items from the Cart table for the current user
    cart_items = CartModel.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Your cart is empty.')
        return redirect(url_for('cart'))

    if request.method == 'POST':
        # Validate stock availability before creating order
        for cart_item in cart_items:
            product = Product.query.get(cart_item.product_id)
            if not product or product.stock_quantity < cart_item.quantity:
                flash(f'Sorry, {product.name} is out of stock or has insufficient quantity.')
                return redirect(url_for('cart'))

        address_line = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        zip_code = request.form.get('zip')

        # Handle persistent address saving
        from models import Address
        if request.form.get('save_address') == 'on':
            existing_addr = Address.query.filter_by(
                user_id=current_user.id,
                address_line=address_line,
                city=city,
                state=state,
                zip_code=zip_code
            ).first()
            if not existing_addr:
                db.session.query(Address).filter_by(user_id=current_user.id).update({Address.is_default: False})
                new_addr = Address(
                    user_id=current_user.id,
                    address_line=address_line,
                    city=city,
                    state=state,
                    zip_code=zip_code,
                    is_default=True
                )
                db.session.add(new_addr)

        # Create new order
        new_order = Order(
            user_id=current_user.id,
            shipping_address=address_line,
            shipping_city=city,
            shipping_state=state,
            shipping_zip=zip_code,
            status='pending'
        )
        db.session.add(new_order)
        try:
            db.session.flush()
            
            # Add order items and update stock
            for cart_item in cart_items:
                product = Product.query.get(cart_item.product_id)
                if not product.update_stock(cart_item.quantity):
                    db.session.rollback()
                    flash(f'Sorry, {product.name} went out of stock.')
                    return redirect(url_for('cart'))
                order_item = OrderItem(
                    order_id=new_order.id,
                    product_id=cart_item.product_id,
                    quantity=cart_item.quantity,
                    price_at_time=product.price,
                    discount_at_time=product.discount
                )
                db.session.add(order_item)
                
            standard_amount = sum(Product.query.get(item.product_id).get_discounted_price() * item.quantity for item in cart_items)
            
            # Coupons processing
            from models import Coupon
            coupon_code = request.form.get('coupon_code', '').strip().upper()
            discount_percent = 0
            if coupon_code:
                coupon = Coupon.query.filter_by(code=coupon_code, active=True).first()
                if coupon:
                    discount_percent = coupon.discount_percent
                    standard_amount = standard_amount * (1 - discount_percent / 100)
                    flash(f'Coupon {coupon_code} applied! {discount_percent}% off.')
                else:
                    flash('Invalid or inactive coupon code.')

            # Create payment record
            payment = Payment(
                order_id=new_order.id,
                amount=standard_amount,
                payment_status='pending',
                payment_method=request.form.get('payment_method', 'credit_card')
            )
            db.session.add(payment)
            # Clear user's cart in the database
            for cart_item in cart_items:
                db.session.delete(cart_item)
            db.session.commit()
            return redirect(url_for('payment_process', order_id=new_order.id))
        except Exception as e:
            app.logger.error(f'Order creation failed: {str(e)}')
            db.session.rollback()
            flash('There was an error processing your order. Please try again.')
            return redirect(url_for('cart'))

    # GET request - show checkout form
    items = []
    total = 0
    for cart_item in cart_items:
        product = Product.query.get(cart_item.product_id)
        if product:
            price = product.get_discounted_price()
            subtotal = price * cart_item.quantity
            total += subtotal
            items.append({
                'product': product,
                'quantity': cart_item.quantity,
                'subtotal': subtotal,
                'unit_price': price
            })
    return render_template('checkout.html', 
                         items=items, 
                         total=total,
                         user=current_user)

@app.route('/order_confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return render_template('order_confirmation.html', order=order)

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
    query = request.args.get('q', '').strip()
    if not query:
        flash('Please enter a search term.')
        return redirect(url_for('products'))
    products = Product.query.filter(Product.name.ilike(f'%{query}%')).all()
    return render_template('products.html', products=products, search_query=query)

# Admin page route
@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)
    products = Product.query.all()
    
    # Sales Metrics
    total_sales = db.session.query(db.func.sum(Payment.amount)).filter(Payment.payment_status == 'completed').scalar() or 0
    total_orders = Order.query.count()
    low_stock_count = Product.query.filter(Product.stock_quantity < 10).count()
    low_stock_products = Product.query.filter(Product.stock_quantity < 10).all()
    users_count = User.query.count()
    
    # Category sales/product distribution
    from collections import Counter
    cat_counts = Counter([p.category for p in products if p.category])
    categories_labels = list(cat_counts.keys())
    categories_data = list(cat_counts.values())
    
    # Daily sales trend for the last 7 days
    from datetime import timedelta, datetime
    today = datetime.utcnow()
    days_labels = []
    sales_data = []
    for i in range(6, -1, -1):
        day_date = today - timedelta(days=i)
        day_str = day_date.strftime('%b %d')
        days_labels.append(day_str)
        # Sum payments on this specific date
        day_sales = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.payment_status == 'completed',
            db.func.date(Payment.payment_date) == day_date.date()
        ).scalar() or 0
        sales_data.append(float(day_sales))
        
    # Top products by rating/stock
    top_products = Product.query.limit(5).all()
    
    return render_template('admin.html', 
                           products=products,
                           total_sales=total_sales,
                           total_orders=total_orders,
                           low_stock_count=low_stock_count,
                           low_stock_products=low_stock_products,
                           users_count=users_count,
                           top_products=top_products,
                           categories_labels=categories_labels,
                           categories_data=categories_data,
                           days_labels=days_labels,
                           sales_data=sales_data)


# Admin add product route
@app.route('/admin/add', methods=['POST'])
@admin_required
def admin_add_product():
    name = request.form.get('name')
    brand = request.form.get('brand')
    description = request.form.get('description')
    price = request.form.get('price')
    image = request.form.get('image')
    category = request.form.get('category')
    discount = request.form.get('discount', 0)
    stock_quantity = request.form.get('stock_quantity', 0)
    specifications = request.form.get('specifications', '')
    
    if not all([name, description, price, image, category]):
        flash('All fields are required.')
        return redirect(url_for('admin'))
        
    product = Product(
        name=name,
        brand=brand,
        description=description,
        price=float(price),
        image=image,
        category=category,
        discount=int(discount) if discount else 0,
        stock_quantity=int(stock_quantity) if stock_quantity else 0,
        specifications=specifications
    )
    db.session.add(product)
    db.session.commit()
    flash('Product added successfully!')
    return redirect(url_for('admin'))

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
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.brand = request.form.get('brand')
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.image = request.form.get('image')
        product.category = request.form.get('category')
        discount = request.form.get('discount', 0)
        product.discount = int(discount) if discount else 0
        stock_quantity = request.form.get('stock_quantity', 0)
        product.stock_quantity = int(stock_quantity) if stock_quantity else 0
        product.specifications = request.form.get('specifications', '')
        db.session.commit()
        flash('Product updated successfully!')
        return redirect(url_for('admin'))
    return render_template('admin_edit_product.html', product=product)


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
            'price': 1599,
            'category': 'Beauty',
            'image': 'beauty.jpg',
            'discount': 10,
            'stock_quantity': 22
        },
        {
            'name': 'Fashion Handbag',
            'description': 'Trendy handbag to complement your style.',
            'price': 2199,
            'category': 'Fashion',
            'image': 'fashion.jpg',
            'discount': 5,
            'stock_quantity': 28
        },
        {
            'name': 'Book: Learn Python',
            'description': 'Comprehensive guide to learning Python programming.',
            'price': 499,
            'category': 'Books',
            'image': 'book.jpg',
            'discount': 0,
            'stock_quantity': 60
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

# ==========================================
# WISHLIST ROUTES
# ==========================================
@app.route('/wishlist')
@login_required
def wishlist():
    from models import Wishlist
    items = Wishlist.query.filter_by(user_id=current_user.id).all()
    return render_template('wishlist.html', items=items)

@app.route('/add_to_wishlist/<int:product_id>', methods=['POST'])
@login_required
def add_to_wishlist(product_id):
    from models import Wishlist
    existing = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if not existing:
        item = Wishlist(user_id=current_user.id, product_id=product_id)
        db.session.add(item)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Added to wishlist'})
    return jsonify({'success': False, 'message': 'Already in wishlist'})

@app.route('/remove_from_wishlist/<int:product_id>', methods=['POST'])
@login_required
def remove_from_wishlist(product_id):
    from models import Wishlist
    item = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Removed from wishlist'})
    return jsonify({'success': False, 'message': 'Item not in wishlist'})

# ==========================================
# PROFILE & ADDRESS MANAGEMENT ROUTES
# ==========================================
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    from models import Address
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_profile':
            current_user.username = request.form.get('username')
            current_user.phone = request.form.get('phone')
            db.session.commit()
            flash('Profile updated successfully!')
        elif action == 'add_address':
            address_line = request.form.get('address_line')
            city = request.form.get('city')
            state = request.form.get('state')
            zip_code = request.form.get('zip_code')
            is_default = request.form.get('is_default') == 'on'
            
            if is_default:
                db.session.query(Address).filter_by(user_id=current_user.id).update({Address.is_default: False})
                
            new_addr = Address(
                user_id=current_user.id,
                address_line=address_line,
                city=city,
                state=state,
                zip_code=zip_code,
                is_default=is_default
            )
            db.session.add(new_addr)
            db.session.commit()
            flash('Address added successfully!')
        elif action == 'delete_address':
            addr_id = int(request.form.get('address_id'))
            addr = Address.query.filter_by(id=addr_id, user_id=current_user.id).first()
            if addr:
                db.session.delete(addr)
                db.session.commit()
                flash('Address deleted!')
        return redirect(url_for('profile'))
        
    addresses = Address.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html', user=current_user, addresses=addresses)

# ==========================================
# FORGOT PASSWORD ROUTE
# ==========================================
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            
            # Send security reset notification email
            MailHelper.send_password_reset_email(user.email, user.username)
            
            flash('Password reset successful! Please log in.')
            return redirect(url_for('show_login'))
        else:
            flash('Email not found.')
    return render_template('forgot_password.html')

# ==========================================
# PAYMENT GATEWAY SIMULATOR ROUTES
# ==========================================
@app.route('/payment/process/<int:order_id>', methods=['GET', 'POST'])
@login_required
def payment_process(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        abort(403)
        
    if request.method == 'POST':
        action = request.form.get('action')
        payment_record = Payment.query.filter_by(order_id=order_id).first()
        
        if action == 'success':
            if payment_record:
                payment_record.payment_status = 'completed'
                payment_record.transaction_id = 'TXN-' + secrets.token_hex(8).upper()
            order.status = 'confirmed'
            db.session.commit()
            
            # Trigger order confirmation email receipt
            MailHelper.send_order_confirmation_email(order.user.email, order.user.username, order)
            
            flash('Payment Successful!')
            return redirect(url_for('order_confirmation', order_id=order_id))
        elif action == 'failure':
            if payment_record:
                payment_record.payment_status = 'failed'
            order.status = 'cancelled'
            
            # Restore stock
            for item in order.items:
                prod = Product.query.get(item.product_id)
                if prod:
                    prod.stock_quantity += item.quantity
            
            db.session.commit()
            flash('Payment Failed! Order Cancelled.')
            return render_template('payment_process.html', order=order, status='failed')
            
    return render_template('payment_process.html', order=order, status='pending')

# ==========================================
# ADMIN CATEGORY CRUD ROUTES
# ==========================================
@app.route('/admin/categories', methods=['GET', 'POST'])
@admin_required
def admin_categories():
    from models import Category
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        existing = Category.query.filter_by(name=name).first()
        if existing:
            flash('Category already exists!')
        else:
            new_cat = Category(name=name, description=description)
            db.session.add(new_cat)
            db.session.commit()
            flash('Category added successfully!')
        return redirect(url_for('admin_categories'))
        
    categories = Category.query.all()
    return render_template('admin_categories.html', categories=categories)

@app.route('/admin/categories/delete/<int:cat_id>', methods=['POST'])
@admin_required
def admin_categories_delete(cat_id):
    from models import Category
    cat = Category.query.get_or_404(cat_id)
    db.session.delete(cat)
    db.session.commit()
    flash('Category deleted successfully!')
    return redirect(url_for('admin_categories'))

# ==========================================
# ADMIN COUPONS CRUD ROUTES
# ==========================================
@app.route('/admin/coupons', methods=['GET', 'POST'])
@admin_required
def admin_coupons():
    from models import Coupon
    if request.method == 'POST':
        code = request.form.get('code').strip().upper()
        discount_percent = int(request.form.get('discount_percent'))
        existing = Coupon.query.filter_by(code=code).first()
        if existing:
            flash('Coupon already exists!')
        else:
            new_coupon = Coupon(code=code, discount_percent=discount_percent)
            db.session.add(new_coupon)
            db.session.commit()
            flash('Coupon created successfully!')
        return redirect(url_for('admin_coupons'))
        
    coupons = Coupon.query.all()
    return render_template('admin_coupons.html', coupons=coupons)

@app.route('/admin/coupons/delete/<int:coupon_id>', methods=['POST'])
@admin_required
def admin_coupons_delete(coupon_id):
    from models import Coupon
    coupon = Coupon.query.get_or_404(coupon_id)
    db.session.delete(coupon)
    db.session.commit()
    flash('Coupon deleted successfully!')
    return redirect(url_for('admin_coupons'))

# ==========================================
# ADMIN ORDER MANAGEMENT ROUTES
# ==========================================
@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.id.desc()).all()
    return render_template('admin_orders.html', orders=orders)

@app.route('/admin/orders/update/<int:order_id>', methods=['POST'])
@admin_required
def admin_orders_update(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get('status')
    tracking_number = request.form.get('tracking_number')
    notes = request.form.get('notes')
    
    if status:
        order.status = status
    if tracking_number:
        order.tracking_number = tracking_number
    if notes:
        order.notes = notes
        
    db.session.commit()
    
    # Trigger order status update notification email
    MailHelper.send_order_status_update_email(order.user.email, order.user.username, order, order.status)
    
    flash('Order updated successfully!')
    return redirect(url_for('admin_orders'))

if __name__ == '__main__':
    app.run(debug=True)
