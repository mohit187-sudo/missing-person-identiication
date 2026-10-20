import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../../frontend/src/pages/LoginPage';
import { AuthProvider } from '../../frontend/src/hooks/useAuth';
import { ToastProvider } from '../../frontend/src/hooks/useToast';

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <ToastProvider>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </ToastProvider>
    </MemoryRouter>,
  );
}

describe('LoginPage', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it('shows the responsible-use notice and blocks public sign-up messaging', () => {
    renderLogin();
    expect(screen.getByText(/Missing Person Identification System/)).toBeInTheDocument();
    expect(screen.getByText(/Public sign-up is disabled/)).toBeInTheDocument();
  });

  it('validates email and password with zod before submitting', async () => {
    renderLogin();
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'not-an-email' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => expect(screen.getByText('Enter a valid email address')).toBeInTheDocument());
    expect(screen.getByText('Password is required')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('submits credentials and surfaces backend errors', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 401,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        error: { code: 'unauthorized', message: 'Invalid email or password.', details: {} },
      }),
    });

    renderLogin();
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'agent@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password/i), { target: { value: 'supersecret1' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => expect(screen.getAllByText('Invalid email or password.').length).toBeGreaterThan(0));
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/auth/login',
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
