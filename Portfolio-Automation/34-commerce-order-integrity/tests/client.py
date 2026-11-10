"""Typed GraphQL Client for Saleor API with Pydantic v2 response contracts."""

from __future__ import annotations

import os
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field


class GraphQLError(Exception):
    """Raised when GraphQL server returns top-level errors."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        self.codes = [
            err.get("extensions", {}).get("exception", {}).get("code")
            or err.get("extensions", {}).get("code")
            or err.get("message", "UNKNOWN_ERROR")
            for err in errors
        ]
        super().__init__(f"GraphQL query failed with errors: {errors}")


class SaleorMutationError(Exception):
    """Raised when mutation returns domain validation errors (e.g. INSUFFICIENT_STOCK)."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        self.codes = [err.get("code", "VALIDATION_ERROR") for err in errors]
        super().__init__(
            f"Saleor mutation failed with error codes {self.codes}: {errors}"
        )


# --- Pydantic v2 Models ---


class BaseGraphQLModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class PageInfo(BaseGraphQLModel):
    has_next_page: bool = Field(alias="hasNextPage")
    has_previous_page: bool = Field(alias="hasPreviousPage")
    start_cursor: str | None = Field(default=None, alias="startCursor")
    end_cursor: str | None = Field(default=None, alias="endCursor")


class ProductNode(BaseGraphQLModel):
    id: str
    name: str
    slug: str | None = None


class ProductEdge(BaseGraphQLModel):
    cursor: str
    node: ProductNode


class ProductConnection(BaseGraphQLModel):
    total_count: int | None = Field(default=None, alias="totalCount")
    edges: list[ProductEdge] = Field(default_factory=list)
    page_info: PageInfo = Field(alias="pageInfo")


class ProductsResponseData(BaseGraphQLModel):
    products: ProductConnection


class CheckoutLine(BaseGraphQLModel):
    id: str
    quantity: int


class Checkout(BaseGraphQLModel):
    id: str
    lines: list[CheckoutLine] = Field(default_factory=list)


class CheckoutCreateData(BaseGraphQLModel):
    checkout: Checkout | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)


class Order(BaseGraphQLModel):
    id: str
    number: str | None = None
    status: str | None = None


class CheckoutCompleteData(BaseGraphQLModel):
    order: Order | None = None
    confirmation_needed: bool | None = Field(default=None, alias="confirmationNeeded")
    errors: list[dict[str, Any]] = Field(default_factory=list)


class BulkCreateError(BaseGraphQLModel):
    path: str | None = None
    field: str | None = None
    message: str | None = None
    code: str | None = None
    index: int | None = None


class BulkProductNode(BaseGraphQLModel):
    id: str
    name: str | None = None
    slug: str | None = None


class BulkResultItem(BaseGraphQLModel):
    product: BulkProductNode | None = None
    errors: list[BulkCreateError] = Field(default_factory=list)


class ProductBulkCreateData(BaseGraphQLModel):
    count: int = 0
    results: list[BulkResultItem] = Field(default_factory=list)
    errors: list[BulkCreateError] = Field(default_factory=list)


# --- Client Implementation ---


class SaleorGraphQLClient:
    """Synchronous and asynchronous client for Saleor GraphQL operations."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_s: float | None = None,
        default_channel: str = "default-channel",
    ) -> None:
        raw_url = base_url or os.getenv("SALEOR_API_URL") or "http://127.0.0.1:8000/graphql/"
        self.base_url = raw_url.strip()
        timeout_val = (
            float(os.getenv("SALEOR_TIMEOUT_S", "30.0"))
            if timeout_s is None
            else timeout_s
        )
        self.timeout = timeout_val
        self.default_channel = default_channel

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        token: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query/mutation and validate errors."""
        req_headers = {"Content-Type": "application/json"}
        if token:
            req_headers["Authorization"] = f"Bearer {token}"
        if headers:
            req_headers.update(headers)

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                self.base_url,
                headers=req_headers,
                json={"query": query, "variables": variables or {}},
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("errors"):
            raise GraphQLError(data["errors"])

        return data.get("data", {})

    def get_products(
        self,
        first: int,
        after: str | None = None,
        channel: str | None = None,
    ) -> ProductConnection:
        """Fetch paginated products and validate into Pydantic model."""
        channel_slug = channel or self.default_channel
        query = """
        query GetProducts($first: Int!, $after: String, $channel: String) {
          products(first: $first, after: $after, channel: $channel) {
            totalCount
            edges {
              cursor
              node {
                id
                name
                slug
              }
            }
            pageInfo {
              hasNextPage
              hasPreviousPage
              startCursor
              endCursor
            }
          }
        }
        """
        raw_data = self.execute(
            query,
            variables={"first": first, "after": after, "channel": channel_slug},
        )
        parsed = ProductsResponseData.model_validate(raw_data)
        return parsed.products

    def create_checkout(
        self,
        variant_id: str,
        quantity: int = 1,
        email: str = "test-buyer@example.com",
        channel: str | None = None,
    ) -> Checkout:
        """Create a new checkout and validate response."""
        channel_slug = channel or self.default_channel
        default_address = {
            "firstName": "John",
            "lastName": "Doe",
            "streetAddress1": "123 Main St",
            "city": "New York",
            "postalCode": "10001",
            "country": "US",
            "countryArea": "NY",
        }
        mutation = """
        mutation CreateCheckout(
          $channel: String!,
          $lines: [CheckoutLineInput!]!,
          $email: String!,
          $address: AddressInput!
        ) {
          checkoutCreate(input: {
            channel: $channel,
            lines: $lines,
            email: $email,
            billingAddress: $address
          }) {
            checkout {
              id
              lines {
                id
                quantity
              }
            }
            errors {
              field
              message
              code
            }
          }
        }
        """
        raw_data = self.execute(
            mutation,
            variables={
                "channel": channel_slug,
                "lines": [{"variantId": variant_id, "quantity": quantity}],
                "email": email,
                "address": default_address,
            },
        )
        payload = raw_data.get("checkoutCreate", {})
        if payload.get("errors"):
            raise SaleorMutationError(payload["errors"])

        parsed = CheckoutCreateData.model_validate(payload)
        if not parsed.checkout:
            raise RuntimeError(
                "Checkout creation succeeded but returned null checkout object"
            )
        return parsed.checkout

    def complete_checkout(
        self,
        checkout_id: str,
        idempotency_key: str | None = None,
    ) -> CheckoutCompleteData:
        """Complete checkout with optional idempotency key."""
        mutation = """
        mutation CompleteCheckout($id: ID!) {
          checkoutComplete(id: $id) {
            order {
              id
              number
              status
            }
            confirmationNeeded
            errors {
              field
              message
              code
            }
          }
        }
        """
        headers = {}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        raw_data = self.execute(
            mutation,
            variables={"id": checkout_id},
            headers=headers,
        )
        payload = raw_data.get("checkoutComplete", {})
        if payload.get("errors"):
            raise SaleorMutationError(payload["errors"])

        return CheckoutCompleteData.model_validate(payload)

    def bulk_create_products(
        self,
        products: list[dict[str, Any]],
        token: str,
        error_policy: str = "REJECT_FAILED_ROWS",
    ) -> ProductBulkCreateData:
        """Bulk create products with staff/app token."""
        mutation = """
        mutation ProductBulkCreate($products: [ProductBulkCreateInput!]!, $errorPolicy: ErrorPolicyEnum) {
          productBulkCreate(products: $products, errorPolicy: $errorPolicy) {
            count
            results {
              product {
                id
                name
                slug
              }
              errors {
                path
                message
                code
              }
            }
            errors {
              path
              message
              code
            }
          }
        }
        """
        raw_data = self.execute(
            mutation,
            variables={"products": products, "errorPolicy": error_policy},
            token=token,
        )
        payload = raw_data.get("productBulkCreate", {})
        return ProductBulkCreateData.model_validate(payload)
