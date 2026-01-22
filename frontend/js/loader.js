export async function loadRound(url) {
  const res = await fetch(url);
  return await res.json();
}
