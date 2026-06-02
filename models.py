from extensions import db
from datetime import datetime
from flask_login import UserMixin

class User(UserMixin, db.Model):
    __tablename__ = 'users'  # Match existing table name
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    _is_admin = db.Column('is_admin', db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviews = db.relationship('Review', backref='user', lazy=True)
    orders = db.relationship('Order', backref='user', lazy=True)

    @property
    def is_admin(self):
        return self._is_admin

    @property
    def name(self):
        return self.username

    @property
    def address(self):
        default_addr = Address.query.filter_by(user_id=self.id, is_default=True).first()
        if not default_addr:
            default_addr = Address.query.filter_by(user_id=self.id).first()
        return default_addr.address_line if default_addr else None

    @property
    def city(self):
        default_addr = Address.query.filter_by(user_id=self.id, is_default=True).first()
        if not default_addr:
            default_addr = Address.query.filter_by(user_id=self.id).first()
        return default_addr.city if default_addr else None

    @property
    def zip_code(self):
        default_addr = Address.query.filter_by(user_id=self.id, is_default=True).first()
        if not default_addr:
            default_addr = Address.query.filter_by(user_id=self.id).first()
        return default_addr.zip_code if default_addr else None

    @property
    def state(self):
        default_addr = Address.query.filter_by(user_id=self.id, is_default=True).first()
        if not default_addr:
            default_addr = Address.query.filter_by(user_id=self.id).first()
        return default_addr.state if default_addr else None


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    image = db.Column(db.String(200), nullable=True)
    discount = db.Column(db.Integer, nullable=True, default=0)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    specifications = db.Column(db.Text, nullable=True)  # Store JSON string of technical parameters
    
    reviews = db.relationship('Review', backref='product', lazy=True)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)
    category_rel = db.relationship('Category', backref='products_list')

    def get_discounted_price(self):
        if self.discount:
            return self.price * (1 - self.discount/100)
        return self.price

    def update_stock(self, quantity):
        if self.stock_quantity >= quantity:
            self.stock_quantity -= quantity
            return True
        return False

    @property
    def rating(self):
        reviews = self.reviews
        review_count = len(reviews)
        return int(round(sum([r.rating for r in reviews]) / review_count)) if review_count else 0

    @property
    def reviews_count(self):
        return len(self.reviews)

class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    product = db.relationship('Product', backref=db.backref('gallery_images', lazy=True, cascade="all, delete-orphan"))

class Review(db.Model):
    __tablename__ = 'reviews'  # Match existing table name
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(100), nullable=True)
    review_text = db.Column(db.Text, nullable=True)
    verified_purchase = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    helpful_count = db.Column(db.Integer, default=0)

    @property
    def username(self):
        return self.user.username if self.user else 'User'

class Order(db.Model):
    __tablename__ = 'orders'  # Match existing table name
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, confirmed, shipped, delivered, cancelled
    items = db.relationship('OrderItem', backref='order', lazy=True)
    shipping_address = db.Column(db.Text, nullable=True)
    shipping_city = db.Column(db.String(100), nullable=True)
    shipping_state = db.Column(db.String(100), nullable=True)
    shipping_zip = db.Column(db.String(20), nullable=True)
    tracking_number = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    @property
    def total_amount(self):
        return sum(item.subtotal for item in self.items)

    def get_status_display(self):
        return self.status.title()

    @property
    def order_id(self):
        return self.id

    @property
    def order_date(self):
        return self.created_at

class OrderItem(db.Model):
    __tablename__ = 'order_items'  # Match existing table name
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_time = db.Column(db.Float, nullable=False)  # Store price at time of purchase
    discount_at_time = db.Column(db.Integer, nullable=True)  # Store discount at time of purchase

    @property
    def subtotal(self):
        if self.discount_at_time:
            discounted_price = self.price_at_time * (1 - self.discount_at_time/100)
            return discounted_price * self.quantity
        return self.price_at_time * self.quantity

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_status = db.Column(db.String(20), nullable=False)  # pending, completed, failed, refunded
    payment_method = db.Column(db.String(50), nullable=False)  # credit_card, debit_card, upi, net_banking
    transaction_id = db.Column(db.String(100), nullable=True)
    order = db.relationship('Order', backref=db.backref('payment', uselist=False), lazy=True)

class Cart(db.Model):
    __tablename__ = 'cart'
    id = db.Column('cart_id', db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    user = db.relationship('User', backref='cart_items', lazy=True)
    product = db.relationship('Product', backref='cart_entries', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Wishlist(db.Model):
    __tablename__ = 'wishlist'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='wishlist_items', lazy=True)
    product = db.relationship('Product', backref='wishlist_entries', lazy=True)

class Address(db.Model):
    __tablename__ = 'addresses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    address_line = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    user = db.relationship('User', backref='addresses_list', lazy=True)

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

class Coupon(db.Model):
    __tablename__ = 'coupons'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    discount_percent = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, default=True)
    expiry_date = db.Column(db.DateTime, nullable=True)
