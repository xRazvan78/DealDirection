"""Task 1: settings, text folding, schema rules and test fixtures."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import PointsLedger, Receipt, ShoppingList, StoreProduct, User
from app.textutil import fold


def make_list(db: Session) -> ShoppingList:
    user = User(email="test-foundation@example.com", password_hash="not-a-real-hash")
    db.add(user)
    db.flush()
    shopping_list = ShoppingList(user_id=user.id, name="Test")
    db.add(shopping_list)
    db.flush()
    return shopping_list


def make_receipt(list_id: int, store_id: int, fingerprint: str) -> Receipt:
    return Receipt(
        list_id=list_id,
        store_id=store_id,
        fingerprint=fingerprint,
        purchased_at=datetime(2026, 11, 6, 12, 0, tzinfo=UTC),
        total=Decimal("100.00"),
        estimate=Decimal("100.00"),
        paid=Decimal("100.00"),
        modifier=Decimal("1.00"),
        points=1000,
    )


def test_settings_match_readme(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None, DATABASE_URL="postgresql://x", JWT_SECRET="x")

    assert settings.MARGIN == Decimal("0.05")
    assert settings.MAX_MODIFIER == Decimal("1.25")
    assert settings.POINTS_PER_LEI == 10
    assert settings.MIN_SPLIT_SAVING_LEI == Decimal("10")
    assert settings.OCR_LANG == "ron+eng"
    assert settings.OCR_PSM == 4
    assert settings.OCR_MIN_MATCH_SCORE == 70
    assert settings.MAX_UPLOAD_MB == 10
    assert settings.TESSERACT_CMD == "tesseract"
    assert settings.TRASH_RETENTION_DAYS == 14


def test_get_settings_is_cached():
    assert get_settings() is get_settings()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Brânză de Țară", "branza de tara"),
        ("ĂÂÎȘȚ ăâîșț", "aaist aaist"),
        ("Ş ţ", "s t"),  # older cedilla forms, common in scraped text
        ("Lapte 3.5%", "lapte 3.5%"),
    ],
)
def test_fold(text, expected):
    assert fold(text) == expected


def test_sample_fixture(db, sample):
    assert len(sample.stores) == 2
    assert [c.level for c in (sample.category, sample.type, sample.size)] == [
        "category",
        "type",
        "size",
    ]
    assert sample.size.parent_id == sample.type.id
    assert sample.type.parent_id == sample.category.id
    assert sample.products[2].price == Decimal("7.90")


def test_data_is_rolled_back_after_each_test(db):
    leftovers = db.scalar(
        select(func.count())
        .select_from(StoreProduct)
        .where(StoreProduct.name.like("Lapte Albalact 3.5%%"))
    )
    assert leftovers == 0


def test_repeated_receipt_fingerprint_raises(db, sample):
    shopping_list = make_list(db)
    db.add(make_receipt(shopping_list.id, sample.stores[0].id, "same"))
    db.flush()

    db.add(make_receipt(shopping_list.id, sample.stores[1].id, "same"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_one_receipt_per_list_and_store(db, sample):
    shopping_list = make_list(db)
    db.add(make_receipt(shopping_list.id, sample.stores[0].id, "first"))
    db.flush()

    db.add(make_receipt(shopping_list.id, sample.stores[0].id, "second"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_new_list_is_a_draft_outside_the_trash(db):
    shopping_list = make_list(db)
    db.refresh(shopping_list)

    assert shopping_list.state == "draft"
    assert shopping_list.suggestion_shown is False
    assert shopping_list.deleted_at is None


def test_soft_deleted_list_keeps_receipt_and_points(db, sample):
    shopping_list = make_list(db)
    receipt = make_receipt(shopping_list.id, sample.stores[0].id, "kept")
    db.add(receipt)
    db.flush()
    db.add(
        PointsLedger(
            user_id=shopping_list.user_id,
            amount=1000,
            reason="Bon",
            receipt_id=receipt.id,
        )
    )

    shopping_list.deleted_at = datetime.now(UTC)
    db.commit()

    assert db.get(Receipt, receipt.id).list_id == shopping_list.id
    db.add(make_receipt(shopping_list.id, sample.stores[1].id, "kept"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_a_list_with_a_receipt_cannot_be_hard_deleted(db, sample):
    shopping_list = make_list(db)
    db.add(make_receipt(shopping_list.id, sample.stores[0].id, "guarded"))
    db.flush()

    with pytest.raises(IntegrityError):
        db.execute(delete(ShoppingList).where(ShoppingList.id == shopping_list.id))
