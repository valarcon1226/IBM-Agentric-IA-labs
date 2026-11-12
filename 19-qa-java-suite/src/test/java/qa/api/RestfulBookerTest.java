package qa.api;

import io.restassured.RestAssured;
import io.restassured.response.Response;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.*;
import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.*;

public class RestfulBookerTest {
    private static String token;

    private static void pause() {
        try {
            // Máx. 1 petición por segundo (pausa entre llamadas)
            Thread.sleep(1100);
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        }
    }

    @BeforeAll
    public static void setup() {
        RestAssured.baseURI = "https://restful-booker.herokuapp.com";
        pause();
        String body = "{\n" +
                "    \"username\" : \"admin\",\n" +
                "    \"password\" : \"password123\"\n" +
                "}";
        Response response = given().header("Content-Type", "application/json")
                .body(body).post("/auth");
        token = response.jsonPath().getString("token");
    }

    @BeforeEach
    public void delay() {
        pause();
    }

    private int createSampleBooking(String fname, String lname, int price) {
        pause();
        String payload = "{\n" +
                "    \"firstname\" : \"" + fname + "\",\n" +
                "    \"lastname\" : \"" + lname + "\",\n" +
                "    \"totalprice\" : " + price + ",\n" +
                "    \"depositpaid\" : true,\n" +
                "    \"bookingdates\" : {\n" +
                "        \"checkin\" : \"2026-01-01\",\n" +
                "        \"checkout\" : \"2026-01-10\"\n" +
                "    },\n" +
                "    \"additionalneeds\" : \"Breakfast\"\n" +
                "}";

        Response res = given().header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .body(payload)
                .post("/booking");

        assertEquals(200, res.getStatusCode());
        return res.jsonPath().getInt("bookingid");
    }

    @Test
    @DisplayName("API-01: Autenticación exitosa obtiene token válido")
    public void testAuthSuccess() {
        String body = "{\n" +
                "    \"username\" : \"admin\",\n" +
                "    \"password\" : \"password123\"\n" +
                "}";
        given().header("Content-Type", "application/json")
                .body(body)
                .post("/auth")
                .then()
                .statusCode(200)
                .body("token", notNullValue());
    }

    @Test
    @DisplayName("API-02: Autenticación con credenciales inválidas")
    public void testAuthInvalidCredentials() {
        String body = "{\n" +
                "    \"username\" : \"badUser\",\n" +
                "    \"password\" : \"badPass\"\n" +
                "}";
        given().header("Content-Type", "application/json")
                .body(body)
                .post("/auth")
                .then()
                .statusCode(200)
                .body("reason", equalTo("Bad credentials"));
    }

    @Test
    @DisplayName("API-03: Crear una nueva reserva")
    public void testCreateBooking() {
        String body = "{\n" +
                "    \"firstname\" : \"Jim\",\n" +
                "    \"lastname\" : \"Brown\",\n" +
                "    \"totalprice\" : 111,\n" +
                "    \"depositpaid\" : true,\n" +
                "    \"bookingdates\" : {\n" +
                "        \"checkin\" : \"2018-01-01\",\n" +
                "        \"checkout\" : \"2019-01-01\"\n" +
                "    },\n" +
                "    \"additionalneeds\" : \"Breakfast\"\n" +
                "}";
        given().header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .body(body).post("/booking")
                .then()
                .statusCode(200)
                .body("bookingid", notNullValue())
                .body("booking.firstname", equalTo("Jim"))
                .body("booking.lastname", equalTo("Brown"))
                .body("booking.totalprice", equalTo(111));
    }

    @Test
    @DisplayName("API-04: Leer reserva por ID existente")
    public void testGetBookingById() {
        int bookingId = createSampleBooking("Alice", "Smith", 250);
        pause();

        given().header("Accept", "application/json")
                .get("/booking/" + bookingId)
                .then()
                .statusCode(200)
                .body("firstname", equalTo("Alice"))
                .body("lastname", equalTo("Smith"))
                .body("totalprice", equalTo(250));
    }

    @Test
    @DisplayName("API-05: Listar todas las reservas")
    public void testGetAllBookings() {
        given().get("/booking")
                .then()
                .statusCode(200)
                .body("size()", greaterThan(0));
    }

    @Test
    @DisplayName("API-06: Actualizar reserva completa (PUT)")
    public void testUpdateBooking() {
        int bookingId = createSampleBooking("Bob", "Marley", 300);
        pause();

        String updatedBody = "{\n" +
                "    \"firstname\" : \"Robert\",\n" +
                "    \"lastname\" : \"Marley\",\n" +
                "    \"totalprice\" : 350,\n" +
                "    \"depositpaid\" : false,\n" +
                "    \"bookingdates\" : {\n" +
                "        \"checkin\" : \"2026-02-01\",\n" +
                "        \"checkout\" : \"2026-02-15\"\n" +
                "    },\n" +
                "    \"additionalneeds\" : \"Dinner\"\n" +
                "}";

        given().header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .header("Cookie", "token=" + token)
                .body(updatedBody)
                .put("/booking/" + bookingId)
                .then()
                .statusCode(200)
                .body("firstname", equalTo("Robert"))
                .body("totalprice", equalTo(350))
                .body("additionalneeds", equalTo("Dinner"));
    }

    @Test
    @DisplayName("API-07: Borrar reserva por ID (DELETE)")
    public void testDeleteBooking() {
        int bookingId = createSampleBooking("Charlie", "Chaplin", 180);
        pause();

        given().header("Content-Type", "application/json")
                .header("Cookie", "token=" + token)
                .delete("/booking/" + bookingId)
                .then()
                .statusCode(201);

        pause();
        given().header("Accept", "application/json")
                .get("/booking/" + bookingId)
                .then()
                .statusCode(404);
    }

    @Test
    @DisplayName("API-08: Negativo PUT con token inválido retorna 403")
    public void testUpdateBookingInvalidTokenReturns403() {
        int bookingId = createSampleBooking("Dave", "Grohl", 199);
        pause();

        String updatedBody = "{\n" +
                "    \"firstname\" : \"Dave\",\n" +
                "    \"lastname\" : \"Grohl\",\n" +
                "    \"totalprice\" : 299,\n" +
                "    \"depositpaid\" : true,\n" +
                "    \"bookingdates\" : {\n" +
                "        \"checkin\" : \"2026-03-01\",\n" +
                "        \"checkout\" : \"2026-03-10\"\n" +
                "    },\n" +
                "    \"additionalneeds\" : \"Guitar\"\n" +
                "}";

        given().header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .header("Cookie", "token=invalid_token_999")
                .body(updatedBody)
                .put("/booking/" + bookingId)
                .then()
                .statusCode(403);
    }

    @Test
    @DisplayName("API-09: Negativo DELETE con token inválido retorna 403")
    public void testDeleteBookingInvalidTokenReturns403() {
        int bookingId = createSampleBooking("Emma", "Watson", 420);
        pause();

        given().header("Content-Type", "application/json")
                .header("Cookie", "token=invalid_token_999")
                .delete("/booking/" + bookingId)
                .then()
                .statusCode(403);
    }

    @Test
    @DisplayName("API-10: Negativo GET con ID inexistente retorna 404")
    public void testGetBookingNonExistentIdReturns404() {
        given().header("Accept", "application/json")
                .get("/booking/999999999")
                .then()
                .statusCode(404);
    }

    @Test
    @DisplayName("API-11: Healthcheck GET /ping retorna 201")
    public void testPingHealthCheck() {
        given().get("/ping")
                .then()
                .statusCode(201);
    }
}
