// `vitest/config` em vez de `vite`: é o que tipa o bloco `test` abaixo.
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig, type Plugin } from 'vitest/config';

const AQUI = dirname(fileURLToPath(import.meta.url));
const CAPTURAS = resolve(AQUI, '..', 'runtime', 'captures');
export const BACKEND_PROXY_PREFIXES = [
  '/api',
  '/corpus',
  '/runtime',
  '/layout',
  '/operational-layout',
] as const;

export function validateProxyTarget(raw: string): string {
  const url = new URL(raw);
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.username !== '' ||
    url.password !== '' ||
    url.search !== '' ||
    url.hash !== '' ||
    (url.pathname !== '' && url.pathname !== '/')
  ) {
    throw new TypeError('VAULT_VITE_PROXY_TARGET precisa ser uma origem HTTP(S) sem credenciais');
  }
  return url.origin;
}

const PROXY_TARGET = validateProxyTarget(
  process.env.VAULT_VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000',
);
export const BACKEND_PROXY = Object.fromEntries(
  BACKEND_PROXY_PREFIXES.map((prefix) => [prefix, { target: PROXY_TARGET }]),
);

/**
 * Recebe uma captura da própria aplicação e grava em `runtime/captures/`.
 *
 * Existe porque a evidência visual precisa vir da aplicação real, e uma aba que não
 * compõe quadros não pode ser fotografada de fora. A página renderiza, lê o canvas e
 * envia o PNG; o servidor de desenvolvimento apenas grava.
 *
 * Só no servidor de desenvolvimento (`apply: 'serve'`): o build de produção não tem
 * este endpoint, e o nome do arquivo é higienizado para não escapar do diretório.
 */
function capturePlugin(): Plugin {
  return {
    name: 'atlas-capture',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/__capture', (req, res) => {
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end('use POST');
          return;
        }
        const pedacos: Buffer[] = [];
        req.on('data', (pedaco: Buffer) => pedacos.push(pedaco));
        req.on('end', () => {
          try {
            const corpo = JSON.parse(Buffer.concat(pedacos).toString('utf8')) as {
              name?: string;
              dataUrl?: string;
            };
            const seguro = (corpo.name ?? 'captura').replace(/[^a-zA-Z0-9._-]/g, '-');
            const base64 = (corpo.dataUrl ?? '').split(',')[1] ?? '';
            if (base64 === '') throw new Error('dataUrl vazia');
            mkdirSync(CAPTURAS, { recursive: true });
            const destino = join(CAPTURAS, `${seguro}.png`);
            writeFileSync(destino, Buffer.from(base64, 'base64'));
            res.setHeader('content-type', 'application/json');
            res.end(JSON.stringify({ written: destino }));
          } catch (error) {
            res.statusCode = 400;
            res.end(String(error));
          }
        });
      });
    },
  };
}

// O navegador usa caminhos same-origin. Em desenvolvimento estes cinco prefixos vão
// ao backend local; `/projection.json` e `/__capture` continuam pertencendo ao Vite.
export default defineConfig({
  plugins: [capturePlugin()],
  worker: {
    // O SharedWorker é módulo (`type: 'module'`). O default IIFE do Vite faz o
    // navegador recusar o script — `Failed to fetch a worker script` — e a trilha
    // viva nunca nasce.
    format: 'es',
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: BACKEND_PROXY,
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
