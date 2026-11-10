"""Seed script for Saleor test stack.

Runs populatedb, creates/verifies a staff user and an App with access token,
and prints the counts of products, orders, and warehouses.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import httpx
import psycopg


def run_populatedb() -> None:
    """Run Saleor's populatedb management command inside the API container."""
    print("Running populatedb inside API container...")
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "api",
        "python",
        "manage.py",
        "populatedb",
        "--createsuperuser",
        "--withoutimages",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"populatedb stdout: {result.stdout}")
        print(f"populatedb stderr: {result.stderr}", file=sys.stderr)
        # If already populated or warning, don't crash if database has data
    else:
        print("populatedb completed successfully.")


def create_app_and_token(api_url: str, staff_email: str, staff_password: str, app_name: str) -> str:
    """Obtain staff JWT token and ensure test App exists with permissions."""
    print(f"Authenticating staff user {staff_email}...")
    token_mutation = """
    mutation TokenCreate($email: String!, $password: String!) {
      tokenCreate(email: $email, password: $password) {
        token
        errors {
          field
          message
          code
        }
      }
    }
    """
    with httpx.Client(timeout=30.0) as client:
        # Wait up to 30s for API readiness
        for _ in range(6):
            try:
                resp = client.post(
                    api_url,
                    json={
                        "query": token_mutation,
                        "variables": {"email": staff_email, "password": staff_password},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    token_data = data.get("tokenCreate", {})
                    if token_data and token_data.get("token"):
                        jwt_token = token_data["token"]
                        break
            except (httpx.HTTPError, KeyError):
                pass
            time.sleep(2)
        else:
            raise RuntimeError(f"Failed to authenticate staff user {staff_email} against {api_url}")

        print("Staff authenticated successfully.")

        # Create App with necessary permissions
        app_mutation = """
        mutation AppCreate($input: AppInput!) {
          appCreate(input: $input) {
            authToken
            app {
              id
              name
            }
            errors {
              field
              message
              code
            }
          }
        }
        """
        headers = {"Authorization": f"Bearer {jwt_token}"}
        app_resp = client.post(
            api_url,
            headers=headers,
            json={
                "query": app_mutation,
                "variables": {
                    "input": {
                        "name": app_name,
                        "permissions": [
                            "MANAGE_ORDERS",
                            "MANAGE_PRODUCTS",
                            "MANAGE_CHECKOUTS",
                            "MANAGE_APPS",
                            "MANAGE_WEBHOOKS",
                        ],
                    }
                },
            },
        )
        app_data = app_resp.json().get("data", {}).get("appCreate", {})
        auth_token = app_data.get("authToken")
        if auth_token:
            print(f"Created App '{app_name}' with token: {auth_token[:8]}***")
            return auth_token

        # If app already exists, query it or create via docker command
        print(f"App '{app_name}' might already exist. Using CLI create_app...")
        cli_res = subprocess.run(
            ["docker", "compose", "exec", "-T", "api", "python", "manage.py", "create_app", f"{app_name}_cli"],
            check=False,
            capture_output=True,
            text=True,
        )
        # Extract token from CLI output
        for line in cli_res.stdout.splitlines():
            if line.strip() and not line.startswith(" ") and len(line.strip()) > 20:
                print(f"Created CLI App token: {line.strip()[:8]}***")
                return line.strip()

        return jwt_token


def query_counts(db_url: str) -> tuple[int, int, int]:
    """Query counts of products, orders, and warehouses directly from database."""
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM product_product;")
        r1 = cur.fetchone()
        assert r1 is not None
        products_count = int(r1[0])

        cur.execute("SELECT count(*) FROM order_order;")
        r2 = cur.fetchone()
        assert r2 is not None
        orders_count = int(r2[0])

        cur.execute("SELECT count(*) FROM warehouse_warehouse;")
        r3 = cur.fetchone()
        assert r3 is not None
        warehouses_count = int(r3[0])

    return products_count, orders_count, warehouses_count


def main() -> None:
    api_url = os.getenv("SALEOR_API_URL", "http://127.0.0.1:8000/graphql/")
    staff_email = os.getenv("STAFF_EMAIL", "admin@example.com")
    staff_password = os.getenv("STAFF_PASSWORD", "admin")
    app_name = os.getenv("APP_NAME", "OrderIntegrityApp")
    db_url = os.getenv("DATABASE_URL", "postgres://saleor:saleor_password@127.0.0.1:5433/saleor")

    run_populatedb()
    create_app_and_token(api_url, staff_email, staff_password, app_name)

    products, orders, warehouses = query_counts(db_url)
    print("=" * 40)
    print(f"Products:   {products}")
    print(f"Orders:     {orders}")
    print(f"Warehouses: {warehouses}")
    print("=" * 40)

    if products == 0 or warehouses == 0:
        raise ValueError("Seed completed but counts are zero!")


if __name__ == "__main__":
    main()
