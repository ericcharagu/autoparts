-- SQL for creating all database tables for the AutoParts application

-- Drop tables in reverse order of dependency to avoid foreign key errors
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS customers;

-- -----------------------------------------------------
-- Table: customers
-- Description: Stores information about all clients (B2C and B2B).
-- -----------------------------------------------------
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20) UNIQUE NOT NULL, -- The primary link for WhatsApp users
    location VARCHAR(100),
    account_type VARCHAR(50) DEFAULT 'B2C',
    is_repeat_customer BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups by phone number
CREATE INDEX idx_customers_phone_number ON customers (phone_number);

-- -----------------------------------------------------
-- Table: users
-- Description: Stores login credentials for staff/admins using the web dashboard.
-- -----------------------------------------------------
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone_number VARCHAR(20) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE
);

-- Indexes for fast lookups
CREATE INDEX idx_users_username ON users (username);
CREATE INDEX idx_users_email ON users (email);

-- -----------------------------------------------------
-- Table: orders
-- Description: Header information for each order, linked to a customer.
-- -----------------------------------------------------
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    quote_id VARCHAR(50) UNIQUE NOT NULL, -- A unique identifier for the quote/order
    customer_id INT NOT NULL,
    garage_id VARCHAR(50), -- Can be NULL for B2C customers
    total_amount NUMERIC(10, 2) NOT NULL,
    payment_status VARCHAR(20) DEFAULT 'pending', -- e.g., pending, paid, cancelled
    payment_due_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT fk_customer
        FOREIGN KEY(customer_id) 
        REFERENCES customers(id)
        ON DELETE CASCADE -- If a customer is deleted, their orders are deleted too
);

-- Indexes for fast lookups
CREATE INDEX idx_orders_quote_id ON orders (quote_id);
CREATE INDEX idx_orders_customer_id ON orders (customer_id);

-- -----------------------------------------------------
-- Table: order_items
-- Description: Individual line items for each order.
-- -----------------------------------------------------
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL,
    item_name VARCHAR(255) NOT NULL,
    product_code VARCHAR(100),
    quantity INT NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    line_total NUMERIC(10, 2) NOT NULL,
    
    CONSTRAINT fk_order
        FOREIGN KEY(order_id)
        REFERENCES orders(id)
        ON DELETE CASCADE -- If an order is deleted, its items are deleted too
);

-- Index for fast lookups
CREATE INDEX idx_order_items_order_id ON order_items (order_id);

-- ---

\echo 'All tables (customers, users, orders, order_items) created successfully.'

-- SQL for inserting realistic Kenyan dummy data into all tables

-- -----------------------------------------------------
-- 1. Dummy Data for 'customers' Table
-- -----------------------------------------------------
INSERT INTO customers (id, name, phone_number, location, account_type, is_repeat_customer) VALUES
(1, 'Wanjiku Motors', '254722123456', 'Kariobangi, Nairobi', 'B2B-Garage', TRUE),
(2, 'Otieno AutoFix', '254711987654', 'Kisumu CBD', 'B2B-Garage', FALSE),
(3, 'Salim Fundi', '254736391323', 'Buru Buru, Nairobi', 'B2C', TRUE), -- Your test number
(4, 'Kipchoge Spares', '254700555888', 'Eldoret Town', 'B2C', TRUE);

--Single Insert 
INSERT INTO customers (id, name, phone_number, location, account_type, is_repeat_customer) VALUES (5, 'Anthony Karanja', '254721498064', 'Westlands, Nairobi', 'BTB', TRUE);

-- Manually set the sequence to avoid conflicts with SERIAL
SELECT setval('customers_id_seq', (SELECT MAX(id) FROM customers));

\echo 'Inserted 4 dummy customers.'

-- -----------------------------------------------------
-- 2. Dummy Data for 'users' Table (Dashboard Admins)
-- Password for all users is: Str0ngP@ssw0rd!
-- -----------------------------------------------------
INSERT INTO users (username, email, phone_number, password_hash, is_active) VALUES
(
    'admin_eric', 'eric.charagu@example.com', '254722000001',
    '$2b$12$EixZa.Gk52ylbL2gBqGkX.EXb3gWnL9fM4iGz3t1L0C/w.eG8G.8y', -- Str0ngP@ssw0rd!
    TRUE
),
(
    'susan_sales', 'susan.w@example.com', '254711000002',
    '$2b$12$EixZa.Gk52ylbL2gBqGkX.EXb3gWnL9fM4iGz3t1L0C/w.eG8G.8y', -- Str0ngP@ssw0rd!
    TRUE
);

\echo 'Inserted 2 dummy users.'

-- -----------------------------------------------------
-- 3. Dummy Data for 'orders' and 'order_items' Tables
-- -----------------------------------------------------

-- Order 1: For Wanjiku Motors (customer_id=1), a repeat B2B customer
INSERT INTO orders (id, quote_id, customer_id, garage_id, total_amount, payment_status, payment_due_date, created_at)
VALUES (1, 'ORD-2024-A4B1', 1, 'GARAGE-WM-01', 82193.50, 'paid', '2024-06-15', '2024-06-01 10:30:00');

INSERT INTO order_items (order_id, item_name, product_code, quantity, unit_price, line_total) VALUES
(1, 'N120MF R POWERLAST', 'POW-N120-MFR', 3, 17978.40, 53935.20),
(1, '045MF NSL POWERLAST', 'POW-45-MF-NSL', 5, 6990.50, 34952.50);
-- A 10% discount would have been applied by the LLM logic on the subtotal of 88887.70

-- Order 2: For Salim Fundi (customer_id=3), a B2C customer
INSERT INTO orders (id, quote_id, customer_id, total_amount, payment_status, payment_due_date, created_at)
VALUES (2, 'ORD-2024-C8D2', 3, 22815.10, 'pending', '2024-07-20', '2024-07-06 14:00:00');

INSERT INTO order_items (order_id, item_name, product_code, quantity, unit_price, line_total) VALUES
(2, 'N150 MFR POWERLAST', 'POW-N150-MFR', 1, 22815.10, 22815.10);

-- Order 3: For Otieno AutoFix (customer_id=2), a new B2B customer
INSERT INTO orders (id, quote_id, customer_id, garage_id, total_amount, payment_status, payment_due_date, created_at)
VALUES (3, 'ORD-2024-E2F3', 2, 'GARAGE-OAF-01', 7183.20, 'pending', '2024-07-21', '2024-07-07 09:15:00');

INSERT INTO order_items (order_id, item_name, product_code, quantity, unit_price, line_total) VALUES
(3, 'CG Oil Filter', '90915-YZZE1', 12, 467.50, 5610.00),
(3, 'Wiper Blades', 'DCSG016', 3, 561.00, 1683.00);


-- Manually set the sequence for the orders table
SELECT setval('orders_id_seq', (SELECT MAX(id) FROM orders));

\echo 'Inserted 3 dummy orders with their items.'

-- ---
-- Final check
-- ---
\echo 'Dummy data script finished.'