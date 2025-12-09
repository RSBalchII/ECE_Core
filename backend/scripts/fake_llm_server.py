from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class FakeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.endswith('/v1/chat/completions') or self.path.endswith('/chat/completions'):
            length = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(length) if length else b''
            try:
                payload = json.loads(raw.decode('utf-8')) if raw else {}
            except Exception:
                payload = {}
            prompt_text = ''
            if isinstance(payload.get('messages'), list) and len(payload.get('messages', [])) > 0:
                prompt_text = payload['messages'][-1].get('content', '')
            elif payload.get('prompt'):
                prompt_text = payload.get('prompt')
            reply = f"[FAKE LLM RESPONSE] {prompt_text}"
            response_body = {"id": "fake-llm-1", "object": "chat.completion", "choices": [{"message": {"role": "assistant", "content": reply}, "index": 0}]}
            body = json.dumps(response_body).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8080), FakeHandler)
    print('Fake LLM server started on 127.0.0.1:8080')
    server.serve_forever()
