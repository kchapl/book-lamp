module.exports = {
    ci: {
        collect: {
            numberOfRuns: 3,
            startServerCommand: "poetry run python scripts/run_lhci_server.py",
            url: [
                "http://localhost:5000/",
                "http://localhost:5000/books",
                "http://localhost:5000/history",
                "http://localhost:5000/stats"
            ],
            settings: {
                chromeFlags: "--no-sandbox --headless --disable-gpu"
            }
        },
        assert: {
            assertions: {
                // Core Web Vitals Targets from performance-engineer skill
                "categories:performance": ["error", { "minScore": 0.9 }],
                "largest-contentful-paint": ["error", { "maxNumericValue": 2500 }],
                "cumulative-layout-shift": ["error", { "maxNumericValue": 0.1 }],
                "interactive": ["error", { "maxNumericValue": 3500 }],

                // Best Practices
                "categories:best-practices": ["error", { "minScore": 0.9 }],
                "categories:accessibility": ["error", { "minScore": 0.9 }],
                "categories:seo": ["error", { "minScore": 0.9 }],

                // Additional constraints
                "total-blocking-time": ["error", { "maxNumericValue": 300 }],
                "resource-summary:script:size": ["warn", { "maxNumericSize": 100000 }],
                "resource-summary:image:size": ["warn", { "maxNumericSize": 500000 }],
                "unused-javascript": ["warn", { "maxLength": 5 }],
                "uses-responsive-images": ["error", { "minScore": 0.5 }],
            }
        },
        upload: {
            target: "temporary-public-storage"
        }
    }
};
