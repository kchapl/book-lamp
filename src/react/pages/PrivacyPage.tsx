import React from 'react';

const SUPPORT_EMAIL = 'belay.sheep382@eagereverest.com';

const PrivacyPage: React.FC = () => {
    return (
        <div className="privacy-page">
            <h1>Privacy Policy</h1>
            <p>
                Book Lamp is a personal reading history tracker. It holds one reader's own
                library and reading history, and this page describes what it stores and
                where that information goes.
            </p>

            <h2>What Book Lamp stores</h2>
            <ul>
                <li>
                    The email address and display name Google gives us when you sign in.
                    There is no password: Google performs the sign-in.
                </li>
                <li>
                    The Books, Readings, ratings, reading-list order and settings you add or
                    change in the app.
                </li>
            </ul>
            <p>Nothing else is collected, and no payment details are handled by this app.</p>

            <h2>Google user data</h2>
            <p>
                Sign-in uses Google's OpenID Connect to learn your email address and display
                name. The Book Lamp MCP service, which lets a connected assistant read your
                reading history, requests only the <code>openid</code> and{' '}
                <code>userinfo.email</code> scopes and uses the address solely to decide
                whether the caller is the one reader it is configured to serve, and to look
                up that reader's own records. It cannot write.
            </p>
            <p>
                Book Lamp's use and transfer of information received from Google APIs adheres
                to the{' '}
                <a href="https://developers.google.com/terms/api-services-user-data-policy">
                    Google API Services User Data Policy
                </a>
                , including the Limited Use requirements.
            </p>

            <h2>Where your data lives</h2>
            <p>
                Your records are stored in a PostgreSQL database belonging to this
                deployment. Book Lamp is a single-reader application: no other reader's
                account can reach your records.
            </p>

            <h2>When data leaves Book Lamp</h2>
            <p>
                The AI recommendations feature sends the titles and authors of Books you have
                rated, together with the titles already in your log, to the
                language-model provider configured for this deployment, so that it can
                suggest what to read next. Nothing else is sent, and the feature is off when
                no provider is configured. Sign-in, and any assistant you connect, reach
                Google rather than a third party of ours.
            </p>

            <h2>Keeping and removing your data</h2>
            <p>
                Your history stays until you remove it: you can delete Books and Readings in
                the app, and you can download everything as a CSV file from the account menu.
                To have the whole account deleted, contact the address below.
            </p>

            <h2>Contact</h2>
            <p>
                Questions about this policy, or a deletion request, can go to{' '}
                <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
            </p>

            <footer className="about-footer">
                <p>Last updated: 14 October 2026</p>
            </footer>
        </div>
    );
};

export default PrivacyPage;
