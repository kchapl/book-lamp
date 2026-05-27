import React from 'react';
import { Link } from 'react-router-dom';

const UnauthorisedPage: React.FC = () => {
    return (
        <div className="unauthorised-page">
            <div className="unauthorised-content">
                <h1>Authentication Required</h1>
                <p>
                    You need to sign in to access your reading history.
                </p>
                <Link to="/connect" className="btn btn-primary">
                    Sign in with Google
                </Link>
            </div>
        </div>
    );
};

export default UnauthorisedPage;