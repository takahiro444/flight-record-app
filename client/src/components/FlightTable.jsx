import React from 'react';
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography, Skeleton, Paper } from '@mui/material';

// Pure table renderer; data & loader passed from parent.
const FlightTable = ({ apiKey, records, loading, error }) => {

  // Records endpoint now callable without API key; show hint if empty.
  if (loading) {
    return (
      <TableContainer>
        <Table stickyHeader size="small">
          <TableHead>
            <TableRow>
              {Array.from({ length: 6 }).map((_, i) => (
                <TableCell key={i}><Skeleton /></TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {Array.from({ length: 5 }).map((_, r) => (
              <TableRow key={r}>
                {Array.from({ length: 6 }).map((_, c) => (
                  <TableCell key={c}><Skeleton /></TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  }
  if (error) return <Typography color="error">Error: {error}</Typography>;
  if (!records.length) return <Typography>No data found.</Typography>;

  return (
    <TableContainer component={Paper}>
      <Table>
        <TableHead>
          <TableRow>
            {Object.keys(records[0]).map((key) => (
              <TableCell key={key}>{key}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {records.map((row, index) => (
            <TableRow key={index}>
              {Object.values(row).map((val, idx) => (
                <TableCell key={idx}>{val !== null ? val : ''}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default FlightTable;