import http.server
import socketserver
import base64
import io
import os
from PIL import Image

PORT = 8000

class Handler(http.server.SimpleHTTPRequestHandler):
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
