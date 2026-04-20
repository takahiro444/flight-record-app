import React from 'react';
import { API_BASE_URL } from '../config';
import { useAuth } from '../auth/AuthContext';

// Hook manages flight retrieval and record listing.
// API_BASE_URL should be the API Gateway stage root, e.g.
//   Development: /apiGateway (handled by proxy rewrite to /prod)
//   Production:  https://<api-gateway-id>.execute-api.<region>.amazonaws.com/prod
// We append concrete resource paths below.
export default function useFlights() {
  const { idToken } = useAuth() || {};
  const [flightResponse, setFlightResponse] = React.useState(null);
  const [records, setRecords] = React.useState([]);
  const [recordsMeta, setRecordsMeta] = React.useState(null); // holds filtered flag, row_count, query_mode
  const [rawRecordsResponse, setRawRecordsResponse] = React.useState(null); // full parsed body for debug
  const [filtered, setFiltered] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);

  const fetchFlightData = async (apiKey, flightIata, date) => {
    setLoading(true); setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/retrieve-store-flight-data`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { 'x-api-key': apiKey } : {}),
          ...(idToken ? { 'Authorization': `Bearer ${idToken}` } : {})
        },
        body: JSON.stringify({ flight_iata: flightIata, date }),
      });
      if (!response.ok) {
        let msg = `Failed flight request (${response.status})`;
        if (response.status === 401) msg = 'Unauthorized (401). Login required or WAF restriction.';
        if (response.status === 403) msg = 'Forbidden (403). API key missing or invalid, or authorizer failure.';
        throw new Error(msg);
      }
      const data = await response.json();
      const parsedBody = typeof data.body === 'string' ? safeParse(data.body) : data.body;
      setFlightResponse(parsedBody || data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchFlightRecords = async (apiKey) => {
    setLoading(true); setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/display-flight-record-table`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { 'x-api-key': apiKey } : {}),
          ...(idToken ? { 'Authorization': `Bearer ${idToken}` } : {})
        },
      });
      if (!response.ok) {
        let msg = `Failed records request (${response.status})`;
        if (response.status === 401) msg = 'Unauthorized (401). Login required or WAF restriction.';
        if (response.status === 403) msg = 'Forbidden (403). API key missing or invalid, or authorizer failure.';
        throw new Error(msg);
      }
      const data = await response.json();
      // Support both legacy non-proxy integration (wrapper object with body field)
      // and Lambda proxy integration (raw JSON body already contains records).
      let parsed;
      if (data && Object.prototype.hasOwnProperty.call(data, 'body')) {
        parsed = typeof data.body === 'string' ? safeParse(data.body) : data.body;
      } else {
        parsed = data; // proxy integration format
      }
      if (parsed && Array.isArray(parsed.records)) {
        setRecords(parsed.records);
        setFiltered(!!parsed.filtered);
        setRecordsMeta({
          filtered: !!parsed.filtered,
          row_count: parsed.row_count,
          query_mode: parsed.query_mode,
          user_sub: parsed.user_sub
        });
        setRawRecordsResponse(parsed);
      } else if (Array.isArray(parsed)) {
        setRecords(parsed);
        setFiltered(false);
        setRecordsMeta({ filtered: false, row_count: parsed.length, query_mode: 'array_only' });
        setRawRecordsResponse(parsed);
      } else {
        setRecords([]);
        setFiltered(false);
        setRecordsMeta(null);
        setRawRecordsResponse(parsed);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  const safeParse = (str) => {
    try { return JSON.parse(str); } catch { return null; }
  };

  return { flightResponse, records, filtered, loading, error, recordsMeta, rawRecordsResponse, fetchFlightData, fetchFlightRecords };
}