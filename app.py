from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from functools import wraps
from extensions import db  # Import db from extensions
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:0555@localhost/EcommerceDB'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)  # Initialize db with app

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'show_login'

import logging

@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    logging.info(f"user_loader loaded user with id: {user_id}, found: {user is not None}")
    return user

# Import models after db initialization to avoid circular imports
from models import User, Product, Review, Order, OrderItem

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
    print('Register route called')
    data = request.form
    print('Form data:', data)
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    confirm_password = data.get('confirm_password')

    if not all([name, email, password, confirm_password]):
        print('Missing required fields')
        flash('Please fill out all required fields.')
        return redirect(url_for('show_register'))

    if password != confirm_password:
        print('Passwords do not match')
        flash('Passwords do not match.')
        return redirect(url_for('show_register'))

    existing_user = User.query.filter_by(email=email).first()
    print('Existing user:', existing_user)
    if existing_user:
        print('Email already registered')
        flash('Email already registered.')
        return redirect(url_for('show_register'))

    hashed_password = generate_password_hash(password)
    new_user = User(name=name, email=email, phone=phone, password_hash=hashed_password)
    db.session.add(new_user)
    try:
        db.session.commit()
        print('Registration successful')
    except Exception as e:
        print('DB commit error:', e)
        flash('Database error: ' + str(e))
        db.session.rollback()
        return redirect(url_for('show_register'))
    flash('Registration successful. Please log in.')
    return redirect(url_for('show_login'))

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
        return redirect(url_for('index'))
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
    products = Product.query.all()
    return render_template('base.html', products=products)

# Products listing route
@app.route('/products')
def products():
    products = Product.query.all()
    # Calculate review count and average rating for each product
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
    return render_template('products.html', products=product_list)

# Category products route
@app.route('/category/<category_name>')
def category_products(category_name):
    products = Product.query.filter(Product.category == category_name).all()
    return render_template('products.html', products=products, category=category_name)

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
            'username': r.user.name if r.user else 'User',
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
def add_to_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    cart = session.get('cart', {})
    if str(product_id) in cart:
        cart[str(product_id)] += quantity
    else:
        cart[str(product_id)] = quantity
    session['cart'] = cart
    flash('Product added to cart.')
    return redirect(url_for('cart'))

# Cart page route
@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    items = []
    total = 0
    for product_id, quantity in cart.items():
        product = Product.query.get(int(product_id))
        if product:
            subtotal = product.price * quantity
            total += subtotal
            items.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
    # Fetch 4 random featured products (excluding those already in cart)
    featured_products = Product.query.filter(~Product.id.in_([int(pid) for pid in cart.keys()])).order_by(db.func.random()).limit(4).all()
    return render_template('cart.html', items=items, total=total, featured_products=featured_products)

# Order confirmation route
@app.route('/order_confirmation', methods=['POST'])
def order_confirmation():
    if not current_user.is_authenticated:
        flash('Please log in to place an order.')
        return redirect(url_for('show_login'))

    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty.')
        return redirect(url_for('cart'))

    user_id = current_user.id
    new_order = Order(user_id=user_id, created_at=datetime.utcnow())
    db.session.add(new_order)
    db.session.commit()

    for product_id, quantity in cart.items():
        order_item = OrderItem(order_id=new_order.id, product_id=int(product_id), quantity=quantity)
        db.session.add(order_item)

    db.session.commit()
    session['cart'] = {}
    flash('Order placed successfully.')
    return render_template('order_confirmation.html', order=new_order)

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

# Checkout route
@app.route('/checkout', methods=['GET'])
def checkout():
    cart = session.get('cart', {})
    items = []
    total = 0
    for product_id, quantity in cart.items():
        product = Product.query.get(int(product_id))
        if product:
            subtotal = product.price * quantity
            total += subtotal
            items.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
    return render_template('checkout.html', products=items, total=total)

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
    # Example: You may want to fetch user-specific orders and reviews here
    orders = []
    reviews = []
    # If you have a user system, fetch orders/reviews for current_user
    return render_template('dashboard.html', orders=orders, reviews=reviews)

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
            'image': 'books.jpg',
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
