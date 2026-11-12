-- Sabor de Casa — WhatsApp restaurant assistant (DECISIONES-13 W8).

CREATE TABLE customers (
    wa_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(150),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    wa_id VARCHAR(20) NOT NULL REFERENCES customers(wa_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('customer', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_messages_wa_id_created_at ON messages (wa_id, created_at);

-- Meta retries webhook deliveries; a message id is only ever processed once.
CREATE TABLE processed_messages (
    message_id VARCHAR(100) PRIMARY KEY,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE menu (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    allergens VARCHAR(255),
    price_cop INTEGER NOT NULL CHECK (price_cop > 0),
    available BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    wa_id VARCHAR(20) NOT NULL REFERENCES customers(wa_id) ON DELETE CASCADE,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    total_cop INTEGER NOT NULL DEFAULT 0,
    address TEXT,
    zone VARCHAR(100),
    payment_method VARCHAR(30),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    dish_id INTEGER NOT NULL REFERENCES menu(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cop INTEGER NOT NULL,
    notes TEXT
);

CREATE TABLE reservations (
    id SERIAL PRIMARY KEY,
    wa_id VARCHAR(20) NOT NULL REFERENCES customers(wa_id) ON DELETE CASCADE,
    reservation_date DATE NOT NULL,
    reservation_time TIME NOT NULL,
    party_size INTEGER NOT NULL CHECK (party_size > 0),
    status VARCHAR(30) NOT NULL DEFAULT 'confirmed',
    reminder_sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE event_leads (
    id SERIAL PRIMARY KEY,
    wa_id VARCHAR(20) NOT NULL REFERENCES customers(wa_id) ON DELETE CASCADE,
    event_type VARCHAR(100),
    event_date DATE,
    guests INTEGER,
    budget_cop INTEGER,
    contact_name VARCHAR(150),
    status VARCHAR(30) NOT NULL DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE handovers (
    id SERIAL PRIMARY KEY,
    wa_id VARCHAR(20) NOT NULL REFERENCES customers(wa_id) ON DELETE CASCADE,
    reason TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- Menu seed: ~15 Colombian dishes, prices in COP (README/knowledge/menu.md must stay consistent).
INSERT INTO menu (name, description, category, allergens, price_cop, available) VALUES
('Bandeja Paisa', 'Carne molida, chicharrón, frijoles, arroz, huevo frito, chorizo, arepa, aguacate y plátano maduro.', 'plato_fuerte', 'puede contener gluten (chorizo)', 34000, TRUE),
('Ajiaco Santafereño', 'Pollo, papa criolla, papa pastusa, papa sabanera, mazorca y guascas, servido con crema de leche y alcaparras.', 'plato_fuerte', 'lácteos', 29000, TRUE),
('Sancocho de Gallina', 'Gallina criolla, yuca, plátano, mazorca y cilantro en caldo.', 'plato_fuerte', 'ninguno conocido', 27000, TRUE),
('Mondongo', 'Callo de res, garbanzo, papa y longaniza en caldo espeso.', 'plato_fuerte', 'ninguno conocido', 26000, TRUE),
('Lechona Tolimense', 'Cerdo relleno de arroz y arveja, horneado lentamente. Disponible solo fines de semana.', 'plato_fuerte', 'ninguno conocido', 25000, FALSE),
('Tamal Tolimense', 'Masa de maíz con cerdo, pollo, huevo y arveja, envuelto en hoja de plátano.', 'plato_fuerte', 'huevo', 16000, TRUE),
('Arroz con Pollo', 'Arroz, pollo desmechado, verduras y color.', 'plato_fuerte', 'ninguno conocido', 22000, TRUE),
('Empanadas de Carne (porción x4)', 'Masa de maíz rellena de carne de res y papa, fritas.', 'entrada', 'fritas en el mismo aceite que productos con gluten', 12000, TRUE),
('Arepa de Choclo con Queso', 'Arepa de maíz tierno con queso campesino.', 'entrada', 'lácteos', 11000, TRUE),
('Patacones con Hogao y Queso', 'Plátano verde frito, hogao casero y queso.', 'entrada', 'lácteos', 14000, TRUE),
('Sobrebarriga en Salsa Criolla', 'Carne de res en salsa criolla, acompañada de arroz y papa.', 'plato_fuerte', 'ninguno conocido', 32000, TRUE),
('Mojarra Frita con Patacón y Ensalada', 'Mojarra entera frita, patacón y ensalada fresca.', 'plato_fuerte', 'pescado', 36000, TRUE),
('Chicharrón Santandereano con Arepa y Yuca', 'Chicharrón de cerdo, arepa de maíz y yuca.', 'plato_fuerte', 'ninguno conocido', 23000, TRUE),
('Postre de Tres Leches', 'Bizcocho bañado en tres leches con crema batida.', 'postre', 'lácteos, gluten, huevo', 11000, TRUE),
('Obleas con Arequipe y Queso', 'Oblea de trigo con arequipe y queso campesino.', 'postre', 'gluten, lácteos', 9000, TRUE),
('Limonada de Coco', 'Limonada con leche de coco y leche condensada.', 'bebida', 'lácteos', 9000, TRUE),
('Jugo Natural de Lulo (en agua)', 'Jugo de lulo preparado en agua.', 'bebida', 'ninguno conocido', 8000, TRUE);
