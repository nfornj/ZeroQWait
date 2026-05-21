/**
 * TelegramConnect.jsx — Lightweight "Connect Telegram" button.
 *
 * Zero-config for the owner. They tap one button, Telegram opens, they tap Start.
 * This component polls the status endpoint every 3 seconds while waiting for the
 * handshake to complete, then shows a "✅ Connected" confirmation.
 *
 * Props:
 *   shopId     {number}   — required, the shop to link
 *   onConnected {function} — optional callback fired when connection is confirmed
 *
 * Usage:
 *   <TelegramConnect shopId={shop.id} onConnected={() => refetch()} />
 */

import React, { useState, useEffect, useRef } from 'react';

const TELEGRAM_BLUE = '#229ED9';

const styles = {
  wrapper: {
    display: 'inline-flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    gap: '8px',
    fontFamily: 'inherit',
  },
  button: (connected, loading) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 20px',
    borderRadius: '8px',
    border: 'none',
    cursor: connected || loading ? 'default' : 'pointer',
    fontWeight: 600,
    fontSize: '14px',
    background: connected ? '#2e7d32' : loading ? '#e0e0e0' : TELEGRAM_BLUE,
    color: connected ? '#fff' : loading ? '#666' : '#fff',
    transition: 'background 0.2s',
    opacity: loading ? 0.8 : 1,
  }),
  errorText: {
    fontSize: '12px',
    color: '#c62828',
    maxWidth: '280px',
  },
};

const TelegramIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.844 14.45l-2.96-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.834.938l.47.171z" />
  </svg>
);

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

export default function TelegramConnect({ shopId, onConnected }) {
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  // Check current status on mount
  useEffect(() => {
    let cancelled = false;
    fetch(`/api/shops/${shopId}/telegram/status`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
    })
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled && d.connected) setConnected(true);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [shopId]);

  // Clean up polling on unmount
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  async function handleConnect() {
    if (connected || loading) return;
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token') || '';
      const res = await fetch(`/api/shops/${shopId}/telegram/connect`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Something went wrong. Please try again.');
      }

      const { deep_link } = await res.json();

      // Open Telegram deep link — works on mobile (opens app) and desktop (opens web)
      window.open(deep_link, '_blank', 'noopener,noreferrer');

      // Poll every 3 seconds for up to 10 minutes until connected
      pollRef.current = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/shops/${shopId}/telegram/status`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          const status = await statusRes.json();
          if (status.connected) {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setConnected(true);
            setLoading(false);
            if (typeof onConnected === 'function') onConnected();
          }
        } catch (_) {}
      }, 3000);

      // Stop polling after 10 minutes regardless
      setTimeout(() => {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setLoading(false);
        }
      }, 600_000);

    } catch (err) {
      setError(err.message || 'Could not start connection. Please try again.');
      setLoading(false);
    }
  }

  return (
    <div style={styles.wrapper}>
      <button
        style={styles.button(connected, loading)}
        onClick={handleConnect}
        disabled={connected || loading}
        aria-label={connected ? 'Telegram connected' : 'Connect Telegram'}
      >
        {connected ? <CheckIcon /> : <TelegramIcon />}
        {connected
          ? '✅ Telegram Connected'
          : loading
          ? 'Waiting for Telegram…'
          : 'Connect Telegram'}
      </button>

      {error && <span style={styles.errorText}>{error}</span>}

      {loading && !connected && (
        <span style={{ fontSize: '12px', color: '#555' }}>
          Tap <strong>Start</strong> in the Telegram window, then come back here.
        </span>
      )}
    </div>
  );
}
