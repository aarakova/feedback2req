"""Disposable F1 browser provider. Never imported by the app or a production worker."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

counts = {}
guard = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        if self.path != '/api/chat':
            self.send_error(404)
            return
        value = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        request = json.loads(value['messages'][-1]['content'])
        text = request['input']['segments'][0]['text']
        with guard:
            counts[text] = counts.get(text, 0) + 1
            occurrence = counts[text]
        if text.startswith('F1-SLOW'):
            time.sleep(6)
        if text.startswith('F1-FAIL') or text.startswith('F1-ONCE') and occurrence == 1:
            self.send_error(503)
            return
        quote = ('ёж🙂\r\n' if '\r\n' in text else 'ёж🙂\n') if text.startswith('F1-REPEAT') else text
        response = {
            'coverage': [{'input_key': 's1', 'reviewed': True, 'disposition': 'completed'}],
            'questions': [], 'uncertainties': [],
            'result': {
                'fragments': [{'local_id': 'f', 'segment_key': 's1', 'quote': quote,
                               'occurrence': 1 if text.startswith('F1-REPEAT') else 0}],
                'findings': [{'local_id': 'n', 'text': 'Синтетическая находка браузерного теста',
                              'types': ['problem', 'request', 'observation', 'need'],
                              'mode': 'inferred' if text.startswith('F1-INFERRED') else 'direct',
                              'fragment_ids': ['f'], 'considered_keys': ['s1'], 'context_keys': []}],
            },
        }
        if text.startswith('F1-INVALID'):
            response['result']['fragments'][0]['quote'] = 'Цитата, которой нет во входе'
        if text.startswith('F1-EMPTY') or text.startswith('F1-INSUFFICIENT'):
            response['result'] = {'fragments': [], 'findings': []}
            response['coverage'][0]['reason'] = 'Синтетический тест без опубликованных находок'
            if text.startswith('F1-INSUFFICIENT'):
                response['coverage'][0]['disposition'] = 'insufficient_information'
        if text.startswith('F1-ANNOTATED'):
            response['questions'] = [{'local_id': 'q', 'text': 'Какое ожидание нужно уточнить?',
                                     'reason': 'Синтетический вопрос попытки', 'blocking': True,
                                     'related': [{'origin': 'output', 'key': 'n'}]}]
            response['uncertainties'] = [{'local_id': 'u', 'reason': 'Синтетическая неопределённость интерпретации',
                                         'related': [{'origin': 'input', 'key': 's1'}]}]
        raw = json.dumps({'done': True, 'message': {'content': json.dumps(response, ensure_ascii=False)}}, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


ThreadingHTTPServer(('0.0.0.0', 11434), Handler).serve_forever()
