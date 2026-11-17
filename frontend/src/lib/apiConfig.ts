export const getApiBase = () => {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== 'undefined') {
    return `http://${window.location.hostname || '127.0.0.1'}:8000`;
  }
  return 'http://127.0.0.1:8000';
};

export const getWsBase = () => {
  if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;
  if (typeof window !== 'undefined') {
    return `ws://${window.location.hostname || '127.0.0.1'}:8000`;
  }
  return 'ws://127.0.0.1:8000';
};
