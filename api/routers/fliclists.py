from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.db import get_db
from api.models.flic_memory import FlicMemory
from api.models.flic_preset import FlicPreset
from api.schemas.flic_memory import FlicMemoryRead
from api.schemas.fliclist import FlicPresetCreate, FlicPresetRead

router = APIRouter(prefix="/fliclists", tags=["fliclists"])


@router.get("/", response_model=list[FlicPresetRead])
def list_presets(db: Session = Depends(get_db)):
    presets = db.query(FlicPreset).order_by(FlicPreset.created_at.desc()).all()
    return presets


@router.post("/", response_model=FlicPresetRead, status_code=status.HTTP_201_CREATED)
def create_preset(payload: FlicPresetCreate, db: Session = Depends(get_db)):
    existing = db.query(FlicPreset).filter(FlicPreset.name == payload.name).one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Preset name already exists")

    preset = FlicPreset(name=payload.name.strip(), filters=payload.filters.model_dump())
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preset(preset_id: int, db: Session = Depends(get_db)):
    preset = db.query(FlicPreset).filter(FlicPreset.id == preset_id).one_or_none()
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found")
    db.delete(preset)
    db.commit()
    return None


@router.get("/history", response_model=list[FlicMemoryRead])
def list_memory(db: Session = Depends(get_db)):
    entries = (
        db.query(FlicMemory)
        .order_by(desc(FlicMemory.created_at), desc(FlicMemory.id))
        .limit(10)
        .all()
    )
    return entries
