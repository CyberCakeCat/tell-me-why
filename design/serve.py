"""Read-only preview: exposes design assets and cases.json only, never project secrets."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlsplit
import mimetypes
ROOT = Path(__file__).resolve().parent
class Preview(SimpleHTTPRequestHandler):
    def do_GET(self):
        route = unquote(urlsplit(self.path).path)
        if route == '/':
            self.send_response(302); self.send_header('Location', '/design/'); self.end_headers(); return
        if route == '/app/data/cases.json':
            target = ROOT.parent / 'app/data/cases.json'
        elif route.startswith('/design/'):
            target = (ROOT / route[len('/design/'):]).resolve()
            if target == ROOT: target = ROOT / 'index.html'
            if ROOT not in target.parents or target.suffix not in {'.html','.css','.js','.json','.svg','.png','.txt','.md'}:
                self.send_error(404); return
        else:
            self.send_error(404); return
        if not target.is_file(): self.send_error(404); return
        data=target.read_bytes(); self.send_response(200)
        self.send_header('Content-Type', (mimetypes.guess_type(str(target))[0] or 'application/octet-stream') + '; charset=utf-8')
        self.send_header('Content-Length', str(len(data))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(data)
    def do_HEAD(self): self.send_error(405)
if __name__ == '__main__':
    print('Tell Me WHY preview: http://127.0.0.1:8765/design/', flush=True)
    ThreadingHTTPServer(('127.0.0.1',8765), Preview).serve_forever()
