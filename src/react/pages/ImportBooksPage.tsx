import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Checkbox } from '../ui';

const ImportBooksPage: React.FC = () => {
    const navigate = useNavigate();
    const [file, setFile] = useState<File | null>(null);
    const [fetchMetadata, setFetchMetadata] = useState(true);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        if (selectedFile) {
            if (!selectedFile.name.endsWith('.csv')) {
                setError('Please select a CSV file');
                return;
            }
            setFile(selectedFile);
            setError(null);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!file) {
            setError('Please select a file');
            return;
        }

        setLoading(true);
        setError(null);

        const formData = new FormData();
        formData.append('file', file);
        if (fetchMetadata) {
            formData.append('fetch_metadata', 'on');
        }

        try {
            const metaTag = document.querySelector('meta[name="csrf-token"]') as HTMLMetaElement | null;
            const cookieMatch = document.cookie.match(/(?:^|;)\s*csrf_token=([^;]+)/);
            const csrfToken = metaTag?.content || (cookieMatch ? decodeURIComponent(cookieMatch[1]) : null);

            const headers: Record<string, string> = {};
            if (csrfToken) {
                headers['X-CSRF-Token'] = csrfToken;
            }

            const response = await fetch('/books/import', {
                method: 'POST',
                headers,
                body: formData,
            });

            if (response.redirected) {
                navigate(new URL(response.url).pathname + response.url.search);
            } else if (!response.ok) {
                throw new Error('Import failed');
            }
        } catch (err) {
            console.error('Import error:', err);
            setError('Failed to import books. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="import-books-page">
            <h1>Import Books</h1>
            <p>Import your reading history from a Libib CSV export.</p>

            <div className="info-box">
                <h2>📋 How to Export from Libib</h2>
                <ol>
                    <li>Log in to your Libib account</li>
                    <li>Go to your library and click "Export"</li>
                    <li>Select "CSV" format</li>
                    <li>Download and upload the file below</li>
                </ol>
            </div>

            <form onSubmit={handleSubmit} className="import-form">
                <div className="file-input-wrapper">
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".csv"
                        onChange={handleFileChange}
                        className="file-input"
                        aria-label="Libib CSV export file"
                    />
                    <Button variant="tonal" onClick={() => fileInputRef.current?.click()}>
                        Choose File
                    </Button>
                    <span className="file-name">
                        {file ? file.name : 'No file selected'}
                    </span>
                </div>

                <label className="checkbox-label">
                    <Checkbox checked={fetchMetadata} onCheckedChange={setFetchMetadata} />
                    Fetch missing book covers and metadata (recommended)
                </label>

                {error && <p className="error-message">{error}</p>}

                <Button type="submit" disabled={loading || !file}>
                    {loading ? 'Importing...' : 'Import Books'}
                </Button>
            </form>
        </div>
    );
};

export default ImportBooksPage;