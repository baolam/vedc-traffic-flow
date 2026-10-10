import { useState, useEffect, useRef } from 'react';

export function useWebSocket(url, fallbackPollingCallback, intervalMs = 2000) {
  const [data, setData] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    let isMounted = true;
    let wsUrl = url;

    // Convert http/https to ws/wss
    if (wsUrl.startsWith('http://')) {
      wsUrl = wsUrl.replace('http://', 'ws://');
    } else if (wsUrl.startsWith('https://')) {
      wsUrl = wsUrl.replace('https://', 'wss://');
    }

    try {
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        if (isMounted) setIsConnected(true);
      };

      socket.onmessage = (event) => {
        if (isMounted) {
          try {
            const parsed = JSON.parse(event.data);
            setData(parsed);
          } catch (err) {
            console.warn('Failed to parse WebSocket message', err);
          }
        }
      };

      socket.onerror = () => {
        if (isMounted) setIsConnected(false);
      };

      socket.onclose = () => {
        if (isMounted) setIsConnected(false);
      };
    } catch (err) {
      if (isMounted) setIsConnected(false);
    }

    // Fallback polling interval if WebSocket is not connected or as backup
    const interval = setInterval(() => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        if (fallbackPollingCallback) {
          fallbackPollingCallback().then(polledData => {
            if (isMounted && polledData) setData(polledData);
          });
        }
      }
    }, intervalMs);

    return () => {
      isMounted = false;
      clearInterval(interval);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [url, intervalMs]);

  return { data, isConnected };
}
