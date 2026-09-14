"""Authenticated Local-only update endpoints."""
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from local_app.updates import UpdateError
from pydantic import BaseModel, Field, StrictBool


class UpdateTab(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    page: str = Field(default='', max_length=120)
    prepared: str = Field(default='', max_length=80)
    saved: StrictBool = False
    busy: StrictBool = False
    closed: StrictBool = False
    warnings: list[str] = Field(default_factory=list, max_length=30)


class InstallRequest(BaseModel):
    preparation: str = Field(max_length=80)
    accept_warnings: StrictBool = False


class ClosedTabs(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)
    confirmed_closed: StrictBool = False


def update_router(require_user):
    router = APIRouter(prefix='/api/local/update', dependencies=[Depends(require_user)])

    def updater(request):
        service = getattr(request.app.state, 'local_update', None)
        host = request.client.host if request.client else None
        if service is None or not request.app.state.local_access.enabled_for(host):
            raise HTTPException(404)
        authority = urlsplit(str(request.base_url))
        if authority.hostname not in ('127.0.0.1', 'localhost', '::1'):
            raise HTTPException(403, 'คำสั่งอัปเดตต้องมาจากโปรแกรม Local')
        if request.method != 'GET':
            if request.headers.get('origin') != str(request.base_url).rstrip('/'):
                raise HTTPException(403, 'คำสั่งอัปเดตต้องมาจากหน้าโปรแกรมเดียวกัน')
        return service

    @router.get('')
    async def status(request: Request):
        return updater(request).status()

    @router.post('/check')
    async def check(request: Request):
        return await updater(request).check()

    @router.post('/seen')
    async def seen(request: Request):
        return await updater(request).claim_popup()

    @router.post('/download')
    async def download(request: Request):
        try:
            return await updater(request).download()
        except UpdateError as exc:
            raise HTTPException(409, str(exc))

    @router.post('/tabs')
    async def tab(payload: UpdateTab, request: Request):
        return updater(request).tab(payload.model_dump())

    @router.post('/prepare')
    async def prepare(request: Request):
        try:
            return await updater(request).prepare()
        except UpdateError as exc:
            raise HTTPException(409, str(exc))

    @router.post('/forget-tabs')
    async def forget_tabs(payload: ClosedTabs, request: Request):
        try:
            return updater(request).forget_tabs(payload.ids, payload.confirmed_closed)
        except UpdateError as exc:
            raise HTTPException(409, str(exc))

    @router.post('/cancel')
    async def cancel(request: Request):
        try:
            return updater(request).cancel()
        except UpdateError as exc:
            raise HTTPException(409, str(exc))

    @router.post('/install')
    async def install(payload: InstallRequest, request: Request):
        try:
            return await updater(request).install(payload.preparation, payload.accept_warnings)
        except UpdateError as exc:
            raise HTTPException(409, str(exc))

    return router
