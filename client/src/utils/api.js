// This file contains utility functions for making API calls to the backend server, handling requests and responses.

import { API_BASE_URL } from '../config';

export const fetchFlightData = async (apiKey, flightIata, date) => {
  try {
    const response = await fetch(`${API_BASE_URL}/retrieve-store-flight-data`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
      },
      body: JSON.stringify({ flight_iata: flightIata, date }),
    });

    if (!response.ok) {
      throw new Error('Failed to fetch flight data');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching flight data:', error);
    throw error;
  }
};

export const fetchFlightRecords = async (apiKey) => {
  try {
    const response = await fetch(`${API_BASE_URL}/display-flight-record-table`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch users');
    }

    const data = await response.json();
  return typeof data.body === 'string' ? JSON.parse(data.body) : data.body;
  } catch (error) {
    console.error('Error fetching users:', error);
    throw error;
  }
};

// Retrieve authenticated identity from backend. Requires idToken in Authorization header.
export const fetchWhoAmI = async (idToken) => {
  try {
    const response = await fetch(`${API_BASE_URL}/whoami`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to fetch whoami (${response.status})`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching whoami:', error);
    throw error;
  }
};

// Chat with Bedrock agent via proxy. Requires idToken for Cognito authorizer.
// Now returns jobId for async processing.
export const postFlightChat = async ({ question, userSub, idToken }) => {
  try {
    const response = await fetch(`${API_BASE_URL}/talk-to-flight-record`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      },
      body: JSON.stringify({ question, user_sub: userSub }),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Chat request failed (${response.status}): ${text || response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error sending chat:', error);
    throw error;
  }
};

// Check status of async chat job. Returns status, answer, agents_invoked when completed.
export const getChatStatus = async ({ jobId, idToken }) => {
  try {
    const response = await fetch(`${API_BASE_URL}/talk-to-flight-record/status/${jobId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      },
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Status check failed (${response.status}): ${text || response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error checking status:', error);
    throw error;
  }
};

// Poll for chat job completion with 4-second intervals, max 5 minutes (75 attempts).
// Calls onProgress callback with status updates including agents_invoked array.
// Returns final result: { status: "COMPLETED", answer, agents_invoked, sessionId, completedAt }
export const pollChatResult = async ({ jobId, idToken, onProgress }) => {
  const POLL_INTERVAL_MS = 4000; // 4 seconds
  const MAX_ATTEMPTS = 75; // 5 minutes total (75 * 4s = 300s)
  
  let attempts = 0;
  
  while (attempts < MAX_ATTEMPTS) {
    attempts++;
    
    try {
      const status = await getChatStatus({ jobId, idToken });
      
      // Call progress callback with current status
      if (onProgress) {
        onProgress({
          status: status.status,
          attempts,
          maxAttempts: MAX_ATTEMPTS,
          agents_invoked: status.agents_invoked || [],
          elapsedSeconds: attempts * (POLL_INTERVAL_MS / 1000),
        });
      }
      
      // Check if job is complete
      if (status.status === 'COMPLETED') {
        return {
          status: 'COMPLETED',
          answer: status.answer,
          agents_invoked: status.agents_invoked || [],
          sessionId: status.sessionId,
          completedAt: status.completedAt,
        };
      }
      
      // Check if job failed
      if (status.status === 'ERROR') {
        throw new Error(status.error || 'Job processing failed');
      }
      
      // Job still pending/processing, wait before next poll
      if (attempts < MAX_ATTEMPTS) {
        await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
      }
      
    } catch (error) {
      console.error(`Polling error (attempt ${attempts}):`, error);
      // On error, still throw but after attempting
      if (attempts >= MAX_ATTEMPTS) {
        throw error;
      }
      // Wait before retry on error
      await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
    }
  }
  
  // Timeout after max attempts
  throw new Error(`Job polling timed out after ${MAX_ATTEMPTS * POLL_INTERVAL_MS / 1000} seconds. The job may still be processing - please check back later.`);
};

// ====================
// EMAIL PARSER API
// ====================

// Submit email text for parsing. Returns jobId for async processing.
export const postEmailParser = async ({ emailText, userSub, idToken }) => {
  try {
    const response = await fetch(`${API_BASE_URL}/parse-email-and-store`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      },
      body: JSON.stringify({ 
        email_text: emailText,
        user_sub: userSub 
      }),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Email parsing request failed (${response.status}): ${text || response.statusText}`);
    }

    const data = await response.json();
    return data; // { jobId, status: "PENDING", message }
  } catch (error) {
    console.error('Error submitting email:', error);
    throw error;
  }
};

// Check status of email parsing job
export const getEmailParserStatus = async ({ jobId, idToken }) => {
  try {
    const response = await fetch(`${API_BASE_URL}/parse-email-and-store/status/${jobId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      },
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Status check failed (${response.status}): ${text || response.statusText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error checking email parser status:', error);
    throw error;
  }
};

// Poll for email parsing completion with 3-second intervals, max 5 minutes (100 attempts).
// Returns final result with: status, total_found, stored_count, duplicate_count, failed_count, stored_flights[], etc.
export const pollEmailParserResult = async ({ jobId, idToken, onProgress }) => {
  const POLL_INTERVAL_MS = 3000; // 3 seconds
  const MAX_ATTEMPTS = 100; // 5 minutes total
  
  let attempts = 0;
  
  while (attempts < MAX_ATTEMPTS) {
    attempts++;
    
    try {
      const status = await getEmailParserStatus({ jobId, idToken });
      
      // Call progress callback
      if (onProgress) {
        onProgress({
          status: status.status,
          attempts,
          maxAttempts: MAX_ATTEMPTS,
          elapsedSeconds: attempts * (POLL_INTERVAL_MS / 1000),
        });
      }
      
      // Check if job is complete
      if (status.status === 'COMPLETED') {
        return {
          status: 'COMPLETED',
          total_found: status.total_found || 0,
          stored_count: status.stored_count || 0,
          duplicate_count: status.duplicate_count || 0,
          failed_count: status.failed_count || 0,
          stored_flights: status.stored_flights || [],
          duplicate_flights: status.duplicate_flights || [],
          failed_flights: status.failed_flights || [],
          summary: status.summary,
          completedAt: status.completedAt,
        };
      }
      
      // Check if job failed
      if (status.status === 'ERROR') {
        throw new Error(status.error || 'Email parsing failed');
      }
      
      // Job still pending/processing, wait before next poll
      if (attempts < MAX_ATTEMPTS) {
        await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
      }
      
    } catch (error) {
      console.error(`Polling error (attempt ${attempts}):`, error);
      if (attempts >= MAX_ATTEMPTS) {
        throw error;
      }
      await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
    }
  }
  
  // Timeout after max attempts
  throw new Error(`Email parsing timed out after ${MAX_ATTEMPTS * POLL_INTERVAL_MS / 1000} seconds.`);
};