import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AddBookPage from '../../pages/AddBookPage';

// Mock the Html5Qrcode library
jest.mock('html5-qrcode', () => {
  const startMock = jest.fn().mockResolvedValue(undefined);
  const stopMock = jest.fn().mockResolvedValue(undefined);
  return {
    Html5Qrcode: jest.fn().mockImplementation(() => ({
      start: startMock,
      stop: stopMock,
    })),
    __esModule: true,
    startMock,
    stopMock,
  };
});

describe('AddBookPage barcode scanner', () => {
  it('opens scanner UI when Scan button is clicked', async () => {
    render(
      <MemoryRouter>
        <AddBookPage />
      </MemoryRouter>
    );

    // Initially, scanner container should be hidden
    const scannerContainer = screen.getByRole('region', { name: /scanner/i })
      .parentElement as HTMLElement;
    expect(scannerContainer).toHaveStyle('display: none');

    // Click the Scan button
    const scanButton = screen.getByRole('button', { name: /📷 scan barcode/i });
    fireEvent.click(scanButton);

    // Wait for scanning state to become true and the container to be visible
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /stop scanner/i })).toBeInTheDocument();
      expect(scannerContainer).toHaveStyle('display: block');
    });
  });
});
