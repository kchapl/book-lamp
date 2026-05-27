import React from 'react';

const AboutPage: React.FC = () => {
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
                <li>Search and filter your collection</li>
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
                <p>Version: 1.0.0</p>
            </footer>
        </div>
    );
};

export default AboutPage;