from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from extensions import db, login_manager
from models import User, Product, Review, Order, OrderItem, Payment, Cart as CartModel
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import secrets
import atexit

app = Flask(__name__)

# Security configurations
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'mysql+mysqlconnector://root:0555@localhost/EcommerceDB')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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

            # Initialize sample data only if products table is empty
            if Product.query.count() == 0:
                # Add sample products
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
            'username': r.user.username if r.user else 'User',
            'created_at': r.created_at,
            'rating': r.rating,
            'review_text': r.review_text,
            'helpful_count': r.helpful_count or 0
        })
    return render_template('product_detail.html', product=product, reviews=review_list, avg_rating=avg_rating, now=datetime.utcnow, timedelta=timedelta)

# Add review route
@app.route('/add_review/<int:product_id>', methods=['POST'])
@login_required
def add_review(product_id):
    rating = int(request.form.get('rating'))
    review_text = request.form.get('review_text')
    new_review = Review(user_id=current_user.id, product_id=product_id, rating=rating, review_text=review_text, created_at=datetime.utcnow())
    db.session.add(new_review)
    db.session.commit()
    flash('Review added!')
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

        # Create new order
        new_order = Order(
            user_id=current_user.id,
            shipping_address=request.form.get('address'),
            shipping_city=request.form.get('city'),
            shipping_state=request.form.get('state'),
            shipping_zip=request.form.get('zip'),
            status='pending'
        )
        db.session.add(new_order)
        try:
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
            # Create payment record
            payment = Payment(
                order_id=new_order.id,
                amount=sum(Product.query.get(item.product_id).get_discounted_price() * item.quantity for item in cart_items),
                payment_status='pending',
                payment_method=request.form.get('payment_method', 'credit_card')
            )
            db.session.add(payment)
            # Clear user's cart in the database
            for cart_item in cart_items:
                db.session.delete(cart_item)
            db.session.commit()
            flash('Order placed successfully! You will receive a confirmation email shortly.')
            return redirect(url_for('order_confirmation', order_id=new_order.id))
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
    return render_template('admin.html', products=products)

# Admin add product route
@app.route('/admin/add', methods=['POST'])
@admin_required
def admin_add_product():
    name = request.form.get('name')
    description = request.form.get('description')
    price = request.form.get('price')
    image = request.form.get('image')
    category = request.form.get('category')
    if not all([name, description, price, image, category]):
        flash('All fields are required.')
        return redirect(url_for('admin'))
    product = Product(name=name, description=description, price=price, image=image, category=category)
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
        product.description = request.form.get('description')
        product.price = request.form.get('price')
        product.image = request.form.get('image')
        product.category = request.form.get('category')
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

if __name__ == '__main__':
    # init_db()
    app.run(debug=True)
