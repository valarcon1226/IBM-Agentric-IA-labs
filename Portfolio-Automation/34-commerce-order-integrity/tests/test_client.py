"""Tests validating the Saleor GraphQL client contracts and error handling."""

from __future__ import annotations

import pytest

from tests.client import GraphQLError, SaleorGraphQLClient, SaleorMutationError


def test_valid_query_parses_into_pydantic_model() -> None:
    client = SaleorGraphQLClient()
    products_conn = client.get_products(first=5)

    assert products_conn.page_info is not None
    assert isinstance(products_conn.page_info.has_next_page, bool)
    assert len(products_conn.edges) > 0

    first_node = products_conn.edges[0].node
    assert first_node.id != ""
    assert first_node.name != ""


def test_invalid_mutation_raises_exception_with_error_code() -> None:
    client = SaleorGraphQLClient()

    # Attempt to create checkout with a completely non-existent variant ID
    invalid_variant_id = "V2FyaWFudDoxOTk5OTk5"

    with pytest.raises((SaleorMutationError, GraphQLError)) as exc_info:
        client.create_checkout(variant_id=invalid_variant_id, quantity=1)

    assert isinstance(exc_info.value, (SaleorMutationError, GraphQLError))
    error = exc_info.value
    # Assert exception contains error code
    assert len(error.codes) > 0
    # Expected Saleor error codes for non-existent or invalid variant
    assert any(
        code in ["NOT_FOUND", "INSUFFICIENT_STOCK", "GRAPHQL_ERROR", "INVALID"]
        or "does not exist" in str(code).lower()
        or "could not resolve" in str(code).lower()
        for code in error.codes
    )
