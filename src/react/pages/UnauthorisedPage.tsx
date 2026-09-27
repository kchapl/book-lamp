import React from 'react';
import GoogleAuth from '../components/GoogleAuth';

const UnauthorisedPage: React.FC = () => {
    return (
        <div className="unauthorised-page">
            <div className="unauthorised-content">
                <h1>Authentication Required</h1>
                <p>
                    Please sign in with Google to access your reading history and bookshelf.
                </p>
                <GoogleAuth />
            </div>
        </div>
    );
};

export default UnauthorisedPage;