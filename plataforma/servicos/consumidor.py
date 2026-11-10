"""
CCM520 - Internet das Coisas | Projeto 2 (o mesmo consumidor das Aulas 7 e 8)
Centro Universitário FEI - Prof. Rafael Gomes Alves

Context Consumer de exemplo: recebe as notificações enviadas pelo Orion
(subscrições) e as guarda em memória para consulta.

  Qualquer POST/PUT/PATCH em http://consumidor:3000/<caminho>  -> registra a notificação
  GET    http://localhost:3001/notificacoes                     -> lista as notificações (mais recente primeiro)
         (no Projeto 2 a porta 3000 do computador é do Grafana: o consumidor fica na 3001)
         ?caminho=/alertas       filtra pelo caminho em que a notificação chegou
         ?subscriptionId=<id>    filtra pelo id da subscrição (notificações no formato padrão)
         ?ultimas=5              limita a quantidade (padrão 20)
  DELETE http://localhost:3001/notificacoes                     -> apaga o histórico

Usa apenas a biblioteca padrão do Python: não precisa de pip install.
"""

import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORTA = 3000
MAXIMO = 500                     # notificações guardadas em memória
CABECALHOS = ("Fiware-Service", "Fiware-ServicePath", "Content-Type",
              "Ngsiv2-AttrsFormat", "Fiware-Correlator", "User-Agent")

notificacoes = []
trava = threading.Lock()


class Consumidor(BaseHTTPRequestHandler):

    def _responder(self, codigo, corpo=None):
        dados = json.dumps(corpo, ensure_ascii=False, indent=2).encode("utf-8") if corpo is not None else b""
        self.send_response(codigo)
        if dados:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def _receber(self):
        url = urlparse(self.path)
        tamanho = int(self.headers.get("Content-Length") or 0)
        bruto = self.rfile.read(tamanho).decode("utf-8", errors="replace") if tamanho else ""
        try:
            corpo = json.loads(bruto) if bruto else None
        except ValueError:
            corpo = bruto                       # payload de texto (httpCustom.payload)
        registro = {
            "recebidaEm": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "metodo": self.command,
            "caminho": url.path,
            "query": {k: v[0] for k, v in parse_qs(url.query).items()},
            "cabecalhos": {h: self.headers[h] for h in CABECALHOS if self.headers.get(h)},
            "corpo": corpo,
        }
        with trava:
            notificacoes.append(registro)
            del notificacoes[:-MAXIMO]
        print(f"\n=== {registro['recebidaEm']}  {self.command} {self.path}")
        for h, v in registro["cabecalhos"].items():
            print(f"    {h}: {v}")
        print(json.dumps(corpo, ensure_ascii=False, indent=2) if not isinstance(corpo, str) else corpo)
        self._responder(200, {"recebida": True})

    do_POST = do_PUT = do_PATCH = _receber

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            return self._responder(200, {"servico": "consumidor", "notificacoes": len(notificacoes)})
        if url.path != "/notificacoes":
            return self._responder(404, {"erro": "use GET /notificacoes"})
        filtros = {k: v[0] for k, v in parse_qs(url.query).items()}
        with trava:
            lista = list(reversed(notificacoes))
        if "caminho" in filtros:
            lista = [n for n in lista if n["caminho"] == filtros["caminho"]]
        if "subscriptionId" in filtros:
            lista = [n for n in lista if isinstance(n["corpo"], dict)
                     and n["corpo"].get("subscriptionId") == filtros["subscriptionId"]]
        self._responder(200, lista[:int(filtros.get("ultimas", 20))])

    def do_DELETE(self):
        if urlparse(self.path).path != "/notificacoes":
            return self._responder(404, {"erro": "use DELETE /notificacoes"})
        with trava:
            notificacoes.clear()
        self._responder(204)

    def log_message(self, formato, *args):
        pass                                    # o log útil já é impresso em _receber


if __name__ == "__main__":
    print(f"Consumidor de notificações ouvindo na porta {PORTA}")
    ThreadingHTTPServer(("0.0.0.0", PORTA), Consumidor).serve_forever()
