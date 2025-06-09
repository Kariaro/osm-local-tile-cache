import http.server
import socketserver
import base64
import io
import os
from PIL import Image
import lxml.html as LH

if True:
    def escape(c):
        if c.isprintable() or c == '\r' or c == '\n' or c == '\t':
            return c
        c = ord(c)
        if c <= 0xff:
            return r'\x{0:02x}'.format(c)
        elif c <= '\uffff':
            return r'\u{0:04x}'.format(c)
        else:
            return r'\U{0:08x}'.format(c)
    xml = LH.parse("index.html")
    root = xml.getroot()
    for elm in root.findall(".//link"):
        with open(elm.attrib['href'], 'r', encoding='utf-8') as f:
            new_elm = LH.Element("style")
            new_elm.text = ''.join(escape(c) for c in f.read())
            p = elm.getparent()
            p.insert(p.index(elm), new_elm)
            p.remove(elm)
    for elm in root.findall(".//script"):
        if not 'src' in elm.attrib:
            continue
        with open(elm.attrib['src'], 'r', encoding='utf-8') as f:
            content = ''.join(escape(c) for c in f.read())
            new_elm = LH.Element("script")
            new_elm.text = content
            p = elm.getparent()
            p.insert(p.index(elm), new_elm)
            p.remove(elm)

    with open('dist/page.html', 'wb') as f:
        xml.write(f, method='html', encoding='utf-8')

PORT = 8000

Handler = http.server.SimpleHTTPRequestHandler
Handler.extensions_map = {
    '.manifest': 'text/cache-manifest',
    '.html': 'text/html',
    '.png': 'image/png',
    '.jpg': 'image/jpg',
    '.svg':	'image/svg+xml',
    '.css':	'text/css',
    '.js':	'application/x-javascript',
    '': 'application/octet-stream', # Default
}

class Handler(Handler):
    def __init__(self, *args, **kwargs):
        self.old_GET = super().do_GET
        super().__init__(*args, **kwargs)

    def do_POST(self):
        if self.path.startswith("/api/tile/"):
            coords = self.path.split("/")[3:]
            content_len = int(self.headers.get('Content-Length'))

            if int(coords[2]) < 8:
                post_body = self.rfile.read(content_len)
                base64data = post_body[len('data:image/png;base64,'):]
                img = Image.open(io.BytesIO(base64.b64decode(base64data)))
                img.convert('RGB').save(f"files/{coords[0]}_{coords[1]}_{coords[2]}.jpg")
            
            print('Tile:', coords, 'Content-Length:', content_len)
            self.send_response(200)
            self.end_headers()
    
    def find_tile(self, x, y, z):
        nx = x // 2
        ny = y // 2
        for nz in range(z-1, 0, -1):
            path = f"files/{nx}_{ny}_{nz}.jpg"
            exists = os.path.exists(path)
            if not exists:
                nx //= 2
                ny //= 2
                continue
            
            # print(path, nx, ny, nz, ':', x, y, z)
            
            img = Image.open(path)
            pick = (2 ** (z - nz))
            res = img.width // pick
            if res < 0:
                res = 1
            tx = x - nx * pick
            ty = y - ny * pick
            # print(tx, ty, (tx * res, ty * res, (tx + 1) * res, (ty + 1) * res))
            img = img.crop((tx * res, ty * res, (tx + 1) * res, (ty + 1) * res))
            return img
        return None
    
    def do_GET(self):
        if self.path.startswith("/api"):
            # print(self, self.__dict__)
            self.send_response(404)
            self.end_headers()
            self.wfile.write(self.path.encode('utf-8'))
        if self.path.startswith("/files/"):
            x, y, z = self.path[7:-4].split("_")
            
            if not os.path.exists(f"files/{x}_{y}_{z}.jpg"):
                img = self.find_tile(int(x), int(y), int(z))
                if img is not None:
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    self.send_response(200)
                    self.send_header("Content-type", "image/png")
                    self.end_headers()
                    self.wfile.write(buf.getvalue())
                    return
            self.old_GET()
        else:
            self.old_GET()

with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
    print("serving at port", PORT)
    httpd.serve_forever()
