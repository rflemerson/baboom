"""Optional end-to-end contract tests against the repository's Django API."""

import json as json_module
from types import SimpleNamespace

import pytest

from mcp_server.tools import api, review, submission
from mcp_server.tools.drafts import update_draft

settings = pytest.importorskip("django.conf").settings

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        not settings.configured,
        reason="Run with --ds=baboom.settings for API contract tests",
    ),
]


@pytest.fixture
def backend(monkeypatch):
    schema = pytest.importorskip("baboom.schema").schema
    core = pytest.importorskip("core.models")
    offers = pytest.importorskip("offers.models")
    scrapers = pytest.importorskip("scrapers.models")
    view = pytest.importorskip("strawberry.django.views").GraphQLView.as_view(
        schema=schema
    )
    factory = pytest.importorskip("django.test").RequestFactory()

    key = core.APIKey.objects.create(name="Contract test")
    brand = core.Brand.objects.create(name="growth", display_name="Growth")
    core.Store.objects.create(name="growth", display_name="Growth")
    page = scrapers.ScrapedPage.objects.create(
        url="https://shop.example/whey",
        store_slug="growth",
        api_context={"image": "https://cdn.example/label"},
    )
    offer = offers.Offer.objects.create(
        store_slug="growth", external_id="contract", name="Whey"
    )
    item = scrapers.ScrapedItem.objects.create(
        offer=offer, source_page=page, status="queued"
    )

    def post(_url, *, json, headers, timeout):
        assert timeout > 0
        request = factory.post(
            "/graphql/",
            data=json,
            content_type="application/json",
            HTTP_X_API_KEY=headers["X-API-KEY"],
        )
        response = view(request)

        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: json_module.loads(response.content),
        )

    monkeypatch.setenv("BACKEND_GRAPHQL_URL", "http://testserver/graphql/")
    monkeypatch.setenv("BACKEND_API_KEY", key.key)
    monkeypatch.setattr(api.requests, "post", post)
    return item, brand


def test_full_review_contract(backend):
    item, brand = backend
    assert int(api.review_queue()[0]["id"]) == item.id
    assert api.catalog_choices("brands")[0]["id"] == brand.id
    assert api.catalog_choices("categories") == []
    assert api.catalog_choices("tags") == []
    checked = review.checkout_item(item.id)
    assert checked["imageUrls"] == ["https://cdn.example/label"]
    assert review.act_on_current_item("heartbeat")["status"] == "processing"
    assert review.act_on_current_item("release")["status"] == "queued"
    review.checkout_item(item.id)
    update_draft({"name": "Whey", "children": [{"name": "Creatine"}]})
    assert submission.submit_draft(confirm=True)["ok"]
    assert review.resume_item(item.id)["reviewItem"]["status"] == "review"
    assert submission.submit_draft(confirm=True)["ok"]
    result = review.approve_current_item(
        create_product={"name": "Whey", "brandId": brand.id}, confirm=True
    )
    assert not result["product"]["isPublished"]
    assert api.catalog_candidates(search="Whey")[0]["id"] == result["product"]["id"]
    assert review.approve_current_item(
        product_id=result["product"]["id"], confirm=True
    )["ok"]


def test_error_and_ignore_contract(backend):
    item, _ = backend
    review.checkout_item(item.id)
    assert review.report_current_item_error("Unreadable", is_fatal=True)["ok"]
    assert review.act_on_current_item("ignore")["status"] == "ignored"
