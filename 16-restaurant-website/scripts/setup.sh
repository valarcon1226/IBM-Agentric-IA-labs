#!/bin/bash
# Wait for WordPress to be ready
echo "Waiting for WordPress installation to be ready..."
sleep 10
cd /var/www/html

if ! wp core is-installed; then
  echo "Installing WordPress..."
  wp core install --url="${WP_URL}" --title="${WP_TITLE}" --admin_user="${WP_ADMIN_USER}" --admin_password="${WP_ADMIN_PASSWORD}" --admin_email="${WP_ADMIN_EMAIL}" --skip-email
fi

wp config set ALLOW_UNFILTERED_UPLOADS true --raw
wp language core install es_ES
wp site switch-language es_ES
wp post delete 1 --force
wp post delete 2 --force
wp post delete 3 --force
wp theme install twentytwentyfour --activate

wp plugin uninstall booking wordpress-seo --deactivate
wp plugin install contact-form-7 --version=5.9.3 --activate
wp plugin install wp-mail-smtp --activate

# Delete default CF7 forms and create a fresh one
for id in $(wp post list --post_type=wpcf7_contact_form --format=ids); do wp post delete $id --force; done
CF7_ID=$(wp post create --post_type=wpcf7_contact_form --post_title="Formulario Eventos" --post_status=publish --porcelain)
wp post meta update $CF7_ID _form '<label> Tipo de evento [text* event-type] </label><label> Fecha [date* event-date] </label><label> Número de invitados [number* guests min:1] </label><label> Nombre [text* your-name] </label><label> Email [email* your-email] </label><label> Teléfono [tel* your-phone] </label>[submit "Enviar"]'
wp post meta update $CF7_ID _mail '{"subject":"Cotización de evento","sender":"[_site_admin_email]","body":"Tipo: [event-type]\nFecha: [event-date]\nInvitados: [guests]\nNombre: [your-name]\nEmail: [your-email]\nTeléfono: [your-phone]","recipient":"[_site_admin_email]","additional_headers":"Reply-To: [your-email]","attachments":"","use_html":false,"exclude_blank":false}' --format=json

wp option update wp_mail_smtp '{"mail":{"from_email":"reservas@sabordecasa.com","from_name":"Sabor de Casa","mailer":"smtp","return_path":false},"smtp":{"host":"mailpit","port":1025,"encryption":"none","auth":false,"user":"","pass":"","autotls":false}}' --format=json


wp rewrite structure '/%postname%/'

# Import map image
MAPA_ID=$(wp media import /scripts/mapa.webp --porcelain)
MAPA_URL=$(wp post get $MAPA_ID --field=guid)

mkdir -p wp-content/mu-plugins
cat << 'PHP' > wp-content/mu-plugins/sabor-custom.php
<?php
/* Plugin Name: Sabor de Casa Custom */
add_action('wp_head', function() {
    $json = [
        '@context' => 'https://schema.org',
        '@type' => 'Restaurant',
        'name' => 'Sabor de Casa',
        'image' => get_home_url() . '/wp-content/uploads/mapa.webp',
        'address' => [
            '@type' => 'PostalAddress',
            'streetAddress' => 'Calle 63 #11-25',
            'addressLocality' => 'Bogota',
            'addressCountry' => 'CO'
        ],
        'servesCuisine' => 'Colombian',
        'priceRange' => '$$',
        'openingHours' => [
            'Tu-Su 12:00-21:00'
        ]
    ];
    echo '<script type="application/ld+json">' . wp_json_encode($json) . '</script>';
    echo '<meta property="og:title" content="Sabor de Casa" />';
    echo '<meta property="og:type" content="restaurant.restaurant" />';
    echo '<meta property="og:url" content="' . get_home_url() . '" />';
});

add_action('wp_footer', function() {
    echo '<a href="https://wa.me/573000000000?text=Hola" class="whatsapp-float" aria-label="Chat en WhatsApp" style="position:fixed;bottom:20px;right:20px;background-color:#25d366;color:white;padding:15px;border-radius:50px;text-decoration:none;z-index:1000;">WhatsApp</a>';
});

// Registrar Custom Post Type para Reservas
add_action('init', function() {
    register_post_type('rtb-booking', [
        'labels' => ['name' => 'Reservas', 'singular_name' => 'Reserva'],
        'public' => false,
        'show_ui' => true,
        'supports' => ['title', 'custom-fields']
    ]);
});

// Procesar Formulario de Reservas
add_action('init', function() {
    if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['sabor_reserva_submit'])) {
        $name = sanitize_text_field($_POST['rtb-name']);
        $email = sanitize_email($_POST['rtb-email']);
        $phone = sanitize_text_field($_POST['rtb-phone']);
        $party = intval($_POST['rtb-party']);
        $date = sanitize_text_field($_POST['rtb-date']);
        $time = sanitize_text_field($_POST['rtb-time']);
        
        $post_id = wp_insert_post([
            'post_title' => "Reserva: $name - $date $time",
            'post_type' => 'rtb-booking',
            'post_status' => 'publish',
            'meta_input' => [
                'email' => $email,
                'phone' => $phone,
                'party' => $party,
                'date' => $date,
                'time' => $time
            ]
        ]);
        
        if ($post_id) {
            wp_mail($email, "Confirmación de Reserva en Sabor de Casa", "Hola $name,\n\nTu reserva para $party personas el $date a las $time ha sido confirmada.\n\nTe esperamos.");
            wp_redirect(add_query_arg('reserva_success', '1', wp_get_referer()));
            exit;
        }
    }
});

// Shortcode de Formulario de Reservas
add_shortcode('booking-form', function() {
    $msg = isset($_GET['reserva_success']) ? '<div class="rtb-message" style="color:green;font-weight:bold;">¡Reserva confirmada con éxito!</div>' : '';
    
    $form = '<form method="POST" action="">';
    $form .= '<label>Personas: <select name="rtb-party" required>';
    for ($i = 1; $i <= 12; $i++) {
        $form .= "<option value=\"$i\">$i</option>";
    }
    $form .= '</select></label><br/>';
    
    $form .= '<label>Fecha: <input type="date" name="rtb-date" id="rtb-date" required></label><br/>';
    
    $form .= '<label>Hora: <select name="rtb-time" id="rtb-time" required>';
    for ($h = 12; $h <= 20; $h++) {
        $form .= "<option value=\"$h:00\">$h:00</option>";
        $form .= "<option value=\"$h:30\">$h:30</option>";
    }
    $form .= '</select></label><br/>';
    
    $form .= '<label>Nombre: <input type="text" name="rtb-name" required></label><br/>';
    $form .= '<label>Email: <input type="email" name="rtb-email" required></label><br/>';
    $form .= '<label>Teléfono: <input type="tel" name="rtb-phone" required></label><br/>';
    $form .= '<button type="submit" name="sabor_reserva_submit">Reservar</button>';
    $form .= '</form>';
    
    return $msg . $form;
});
PHP
wp post create --post_type=page --post_title="Inicio" --post_status=publish \
--post_content='<!-- wp:heading {"level":1} --><h1>Bienvenido a Sabor de Casa</h1><!-- /wp:heading -->
<!-- wp:paragraph --><p>Disfruta de la mejor comida típica colombiana.</p><!-- /wp:paragraph -->'

wp post create --post_type=page --post_title="Menú" --post_status=publish \
--post_content='<!-- wp:heading --><h2>Platos fuertes</h2><!-- /wp:heading -->
<!-- wp:table -->
<table class="wp-block-table"><tbody>
<tr><td>Bandeja Paisa</td><td>Carne molida, chicharrón, frijoles, arroz, huevo frito, chorizo, arepa, aguacate, plátano maduro (Alérgenos: Gluten)</td><td>$34.000 COP</td></tr>
<tr><td>Ajiaco Santafereño</td><td>Pollo, papa criolla, papa pastusa, papa sabanera, mazorca, guascas, crema de leche, alcaparras (Alérgenos: Lácteos)</td><td>$29.000 COP</td></tr>
<tr><td>Sancocho de Gallina</td><td>Gallina criolla, yuca, plátano, mazorca, cilantro (Alérgenos: Ninguno)</td><td>$27.000 COP</td></tr>
<tr><td>Mondongo</td><td>Callo de res, garbanzo, papa, longaniza (Alérgenos: Ninguno)</td><td>$26.000 COP</td></tr>
<tr><td>Lechona Tolimense</td><td>Cerdo relleno de arroz y arveja (Alérgenos: Ninguno)</td><td>$25.000 COP</td></tr>
<tr><td>Tamal Tolimense</td><td>Masa de maíz, cerdo, pollo, huevo, arveja, hoja de plátano (Alérgenos: Huevo)</td><td>$16.000 COP</td></tr>
<tr><td>Arroz con Pollo</td><td>Arroz, pollo desmechado, verduras, color (Alérgenos: Ninguno)</td><td>$22.000 COP</td></tr>
<tr><td>Sobrebarriga en Salsa Criolla</td><td>Carne de res, salsa criolla, arroz, papa (Alérgenos: Ninguno)</td><td>$32.000 COP</td></tr>
<tr><td>Mojarra Frita con Patacón y Ensalada</td><td>Mojarra entera, patacón, ensalada (Alérgenos: Pescado)</td><td>$36.000 COP</td></tr>
<tr><td>Chicharrón Santandereano con Arepa y Yuca</td><td>Chicharrón de cerdo, arepa de maíz, yuca (Alérgenos: Ninguno)</td><td>$23.000 COP</td></tr>
<tr><td>Empanadas de Carne (porción x4)</td><td>Masa de maíz, carne de res, papa, fritas (Alérgenos: Gluten)</td><td>$12.000 COP</td></tr>
<tr><td>Arepa de Choclo con Queso</td><td>Maíz tierno, queso campesino (Alérgenos: Lácteos)</td><td>$11.000 COP</td></tr>
<tr><td>Patacones con Hogao y Queso</td><td>Plátano verde frito, hogao, queso (Alérgenos: Lácteos)</td><td>$14.000 COP</td></tr>
<tr><td>Postre de Tres Leches</td><td>Bizcocho, tres leches, crema batida (Alérgenos: Lácteos, gluten, huevo)</td><td>$11.000 COP</td></tr>
<tr><td>Obleas con Arequipe y Queso</td><td>Oblea de trigo, arequipe, queso campesino (Alérgenos: Gluten, lácteos)</td><td>$9.000 COP</td></tr>
<tr><td>Limonada de Coco</td><td>Limón, leche de coco, leche condensada (Alérgenos: Lácteos)</td><td>$9.000 COP</td></tr>
<tr><td>Jugo Natural de Lulo (en agua)</td><td>Lulo, agua, azúcar (Alérgenos: Ninguno)</td><td>$8.000 COP</td></tr>
</tbody></table>
<!-- /wp:table -->'

wp post create --post_type=page --post_title="Reservas" --post_status=publish \
--post_content='<!-- wp:paragraph --><p>Reserva tu mesa con nosotros. Capacidad máxima por franja: 40 personas. Tamaño máximo por reserva: 12 personas.</p><!-- /wp:paragraph --><!-- wp:shortcode -->[booking-form]<!-- /wp:shortcode -->'

wp post create --post_type=page --post_title="Domicilios" --post_status=publish \
--post_content='<!-- wp:heading --><h2>Zonas y costos</h2><!-- /wp:heading -->
<!-- wp:list -->
<ul><li>Chapinero: $5.000</li><li>Teusaquillo: $6.000</li><li>Usaquén: $7.000</li><li>Suba: $9.000</li></ul>
<!-- /wp:list -->
<!-- wp:paragraph --><p>Pedido mínimo para domicilio: $25.000.</p><!-- /wp:paragraph -->'

wp post create --post_type=page --post_title="Contacto" --post_status=publish \
--post_content="<!-- wp:paragraph --><p><strong>Dirección:</strong> Calle 63 #11-25, Chapinero, Bogotá.</p><!-- /wp:paragraph -->
<!-- wp:html -->
<a href=\"https://maps.google.com/?q=Calle+63+%2311-25,+Chapinero,+Bogota\" target=\"_blank\">
  <img src=\"${MAPA_URL}\" alt=\"Mapa de ubicación en Google Maps\" loading=\"lazy\" width=\"600\" height=\"300\" />
</a>
<!-- /wp:html -->"

wp post create --post_type=page --post_title="Política de Privacidad" --post_status=publish \
--post_content='<!-- wp:paragraph --><p>Política de privacidad...</p><!-- /wp:paragraph -->'

wp post create --post_type=page --post_title="Eventos y Catering" --post_name="eventos-y-catering" --post_status=publish \
--post_content="<!-- wp:paragraph --><p>Cotiza tu evento.</p><!-- /wp:paragraph --><!-- wp:shortcode -->[contact-form-7 id=\"$CF7_ID\" title=\"Formulario Eventos\"]<!-- /wp:shortcode -->"

HOME_ID=$(wp post list --post_type=page --post_status=publish --name="inicio" --field=ID)
wp option update show_on_front 'page'
wp option update page_on_front $HOME_ID

echo "Setup completed successfully."
