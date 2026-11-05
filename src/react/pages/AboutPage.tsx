import React, { useEffect, useState } from 'react';
import { getAppInfo } from '../services/api';

const AboutPage: React.FC = () => {
    // The commit belongs to the running server, not to the bundle that was
    // built from it, so the page asks rather than baking it in at build time.
    const [version, setVersion] = useState<string | null>(null);

    useEffect(() => {
        getAppInfo()
            .then((info) => setVersion(info.version))
            .catch(() => setVersion('unknown'));
    }, []);

    return (
        <div className="about-page">
            <h1>About Book Lamp</h1>
            <p>
                Book Lamp is a personal reading history tracker that helps you keep
                track of books you've read, are currently reading, or want to read.
            </p>

            <h2>Features</h2>
            <ul>
                <li>Track your reading history with ratings and notes</li>
                <li>Organise books into a reading list</li>
                <li>View statistics about your reading habits</li>
                <li>Search and filter your books</li>
                <li>Import reading history from Libib</li>
                <li>Barcode scanning for quick book entry</li>
            </ul>

            <h2>Getting Started</h2>
            <ol>
                <li>Sign in with your Google account</li>
                <li>Add books manually or scan barcodes</li>
                <li>Record your reading progress</li>
                <li>View your reading statistics</li>
            </ol>

            <footer className="about-footer">
                <p>Version: {version ?? '…'}</p>
            </footer>
        </div>
    );
};

export default AboutPage;