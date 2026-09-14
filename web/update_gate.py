"""Keep complete requests, not just individual browser steps, out of updates."""
from starlette.responses import JSONResponse


class UpdateWorkMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        guarded = (scope['type'] == 'websocket' and path == '/ws/search') or (
            scope['type'] == 'http' and scope.get('method') not in ('GET', 'HEAD', 'OPTIONS')
            and not path.startswith('/api/local/update'))
        application = scope.get('app')
        gate = getattr(getattr(application, 'state', None), 'browser_gate', None)
        update = getattr(getattr(application, 'state', None), 'local_update', None)
        if not guarded or gate is None or update is None:
            return await self.app(scope, receive, send)
        reservation = gate.work()
        try:
            reservation.__enter__()
        except RuntimeError as exc:
            if scope['type'] == 'websocket':
                await send({'type': 'websocket.close', 'code': 1013})
            else:
                await JSONResponse({'detail': str(exc)}, status_code=409)(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            reservation.__exit__(None, None, None)
