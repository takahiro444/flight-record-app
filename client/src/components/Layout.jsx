import React from 'react';
import { Container, CssBaseline } from '@mui/material';

const Layout = ({ children }) => (
  <Container component="main" maxWidth="md">
    <CssBaseline />
    {children}
  </Container>
);

export default Layout;
