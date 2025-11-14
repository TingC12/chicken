# app/routers/inventory.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user_id
from app.models.economy import InventoryItem, StoreItem, ItemUsage
from app.schemas.economy import InventoryItemRow, UseItemIn, UseItemResult
from app.services.level import apply_exp_and_update
from app.models.user import User
from random import randint

router = APIRouter(prefix="/inventory", tags=["inventory"])

@router.get("/bag", response_model=list[InventoryItemRow])
def get_bag(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(InventoryItem)
        .join(StoreItem, InventoryItem.item_id == StoreItem.id)
        .filter(InventoryItem.user_id == user_id, InventoryItem.quantity > 0)
        .all()
    )
    result: list[InventoryItemRow] = []
    for inv in rows:
        result.append(
            InventoryItemRow(
                item_id=inv.item.id,
                name=inv.item.name,
                quantity=inv.quantity,
                description=inv.item.description,
            )
        )
    return result

@router.post("/use", response_model=UseItemResult)
def use_item(
    payload: UseItemIn,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # 找背包
    inv = db.query(InventoryItem).filter(
        InventoryItem.user_id == user_id,
        InventoryItem.item_id == payload.item_id,
    ).first()

    if not inv or inv.quantity <= 0:
        raise HTTPException(status_code=400, detail="item not in inventory")

    # 找道具資料
    item = db.query(StoreItem).filter(StoreItem.id == payload.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="item not found")

    # 找 user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    # 計算這次 EXP（隨機）
    if item.exp_min == item.exp_max:
        exp_gain = item.exp_min
    else:
        exp_gain = randint(item.exp_min, item.exp_max)

    # 使用一次：背包數量 -1
    inv.quantity -= 1
    db.commit()

    # 實際加到 user.exp / level
    apply_exp_and_update(user, exp_gain)
    db.commit()
    db.refresh(user)

    # 紀錄使用紀錄
    usage = ItemUsage(
        user_id=user_id,
        item_id=item.id,
        exp_gain=exp_gain,
    )
    db.add(usage)
    db.commit()

    remaining_qty = max(inv.quantity, 0)

    return UseItemResult(
        item_id=item.id,
        item_name=item.name,
        exp_gain=exp_gain,
        new_exp=user.exp,
        new_level=user.level,
        remaining_quantity=remaining_qty,
    )
