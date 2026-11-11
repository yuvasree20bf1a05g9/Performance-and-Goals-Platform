"""The ORM must match the data dictionary exactly (prevents schema drift between layers)."""
from backend.app.models import MODEL_BY_TABLE
from domain.schema import TABLES


def test_orm_matches_data_dictionary():
    for t in TABLES:
        model = MODEL_BY_TABLE[t.name]
        orm_cols = [c.key for c in model.__table__.columns]
        assert orm_cols == t.field_names(), t.name
        assert [c.key for c in model.__table__.primary_key.columns] == [t.pk]
        for f in t.fields:
            col = model.__table__.columns[f.name]
            if f.name != t.pk:
                assert col.nullable == (not f.required), f"{t.name}.{f.name} nullability"
            if f.fk:
                assert {fk.target_fullname for fk in col.foreign_keys} == {f.fk}, f"{t.name}.{f.name} FK"
