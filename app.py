from aiohttp import web
from asyncssh import connect
import asyncssh
import json
import mimetypes
import aiohttp
import asyncio
async def handle_command(request):
    async with connect("localhost") as conn:
        result = await conn.run('ls -l', check=True)
        return web.Response(text=result.stdout)

async def websocket_handler(request):
    print('Websocket connection starting')
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)
    print('Websocket connection ready')
    async with connect("localhost") as conn:
        (sshWriter, sshReader, sshExReader)= await conn.open_session()
        app = request.app()
        ws_task = app.loop.create_task(ws.receive())
        ssh_task = app.loop.create_task(sshReader.read(1024))
        sshex_task = app.loop.create_task(sshExReader.read(1024))
            
        while True:
            
            done, pending = await asyncio.wait([ws_task,ssh_task,sshex_task],return_when=asyncio.FIRST_COMPLETED)

            if ws_task in done:
                msg = ws_task.result()
                print(msg)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close':
                        conn.close()
                        await conn.wait_closed()
                        break
                    else:
                        sshWriter.write(msg.data)
                        await sshWriter.drain()
                    ws_task = app.loop.create_task(ws.receive())
        
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    conn.close()
                    await conn.wait_closed()
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print('ws connection closed with exception %s' %
                            ws.exception())
                    conn.close()
                    await conn.wait_closed()
                    break
                    
            if ssh_task in done:
                data = ssh_task.result()
                print(data)
                await ws.send_str(data)
                ssh_task = app.loop.create_task(sshReader.read(1024))
            if sshex_task in done:
                data = sshex_task.result()
                print(data)
                await ws.send_str(data)
                ssh_task = app.loop.create_task(sshExReader.read(1024))
        
            
    print('Websocket connection closed')
    return ws   


async def handle_sftp(request):
    #ref: https://www.programcreek.com/python/example/91858/aiohttp.web.StreamResponse
    fileName = r'example.txt'
    async with asyncssh.connect('localhost') as conn:
        async with conn.start_sftp_client() as sftp:
            async with sftp.open(fileName,encoding=None) as file:
                response = web.StreamResponse(headers={
                    'CONTENT-DISPOSITION': 'attachment; filename="%s"' % fileName
                })
                response.content_type = mimetypes.guess_type(fileName)
                await response.prepare(request)
                stat = await file.stat()
                print(str(stat))
                try:
                    while True:
                        data = await file.read(102400)
                        if not data:
                            break
                        await response.write(data)
                    return response
                finally:
                    #await response.write_eof()
                    print('finished downloading file')
                    await file.close() 
                    

async def handle(request):
    return web.FileResponse('index.html')

app = web.Application()

app.add_routes([web.get('/',handle),
                web.get('/command',handle_command),
                web.get('/sftp',handle_sftp)])
app.add_routes([web.get('/ws', websocket_handler)])

web.run_app(app)