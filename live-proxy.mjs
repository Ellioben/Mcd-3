#!/usr/bin/env node
/* 本地 CORS 代理：浏览器 → http://127.0.0.1:8787/mcp → https://mcp.mcd.cn
   mcp.mcd.cn 不返回 Access-Control-Allow-Origin，浏览器直连会被拦，
   启动方式：cd mcd && node live-proxy.mjs ，然后打开 live.html */
import http from 'node:http';

const TARGET = 'https://mcp.mcd.cn';
const TOKEN  = 'Bearer mOMLLKPQsweEhKRnsR67f7v48DWVRv4B';
const PORT   = 8787;

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if(req.method === 'OPTIONS'){ res.writeHead(204); res.end(); return; }
  if(req.method !== 'POST' || req.url !== '/mcp'){
    res.writeHead(404); res.end('use POST /mcp'); return;
  }
  let body = '';
  for await (const chunk of req) body += chunk;
  try{
    const upstream = await fetch(TARGET, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
        'Authorization': TOKEN,
      },
      body,
    });
    res.writeHead(upstream.status, { 'Content-Type': upstream.headers.get('content-type') || 'application/json' });
    res.end(await upstream.text());
  }catch(e){
    res.writeHead(502); res.end(JSON.stringify({ error: String(e) }));
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`MCP 代理已启动 → http://127.0.0.1:${PORT}/mcp`);
  console.log('现在打开 live.html 即可');
});
