// client/src/theme/index.js
// Material You (Material Design 3) inspired theme built on MUI v5.
// Keeps the blue + white identity, but adopts M3 cues: generous radii,
// tonal surfaces, restrained elevation, and system-native typography.
import { createTheme, alpha } from '@mui/material/styles';

const FONT_DISPLAY = '"Google Sans", "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
const FONT_TEXT = '"Google Sans Text", "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
const FONT_MONO = '"Roboto Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';

// M3 tonal palette approximations anchored to the existing blue primary.
const primary = {
  main: '#0b57d0',        // M3 primary-40
  dark: '#062e6f',        // primary-20
  light: '#a8c7fa',        // primary-80
  contrastText: '#ffffff',
};
const secondary = {
  main: '#5b5f77',        // neutral-variant for tertiary accents
  light: '#dee3ff',
  dark: '#3a3f55',
  contrastText: '#ffffff',
};
const surface = {
  default: '#f8faff',     // surface-tint with a drop of primary
  paper: '#ffffff',
  container: '#eef1f8',   // surface-container-low
  containerHigh: '#e3e8f3',
};

const theme = createTheme({
  palette: {
    mode: 'light',
    primary,
    secondary,
    background: {
      default: surface.default,
      paper: surface.paper,
    },
    success: { main: '#1e6e3a', light: '#c7f0d3' },
    info: { main: '#0b57d0', light: '#d5e3ff' },
    warning: { main: '#8a5300', light: '#ffe0b2' },
    error: { main: '#b3261e', light: '#f9dedc' },
    divider: alpha('#1f1f1f', 0.08),
    text: {
      primary: '#1a1c1e',
      secondary: '#44474e',
    },
  },
  shape: {
    borderRadius: 12,
  },
  typography: {
    fontFamily: FONT_TEXT,
    h1: { fontFamily: FONT_DISPLAY, fontSize: '2.25rem', fontWeight: 500, letterSpacing: '-0.01em' },
    h2: { fontFamily: FONT_DISPLAY, fontSize: '1.75rem', fontWeight: 500, letterSpacing: '-0.005em' },
    h3: { fontFamily: FONT_DISPLAY, fontSize: '1.5rem', fontWeight: 500 },
    h4: { fontFamily: FONT_DISPLAY, fontSize: '1.25rem', fontWeight: 500 },
    h5: { fontFamily: FONT_DISPLAY, fontSize: '1.125rem', fontWeight: 500 },
    h6: { fontFamily: FONT_DISPLAY, fontSize: '1rem', fontWeight: 500, letterSpacing: '0.01em' },
    subtitle1: { fontSize: '1rem', fontWeight: 500 },
    subtitle2: { fontSize: '0.875rem', fontWeight: 500 },
    body1: { fontSize: '0.9375rem', lineHeight: 1.55 },
    body2: { fontSize: '0.875rem', lineHeight: 1.55 },
    button: { fontWeight: 500, letterSpacing: '0.02em', textTransform: 'none' },
    caption: { fontSize: '0.75rem', lineHeight: 1.4 },
    overline: { fontWeight: 500, letterSpacing: '0.08em' },
  },
  shadows: [
    'none',
    // M3-ish soft shadows: small offset, wide soft blur, cool tint.
    '0 1px 2px 0 rgba(11, 87, 208, 0.06), 0 1px 3px 1px rgba(11, 87, 208, 0.04)',
    '0 1px 2px 0 rgba(11, 87, 208, 0.08), 0 2px 6px 2px rgba(11, 87, 208, 0.05)',
    '0 1px 3px 0 rgba(11, 87, 208, 0.10), 0 4px 8px 3px rgba(11, 87, 208, 0.06)',
    '0 2px 3px 0 rgba(11, 87, 208, 0.10), 0 6px 10px 4px rgba(11, 87, 208, 0.07)',
    '0 4px 4px 0 rgba(11, 87, 208, 0.12), 0 8px 12px 6px rgba(11, 87, 208, 0.08)',
    ...Array(19).fill('0 4px 4px 0 rgba(11, 87, 208, 0.12), 0 8px 12px 6px rgba(11, 87, 208, 0.08)'),
  ],
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: surface.default,
          backgroundImage:
            `radial-gradient(1200px 600px at 10% -20%, ${alpha(primary.main, 0.06)}, transparent 60%),` +
            `radial-gradient(800px 400px at 95% 0%, ${alpha(primary.main, 0.04)}, transparent 60%)`,
          backgroundAttachment: 'fixed',
        },
        '::selection': {
          backgroundColor: alpha(primary.main, 0.2),
        },
      },
    },
    MuiAppBar: {
      defaultProps: {
        elevation: 0,
        color: 'default',
      },
      styleOverrides: {
        root: {
          backgroundColor: alpha('#ffffff', 0.78),
          backdropFilter: 'saturate(180%) blur(12px)',
          WebkitBackdropFilter: 'saturate(180%) blur(12px)',
          color: '#1a1c1e',
          border: 'none',
          borderBottom: `1px solid ${alpha('#1f1f1f', 0.08)}`,
        },
        // When a caller explicitly sets color="primary" we still want the
        // translucent surface look — override MUI's colorPrimary class.
        colorPrimary: {
          backgroundColor: alpha('#ffffff', 0.78),
          color: '#1a1c1e',
        },
      },
    },
    MuiToolbar: {
      styleOverrides: {
        root: {
          minHeight: 64,
        },
      },
    },
    MuiPaper: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
        rounded: {
          borderRadius: 16,
        },
        // Keep Paper unadorned at elevation 0 so that callers like AppBar
        // can supply their own border/shadow rules without collisions.
        elevation1: {
          boxShadow: '0 1px 2px 0 rgba(11, 87, 208, 0.06)',
        },
        elevation2: {
          boxShadow: '0 1px 3px 0 rgba(11, 87, 208, 0.08), 0 2px 6px 2px rgba(11, 87, 208, 0.04)',
        },
        elevation3: {
          boxShadow: '0 1px 3px 0 rgba(11, 87, 208, 0.10), 0 4px 8px 3px rgba(11, 87, 208, 0.05)',
        },
      },
    },
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          borderRadius: 16,
          border: `1px solid ${alpha('#1f1f1f', 0.08)}`,
        },
      },
    },
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          borderRadius: 999,
          paddingInline: 20,
          paddingBlock: 8,
          minHeight: 40,
          transition: 'background-color 160ms ease, box-shadow 160ms ease, transform 120ms ease',
          '&:hover': { boxShadow: '0 1px 2px 0 rgba(11, 87, 208, 0.10)' },
          '&:active': { transform: 'translateY(0.5px)' },
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0 1px 3px 0 rgba(11, 87, 208, 0.20), 0 2px 6px 2px rgba(11, 87, 208, 0.08)',
          },
        },
        outlined: {
          borderColor: alpha('#1f1f1f', 0.16),
          '&:hover': {
            backgroundColor: alpha(primary.main, 0.06),
            borderColor: alpha(primary.main, 0.40),
          },
        },
        text: {
          '&:hover': {
            backgroundColor: alpha(primary.main, 0.06),
          },
        },
        sizeSmall: { minHeight: 32, paddingInline: 14, paddingBlock: 4 },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          borderRadius: 999,
          transition: 'background-color 160ms ease',
          '&:hover': {
            backgroundColor: alpha(primary.main, 0.08),
          },
        },
      },
    },
    MuiFab: {
      defaultProps: { color: 'primary' },
      styleOverrides: {
        root: {
          borderRadius: 16,
          boxShadow: '0 1px 3px 0 rgba(11, 87, 208, 0.18), 0 4px 8px 3px rgba(11, 87, 208, 0.10)',
          '&:hover': {
            boxShadow: '0 2px 4px 0 rgba(11, 87, 208, 0.22), 0 6px 12px 4px rgba(11, 87, 208, 0.14)',
          },
        },
        extended: {
          borderRadius: 16,
          paddingInline: 20,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          fontWeight: 500,
          letterSpacing: '0.01em',
        },
        outlined: {
          borderColor: alpha('#1f1f1f', 0.16),
        },
        filled: {
          backgroundColor: surface.container,
          color: '#1a1c1e',
        },
        colorSuccess: { backgroundColor: '#d7f0df', color: '#0d5128' },
        colorInfo: { backgroundColor: '#d9e7ff', color: '#0b4aa2' },
        colorError: { backgroundColor: '#fcdedc', color: '#8a1b14' },
        colorWarning: { backgroundColor: '#ffe9c9', color: '#6b3f00' },
      },
    },
    MuiToggleButtonGroup: {
      styleOverrides: {
        root: {
          backgroundColor: surface.container,
          padding: 4,
          borderRadius: 999,
          gap: 4,
        },
        grouped: {
          border: 'none',
          '&:not(:first-of-type)': { borderRadius: 999, marginLeft: 0 },
          '&:first-of-type': { borderRadius: 999 },
        },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          border: 'none',
          borderRadius: 999,
          paddingInline: 16,
          paddingBlock: 6,
          textTransform: 'none',
          fontWeight: 500,
          color: '#44474e',
          '&.Mui-selected': {
            backgroundColor: primary.main,
            color: '#ffffff',
            '&:hover': { backgroundColor: primary.dark },
          },
          '&:hover': {
            backgroundColor: alpha(primary.main, 0.08),
          },
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        variant: 'outlined',
        size: 'small',
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          backgroundColor: '#ffffff',
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: alpha('#1f1f1f', 0.14),
          },
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: alpha(primary.main, 0.40),
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderWidth: 1.5,
          },
        },
      },
    },
    MuiAccordion: {
      defaultProps: { elevation: 0, disableGutters: true },
      styleOverrides: {
        root: {
          borderRadius: 16,
          border: `1px solid ${alpha('#1f1f1f', 0.08)}`,
          backgroundColor: surface.paper,
          '&::before': { display: 'none' },
          '&.Mui-expanded': { margin: 0 },
          overflow: 'hidden',
        },
      },
    },
    MuiAccordionSummary: {
      styleOverrides: {
        root: {
          minHeight: 56,
          paddingInline: 20,
          '&.Mui-expanded': { minHeight: 56 },
          '&:hover': { backgroundColor: alpha(primary.main, 0.04) },
        },
        content: {
          '&.Mui-expanded': { margin: '12px 0' },
        },
      },
    },
    MuiAccordionDetails: {
      styleOverrides: {
        root: {
          paddingInline: 20,
          paddingBlock: 8,
        },
      },
    },
    MuiTableContainer: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          border: `1px solid ${alpha('#1f1f1f', 0.08)}`,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottomColor: alpha('#1f1f1f', 0.06),
        },
        head: {
          backgroundColor: surface.container,
          fontWeight: 600,
          fontSize: '0.8125rem',
          color: '#1a1c1e',
          letterSpacing: '0.02em',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'background-color 120ms ease',
          '&:hover': { backgroundColor: alpha(primary.main, 0.04) },
          '&:last-child td': { borderBottom: 'none' },
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 12 },
        standardSuccess: { backgroundColor: '#e7f6ec', color: '#0d5128' },
        standardInfo: { backgroundColor: '#e3ecff', color: '#0b4aa2' },
        standardWarning: { backgroundColor: '#fff1dd', color: '#6b3f00' },
        standardError: { backgroundColor: '#fde6e5', color: '#8a1b14' },
      },
    },
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          borderRadius: 8,
          backgroundColor: '#1a1c1e',
          fontSize: '0.75rem',
          fontWeight: 500,
          paddingInline: 10,
          paddingBlock: 6,
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 24,
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: { borderColor: alpha('#1f1f1f', 0.08) },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: { borderRadius: 999, height: 6, backgroundColor: alpha(primary.main, 0.12) },
        bar: { borderRadius: 999 },
      },
    },
    MuiCircularProgress: {
      styleOverrides: {
        circle: { strokeLinecap: 'round' },
      },
    },
    MuiLink: {
      defaultProps: { underline: 'hover' },
      styleOverrides: {
        root: { fontWeight: 500 },
      },
    },
    MuiTypography: {
      styleOverrides: {
        root: {
          '& code, & pre': { fontFamily: FONT_MONO },
        },
      },
    },
  },
});

export default theme;
