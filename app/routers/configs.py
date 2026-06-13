import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import AIConfig
from app.schemas import AIConfigCreate, AIConfigUpdate, AIConfigResponse
from app.config import encrypt_api_key

logger = logging.getLogger("app.configs")
router = APIRouter(prefix="/api/configs/ai", tags=["AI Config"])


@router.get("", response_model=list[AIConfigResponse])
def list_configs(db: Session = Depends(get_db)):
    return db.query(AIConfig).order_by(AIConfig.created_at.desc()).all()


@router.post("", response_model=AIConfigResponse, status_code=201)
def create_config(data: AIConfigCreate, db: Session = Depends(get_db)):
    config = AIConfig(
        provider=data.provider,
        api_key=encrypt_api_key(data.api_key),
        api_base=data.api_base,
        quick_model=data.quick_model,
        deep_model=data.deep_model,
    )
    if db.query(AIConfig).count() == 0:
        config.is_active = True
    db.add(config)
    db.commit()
    db.refresh(config)
    logger.info("AI config %d created provider=%s", config.id, config.provider)
    return config


@router.put("/{config_id}", response_model=AIConfigResponse)
def update_config(config_id: int, data: AIConfigUpdate, db: Session = Depends(get_db)):
    config = db.query(AIConfig).get(config_id)
    if not config:
        raise HTTPException(404, "Config not found")
    if data.api_key is not None:
        config.api_key = encrypt_api_key(data.api_key)
    for field in ("provider", "api_base", "quick_model", "deep_model"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(config, field, val)
    if data.is_active:
        db.query(AIConfig).filter(AIConfig.id != config_id).update({"is_active": False})
        config.is_active = True
    db.commit()
    db.refresh(config)
    return config


@router.delete("/{config_id}", status_code=204)
def delete_config(config_id: int, db: Session = Depends(get_db)):
    config = db.query(AIConfig).get(config_id)
    if not config:
        raise HTTPException(404, "Config not found")
    db.delete(config)
    db.commit()
    logger.info("AI config %d deleted provider=%s", config_id, config.provider)


@router.post("/{config_id}/activate", response_model=AIConfigResponse)
def activate_config(config_id: int, db: Session = Depends(get_db)):
    config = db.query(AIConfig).get(config_id)
    if not config:
        raise HTTPException(404, "Config not found")
    db.query(AIConfig).update({"is_active": False})
    config.is_active = True
    db.commit()
    db.refresh(config)
    logger.info("AI config %d activated provider=%s", config_id, config.provider)
    return config
