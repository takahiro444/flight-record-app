import React, { useMemo, useState } from 'react';
import {
  Box,
  Fab,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  IconButton,
  Tooltip,
  CircularProgress,
  Stack,
  Typography,
  Divider,
  Chip,
} from '@mui/material';
import ChatIcon from '@mui/icons-material/Chat';
import CloseIcon from '@mui/icons-material/Close';
import SendIcon from '@mui/icons-material/Send';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { postFlightChat, pollChatResult } from '../utils/api';

// Floating chat widget gated by authentication.
// Props:
// - isAuthenticated: boolean
// - idToken: string | null
// - userSub: string | undefined
// - defaultQuestion?: string
// - onRequireLogin?: () => void

const ChatWidget = ({ isAuthenticated, idToken, userSub, defaultQuestion = '', onRequireLogin }) => {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState(defaultQuestion);
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState([]); // {role:'user'|'assistant', text, agents_invoked?, processing?}
  const [error, setError] = useState('');
  const [processingStatus, setProcessingStatus] = useState(null); // {elapsedSeconds, agents_invoked}

  const canSend = useMemo(() => !!question.trim() && !!idToken && !!userSub && !sending, [question, idToken, userSub, sending]);

  const handleOpen = () => {
    if (!isAuthenticated) {
      onRequireLogin?.();
      return;
    }
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    setError('');
  };

  const handleSend = async () => {
    if (!canSend) return;
    setSending(true);
    setError('');
    setProcessingStatus(null);
    const q = question.trim();
    setMessages(prev => [...prev, { role: 'user', text: q }]);
    
    try {
      const resp = await postFlightChat({ question: q, userSub, idToken });
      
      // Check if response is async (has jobId) or sync (has answer)
      if (resp?.jobId) {
        // Async response - start polling
        const processingMessageIndex = messages.length + 1; // Index where processing message will be
        
        // Add placeholder processing message
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          text: 'AI agents are analyzing your request...', 
          processing: true,
          agents_invoked: []
        }]);
        
        // Poll for result with progress updates
        const result = await pollChatResult({
          jobId: resp.jobId,
          idToken,
          onProgress: (progress) => {
            // Update processing status for UI
            setProcessingStatus({
              elapsedSeconds: progress.elapsedSeconds,
              agents_invoked: progress.agents_invoked || []
            });
            
            // Update the processing message with real-time agent badges
            setMessages(prev => {
              const updated = [...prev];
              if (updated[processingMessageIndex]) {
                updated[processingMessageIndex] = {
                  ...updated[processingMessageIndex],
                  agents_invoked: progress.agents_invoked || [],
                  text: `AI agents analyzing... (${Math.floor(progress.elapsedSeconds)}s elapsed)`
                };
              }
              return updated;
            });
          }
        });
        
        // Replace processing message with final answer
        setMessages(prev => {
          const updated = [...prev];
          if (updated[processingMessageIndex]) {
            updated[processingMessageIndex] = {
              role: 'assistant',
              text: result.answer || '(no answer returned)',
              agents_invoked: result.agents_invoked || [],
              processing: false
            };
          }
          return updated;
        });
        setProcessingStatus(null);
        
      } else {
        // Sync response (backward compatibility or immediate answer)
        const answer = resp?.answer || '(no answer returned)';
        const agentsInvoked = resp?.agents_invoked || [];
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          text: answer, 
          agents_invoked: agentsInvoked 
        }]);
      }
      
      setQuestion('');
    } catch (e) {
      const msg = e?.message || 'Failed to send chat';
      setError(msg);
      setMessages(prev => {
        // Remove processing message if it exists
        const filtered = prev.filter(m => !m.processing);
        return [...filtered, { role: 'assistant', text: `Error: ${msg}` }];
      });
      setProcessingStatus(null);
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <Tooltip title={isAuthenticated ? 'Chat with your flight data agent' : 'Login required'} placement="left">
        <Fab
          color="primary"
          aria-label="chat"
          onClick={handleOpen}
          sx={{ position: 'fixed', bottom: 24, right: 24, zIndex: 1500 }}
        >
          <ChatIcon />
        </Fab>
      </Tooltip>

      <Dialog open={open} onClose={handleClose} fullWidth maxWidth="sm">
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          Flight Agent Chat
          <IconButton onClick={handleClose} aria-label="close" size="small">
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent dividers sx={{ minHeight: 240 }}>
          <Stack spacing={1} sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Ask questions scoped to your data. The agent uses your Cognito identity (sub) to query Postgres.
            </Typography>
            {userSub && (
              <Typography variant="caption" color="text.secondary">sub: {userSub}</Typography>
            )}
          </Stack>
          <Divider sx={{ mb: 2 }} />
          <Stack spacing={1} sx={{ maxHeight: 260, overflowY: 'auto', pr: 1 }}>
            {messages.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                No messages yet. Try asking: "Give me a brief stats overview and monthly mileage for 2024."
              </Typography>
            )}
            {messages.map((m, idx) => (
              <Box
                key={idx}
                sx={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '100%',
                }}
              >
                {/* Show agent badges for assistant responses */}
                {m.role === 'assistant' && m.agents_invoked && m.agents_invoked.length > 0 && (
                  <Box sx={{ mb: 0.5, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                    {m.agents_invoked.map((agent, i) => (
                      <Chip
                        key={i}
                        label={agent}
                        size="small"
                        icon={<SmartToyIcon />}
                        color="success"
                        variant="outlined"
                        sx={{ fontSize: '0.7rem', height: 22 }}
                      />
                    ))}
                  </Box>
                )}
                {/* Message bubble */}
                <Box
                  sx={{
                    bgcolor: m.role === 'user' ? 'primary.light' : 'grey.100',
                    color: m.role === 'user' ? 'primary.contrastText' : 'text.primary',
                    px: 1.5,
                    py: 1,
                    borderRadius: 2,
                    maxWidth: '100%',
                  }}
                >
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>{m.text}</Typography>
                </Box>
              </Box>
            ))}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ alignItems: 'center', gap: 1, px: 3, pb: 2 }}>
          <TextField
            fullWidth
            placeholder="Ask about your flights..."
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyPress={e => e.key === 'Enter' && handleSend()}
            size="small"
            disabled={sending}
          />
          <Button
            variant="contained"
            endIcon={sending ? <CircularProgress size={16} color="inherit" /> : <SendIcon />}
            onClick={handleSend}
            disabled={!canSend || sending}
          >
            Send
          </Button>
        </DialogActions>
        {error && (
          <Typography color="error" variant="caption" sx={{ px: 3, pb: 2 }}>
            {error}
          </Typography>
        )}
      </Dialog>
    </>
  );
};

export default ChatWidget;
