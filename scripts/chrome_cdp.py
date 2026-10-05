import base64,json,os,socket,struct,urllib.request,time
from urllib.parse import urlparse
class CDP:
 def __init__(self):
  tabs=json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
  u=urlparse(next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page'))
  self.s=socket.create_connection((u.hostname,u.port),timeout=30); self.ident=0
  key=base64.b64encode(os.urandom(16)).decode()
  self.s.sendall(f'GET {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: http://localhost:9222\r\n\r\n'.encode())
  h=b''
  while b'\r\n\r\n' not in h:h+=self.s.recv(1)
  assert b'101' in h,h
 def read(self,n):
  r=b''
  while len(r)<n:
   chunk=self.s.recv(n-len(r))
   if not chunk:raise ConnectionError('Socket closed')
   r+=chunk
  return r
 def frame(self,data):
  data=data.encode();n=len(data);mask=os.urandom(4)
  head=bytes([0x81,0x80|n]) if n<126 else bytes([0x81,0xfe])+struct.pack('!H',n) if n<65536 else bytes([0x81,0xff])+struct.pack('!Q',n)
  self.s.sendall(head+mask+bytes(v^mask[i%4] for i,v in enumerate(data)))
 def recv(self):
  a,b=self.read(2);n=b&127
  if n==126:n=struct.unpack('!H',self.read(2))[0]
  if n==127:n=struct.unpack('!Q',self.read(8))[0]
  if b&128:mask=self.read(4)
  data=self.read(n)
  if (a&15)==8:raise ConnectionError('Websocket closed')
  return json.loads(data)
 def call(self,method,params={}):
  self.ident+=1;ident=self.ident;self.frame(json.dumps({'id':ident,'method':method,'params':params}))
  while True:
   msg=self.recv()
   if msg.get('id')==ident:
    if 'error' in msg:raise RuntimeError(msg['error'])
    return msg.get('result',{})
 def js(self,expression):
  r=self.call('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
  if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
  return r.get('result',{}).get('value')
 def screenshot(self,path):
  r=self.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False});open(path,'wb').write(base64.b64decode(r['data']))
if __name__=='__main__':
 c=CDP();c.call('Page.enable');c.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
 print(c.js('({ready:document.documentElement.dataset.ready,points:document.getElementById("point-count").textContent,errors:document.getElementById("viewer-error").textContent,width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight})'))
 c.screenshot('/home/lee/vivecode/preview-desktop.png')
 print('Screenshot saved')
