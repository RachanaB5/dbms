-- Create the database
drop database if exists EcommerceDB;
CREATE DATABASE EcommerceDB;
USE EcommerceDB;

-- Users Table
CREATE TABLE Users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data into Users
INSERT INTO Users (username, email, password_hash) VALUES
('john_doe', 'john@example.com', 'hashedpassword1'),
('jane_smith', 'jane@example.com', 'hashedpassword2'),
('alice_johnson', 'alice@example.com', 'hashedpassword3'),
('bob_williams', 'bob@example.com', 'hashedpassword4'),
('charlie_brown', 'charlie@example.com', 'hashedpassword5'),
('dave_clark', 'dave@example.com', 'hashedpassword6'),
('eve_miller', 'eve@example.com', 'hashedpassword7');

-- Products Table
CREATE TABLE Products (
    product_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INT NOT NULL
);

-- Insert sample data into Products
INSERT INTO Products (name, description, price, stock_quantity) VALUES
('Laptop', 'High-performance laptop', 1200.00, 50),
('Smartphone', 'Latest model smartphone', 800.00, 100),
('Headphones', 'Noise-canceling headphones', 150.00, 75),
('Smartwatch', 'Waterproof smartwatch', 200.00, 60),
('Tablet', 'Lightweight tablet', 500.00, 80),
('Gaming Console', 'Next-gen gaming console', 700.00, 40),
('Wireless Mouse', 'Ergonomic wireless mouse', 50.00, 150);


-- Orders Table
CREATE TABLE Orders (
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    total_amount DECIMAL(10,2) NOT NULL,
    status ENUM('Pending', 'Shipped', 'Delivered', 'Cancelled') DEFAULT 'Pending',
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
);

-- Insert sample data into Orders
INSERT INTO Orders (user_id, total_amount, status) VALUES
(1, 1200.00, 'Shipped'),
(2, 800.00, 'Delivered'),
(3, 150.00, 'Pending'),
(4, 200.00, 'Cancelled'),
(5, 500.00, 'Shipped'),
(6, 700.00, 'Delivered'),
(7, 50.00, 'Pending');

-- Cart Table
CREATE TABLE Cart (
    cart_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    product_id INT,
    quantity INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES Products(product_id) ON DELETE CASCADE
);

-- Insert sample data into Cart
INSERT INTO Cart (user_id, product_id, quantity) VALUES
(1, 1, 1),
(2, 2, 1),
(3, 3, 2),
(4, 4, 1),
(5, 5, 1),
(6, 6, 1),
(7, 7, 2);

-- Reviews Table
CREATE TABLE Reviews (
    review_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    product_id INT,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES Products(product_id) ON DELETE CASCADE
);

-- Insert sample data into Reviews
INSERT INTO Reviews (user_id, product_id, rating, review_text) VALUES
(1, 1, 5, 'Excellent product!'),
(2, 2, 4, 'Very good but a bit expensive.'),
(3, 3, 3, 'Average quality.'),
(4, 4, 5, 'Loved it!'),
(5, 5, 4, 'Useful and handy device.'),
(6, 6, 5, 'Amazing gaming experience!'),
(7, 7, 3, 'Not bad, but could be better.');

-- Payments Table
CREATE TABLE Payments (
    payment_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    order_id INT,
    amount DECIMAL(10,2) NOT NULL,
    payment_status ENUM('Pending', 'Completed', 'Failed') DEFAULT 'Pending',
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES Orders(order_id) ON DELETE CASCADE
);

-- Insert sample data into Payments
INSERT INTO Payments (user_id, order_id, amount, payment_status) VALUES
(1, 1, 1200.00, 'Completed'),
(2, 2, 800.00, 'Completed'),
(3, 3, 150.00, 'Pending'),
(4, 4, 200.00, 'Failed'),
(5, 5, 500.00, 'Completed'),
(6, 6, 700.00, 'Completed'),
(7, 7, 50.00, 'Pending');

-- Stored Procedure for Applying Discount on High Orders
DELIMITER //
CREATE PROCEDURE ApplyDiscount(IN orderID INT)
BEGIN
    UPDATE Orders 
    SET total_amount = total_amount * 0.90 -- 10% Discount
    WHERE order_id = orderID AND total_amount > 500;
END //
DELIMITER ;

-- Stored Procedure for Processing Refunds
DELIMITER //
CREATE PROCEDURE ProcessRefund(IN orderID INT)
BEGIN
    DECLARE orderAmount DECIMAL(10,2);
    SELECT total_amount INTO orderAmount FROM Orders WHERE order_id = orderID;
    INSERT INTO Refunds (order_id, amount, refund_status) VALUES (orderID, orderAmount, 'Processed');
END //
DELIMITER ;

-- Security: Logging User Authentication
CREATE TABLE UserAuthLogs (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
);

DELIMITER //
CREATE TRIGGER LogUserLogin
AFTER INSERT ON Users
FOR EACH ROW
BEGIN
    INSERT INTO UserAuthLogs (user_id) VALUES (NEW.id);
END //
DELIMITER ;

-- 1. Find total revenue for each month
SELECT DATE_FORMAT(order_date, '%Y-%m') AS month, SUM(total_amount) AS total_revenue
FROM Orders
GROUP BY month;

-- 2. Get the top 5 best-selling products
SELECT p.name, COUNT(o.order_id) AS sales_count
FROM Orders o
JOIN Cart c ON o.user_id = c.user_id
JOIN Products p ON c.product_id = p.product_id
GROUP BY p.name
ORDER BY sales_count DESC
LIMIT 5;

-- 3. Find customers who have spent the most
SELECT u.username, SUM(o.total_amount) AS total_spent
FROM Users u
JOIN Orders o ON u.id = o.user_id
GROUP BY u.username
ORDER BY total_spent DESC
LIMIT 10;

-- 4. Retrieve details of unshipped orders
SELECT * FROM Orders WHERE status = 'Pending';

-- 5. List all customers who have never placed an order
SELECT username FROM Users WHERE id NOT IN (SELECT DISTINCT user_id FROM Orders);

-- 7. Identify products with low stock
SELECT name, stock_quantity FROM Products WHERE stock_quantity < 10;

-- 8. Get all reviews with product names
SELECT p.name AS product_name, r.rating, r.review_text
FROM Reviews r
JOIN Products p ON r.product_id = p.product_id;

-- 9. Count the number of orders for each order status
SELECT status, COUNT(*) AS count
FROM Orders
GROUP BY status;

-- 10. List all payments that are pending
SELECT * FROM Payments WHERE payment_status = 'Pending';

UPDATE Users SET password_hash = SHA2('hashedpassword1', 256) WHERE id = 1;
ALTER TABLE Cart ADD CONSTRAINT unique_cart UNIQUE (user_id, product_id);

DELIMITER //
CREATE TRIGGER ReduceStock AFTER INSERT ON Orders
FOR EACH ROW
BEGIN
    UPDATE Products 
    SET stock_quantity = stock_quantity - (SELECT quantity FROM Cart WHERE user_id = NEW.user_id)
    WHERE product_id IN (SELECT product_id FROM Cart WHERE user_id = NEW.user_id);
END //
DELIMITER ;

-- Total Revenue
SELECT SUM(total_amount) AS Total_Revenue FROM Orders WHERE status = 'Delivered';

-- Top-Selling Products
SELECT p.name, COUNT(o.order_id) AS Orders_Count
FROM Orders o
JOIN Cart c ON o.user_id = c.user_id
JOIN Products p ON c.product_id = p.product_id
GROUP BY p.name
ORDER BY Orders_Count DESC
LIMIT 5;
ALTER TABLE users MODIFY password_hash VARCHAR(256);

ALTER TABLE products ADD COLUMN category VARCHAR(50);
ALTER TABLE products ADD COLUMN image VARCHAR(100);
ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;

SHOW TABLES;
SELECT * FROM users;
SELECT * FROM cart;

-- Correct sequence for users table
ALTER TABLE users DROP PRIMARY KEY;
ALTER TABLE users CHANGE user_id id INT AUTO_INCREMENT PRIMARY KEY;

-- Remove duplicate add column for discount
ALTER TABLE products ADD COLUMN discount INT DEFAULT 0;

INSERT INTO products (product_id, name, description, price, stock_quantity, image, discount, category) VALUES
(1, 'Laptop', 'High-performance laptop for work and play.', 74899.00, 50, 'laptop.jpg', 10, 'Electronics'),
(2, 'Smartphone', 'Latest model smartphone with advanced features.', 24999.00, 100, 'smart-phone.jpg', 8, 'Electronics'),
(3, 'Headphones', 'Noise-canceling headphones for music lovers.', 2999.00, 75, 'headphones.jpg', 12, 'Electronics'),
(4, 'Smartwatch', 'Waterproof smartwatch with fitness tracking.', 2499.00, 60, 'smart-watch.jpg', 5, 'Electronics'),
(5, 'Tablet', 'Lightweight tablet for entertainment and productivity.', 39999.00, 80, 'tablet.jpg', 15, 'Electronics'),
(6, 'Gaming Console', 'Next-gen gaming console for immersive experiences.', 79999.00, 40, 'gaming-console.jpg', 0, 'Gadgets'),
(7, 'Wireless Mouse', 'Ergonomic wireless mouse for smooth navigation.', 1999.00, 150, 'mouse.jpg', 0, 'Gadgets'),
(8, 'Smart Watch', 'Track your fitness and notifications on the go.', 2999.00, 30, 'smart-watch.jpg', 5, 'Electronics'),
(9, 'Home Decor Set', 'Beautiful decor set to enhance your living space.', 122499.00, 18, 'home.jpg', 20, 'Home & Kitchen'),
(10, 'Beauty Kit', 'Complete beauty kit for your daily routine.', 1599.00, 22, 'beauty.jpg', 10, 'Beauty'),
(11, 'Fashion Handbag', 'Trendy handbag to complement your style.', 2199.00, 28, 'fashion.jpg', 5, 'Fashion'),
(12, 'Book: Learn Python', 'Comprehensive guide to learning Python programming.', 499.00, 60, 'book.jpg', 0, 'Books'),
(13, 'Keyboard', 'Mechanical keyboard for fast and accurate typing.', 3499.00, 35, 'keyboard.jpg', 0, 'Electronics');

SELECT * FROM users;
SELECT * FROM cart;

-- === USER ID COLUMN MIGRATION FOR FLASK/SQLALCHEMY COMPATIBILITY ===
-- 1. Drop foreign keys referencing users.user_id
ALTER TABLE Orders DROP FOREIGN KEY orders_ibfk_1;
ALTER TABLE Cart DROP FOREIGN KEY cart_ibfk_1;
ALTER TABLE Reviews DROP FOREIGN KEY reviews_ibfk_1;
ALTER TABLE Payments DROP FOREIGN KEY payments_ibfk_1;

-- 2. Remove AUTO_INCREMENT from user_id (if needed)
ALTER TABLE Users MODIFY user_id INT;

-- 3. Drop primary key
ALTER TABLE Users DROP PRIMARY KEY;

-- 4. Rename user_id to id and set as AUTO_INCREMENT PRIMARY KEY
ALTER TABLE Users CHANGE user_id id INT AUTO_INCREMENT PRIMARY KEY;

-- 6. Recreate foreign keys to reference users.id
ALTER TABLE Orders ADD CONSTRAINT orders_ibfk_1 FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE;
ALTER TABLE Cart ADD CONSTRAINT cart_ibfk_1 FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE;
ALTER TABLE Reviews ADD CONSTRAINT reviews_ibfk_1 FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE;
ALTER TABLE Payments ADD CONSTRAINT payments_ibfk_1 FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE;

select * from users;
select * from products;
select * from orders;
select * from cart;      
