"""One app: inherited Dashboard + MCP + shared catalog."""
import logging
from logging.handlers import RotatingFileHandler
import os
import asyncio
import uvicorn
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from mcp_bridge import server,catalog,DESCRIPTIONS
from dashboard import routes

async def health(request):
    return JSONResponse({'service':'gphotos-content-vision','version':'2.1','tools':len(DESCRIPTIONS),'pid':os.getpid()})

inner_app=server.streamable_http_app(host='127.0.0.1',json_response=True,
    custom_starlette_routes=[Route('/health',health),*routes(catalog)])

async def app(scope,receive,send):
    if scope['type']=='http':
        headers=dict(scope['headers'])
        host=headers.get(b'host',b'').decode().lower()
        origin=headers.get(b'origin',b'').decode().lower()
        allowed=('127.0.0.1:8898','localhost:8898','127.0.0.1:8899','localhost:8899')
        if host not in allowed or (origin and origin!='http://'+host):
            await PlainTextResponse('Forbidden host/origin',status_code=403)(scope,receive,send)
            return
        total=0
        async def bounded_receive():
            nonlocal total
            message=await receive()
            total+=len(message.get('body',b''))
            if total>70*1024*1024:
                raise ValueError('Request exceeds 70 MiB')
            return message
        await inner_app(scope,bounded_receive,send)
    else:
        await inner_app(scope,receive,send)

async def run():
    first=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8898,log_config=None,access_log=False))
    second=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8899,lifespan='off',log_config=None,access_log=False))
    await asyncio.gather(first.serve(),second.serve())

if __name__=='__main__':
    handler=RotatingFileHandler(catalog.store.root/'service.log',maxBytes=2_000_000,backupCount=3,encoding='utf-8')
    logging.basicConfig(level=logging.INFO,handlers=[handler])
    asyncio.run(run())
