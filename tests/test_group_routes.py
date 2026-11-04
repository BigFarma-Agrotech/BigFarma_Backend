"""Group buy routes that used to 500: share/chat endpoints, access checks, public group routes."""
from features.group_buy.models import GroupBuy, GroupMember, GroupMemberStatus
from tests.test_order_notifications_api import env  # noqa: F401


def _make_group(creator_id, product_id):
    from database import get_db
    import main
    db = next(main.app.dependency_overrides[get_db]())
    group = GroupBuy(group_name="Lekki Cabbage Group", group_location="Lekki", shareable_link="lekki-cabbage",
                     product_id=product_id, target_quantity="100 kg", target_quantity_numeric=100,
                     quantity_unit="kg", creator_id=creator_id, individual_contribution=5000, is_public=True)
    db.add(group)
    db.commit()
    db.add(GroupMember(group_id=group.id, user_id=creator_id, status=GroupMemberStatus.ACTIVE))
    db.commit()
    return group.public_id


def test_share_works_and_non_members_get_403(env):
    client, current, farmer_id, consumer_id, product_id, _ = env
    public_id = _make_group(consumer_id, product_id)

    current["user_id"] = consumer_id
    share = client.get(f"/api/v1/groups/{public_id}/share")
    assert share.status_code == 200, share.text  # was a 500 (missing "group" key)
    assert "lekki-cabbage" in share.json()["invitation_link"]

    # No chat yet: a clear 404 rather than a crash
    assert client.get(f"/api/v1/groups/{public_id}/chat/stats").status_code == 404

    # Someone outside the group is refused, not shown a server error
    current["user_id"] = farmer_id
    assert client.get(f"/api/v1/groups/{public_id}/share").status_code == 403


def test_public_group_routes_are_reachable(env):
    client, current, _, consumer_id, product_id, _ = env
    public_id = _make_group(consumer_id, product_id)

    listed = client.get("/api/v1/groups/public")
    assert listed.status_code == 200, listed.text  # was captured by /groups/{group_id}
    assert [g["public_id"] for g in listed.json()] == [public_id]

    by_id = client.get(f"/api/v1/groups/public/{public_id}")
    by_link = client.get("/api/v1/groups/public/lekki-cabbage")
    assert by_id.status_code == by_link.status_code == 200, (by_id.text, by_link.text)
    assert by_id.json()["group"]["group_name"] == by_link.json()["group"]["group_name"] == "Lekki Cabbage Group"
    assert client.get("/api/v1/groups/public/nope").status_code == 404


def test_group_lists_carry_the_product_picture_as_cover(env):
    client, current, _, consumer_id, product_id, _ = env
    from tests.test_stock import _db
    from features.marketplace.models import Product
    db = _db()
    db.get(Product, product_id).images = "https://example.com/cabbage.jpg,https://example.com/other.jpg"
    db.commit()
    public_id = _make_group(consumer_id, product_id)

    listed = client.get("/api/v1/groups/public").json()
    assert listed[0]["product_image"] == "https://example.com/cabbage.jpg"

    current["user_id"] = consumer_id
    mine = client.get("/api/v1/groups")
    assert mine.status_code == 200, mine.text
    assert [g["product_image"] for g in mine.json() if g["public_id"] == public_id] == ["https://example.com/cabbage.jpg"]

    # No picture on the product: no cover, not an error
    db.get(Product, product_id).images = ""
    db.commit()
    assert client.get("/api/v1/groups/public").json()[0]["product_image"] is None
