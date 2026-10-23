// Test-only TCP relay: container browser keeps the approved localhost Origin.
// Bytes pass through unchanged to the actual Nginx; no HTTP/header simulation.
import net from 'node:net';

const target = process.env.F2R_E2E_TUNNEL;
if (!target) throw new Error('Set F2R_E2E_TUNNEL to the isolated test frontend');
const [host, port] = target.split(':');
const server = net.createServer(socket => {
  const upstream = net.connect(Number(port), host);
  socket.pipe(upstream).pipe(socket);
  upstream.on('error', () => socket.destroy());
  socket.on('error', () => upstream.destroy());
  socket.on('close', () => upstream.destroy());
});
server.listen(18080, '127.0.0.1');
