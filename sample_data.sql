-- ============================================
-- QueryEase Sample Ecommerce Database
-- ============================================

-- Customers
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    city VARCHAR(100),
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Categories
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

-- Products
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    category_id INT REFERENCES categories(id),
    price DECIMAL(10,2) NOT NULL,
    stock INT DEFAULT 0
);

-- Orders
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id),
    status VARCHAR(50) DEFAULT 'pending',
    total DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Order Items
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(id),
    product_id INT REFERENCES products(id),
    quantity INT NOT NULL,
    price DECIMAL(10,2) NOT NULL
);

-- Reviews
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id),
    product_id INT REFERENCES products(id),
    rating INT CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- DATA
-- ============================================

INSERT INTO customers (name, email, city, phone) VALUES
('Aarav Mehta',     'aarav@gmail.com',    'Mumbai',    '9876543210'),
('Priya Sharma',    'priya@gmail.com',    'Delhi',     '9812345678'),
('Rohan Verma',     'rohan@gmail.com',    'Bangalore', '9823456789'),
('Sneha Patil',     'sneha@gmail.com',    'Pune',      '9834567890'),
('Karan Singh',     'karan@gmail.com',    'Mumbai',    '9845678901'),
('Ananya Nair',     'ananya@gmail.com',   'Chennai',   '9856789012'),
('Vikram Joshi',    'vikram@gmail.com',   'Hyderabad', '9867890123'),
('Pooja Gupta',     'pooja@gmail.com',    'Delhi',     '9878901234'),
('Arjun Das',       'arjun@gmail.com',    'Kolkata',   '9889012345'),
('Meera Iyer',      'meera@gmail.com',    'Chennai',   '9890123456'),
('Rahul Tiwari',    'rahul@gmail.com',    'Lucknow',   '9901234567'),
('Divya Pillai',    'divya@gmail.com',    'Bangalore', '9912345678'),
('Nikhil Bajaj',    'nikhil@gmail.com',   'Mumbai',    '9923456789'),
('Kavya Reddy',     'kavya@gmail.com',    'Hyderabad', '9934567890'),
('Siddharth Shah',  'siddharth@gmail.com','Ahmedabad', '9945678901');

INSERT INTO categories (name) VALUES
('Electronics'),
('Clothing'),
('Footwear'),
('Books'),
('Home & Kitchen');

INSERT INTO products (name, category_id, price, stock) VALUES
('iPhone 15',           1, 79999, 50),
('Samsung Galaxy S24',  1, 69999, 40),
('MacBook Pro 14"',     1, 149999, 20),
('Sony WH-1000XM5',     1, 24999, 60),
('iPad Air',            1, 59999, 35),
('OnePlus 12',          1, 49999, 45),
('Levi 511 Jeans',      2, 3999,  100),
('Nike Dri-FIT Tshirt', 2, 1999,  150),
('Zara Formal Shirt',   2, 2999,  80),
('H&M Winter Jacket',   2, 5999,  60),
('Nike Air Max',        3, 8999,  70),
('Adidas Ultraboost',   3, 10999, 55),
('Puma RS-X',           3, 6999,  65),
('Atomic Habits',       4, 499,   200),
('The Alchemist',       4, 299,   250),
('Deep Work',           4, 399,   180),
('Instant Pot Duo',     5, 7999,  40),
('Philips Air Fryer',   5, 5999,  50),
('Dyson V11 Vacuum',    5, 39999, 15),
('IKEA Study Lamp',     5, 1499,  90);

INSERT INTO orders (customer_id, status, total, created_at) VALUES
(1,  'delivered', 79999,  NOW() - INTERVAL '60 days'),
(2,  'delivered', 24999,  NOW() - INTERVAL '55 days'),
(3,  'delivered', 149999, NOW() - INTERVAL '50 days'),
(4,  'delivered', 8999,   NOW() - INTERVAL '45 days'),
(5,  'cancelled', 3999,   NOW() - INTERVAL '40 days'),
(6,  'delivered', 69999,  NOW() - INTERVAL '35 days'),
(7,  'delivered', 59999,  NOW() - INTERVAL '30 days'),
(8,  'pending',   10999,  NOW() - INTERVAL '25 days'),
(9,  'delivered', 499,    NOW() - INTERVAL '20 days'),
(10, 'delivered', 7999,   NOW() - INTERVAL '15 days'),
(1,  'delivered', 24999,  NOW() - INTERVAL '10 days'),
(2,  'pending',   149999, NOW() - INTERVAL '8 days'),
(3,  'delivered', 5999,   NOW() - INTERVAL '7 days'),
(4,  'delivered', 1999,   NOW() - INTERVAL '6 days'),
(5,  'delivered', 39999,  NOW() - INTERVAL '5 days'),
(6,  'cancelled', 6999,   NOW() - INTERVAL '4 days'),
(7,  'delivered', 299,    NOW() - INTERVAL '3 days'),
(8,  'delivered', 49999,  NOW() - INTERVAL '2 days'),
(11, 'delivered', 5999,   NOW() - INTERVAL '2 days'),
(12, 'pending',   79999,  NOW() - INTERVAL '1 day'),
(13, 'delivered', 2999,   NOW() - INTERVAL '1 day'),
(14, 'delivered', 10999,  NOW()),
(15, 'delivered', 399,    NOW());

INSERT INTO order_items (order_id, product_id, quantity, price) VALUES
(1,  1,  1, 79999),
(2,  4,  1, 24999),
(3,  3,  1, 149999),
(4,  11, 1, 8999),
(5,  7,  1, 3999),
(6,  2,  1, 69999),
(7,  5,  1, 59999),
(8,  12, 1, 10999),
(9,  14, 1, 499),
(10, 17, 1, 7999),
(11, 4,  1, 24999),
(12, 3,  1, 149999),
(13, 18, 1, 5999),
(14, 8,  1, 1999),
(15, 19, 1, 39999),
(16, 13, 1, 6999),
(17, 15, 1, 299),
(18, 6,  1, 49999),
(19, 10, 1, 5999),
(20, 1,  1, 79999),
(21, 9,  1, 2999),
(22, 12, 1, 10999),
(23, 16, 1, 399);

INSERT INTO reviews (customer_id, product_id, rating, comment) VALUES
(1,  1,  5, 'Amazing phone, totally worth it!'),
(2,  4,  4, 'Great sound quality, comfortable fit.'),
(3,  3,  5, 'Best laptop I have ever owned.'),
(4,  11, 4, 'Very comfortable for long walks.'),
(6,  2,  4, 'Smooth performance, good camera.'),
(7,  5,  5, 'Perfect for work and entertainment.'),
(9,  14, 5, 'Life changing book, highly recommend.'),
(10, 17, 4, 'Makes cooking so easy and fast.'),
(1,  4,  5, 'Best headphones under 25k.'),
(11, 10, 3, 'Good jacket but sizing runs small.'),
(12, 1,  5, 'Excellent build quality.'),
(13, 9,  4, 'Clean design, fits well.'),
(14, 12, 5, 'Super comfortable, worth every rupee.'),
(15, 16, 4, 'Really helped with my focus.');
