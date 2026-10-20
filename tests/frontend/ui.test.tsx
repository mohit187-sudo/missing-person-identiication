import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  Alert,
  Badge,
  ConfirmDialog,
  EmptyState,
  Pagination,
  ProgressBar,
  formatScore,
} from '../../frontend/src/components/ui';

describe('Badge', () => {
  it('renders a humanised label for machine values', () => {
    render(<Badge value="requires_manual_review" />);
    expect(screen.getByText('requires manual review')).toBeInTheDocument();
  });

  it('renders a custom label when given', () => {
    render(<Badge value="demo" label="DEMO DATA" />);
    expect(screen.getByText('DEMO DATA')).toBeInTheDocument();
  });
});

describe('ProgressBar', () => {
  it('clamps and displays percentage', () => {
    render(<ProgressBar value={0.456} label="Processing" />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '46');
    expect(screen.getByText('46%')).toBeInTheDocument();
  });
});

describe('Pagination', () => {
  it('disables previous on first page and fires callbacks', () => {
    const onPage = vi.fn();
    render(<Pagination page={1} pages={3} total={42} onPage={onPage} />);
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: /next/i }));
    expect(onPage).toHaveBeenCalledWith(2);
    expect(screen.getByText(/Page 1 of 3 · 42 records/)).toBeInTheDocument();
  });
});

describe('EmptyState', () => {
  it('shows title and description', () => {
    render(<EmptyState title="Nothing here" description="Try again later" />);
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
    expect(screen.getByText('Try again later')).toBeInTheDocument();
  });
});

describe('Alert', () => {
  it('marks errors with role=alert', () => {
    render(<Alert kind="error" title="Broken">Details</Alert>);
    expect(screen.getByRole('alert')).toHaveTextContent('Broken');
  });
});

describe('ConfirmDialog', () => {
  it('confirms and cancels through callbacks', () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        title="Archive case?"
        message="This is permanent-ish."
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    expect(onConfirm).toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalled();
  });

  it('renders nothing when closed', () => {
    render(<ConfirmDialog open={false} title="X" message="Y" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});

describe('formatScore', () => {
  it('formats similarity scores to 4 decimals', () => {
    expect(formatScore(0.876543)).toBe('0.8765');
    expect(formatScore(1)).toBe('1.0000');
  });
});
