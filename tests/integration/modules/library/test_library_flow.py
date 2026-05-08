import os
import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.fixture
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    """Log in as admin and return client with session cookie."""
    email = os.environ["LOGSCOPE_ADMIN_EMAIL"]
    password = os.environ["LOGSCOPE_ADMIN_PASSWORD"]
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200
    return client


class TestLibraryFlow:
    """End-to-end flow: vendor → product → log_type → fields → parse_rule → publish → sample → overview."""

    async def test_full_flow(self, authenticated_client: AsyncClient):
        """Should walk through every Library write path and finish at a published state."""
        # Arrange — generate unique slug to avoid conflicts across re-runs
        unique = uuid.uuid4().hex[:8]
        vendor_slug = f"vendor-{unique}"

        # Act 1: create vendor
        r = await authenticated_client.post(
            "/api/v1/library/vendors",
            json={"name": f"Vendor {unique}", "slug": vendor_slug},
        )
        # Assert 1
        assert r.status_code == 201, r.text
        vendor = r.json()["data"]

        # Act 2: create product under vendor
        r = await authenticated_client.post(
            f"/api/v1/library/vendors/{vendor_slug}/products",
            json={"name": "Test Product", "slug": "test-product", "category": "network"},
        )
        # Assert 2
        assert r.status_code == 201
        product = r.json()["data"]

        # Act 3: create log_type
        r = await authenticated_client.post(
            f"/api/v1/library/products/{product['id']}/log_types",
            json={"name": "Traffic", "slug": "traffic", "format": "csv"},
        )
        # Assert 3
        assert r.status_code == 201
        log_type = r.json()["data"]
        assert log_type["status"] == "draft"

        # Act 4: replace fields
        r = await authenticated_client.put(
            f"/api/v1/library/log_types/{log_type['id']}/fields",
            json={
                "fields": [
                    {"field_name": "src_ip", "field_type": "ip", "is_identifier": True},
                    {"field_name": "dst_ip", "field_type": "ip", "is_identifier": True},
                    {"field_name": "action", "field_type": "string"},
                ]
            },
        )
        # Assert 4
        assert r.status_code == 200
        assert len(r.json()["data"]) == 3

        # Act 5: create draft parse_rule
        r = await authenticated_client.post(
            f"/api/v1/library/log_types/{log_type['id']}/parse_rules",
            json={
                "vrl_code": ". = parse_csv!(.message)",
                "engine_version": "0.32",
                "notes": "v1 draft",
            },
        )
        # Assert 5
        assert r.status_code == 201
        parse_rule = r.json()["data"]
        assert parse_rule["version"] == 1
        assert parse_rule["status"] == "draft"

        # Act 6: publish
        r = await authenticated_client.post(
            f"/api/v1/library/log_types/{log_type['id']}/publish",
        )
        # Assert 6
        assert r.status_code == 200
        published_lt = r.json()["data"]
        assert published_lt["status"] == "published"
        assert published_lt["published_at"] is not None

        # Act 6.5: GET nested detail
        r = await authenticated_client.get(
            f"/api/v1/library/vendors/{vendor_slug}/products/test-product",
        )
        # Assert 6.5
        assert r.status_code == 200
        detail = r.json()["data"]
        assert detail["slug"] == "test-product"
        assert len(detail["log_types"]) == 1
        my_lt = detail["log_types"][0]
        assert my_lt["status"] == "published"
        assert len(my_lt["fields"]) == 3
        assert my_lt["current_parse_rule"]["status"] == "published"
        assert len(my_lt["samples"]) == 0  # sample 還沒加

        # Act 7: re-publish should 409
        r = await authenticated_client.post(
            f"/api/v1/library/log_types/{log_type['id']}/publish",
        )
        # Assert 7
        assert r.status_code == 409

        # Act 8: add sample
        r = await authenticated_client.post(
            f"/api/v1/library/log_types/{log_type['id']}/samples",
            json={"raw_log": "1,2,allow", "label": "normal"},
        )
        # Assert 8
        assert r.status_code == 201

        # Act 9: overview reflects state
        r = await authenticated_client.get("/api/v1/library/overview")
        # Assert 9
        assert r.status_code == 200
        groups = r.json()["data"]
        my_group = next(g for g in groups if g["vendor"]["slug"] == vendor_slug)
        assert len(my_group["products"]) == 1
        op = my_group["products"][0]
        assert op["log_type_counts"]["published"] == 1
        assert op["is_empty"] is False

        # Cleanup: delete in reverse order (log_type cascades fields/rules/samples)
        r = await authenticated_client.delete(f"/api/v1/library/log_types/{log_type['id']}")
        assert r.status_code == 204
        r = await authenticated_client.delete(f"/api/v1/library/products/{product['id']}")
        assert r.status_code == 204
        r = await authenticated_client.delete(f"/api/v1/library/vendors/{vendor['id']}")
        assert r.status_code == 204

    async def test_cascade_delete_returns_409(self, authenticated_client: AsyncClient):
        """Deleting vendor with products should return 409, not 500."""
        # Arrange
        unique = uuid.uuid4().hex[:8]
        vendor_slug = f"v409-{unique}"

        r = await authenticated_client.post(
            "/api/v1/library/vendors",
            json={"name": f"V409 {unique}", "slug": vendor_slug},
        )
        assert r.status_code == 201
        vendor = r.json()["data"]

        r = await authenticated_client.post(
            f"/api/v1/library/vendors/{vendor_slug}/products",
            json={"name": "P", "slug": "p", "category": "network"},
        )
        assert r.status_code == 201
        product = r.json()["data"]

        # Act: try to delete vendor while it has a product
        r = await authenticated_client.delete(f"/api/v1/library/vendors/{vendor['id']}")

        # Assert
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "conflict"

        # Cleanup
        await authenticated_client.delete(f"/api/v1/library/products/{product['id']}")
        await authenticated_client.delete(f"/api/v1/library/vendors/{vendor['id']}")
