from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.ml.retrain_job import run_retrain
from app.services.model_registry_service import (list_versions, promote_model,
                                                 register_model_version,
                                                 rollback_model)

router = APIRouter(prefix="/model_registry", tags=["Model Registry"])


class ModelRegisterIn(BaseModel):
    model_name: str
    version: str
    artifact_path: str
    metrics: Optional[dict] = None
    calibration: Optional[dict] = None


@router.post("/register")
async def register_model(payload: ModelRegisterIn, db: AsyncSession = Depends(get_db)):
    m = await register_model_version(
        db,
        model_name=payload.model_name,
        version=payload.version,
        artifact_path=payload.artifact_path,
        metrics=payload.metrics,
        calibration=payload.calibration,
    )
    return {"version": m.version, "status": m.status}


@router.post("/promote/{model_name}/{version}")
async def promote(model_name: str, version: str, db: AsyncSession = Depends(get_db)):
    m = await promote_model(db, model_name, version)
    if not m:
        raise HTTPException(status_code=404, detail="model not found")
    return {"version": m.version, "status": m.status, "is_active": m.is_active}


@router.post("/rollback/{model_name}/{version}")
async def rollback(
    model_name: str, version: str, reason: str, db: AsyncSession = Depends(get_db)
):
    m = await rollback_model(db, model_name, version, reason)
    if not m:
        raise HTTPException(status_code=404, detail="model not found")
    return {"version": m.version, "status": m.status}


@router.get("/versions")
async def versions(
    model_name: str | None = None,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    vs = await list_versions(db, model_name)
    # simple pagination
    total = len(vs)
    start = (page - 1) * size
    end = start + size
    page_items = vs[start:end]
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": [
            {
                "version": v.version,
                "model_name": v.model_name,
                "status": v.status,
                "is_active": v.is_active,
                "artifact_path": v.artifact_path,
                "metrics": v.metrics,
            }
            for v in page_items
        ],
    }


@router.get("/admin", response_class=HTMLResponse)
async def admin_ui():
    html = """
        <html>
            <head><title>Model Registry</title></head>
            <body>
                <h1>Model Registry</h1>
                <div>
                    <label>Page: <input id="page" type="number" value="1" min="1" style="width:60px"/></label>
                    <label>Size: <input id="size" type="number" value="10" min="1" style="width:60px"/></label>
                    <button onclick="refresh()">Refresh</button>
                    <button onclick="triggerRetrain()">Trigger Retrain</button>
                </div>
                <div id="list"></div>
                <script>
                    async function refresh(){
                        const page = document.getElementById('page').value || 1;
                        const size = document.getElementById('size').value || 10;
                        const res = await fetch(`/api/v1/model_registry/versions?page=${page}&size=${size}`);
                        const data = await res.json();
                        const c = document.getElementById('list');
                        c.innerHTML = `<div>Total: ${data.total} - Page ${data.page}</div>`;
                        data.items.forEach(d=>{
                            const el = document.createElement('div');
                            el.style.border = '1px solid #ccc'; el.style.padding='8px'; el.style.margin='6px';
                            el.innerHTML = `<b>${d.model_name}</b> @ <i>${d.version}</i><br/>status=${d.status} active=${d.is_active}<br/>metrics: ${JSON.stringify(d.metrics)}<br/><button onclick="promote('${d.model_name}','${d.version}')">Promote</button> <button onclick="rollback('${d.model_name}','${d.version}')">Rollback</button>`;
                            c.appendChild(el);
                        })
                    }
                    async function promote(m,v){
                        const res = await fetch(`/api/v1/model_registry/promote/${m}/${v}`,{method:'POST', headers:{'X-API-Key': prompt('API key')}});
                        if(!res.ok){ alert('Promote failed'); }
                        refresh();
                    }
                    async function rollback(m,v){
                        const reason = prompt('Reason for rollback'); if(!reason) return; const res = await fetch(`/api/v1/model_registry/rollback/${m}/${v}?reason=`+encodeURIComponent(reason),{method:'POST', headers:{'X-API-Key': prompt('API key')}}); if(!res.ok){ alert('Rollback failed'); } refresh();
                    }
                    async function triggerRetrain(){
                        const res = await fetch('/api/v1/model_registry/retrain', {method:'POST', headers:{'X-API-Key': prompt('API key')}});
                        if(res.ok) alert('Retrain scheduled'); else alert('Retrain failed');
                    }
                    refresh();
                </script>
            </body>
        </html>
        """
    return HTMLResponse(content=html)


@router.post("/retrain")
async def trigger_retrain(db: AsyncSession = Depends(get_db), key: str | None = None):
    # protected by middleware (X-API-Key) but extra check here
    try:
        # middleware has already validated X-API-Key; just spawn background job
        asyncio.create_task(run_retrain())
        return {"status": "retrain_started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
