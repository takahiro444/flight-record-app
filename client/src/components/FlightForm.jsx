import React, { useState } from 'react';
import { 
  TextField, 
  Button, 
  Typography, 
  InputAdornment, 
  IconButton, 
  ToggleButtonGroup,
  ToggleButton,
  Box,
  CircularProgress,
  Alert,
  Chip,
  Stack
} from '@mui/material';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import EmailIcon from '@mui/icons-material/Email';
import EditIcon from '@mui/icons-material/Edit';
import { postEmailParser, pollEmailParserResult } from '../utils/api';
import { useAuth } from '../auth/AuthContext';

// Presentational form with toggle: manual entry or email paste
const FlightForm = ({ onApiKeyChange, fetchFlightData, loading, error }) => {
  const { idToken } = useAuth();
  const [apiKey, setApiKey] = useState('');
  const [mode, setMode] = useState('email'); // 'manual' or 'email'
  
  // Manual entry fields
  const [flightIata, setFlightIata] = useState('');
  const [date, setDate] = useState('');
  
  // Email parsing fields
  const [emailText, setEmailText] = useState('');
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailError, setEmailError] = useState(null);
  const [emailResult, setEmailResult] = useState(null);
  const [emailProgress, setEmailProgress] = useState(null);
  
  const [showApiKey, setShowApiKey] = useState(false);

  const handleManualSubmit = async (e) => {
    e.preventDefault();
    await fetchFlightData(apiKey, flightIata, date);
    onApiKeyChange?.(apiKey);
  };

  const handleEmailSubmit = async (e) => {
    e.preventDefault();
    
    if (!idToken) {
      setEmailError('Authentication required. Please log in.');
      return;
    }
    
    if (!emailText || emailText.trim().length < 20) {
      setEmailError('Please paste a flight confirmation email (at least 20 characters).');
      return;
    }
    
    setEmailLoading(true);
    setEmailError(null);
    setEmailResult(null);
    setEmailProgress({ status: 'PENDING', elapsedSeconds: 0 });
    onApiKeyChange?.(apiKey);
    
    try {
      // Submit email for parsing
      const response = await postEmailParser({
        emailText: emailText,
        idToken
      });
      
      if (!response.jobId) {
        throw new Error('No jobId returned from API');
      }
      
      // Poll for results
      const result = await pollEmailParserResult({
        jobId: response.jobId,
        idToken,
        onProgress: (progress) => {
          setEmailProgress(progress);
        }
      });
      
      setEmailResult(result);
      
      // Clear form if successful
      if (result.stored_count > 0) {
        setEmailText('');
      }
      
    } catch (err) {
      setEmailError(err.message || 'Failed to parse email');
    } finally {
      setEmailLoading(false);
      setEmailProgress(null);
    }
  };

  const renderEmailResult = () => {
    if (!emailResult) return null;
    
    const { total_found, stored_count, duplicate_count, failed_count, stored_flights, duplicate_flights, failed_flights, summary } = emailResult;
    
    return (
      <Box sx={{ mt: 2 }}>
        <Alert severity={stored_count > 0 ? 'success' : 'warning'} sx={{ mb: 2 }}>
          <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
            Parsing Complete
          </Typography>
          <Typography variant="body2">{summary}</Typography>
        </Alert>
        
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <Chip label={`Found: ${total_found}`} size="small" />
          <Chip label={`Stored: ${stored_count}`} color="success" size="small" />
          {duplicate_count > 0 && <Chip label={`Duplicates: ${duplicate_count}`} color="warning" size="small" />}
          {failed_count > 0 && <Chip label={`Failed: ${failed_count}`} color="error" size="small" />}
        </Stack>
        
        {stored_flights && stored_flights.length > 0 && (
          <Box sx={{ mb: 1 }}>
            <Typography variant="caption" display="block" sx={{ fontWeight: 'bold' }}>Stored Flights:</Typography>
            {stored_flights.map((flight, idx) => (
              <Typography key={idx} variant="caption" display="block" sx={{ ml: 1 }}>
                • {flight.flight_iata} on {flight.date}
              </Typography>
            ))}
          </Box>
        )}
        
        {duplicate_flights && duplicate_flights.length > 0 && (
          <Box sx={{ mb: 1 }}>
            <Typography variant="caption" display="block" sx={{ fontWeight: 'bold', color: 'warning.main' }}>
              Duplicates Skipped:
            </Typography>
            {duplicate_flights.map((flight, idx) => (
              <Typography key={idx} variant="caption" display="block" sx={{ ml: 1, color: 'text.secondary' }}>
                • {flight.flight_iata} on {flight.date}
              </Typography>
            ))}
          </Box>
        )}
        
        {failed_flights && failed_flights.length > 0 && (
          <Box>
            <Typography variant="caption" display="block" sx={{ fontWeight: 'bold', color: 'error.main' }}>
              Failed:
            </Typography>
            {failed_flights.map((flight, idx) => (
              <Typography key={idx} variant="caption" display="block" sx={{ ml: 1, color: 'text.secondary' }}>
                • {flight.flight_iata} on {flight.date}: {flight.reason}
              </Typography>
            ))}
          </Box>
        )}
      </Box>
    );
  };

  return (
    <Box>
      {/* API Key Field - Always shown */}
      <TextField
        label="API Key"
        variant="outlined"
        fullWidth
        required
        type={showApiKey ? 'text' : 'password'}
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        margin="normal"
        InputProps={{
          endAdornment: (
            <InputAdornment position="end">
              <IconButton
                aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
                onClick={() => setShowApiKey((prev) => !prev)}
                edge="end"
              >
                {showApiKey ? <VisibilityOff /> : <Visibility />}
              </IconButton>
            </InputAdornment>
          ),
        }}
      />
      
      {/* Mode Toggle */}
      <Box sx={{ mt: 2, mb: 2 }}>
        <ToggleButtonGroup
          value={mode}
          exclusive
          onChange={(e, newMode) => newMode && setMode(newMode)}
          fullWidth
          size="small"
        >
          <ToggleButton value="email">
            <EmailIcon sx={{ mr: 1 }} fontSize="small" />
            Paste Email
          </ToggleButton>
          <ToggleButton value="manual">
            <EditIcon sx={{ mr: 1 }} fontSize="small" />
            Manual Entry
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>
      
      {/* Manual Entry Form */}
      {mode === 'manual' && (
        <form onSubmit={handleManualSubmit}>
          <TextField
            label="Flight IATA Code"
            variant="outlined"
            fullWidth
            required
            value={flightIata}
            onChange={(e) => setFlightIata(e.target.value)}
            margin="normal"
            placeholder="e.g., UA234"
          />
          
          <TextField
            label="Departure Date (YYYY-MM-DD)"
            type="date"
            variant="outlined"
            fullWidth
            required
            value={date}
            onChange={(e) => setDate(e.target.value)}
            margin="normal"
            InputLabelProps={{
              shrink: true,
            }}
          />
          
          <Button type="submit" variant="contained" color="primary" fullWidth disabled={loading} sx={{ mt: 2 }}>
            {loading ? 'Submitting...' : 'Submit Flight'}
          </Button>
          {error && <Typography color="error" sx={{ mt: 1 }}>{error}</Typography>}
        </form>
      )}
      
      {/* Email Paste Form */}
      {mode === 'email' && (
        <form onSubmit={handleEmailSubmit}>
          <TextField
            label="Flight Confirmation Email"
            variant="outlined"
            fullWidth
            required
            multiline
            rows={8}
            value={emailText}
            onChange={(e) => setEmailText(e.target.value)}
            margin="normal"
            placeholder="Paste your entire flight confirmation email here..."
            helperText="AI will extract flight numbers and dates automatically"
          />
          
          <Button 
            type="submit" 
            variant="contained" 
            color="primary" 
            fullWidth 
            disabled={emailLoading}
            sx={{ mt: 2 }}
          >
            {emailLoading ? (
              <>
                <CircularProgress size={20} sx={{ mr: 1 }} />
                {emailProgress ? `Processing... ${emailProgress.elapsedSeconds}s` : 'Processing...'}
              </>
            ) : (
              'Parse & Store Flights'
            )}
          </Button>
          
          {emailError && (
            <Alert severity="error" sx={{ mt: 2 }}>{emailError}</Alert>
          )}
          
          {emailProgress && emailProgress.status === 'PROCESSING' && (
            <Alert severity="info" sx={{ mt: 2 }}>
              AI is analyzing your email... {emailProgress.elapsedSeconds}s elapsed
            </Alert>
          )}
          
          {renderEmailResult()}
        </form>
      )}
    </Box>
  );
};

export default FlightForm;