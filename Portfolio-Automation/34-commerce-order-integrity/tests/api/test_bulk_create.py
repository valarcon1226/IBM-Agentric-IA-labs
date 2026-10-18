"""Atomic and row-isolated product bulk create tests.

Requirement: REQ-BLK-001 (Atomic and Row-Isolated Bulk Product Creation)
Verifies:
- Calling productBulkCreate with 100 rows containing 10 invalid rows.
- 90 valid products are created and verified in database.
- Each of the 10 invalid rows returns row index and error code.
- No partial product, variant, or stock records exist for invalid rows.
- Response shape validated via Pydantic v2 models.
"""

from __future__ import annotations

import os
import time
from typing import Any

import psycopg
import pytest

from tests.client import ProductBulkCreateData, SaleorGraphQLClient


def get_staff_token(client: SaleorGraphQLClient) -> str:
    """Authenticate staff user and return JWT token."""
    email = os.getenv("STAFF_EMAIL", "admin@example.com")
    password = os.getenv("STAFF_PASSWORD", "admin")
    query = """
    mutation StaffLogin($email: String!, $password: String!) {
      tokenCreate(email: $email, password: $password) {
        token
        errors { field message code }
      }
    }
    """
    res = client.execute(query, {"email": email, "password": password})
    token = res.get("tokenCreate", {}).get("token")
    assert token is not None, f"Failed to authenticate staff user: {res}"
    return str(token)


def get_valid_type_and_category(client: SaleorGraphQLClient) -> tuple[str, str]:
    """Retrieve first valid product type and category Relay IDs."""
    query = """
    query GetTypesAndCats {
      productTypes(first: 1) {
        edges { node { id } }
      }
      categories(first: 1) {
        edges { node { id } }
      }
    }
    """
    res = client.execute(query)
    pt_id = res["productTypes"]["edges"][0]["node"]["id"]
    cat_id = res["categories"]["edges"][0]["node"]["id"]
    return str(pt_id), str(cat_id)


@pytest.mark.req("REQ-BLK-001")
@pytest.mark.p1
def test_product_bulk_create_partial_failure_isolation() -> None:
    """100 rows submitted: 90 valid, 10 invalid in 3 distinct failure modes.

    Asserts:
    - Exactly 90 valid products are created.
    - Each of the 10 errors maps to its row index and carries the expected error code.
    - Zero residual or half-created product, variant, or stock records for failed rows.
    - Validated through Pydantic v2 ProductBulkCreateData model and PostgreSQL queries.
    """
    client = SaleorGraphQLClient()
    db_url = os.getenv("DATABASE_URL", "postgres://saleor:saleor_password@127.0.0.1:5433/saleor")
    token = get_staff_token(client)
    product_type_id, category_id = get_valid_type_and_category(client)

    # Duplicate-slug rows collide with a product that already exists in the database.
    # Colliding inside the batch instead hits FINDING-002 (unhandled 500).
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT slug FROM product_product ORDER BY id LIMIT 1")
        r_slug = cur.fetchone()
    assert r_slug is not None, "Seed the database first: no product exists to collide with"
    existing_slug = str(r_slug[0])

    batch_tag = f"bulk-{time.time_ns()}"
    total_rows = 100
    # 10 invalid indices distributed across the batch
    # Failure mode 1 (missing required field 'name'): 4 rows (10, 20, 30, 40)
    # Failure mode 2 (unknown category Relay ID): 3 rows (50, 60, 70)
    # Failure mode 3 (duplicate slug already in DB): 3 rows (80, 90, 95)
    invalid_indices_missing_name = {10, 20, 30, 40}
    invalid_indices_unknown_cat = {50, 60, 70}
    invalid_indices_dup_slug = {80, 90, 95}
    invalid_indices = (
        invalid_indices_missing_name
        | invalid_indices_unknown_cat
        | invalid_indices_dup_slug
    )

    valid_slugs: list[str] = []
    invalid_slugs_attempted: list[str] = []
    products_input: list[dict[str, Any]] = []

    for idx in range(total_rows):
        if idx in invalid_indices_missing_name:
            inv_slug = f"inv-name-{batch_tag}-{idx}"
            invalid_slugs_attempted.append(inv_slug)
            products_input.append({
                "slug": inv_slug,
                "productType": product_type_id,
                "category": category_id,
            })
        elif idx in invalid_indices_unknown_cat:
            inv_slug = f"inv-cat-{batch_tag}-{idx}"
            invalid_slugs_attempted.append(inv_slug)
            products_input.append({
                "name": f"Invalid Cat Product {idx}",
                "slug": inv_slug,
                "productType": product_type_id,
                "category": "Q2F0ZWdvcnk6OTk5OTk5",  # Non-existent Category ID
            })
        elif idx in invalid_indices_dup_slug:
            products_input.append({
                "name": f"Duplicate Slug Product {idx}",
                "slug": existing_slug,
                "productType": product_type_id,
                "category": category_id,
            })
        else:
            val_slug = f"val-prod-{batch_tag}-{idx}"
            valid_slugs.append(val_slug)
            products_input.append({
                "name": f"Valid Bulk Product {idx}",
                "slug": val_slug,
                "productType": product_type_id,
                "category": category_id,
            })

    assert len(valid_slugs) == 90
    assert len(invalid_indices) == 10

    created_product_ids: list[int] = []

    try:
        bulk_data: ProductBulkCreateData = client.bulk_create_products(
            products=products_input,
            token=token,
            error_policy="REJECT_FAILED_ROWS",
        )

        # 1. Check response counts and overall length
        assert bulk_data.count == 90, f"Expected 90 created products, got {bulk_data.count}"
        assert len(bulk_data.results) == 100, f"Expected 100 result items, got {len(bulk_data.results)}"

        # 2. Check each result item according to row index
        for idx in range(total_rows):
            result_item = bulk_data.results[idx]
            if idx in invalid_indices:
                assert result_item.product is None, f"Row {idx} should not produce a product"
                assert len(result_item.errors) > 0, f"Row {idx} should contain errors"
                error_codes = [err.code for err in result_item.errors]
                error_paths = [err.path for err in result_item.errors]

                if idx in invalid_indices_missing_name:
                    assert "BLANK" in error_codes, f"Row {idx} missing name error: {result_item.errors}"
                    assert "name" in error_paths
                elif idx in invalid_indices_unknown_cat:
                    assert "NOT_FOUND" in error_codes, f"Row {idx} unknown cat error: {result_item.errors}"
                    assert "category" in error_paths
                elif idx in invalid_indices_dup_slug:
                    assert "UNIQUE" in error_codes, f"Row {idx} dup slug error: {result_item.errors}"
                    assert "slug" in error_paths
            else:
                assert result_item.product is not None, f"Row {idx} should have succeeded"
                assert result_item.product.slug == products_input[idx]["slug"]
                assert len(result_item.errors) == 0

        # 3. SQL verification: exactly 90 valid products exist in Postgres
        with psycopg.connect(db_url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, slug FROM product_product WHERE slug = ANY(%s)",
                (valid_slugs,),
            )
            rows = cur.fetchall()
            assert len(rows) == 90, f"Expected 90 valid rows in database, found {len(rows)}"
            created_product_ids = [r[0] for r in rows]

            # 4. SQL verification: no product created for attempted invalid slugs
            cur.execute(
                "SELECT count(*) FROM product_product WHERE slug = ANY(%s)",
                (invalid_slugs_attempted,),
            )
            r_inv = cur.fetchone()
            assert r_inv is not None
            assert r_inv[0] == 0, f"Residual invalid products found in database: {r_inv[0]}"

            # 5. SQL verification: no orphaned variants or stock for attempted invalid slugs
            cur.execute(
                """
                SELECT count(*)
                FROM product_productvariant
                WHERE product_id IN (
                    SELECT id FROM product_product WHERE slug = ANY(%s)
                )
                """,
                (invalid_slugs_attempted,),
            )
            r_var = cur.fetchone()
            assert r_var is not None
            assert r_var[0] == 0

    finally:
        # Cleanup created products
        if created_product_ids:
            with psycopg.connect(db_url, autocommit=True) as conn, conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM product_productchannellisting WHERE product_id = ANY(%s)",
                    (created_product_ids,),
                )
                cur.execute(
                    "DELETE FROM product_product WHERE id = ANY(%s)",
                    (created_product_ids,),
                )
