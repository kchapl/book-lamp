import React from 'react';

const SUPPORT_EMAIL = 'belay.sheep382@eagereverest.com';

const TermsPage: React.FC = () => {
    return (
        <div className="terms-page">
            <h1>Terms of Service</h1>
            <p>
                Book Lamp is a personal reading history tracker, provided for the use of the
                reader whose Google account it is configured for. By signing in you accept
                these terms.
            </p>

            <h2>Using Book Lamp</h2>
            <p>
                Sign in with your own Google account. Do not attempt to reach another
                reader's records, and do not use automated means to overload the service.
            </p>

            <h2>Your data is yours</h2>
            <p>
                The library and reading history you record remain yours. You can export them
                as a CSV file at any time, and the <a href="/privacy">Privacy Policy</a>{' '}
                describes what is stored and where it goes.
            </p>

            <h2>No warranty</h2>
            <p>
                Book Lamp is provided as-is, without warranty of any kind. It is a personal
                project, not a commercial service: keep your own copy of anything you cannot
                afford to lose, using the export.
            </p>

            <h2>Availability and changes</h2>
            <p>
                The service may change, or be unavailable, at any time. These terms may be
                updated; the date below shows when they last changed.
            </p>

            <h2>Contact</h2>
            <p>
                Questions about these terms can go to{' '}
                <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
            </p>

            <footer className="about-footer">
                <p>Last updated: 14 October 2026</p>
            </footer>
        </div>
    );
};

export default TermsPage;
