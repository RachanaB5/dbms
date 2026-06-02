import os
import unittest
from app import app, db
from models import User, Product, Category, Coupon, Wishlist, Address, Order, OrderItem, Payment, Cart as CartModel
from werkzeug.security import generate_password_hash

class ECommerceRestorationTest(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        
        self.client = app.test_client()
        
        with app.app_context():
            # Safely drop all existing tables to guarantee a clean slate
            from sqlalchemy import text
            db.session.execute(text('SET FOREIGN_KEY_CHECKS=0'))
            db.drop_all()
            db.session.execute(text('SET FOREIGN_KEY_CHECKS=1'))
            db.session.commit()
            
            # Create fresh tables
            db.create_all()
            
            # Seed Category
            self.cat1 = Category(name="Electronics", description="Test Category")
            db.session.add(self.cat1)
            
            # Seed Product
            self.prod1 = Product(
                name="Test Laptop",
                description="Fast test laptop",
                price=50000.0,
                category="Electronics",
                image="laptop.jpg",
                discount=10,
                stock_quantity=5
            )
            db.session.add(self.prod1)
            
            # Seed Coupon
            self.coupon = Coupon(code="SAVE10", discount_percent=10, active=True)
            db.session.add(self.coupon)
            
            # Seed Admin
            self.admin_user = User(
                username="admin",
                email="admin@example.com",
                password_hash=generate_password_hash("admin123"),
                _is_admin=True
            )
            db.session.add(self.admin_user)
            
            # Seed Standard User
            self.std_user = User(
                username="testuser",
                email="testuser@example.com",
                password_hash=generate_password_hash("password123"),
                _is_admin=False
            )
            db.session.add(self.std_user)
            db.session.commit()
            
            self.prod_id = self.prod1.id
            self.user_id = self.std_user.id
            self.admin_id = self.admin_user.id

    def tearDown(self):
        with app.app_context():
            from sqlalchemy import text
            db.session.execute(text('SET FOREIGN_KEY_CHECKS=0'))
            db.drop_all()
            db.session.execute(text('SET FOREIGN_KEY_CHECKS=1'))
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        # Restore the main development database to a pristine, seeded state after all tests finish
        from init_db import init_db
        init_db()

    def login_user(self, email, password):
        return self.client.post('/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    def logout_user(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_authentication_flow(self):
        # Register test
        response = self.client.post('/register', data={
            'name': 'newuser',
            'email': 'newuser@example.com',
            'phone': '1234567890',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b'Registration successful', response.data)

        # Login test
        response = self.login_user('newuser@example.com', 'password123')
        self.assertIn(b'newuser', response.data)

    def test_wishlist_operations(self):
        # Must log in first
        self.login_user('testuser@example.com', 'password123')
        
        # Add to wishlist
        response = self.client.post(f'/add_to_wishlist/{self.prod_id}', headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json().get('success'))
        
        # Check Wishlist Listing
        response = self.client.get('/wishlist')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Laptop', response.data)
        
        # Remove from wishlist
        response = self.client.post(f'/remove_from_wishlist/{self.prod_id}', headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json().get('success'))

    def test_profile_address_management(self):
        self.login_user('testuser@example.com', 'password123')
        
        # Add address
        response = self.client.post('/profile', data={
            'action': 'add_address',
            'address_line': '123 Test St',
            'city': 'TestCity',
            'state': 'TS',
            'zip_code': '12345',
            'is_default': 'on'
        }, follow_redirects=True)
        self.assertIn(b'Address added successfully', response.data)
        
        # Verify user address getter properties
        with app.app_context():
            u = User.query.get(self.user_id)
            self.assertEqual(u.address, '123 Test St')
            self.assertEqual(u.city, 'TestCity')
            self.assertEqual(u.state, 'TS')
            self.assertEqual(u.zip_code, '12345')

    def test_cart_and_checkout_flow(self):
        self.login_user('testuser@example.com', 'password123')
        
        # Add item to cart
        self.client.post(f'/add_to_cart/{self.prod_id}', data={'quantity': '2'}, follow_redirects=True)
        
        # Checkout with coupon application
        response = self.client.post('/checkout', data={
            'address': '123 Test St',
            'city': 'TestCity',
            'state': 'TS',
            'zip': '12345',
            'payment_method': 'card',
            'coupon_code': 'SAVE10',
            'save_address': 'on'
        }, follow_redirects=True)
        
        # The user should be redirected to the payment process simulator
        self.assertIn(b'Process Payment', response.data)
        self.assertIn(b'Simulate Payment Success', response.data)
        self.assertIn(b'Simulate Payment Failure', response.data)
        
        # Process Mock payment: Simulate success
        with app.app_context():
            o = Order.query.filter_by(user_id=self.user_id).first()
            order_id = o.id
            
        response = self.client.post(f'/payment/process/{order_id}', data={
            'action': 'success'
        }, follow_redirects=True)
        self.assertIn(b'Order Confirmation', response.data)
        
        with app.app_context():
            o = Order.query.get(order_id)
            p = Payment.query.filter_by(order_id=order_id).first()
            self.assertEqual(o.status, 'confirmed')
            self.assertEqual(p.payment_status, 'completed')
            # 2 Laptops purchased. Stock should decrease from 5 to 3
            prod = Product.query.get(self.prod_id)
            self.assertEqual(prod.stock_quantity, 3)

    def test_admin_dashboard_and_crud(self):
        self.login_user('admin@example.com', 'admin123')
        
        # Admin Analytics home
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sales Analytics', response.data)
        
        # Category CRUD
        response = self.client.post('/admin/categories', data={
            'name': 'Novelties',
            'description': 'Unique stuff'
        }, follow_redirects=True)
        self.assertIn(b'Category added successfully', response.data)
        
        # Coupon CRUD
        response = self.client.post('/admin/coupons', data={
            'code': 'HELLO50',
            'discount_percent': '50'
        }, follow_redirects=True)
        self.assertIn(b'Coupon created successfully', response.data)

if __name__ == '__main__':
    unittest.main()
