from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MaterialGroupOut, MaterialGroupSummaryOut
from app.services.material_group import build_material_catalog, build_material_groups

router = APIRouter(prefix="/api/material-groups", tags=["material"])


def _parse_keys(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return keys or None


@router.get("/catalog", response_model=list[MaterialGroupSummaryOut])
def list_material_catalog(
    search: str | None = Query(None, description="按物料族或 LOT NO. 模糊筛选目录"),
    db: Session = Depends(get_db),
):
    return build_material_catalog(db, search=search)


@router.get("", response_model=list[MaterialGroupOut])
def list_material_groups(
    lot_no: str | None = Query(None),
    stage: str | None = Query(None),
    material_keys: str | None = Query(None, description="逗号分隔的物料族 key，仅返回选中项详情"),
    db: Session = Depends(get_db),
):
    return build_material_groups(
        db,
        lot_no=lot_no,
        stage=stage,
        material_keys=_parse_keys(material_keys),
    )
