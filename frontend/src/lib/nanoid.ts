// Lightweight nanoid replacement — no external dep needed
export function nanoid(size = 21): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-";
  let id = "";
  const bytes = crypto.getRandomValues(new Uint8Array(size));
  for (let i = 0; i < size; i++) {
    id += chars[bytes[i] & 63];
  }
  return id;
}
